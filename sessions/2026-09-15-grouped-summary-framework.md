# 2026-09-15 — Grouping-agnostic summary framework (B14a structure) and persisted stress index

Rodrigo approved three design points before code: persist `stress_index` in the run NetCDF, keep the descriptive stress statistics and add the share of cells at or above each risk threshold, and write grouped results to a separate `<run>_grouped_<name>.json`. Starting commit: `38bfab0` plus the uncommitted 09-14 records.

## What was built

`src/soil_moisture_trio/grouped_summary.py`, pure numpy, no I/O in the summariser, no SLGA import.

`summarise_by_group(risk_map, stress_index, risk_valid_mask, group_ids, group_valid_mask, config, grouping_name, group_labels)`:

- `summary_mask = risk_valid_mask & group_valid_mask`, per the architecture invariant. Both masks are inputs. The function never derives a coverage rule, band or polygon.
- One row per integer group id present in the summary mask: cell count, share of the summary domain, share of the risk-valid domain, category counts and proportions (denominator: the row's cell count), share of cells at or above the watch, alert and critical thresholds from `ClassifierConfig`, and stress mean, min, max, p10, median, p90 with the finite count.
- One `uncovered` row for `risk_valid_mask & ~group_valid_mask`, same breakdown, so no valid cell disappears.
- Header records `risk_valid_cells`, `summary_cells`, `uncovered_cells`, a `reconciled` flag (group counts + uncovered == risk-valid cells), the thresholds used, and a `denominators` map naming the denominator of every proportion.
- `stress_index=None` is accepted for saved runs that predate the persisted variable. Stress statistics and threshold shares are then null and `stress_available` is false.

`save_grouped_summary()` writes `<run>_grouped_<name>.json` beside the existing outputs and touches nothing else.

`save_risk_outputs()` takes an optional `stress_index` and writes it as a float32 variable. `main.py` now passes it. `risk_level` and the summary JSON are unchanged. Runs saved before this change have no `stress_index` variable.

## Verification

`tests/test_grouped_summary.py`, 11 tests: hand-computed three-group fixture with an invalid cell and an uncovered cell, input immutability by byte comparison, all-uncovered case, absent stress index, four rejected-input cases (non-integer ids, shape mismatch, non-boolean mask, stress shape mismatch), separate-file naming, `risk_level` byte-identical with and without `stress_index`, and one real-data test: the March 2026 boundary run grouped by a trivial coverage split (≥0.5 or not) from the real bundle through `load_soil_context()`, asserting reconciliation, at most one uncovered cell, and that category totals across groups plus uncovered equal the run's own counts. That test skips when either local file is absent and passed here.

Full suite: 183 passed, 1 authenticated SLGA test skipped. Ruff clean, `git diff --check` clean.

## Renderer and first live run

`scripts/render_grouped_summary.py` (`uv run python -m scripts.render_grouped_summary --grouped-json ... --output ... --title ...`): one self-contained HTML page per call, a section per grouped JSON with header counts, a reconciliation line, an inline-SVG stacked bar per group, and a category/threshold/stress table. Denominators are printed from the JSON. Two tests: with and without stress, and an unreconciled payload is flagged. Suite 185 passed.

Live run, Rodrigo's request: SWAZ boundary, 2026-07-25 to 2026-09-13 (50 days, end = today minus two for SILO lag; AWRA-L was available to 09-14). `main.py` with the persisted stress index. Result: 9,650 valid cells, low 45.1%, watch 37.3%, alert 17.6%, critical 0. Outputs in `outputs/risk_2026_jul25-sep13_SWAZ_boundary/` (gitignored): run NetCDF with `stress_index`, summary JSON, PNGs, two grouped JSONs and `grouped_summary.html`.

Groupings applied through `load_soil_context()`: (a) coverage ≥ 0.5 or not, a framework exercise, 0 uncovered; (b) AWC terciles cut on the risk-valid domain (86 and 103 mm), coverage < 0.5 as uncovered (58 cells). Tercile result: alert share 20.4%, 22.1%, 10.3% from low to high AWC, stress median 0.427, 0.460, 0.347. The high-AWC tercile is the least stressed in this window. In the March run the ordering was reversed (alert 4%, 16%, 26%). The bands are illustrative, not B25a's, and the sign flip between windows is exactly what the review needs to interpret before any SSA2026 figure. Possible geographic confounding (AWC clusters spatially within the zone) is not checked.

## Authored text, grouping rasters, driver and page

Rodrigo asked for the run's figures and group maps in the page and readable titles with short explanations. Two design rules, agreed: interpretation is authored by whoever defines a grouping and travels with the JSON (`title`, `description`, `notes` on `GroupedSummary`); the renderer prints it and adds only fixed method text. And a map needs the grouping, so `save_grouped_summary()` now also writes `<run>_grouped_<name>.nc` with `group_id`, `group_valid_mask` and `risk_valid_mask`, which also satisfies the backlog's "persist the grouping definition".

`scripts/grouped_soil_context.py` replaces the scratch driver: run NetCDF plus bundle in, `coverage_split` and `awc_terciles` groupings out with their text. Reconciliation failure raises. Tested on the real 50-day run (skips if absent). `scripts/render_grouped_summary.py` embeds the run PNGs, draws one group map per grouping (valid cells only, uncovered grey, invalid white, boundary outline), and takes `--intro` and `--scope-note`. A first map drew every finite-AWC cell including those outside the boundary, which is why the raster carries `risk_valid_mask`.

Group colours: ordered groups sample the same `RdYlBu` family as the run's continuous stress panel, lowest band warm, highest blue, with a matching swatch beside each bar label. The four risk-category colours are not reused for groups, so a group map cannot be misread as a risk map. Rodrigo's call after the first version used an unordered qualitative palette.

The regenerated page shows higher-AWC cells along the west and south coasts and lower-AWC cells across the northern and eastern wheatbelt. With tercile bands, AWC and the rainfall gradient are not separable, which the authored notes state. Suite 187 passed, Ruff clean.

## Limits

The real-data test uses a coverage split as the grouping only to exercise the framework. It is not a soil band and makes no scientific claim. B25c (bands, reference domain, minimum coverage) still waits on Karen Holmes and Dennis van Gool. No figure claiming soil stratification exists. Operational runs still do not load soil context.
