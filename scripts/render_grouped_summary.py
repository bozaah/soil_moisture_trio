"""Render grouped-summary JSON files to one self-contained HTML page.

Inputs are the ``<run>_grouped_<name>.json`` files written by
``soil_moisture_trio.grouped_summary.save_grouped_summary``. For each one the page
shows the authored title, description and notes carried in the JSON, a map of the
grouping (drawn from the sibling ``<run>_grouped_<name>.nc`` raster when present),
a stacked bar of risk categories per group, and a table with counts, threshold
shares and stress statistics. The run's own figures are embedded when given.

Everything is inline (base64 PNG, inline SVG and CSS). The renderer prints the
JSON's text and numbers and adds only fixed method explanation. It writes no
interpretation of its own: that belongs to whoever defines a grouping.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import xarray as xr  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

from src.soil_moisture_trio.risk import RISK_COLORS, RISK_LABELS, RiskLevel  # noqa: E402

CATEGORY_ORDER = [level.name.lower() for level in RiskLevel]
CATEGORY_COLOURS = {level.name.lower(): RISK_COLORS[level] for level in RiskLevel}
CATEGORY_LABELS = {level.name.lower(): RISK_LABELS[level] for level in RiskLevel}
THRESHOLD_KEYS = ["watch", "alert", "critical"]
UNCOVERED_COLOUR = "#bdbdbd"
GROUP_CMAP = "RdYlBu"  # same family as the run's continuous stress panel: warm = less water, blue = more

CSS = """
body { font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 2rem auto; max-width: 1100px;
       padding: 0 1rem; color: #222; background: #fff; line-height: 1.45; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.25rem; margin-top: 2.5rem; border-top: 1px solid #ddd; padding-top: 1rem; }
h3 { font-size: 1.05rem; margin-top: 1.5rem; }
table { border-collapse: collapse; margin: 0.75rem 0 1.25rem; font-size: 0.88rem; width: 100%; }
th, td { border: 1px solid #ddd; padding: 0.3rem 0.5rem; text-align: right; white-space: nowrap; }
th:first-child, td:first-child { text-align: left; white-space: normal; }
thead th { background: #f3f3f3; }
.meta { color: #555; font-size: 0.88rem; } .ok { color: #1a7f37; } .bad { color: #b3261e; font-weight: 600; }
.note { background: #fff8e1; border-left: 4px solid #f0b429; padding: 0.5rem 0.75rem; font-size: 0.9rem; margin: 1rem 0; }
.scope { background: #eef3fb; border-left: 4px solid #3b6fc4; padding: 0.5rem 0.75rem; font-size: 0.9rem; margin: 1rem 0; }
.legend span { display: inline-block; margin-right: 1rem; font-size: 0.85rem; }
.legend i { display: inline-block; width: 0.9rem; height: 0.9rem; vertical-align: middle; margin-right: 0.3rem; border: 1px solid #999; }
img { max-width: 100%; height: auto; display: block; margin: 0.5rem 0; }
ul.notes li { margin-bottom: 0.3rem; }
figure { margin: 1rem 0; } figcaption { font-size: 0.85rem; color: #555; }
.wrap { overflow-x: auto; }
"""

METHOD = (
    "A grouped summary takes a finished drought-risk run and counts its cells by group. The per-cell risk category "
    "and stress index are exactly those of the run; grouping never recalculates them. Cells the run marked invalid "
    "(outside the boundary, or missing weather or soil-moisture input) are excluded before grouping. Cells that are "
    "valid in the run but cannot be assigned to a group are reported in an <em>uncovered</em> row, so every valid "
    "cell appears exactly once and the groups plus uncovered add back to the run's valid total. The stacked bar "
    "shows the share of each group in each risk category. In the table, <em>≥ watch/alert/critical</em> is the "
    "share of the group's cells whose stress index reaches that threshold, and the stress columns describe the "
    "distribution of the index within the group."
)


def _fmt(value: Optional[float], digits: int = 3, pct: bool = False) -> str:
    if value is None:
        return "—"
    return f"{100 * value:.1f}%" if pct else f"{value:.{digits}f}"


def _png_data_uri(png_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _embed_png_file(path: Optional[Path], caption: str) -> str:
    if path is None:
        return ""
    if not path.is_file():
        return f'<p class="bad">Figure not found: <code>{html.escape(str(path))}</code></p>'
    return f'<figure><img src="{_png_data_uri(path.read_bytes())}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'


def _group_colours(group_ids: List[int]) -> Dict[int, str]:
    """Ordered colours for ordered groups: first group warm, last group blue.

    Groups are listed in ascending id order, and the drivers assign ids in
    ascending order of the grouped quantity, so the lowest band is warm and the
    highest blue, matching the run's own stress panel (red = dry, blue = wet).
    """
    cmap = plt.get_cmap(GROUP_CMAP)
    n = len(group_ids)
    positions = [0.15] if n == 1 else [0.15 + 0.7 * i / (n - 1) for i in range(n)]
    return {gid: matplotlib.colors.to_hex(cmap(pos)) for gid, pos in zip(group_ids, positions)}


def _group_map_png(raster_nc: Path, payload: Dict, boundary_gpkg: Optional[Path]) -> Optional[bytes]:
    """Map of group membership from the persisted grouping raster. Uncovered risk cells in grey."""
    with xr.open_dataset(raster_nc) as ds:
        lats = ds.lat.values.copy()
        lons = ds.lon.values.copy()
        gids = ds["group_id"].values.copy()
        gvalid = ds["group_valid_mask"].values.astype(bool)
        rvalid = ds["risk_valid_mask"].values.astype(bool)
    group_ids = [g["group_id"] for g in payload["groups"]]
    if not group_ids:
        return None
    colours = _group_colours(group_ids)
    index = np.full(gids.shape, np.nan)
    for i, gid in enumerate(group_ids):
        index[rvalid & gvalid & (gids == gid)] = i
    index[rvalid & ~gvalid] = len(group_ids)  # valid in the run, not assignable: uncovered
    # cells the run marked invalid stay masked (white), matching the run's own map
    cmap = ListedColormap([colours[g] for g in group_ids] + [UNCOVERED_COLOUR])
    norm = BoundaryNorm(np.arange(len(group_ids) + 2) - 0.5, cmap.N)

    fig, ax = plt.subplots(figsize=(7.5, 5.5), constrained_layout=True)
    mesh = ax.pcolormesh(lons, lats, np.ma.masked_invalid(index), cmap=cmap, norm=norm, shading="auto")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(payload["title"], fontsize=10)
    ax.set_aspect("equal", adjustable="box")
    cbar = fig.colorbar(mesh, ax=ax, orientation="vertical", pad=0.02, fraction=0.046)
    cbar.set_ticks(np.arange(len(group_ids) + 1))
    cbar.set_ticklabels([g["label"] for g in payload["groups"]] + ["uncovered"])
    cbar.ax.tick_params(labelsize=8)
    if boundary_gpkg and boundary_gpkg.is_file():
        import geopandas as gpd

        gpd.read_file(boundary_gpkg).to_crs("EPSG:4326").boundary.plot(ax=ax, color="black", linewidth=0.7, zorder=5)
    buf = io.BytesIO()
    fig.savefig(buf, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _bars_svg(rows: List[Dict], colours: Dict[int, str]) -> str:
    if not rows:
        return ""
    row_h, label_w, bar_w, gap = 22, 260, 560, 6
    height = len(rows) * (row_h + gap)
    parts = [f'<svg width="{label_w + bar_w + 20}" height="{height}" role="img" aria-label="Risk category shares per group">']
    for i, row in enumerate(rows):
        y = i * (row_h + gap)
        label = html.escape(f"{row['label']} (n={row['cell_count']:,})")
        swatch = colours.get(row["group_id"], UNCOVERED_COLOUR) if row["group_id"] is not None else UNCOVERED_COLOUR
        parts.append(f'<rect x="{label_w - 22}" y="{y + 4}" width="12" height="{row_h - 8}" fill="{swatch}" stroke="#666" stroke-width="0.5"/>')
        parts.append(f'<text x="{label_w - 28}" y="{y + row_h * 0.7}" text-anchor="end" font-size="11">{label}</text>')
        x = label_w
        for key in CATEGORY_ORDER:
            p = row["category_proportions"].get(key) or 0.0
            w = bar_w * p
            if w > 0:
                parts.append(
                    f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{row_h}" fill="{CATEGORY_COLOURS[key]}" stroke="#666" stroke-width="0.5">'
                    f"<title>{CATEGORY_LABELS[key]}: {100 * p:.1f}%</title></rect>"
                )
            x += w
    parts.append("</svg>")
    return "".join(parts)


def _table(rows: List[Dict], stress_available: bool) -> str:
    head = ["Group", "Cells", "Share of grouped", "Share of valid"]
    head += [CATEGORY_LABELS[k] for k in CATEGORY_ORDER]
    head += [f"≥ {k}" for k in THRESHOLD_KEYS]
    if stress_available:
        head += ["Stress mean", "p10", "median", "p90"]
    out = ['<div class="wrap"><table><thead><tr>' + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for row in rows:
        cells = [
            html.escape(row["label"]),
            f"{row['cell_count']:,}",
            _fmt(row["share_of_summary_domain"], pct=True),
            _fmt(row["share_of_risk_valid_domain"], pct=True),
        ]
        cells += [f"{row['category_counts'][k]:,} ({_fmt(row['category_proportions'][k], pct=True)})" for k in CATEGORY_ORDER]
        cells += [_fmt(row["share_at_or_above_threshold"].get(k), pct=True) for k in THRESHOLD_KEYS]
        if stress_available:
            stress = row.get("stress") or {}
            cells += [_fmt(stress.get(k)) for k in ("mean", "p10", "median", "p90")]
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _section(payload: Dict, source: Path, boundary_gpkg: Optional[Path]) -> str:
    rows = list(payload["groups"]) + ([payload["uncovered"]] if payload.get("uncovered") else [])
    colours = _group_colours([g["group_id"] for g in payload["groups"]])
    recon_html = (
        '<span class="ok">Groups plus uncovered equal the valid cells.</span>'
        if payload["reconciled"]
        else '<span class="bad">NOT reconciled: groups plus uncovered do not equal the valid cells.</span>'
    )
    denominators = "".join(f"<li><code>{html.escape(k)}</code>: {html.escape(v)}</li>" for k, v in payload["denominators"].items())
    thresholds = ", ".join(f"{k} ≥ {v}" for k, v in payload["thresholds"].items())
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in payload.get("notes", []))
    stress_note = (
        ""
        if payload["stress_available"]
        else '<p class="note">This run\'s saved output has no <code>stress_index</code>. Threshold shares and stress statistics are unavailable; category counts come from <code>risk_level</code> only.</p>'
    )
    raster_nc = source.with_suffix(".nc")
    map_html = ""
    if raster_nc.is_file():
        png = _group_map_png(raster_nc, payload, boundary_gpkg)
        if png:
            map_html = f'<figure><img src="{_png_data_uri(png)}" alt="Map of group membership"><figcaption>Where each group sits within the valid cells of the run. Colours run warm to blue from the lowest to the highest group, the same family as the stress panel above. Grey: valid cells not assigned to a group (uncovered). White: cells the run marked invalid.</figcaption></figure>'
    else:
        map_html = f'<p class="meta">No grouping raster beside the JSON (<code>{html.escape(raster_nc.name)}</code>), so no map is drawn.</p>'
    description = f"<p>{html.escape(payload.get('description', ''))}</p>" if payload.get("description") else ""
    return f"""
<h2>{html.escape(payload['title'])}</h2>
{description}
<p class="meta">Valid cells in the run {payload['risk_valid_cells']:,}; grouped {payload['summary_cells']:,}; uncovered {payload['uncovered_cells']:,}. {recon_html}
Thresholds: {html.escape(thresholds)}. Source: <code>{html.escape(source.name)}</code>.</p>
{stress_note}
{map_html}
<h3>Risk categories by group</h3>
{_bars_svg(rows, colours)}
{_table(rows, payload['stress_available'])}
{f'<h3>Notes</h3><ul class="notes">{notes}</ul>' if notes else ''}
<details><summary class="meta">Denominators used above</summary><ul class="meta">{denominators}</ul></details>
"""


def render_grouped_summaries(
    inputs: List[Path],
    output: Path,
    title: str,
    intro: str = "",
    risk_png: Optional[Path] = None,
    diagnostics_png: Optional[Path] = None,
    boundary_gpkg: Optional[Path] = None,
    scope_note: str = "",
) -> Path:
    sections = [_section(json.loads(p.read_text(encoding="utf-8")), p, boundary_gpkg) for p in inputs]
    legend = "".join(f'<span><i style="background:{CATEGORY_COLOURS[k]}"></i>{CATEGORY_LABELS[k]}</span>' for k in CATEGORY_ORDER)
    run_figs = ""
    if risk_png or diagnostics_png:
        run_figs = (
            "<h2>The run being grouped</h2>"
            + _embed_png_file(risk_png, "Risk categories (left) and continuous stress index (right) for the run.")
            + _embed_png_file(diagnostics_png, "Stress-index diagnostics for the run.")
        )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body>
<h1>{html.escape(title)}</h1>
{f'<p>{html.escape(intro)}</p>' if intro else ''}
{f'<p class="scope">{html.escape(scope_note)}</p>' if scope_note else ''}
<h2>How to read this page</h2>
<p>{METHOD}</p>
<p class="legend">{legend}</p>
{run_figs}
{''.join(sections)}
</body></html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Render grouped-summary JSON files to a self-contained HTML page.")
    parser.add_argument("--grouped-json", required=True, type=Path, nargs="+", help="One or more *_grouped_*.json files")
    parser.add_argument("--output", required=True, type=Path, help="Output HTML path")
    parser.add_argument("--title", default="Grouped drought-risk summary", help="Page title")
    parser.add_argument("--intro", default="", help="One paragraph under the title, authored by the caller")
    parser.add_argument("--scope-note", default="", help="Highlighted scope or approval statement")
    parser.add_argument("--risk-png", default=None, type=Path, help="Run's risk map PNG to embed")
    parser.add_argument("--diagnostics-png", default=None, type=Path, help="Run's stress diagnostics PNG to embed")
    parser.add_argument("--boundary-gpkg", default=None, type=Path, help="Boundary to outline on group maps")
    args = parser.parse_args()
    out = render_grouped_summaries(
        args.grouped_json, args.output, args.title, args.intro, args.risk_png, args.diagnostics_png, args.boundary_gpkg, args.scope_note
    )
    print(out)


if __name__ == "__main__":
    main()
