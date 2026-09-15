# Session — 2026-03-25: Plot Fixes + Output Subdirectory (Sprint 8)

## Goal

Four UX/output quality fixes identified from visual review of Sprint 7 outputs:

1. Bulletin PNG not rendering in VSCode markdown preview
2. Southern coast of WA clipped in risk map figure
3. Diagnostic histogram showed stress index distribution — user wanted soil moisture percentile rank instead
4. All run outputs land flat in `outputs/` — mixing across runs

---

## Issue 1 — Bulletin PNG path not resolving in preview

**Root cause:** `render_bulletin.py` passed `map_png` as-is to the template context (e.g., `outputs/risk_foo.png`). When the bulletin itself is also in `outputs/`, VSCode markdown preview resolves image paths relative to the file's location — so it looked for `outputs/outputs/risk_foo.png`, which does not exist.

**Fix:** `scripts/render_bulletin.py` now computes the image path relative to the output bulletin file's parent directory:

```python
def _relative_png(map_png: Path | None, output: Path) -> str | None:
    if map_png is None:
        return None
    try:
        return str(Path(map_png).resolve().relative_to(output.resolve().parent))
    except ValueError:
        return str(map_png)
```

`ValueError` is caught for the case where the PNG and bulletin are on different drives or the path cannot be expressed as relative — in which case the original path is used as a fallback.

**Verified:** `outputs/risk_2026_mar_SWAZ/bulletin_2026_mar_SWAZ.md` now embeds `![...](risk_2026_mar_SWAZ.png)` — a relative path within the same directory. VSCode preview renders the map correctly.

---

## Issue 2 — South coast of WA clipped in risk map

**Root cause:** `save_risk_plot` set `ax.set_ylim(np.min(lats), np.max(lats))` exactly. `pcolormesh` renders each cell centred on its coordinate, so the southernmost cell (centred at `min_lat`) extends half a cell width (~0.025°) below the axis limit and was clipped.

**Fix:** `src/soil_moisture_trio/plot.py` — compute cell height from the lat coordinate spacing and apply it as padding:

```python
cell_h = float(np.diff(lats).mean()) if len(lats) > 1 else 0.05
y_pad = max(abs(cell_h), 0.3)
ax.set_ylim(np.min(lats) - y_pad, np.max(lats) + 0.1)
```

`0.3°` minimum south buffer (~6 cells) gives visible breathing room at the southern boundary. `0.1°` north buffer is cosmetic.

---

## Issue 3 — Diagnostic histogram: stress index → soil moisture percentile

**Problem:** The left panel of `plot_dryness_diagnostics` showed the distribution of the Dryness–Stress Index. At the `moisture_threshold=0.50` setting, the index distribution for March SWAZ piled up around 0.40 (atmospheric floor when soil moisture is above median) — not a useful diagnostic. The soil moisture percentile rank distribution is more informative: it shows directly how cells are distributed across the historical climatology for the period.

**Fix:** Changed the histogram to plot `soil_flat` instead of `stress_flat`:

```python
ax1.hist(soil_flat[valid], bins=40, color="steelblue", alpha=0.8)
ax1.set_xlabel("Soil Moisture Percentile Rank (0–1)")
ax1.set_title("Distribution of Soil Moisture Percentile Rank")
```

The scatter plot (Panel B: SM vs VPD coloured by stress index) is unchanged.

---

## Issue 4 — Output subdirectory convention

**Problem:** All pipeline outputs (`.nc`, `_summary.json`, `.png`, `stress_diagnostics.png`) landed flat in `outputs/`, making it hard to distinguish between runs.

**Fix:** Added `--output-dir` flag to `main.py`. When set, `--risk-output-prefix` and `--risk-plot-path` are treated as basenames within that directory:

```python
if output_dir is not None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if risk_output_prefix:
        risk_output_prefix = str(out / Path(risk_output_prefix).name)
    if risk_plot_path:
        risk_plot_path = str(out / Path(risk_plot_path).name)
```

`stress_diagnostics.png` is derived from `risk_plot_path` via `.with_name("stress_diagnostics.png")` in `main.py`, so it also lands in the output dir automatically.

**New run convention:**

```bash
uv run python main.py \
  --output-dir outputs/risk_2026_mar_SWAZ \
  --risk-output-prefix risk_2026_mar_SWAZ \
  --risk-plot-path risk_2026_mar_SWAZ.png \
  ...
```

**Bulletin convention (pass same dir):**

```bash
uv run python scripts/render_bulletin.py \
  --summary-json outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ_summary.json \
  --map-png outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ.png \
  --output outputs/risk_2026_mar_SWAZ/bulletin_2026_mar_SWAZ.md
```

All outputs — NetCDF, JSON, risk PNG, diagnostics PNG, bulletin — co-located under `outputs/{run_name}/`.

---

## Verification

March 2026 SWAZ run regenerated with all fixes:

| Risk level | Cells | % valid |
|---|---|---|
| Critical | 405 | 1.69% |
| Alert | 3,745 | 15.65% |
| Watch | 10,351 | 43.25% |
| Low | 9,432 | 39.41% |
| Valid | 23,933 | 82.13% |

11 unit tests pass. Bulletin PNG renders in VSCode preview. South coast visible. Histogram shows SM percentile rank distribution.

---

## Changes Summary

| File | Change |
|---|---|
| `scripts/render_bulletin.py` | `_relative_png()` helper — PNG path relative to bulletin output dir |
| `src/soil_moisture_trio/plot.py` | South y-axis buffer (~0.3°); histogram changed to soil moisture percentile rank |
| `main.py` | `--output-dir` flag added; routes prefix + plot path into subdir when set |
| `outputs/risk_2026_mar_SWAZ/` | New run outputs (all files co-located) |
