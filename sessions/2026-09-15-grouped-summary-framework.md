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

## Limits

The real-data test uses a coverage split as the grouping only to exercise the framework. It is not a soil band and makes no scientific claim. B25c (bands, reference domain, minimum coverage) still waits on Karen Holmes and Dennis van Gool. No figure claiming soil stratification exists. Operational runs still do not load soil context.
