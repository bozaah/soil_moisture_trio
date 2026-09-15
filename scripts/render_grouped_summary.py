"""Render one or more grouped-summary JSON files to a self-contained HTML page.

Reads the ``<run>_grouped_<name>.json`` files written by
``soil_moisture_trio.grouped_summary.save_grouped_summary`` and renders, per
grouping, the header counts, a reconciliation line, a category table and a
stacked bar per group. Inline SVG and CSS, no external assets.

The page shows what the JSON contains and nothing more. Denominators are printed
from the JSON's ``denominators`` map, not assumed.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Dict, List, Optional

from src.soil_moisture_trio.risk import RISK_COLORS, RISK_LABELS, RiskLevel

CATEGORY_ORDER = [level.name.lower() for level in RiskLevel]
CATEGORY_COLOURS = {level.name.lower(): RISK_COLORS[level] for level in RiskLevel}
CATEGORY_LABELS = {level.name.lower(): RISK_LABELS[level] for level in RiskLevel}
STRESS_KEYS = ["count_finite", "mean", "p10", "median", "p90", "min", "max"]
THRESHOLD_KEYS = ["watch", "alert", "critical"]

CSS = """
body { font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 2rem auto; max-width: 1100px;
       padding: 0 1rem; color: #222; background: #fff; line-height: 1.4; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.2rem; margin-top: 2.5rem; border-top: 1px solid #ddd; padding-top: 1rem; }
table { border-collapse: collapse; margin: 0.75rem 0 1.25rem; font-size: 0.9rem; width: 100%; }
th, td { border: 1px solid #ddd; padding: 0.3rem 0.5rem; text-align: right; white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
thead th { background: #f3f3f3; }
.meta { color: #555; font-size: 0.9rem; } .ok { color: #1a7f37; } .bad { color: #b3261e; font-weight: 600; }
.note { background: #fff8e1; border-left: 4px solid #f0b429; padding: 0.5rem 0.75rem; font-size: 0.9rem; margin: 1rem 0; }
.legend span { display: inline-block; margin-right: 1rem; font-size: 0.85rem; }
.legend i { display: inline-block; width: 0.9rem; height: 0.9rem; vertical-align: middle; margin-right: 0.3rem; border: 1px solid #999; }
"""


def _fmt(value: Optional[float], digits: int = 3, pct: bool = False) -> str:
    if value is None:
        return "—"
    if pct:
        return f"{100 * value:.1f}%"
    return f"{value:.{digits}f}"


def _bars_svg(rows: List[Dict]) -> str:
    """One stacked horizontal bar per row, width proportional to category proportion."""
    if not rows:
        return ""
    row_h, label_w, bar_w, gap = 22, 220, 600, 6
    height = len(rows) * (row_h + gap)
    parts = [f'<svg width="{label_w + bar_w + 70}" height="{height}" role="img" aria-label="Category shares per group">']
    for i, row in enumerate(rows):
        y = i * (row_h + gap)
        label = html.escape(f"{row['label']} (n={row['cell_count']})")
        parts.append(f'<text x="{label_w - 8}" y="{y + row_h * 0.7}" text-anchor="end" font-size="12">{label}</text>')
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
    head = ["Group", "Cells", "Share of summary", "Share of risk-valid"]
    head += [CATEGORY_LABELS[k] for k in CATEGORY_ORDER]
    head += [f"≥ {k} thr." for k in THRESHOLD_KEYS]
    if stress_available:
        head += ["Stress mean", "p10", "median", "p90"]
    out = ["<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for row in rows:
        cells = [
            html.escape(row["label"]),
            str(row["cell_count"]),
            _fmt(row["share_of_summary_domain"], pct=True),
            _fmt(row["share_of_risk_valid_domain"], pct=True),
        ]
        cells += [f"{row['category_counts'][k]} ({_fmt(row['category_proportions'][k], pct=True)})" for k in CATEGORY_ORDER]
        cells += [_fmt(row["share_at_or_above_threshold"].get(k), pct=True) for k in THRESHOLD_KEYS]
        if stress_available:
            stress = row.get("stress") or {}
            cells += [_fmt(stress.get(k)) for k in ("mean", "p10", "median", "p90")]
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _section(payload: Dict, source: Path) -> str:
    rows = list(payload["groups"]) + ([payload["uncovered"]] if payload.get("uncovered") else [])
    recon = payload["reconciled"]
    recon_html = (
        '<span class="ok">reconciled: groups + uncovered = risk-valid cells</span>'
        if recon
        else '<span class="bad">NOT reconciled: groups + uncovered ≠ risk-valid cells</span>'
    )
    denominators = "".join(
        f"<li><code>{html.escape(k)}</code>: {html.escape(v)}</li>" for k, v in payload["denominators"].items()
    )
    thresholds = ", ".join(f"{k} ≥ {v}" for k, v in payload["thresholds"].items())
    stress_note = (
        ""
        if payload["stress_available"]
        else '<p class="note">No <code>stress_index</code> in this run\'s saved output. Stress statistics and threshold shares are unavailable; category counts come from <code>risk_level</code> only.</p>'
    )
    return f"""
<h2>Grouping: {html.escape(payload['grouping_name'])}</h2>
<p class="meta">Source: <code>{html.escape(str(source))}</code></p>
<p>Total cells {payload['total_cells']:,}, risk-valid {payload['risk_valid_cells']:,},
summarised {payload['summary_cells']:,}, uncovered {payload['uncovered_cells']:,}. {recon_html}.
Thresholds: {html.escape(thresholds)}.</p>
{stress_note}
{_bars_svg(rows)}
{_table(rows, payload['stress_available'])}
<details><summary class="meta">Denominators</summary><ul class="meta">{denominators}</ul></details>
"""


def render_grouped_summaries(inputs: List[Path], output: Path, title: str) -> Path:
    sections = []
    for path in inputs:
        with path.open(encoding="utf-8") as fp:
            payload = json.load(fp)
        sections.append(_section(payload, path))
    legend = "".join(
        f'<span><i style="background:{CATEGORY_COLOURS[k]}"></i>{CATEGORY_LABELS[k]}</span>' for k in CATEGORY_ORDER
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="meta">Grouped summaries of an existing drought-risk run. Grouping does not alter per-cell risk, stress or validity.
Every proportion's denominator is listed under each section.</p>
<p class="legend">{legend}</p>
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
    args = parser.parse_args()
    out = render_grouped_summaries(args.grouped_json, args.output, args.title)
    print(out)


if __name__ == "__main__":
    main()
