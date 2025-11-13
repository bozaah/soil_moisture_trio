# Project Plan: Soil Moisture Trio

This document outlines the development plan and the current status of the `soil-moisture-trio` project.

## Sprint Goals
1. **Ensure Correctness & Reliability:** We implemented `pytest`-based unit tests and updated tests to mock the real-data loader for speed.
2. **Improve Maintainability:** The code was refactored (core modules split, `ClassifierConfig` introduced) and CatBoost replaced the previous MLP for tabular training.
3. **Integrate Real-World Data:** AWRAL (`sm_pct`) and SILO variables are now ingested by the pipeline; synthetic data paths have been retired.
4. **Visualize Results:** An optional `--visualize` flow produces a Folium map plus PNG exports.

## Phase 1: Testing & Refactoring (Internal Plumbing) — status: complete

- [x] **Add Basic Testing (`pytest`)** — tests added and run as part of local development.
  - [x] `pytest` introduced and CI-friendly tests created.
  - [x] Tests mock `_load_all_real_data` to remain fast/deterministic.

- [x] **Refactor the Codebase**
  - [x] Project restructured: `config.py`, `pipeline.py`, plotting and viz modules separated.
  - [x] `main.py` remains a thin orchestrator.

- [x] **Optimize Model Training**
  - [x] CatBoost integrated for faster tabular training; hyperparameters exposed via `ClassifierConfig`.

## Phase 2: Data & Visualization (External-Facing)

- [x] **Soil Moisture (AWRAL `sm_pct`)** — integrated and now required. The loader is defensive: it will autodetect whether `sm_pct` is provided as percent (0–100) or already as a fraction (0–1) and only convert when necessary. This avoids silent unit errors across deployments.
- [x] **SILO variables** (`tmax`, `vpd`) — integrated and default to the `weather_tools` COG loader.
- [x] **SILO COG Loader** — default behavior is to use COG subsetting by bounding box for efficient downloads; `--no-silo-cog-loader` can revert to NetCDF.
- [x] Retired synthetic-data code paths.
- [x] Clip/align grids to Australian bounds and maintain NoData masks through training/prediction/risk outputs.

- [x] **Visualization (`folium`)**
  - [x] Interactive map generation implemented.
  - [x] Optional PNG export via `--risk-plot-path`.

## Phase 3: Decision Support & Risk Layer

- [x] **Define Risk Rubric** — implemented in `src/soil_moisture_trio/risk.py`. The method computes a continuous `stress_index` per cell and maps it to categorical risk bands.

- [ ] **Aggregate Insights** — backlog: regional aggregation, trend analysis, and hotspot detection.

## Recent fixes & design changes (delta)

- `assess_risk_levels()` now returns `(risk_map, summary, stress_index)` and `pipeline.assess_risk()` exposes `'stress_index'` in its return dict.
- Diagnostic plotting functions were hardened (masking/flattening). The diagnostics scatter now plots Soil Moisture vs VPD (vapour pressure deficit) coloured by the composite `stress_index`. A lat/lon alignment bug was fixed that previously caused unrealistic diagnostics.
- The loader now requires `sm_pct`; legacy `sm` fallback removed to prevent silent unit mixups. The loader's autodetection logic handles both percent and fraction encodings.

## Thresholds — action required

Diagnostics show that current operational soil-moisture grids have much smaller values than the older absolute cutoff of 0.25 would expect. Suggested actions:

1. Short term: keep the hardcoded thresholds for compatibility but validate them on your dataset; consider lowering `moisture_threshold` to ~0.01–0.03 (1–3% volumetric fraction) if diagnostics show very small soil-moisture values.
2. Medium term (recommended): implement an automated calibration step that computes thresholds from a reference climatology (e.g., set `moisture_threshold` = 25th percentile of a multi-year baseline for the selected region/season).
3. Add an integration test that simulates missing `sm_pct` to ensure the pipeline fails with a clear error message (we now intentionally raise an error when `sm_pct` is absent).

## Next steps / backlog

- [ ] Add integration test for missing `sm_pct` product and assert clear error message.
- [ ] Optionally add `--allow-legacy-sm` CLI flag for one-off compatibility runs (with a prominent warning about units).
- [ ] Implement an automated threshold-calibration routine (compute percentiles over a reference period and persist recommended defaults in `ClassifierConfig`).
- [ ] Document the `sm_pct` requirement and threshold recommendations in onboarding docs.

## Development TODOs

Actionable items to pick up in the next sprint:

- [ ] Convert stdout prints used for loader detection and diagnostics to structured logging (`logging` at INFO level) and add a module-level logger so messages can be silenced or redirected in production.
- [ ] Add a unit test for the `sm_pct` conversion heuristic (synthetic arrays): assert that arrays with max>1.1 are divided by 100 and arrays with max<=1.1 are left unchanged.
- [ ] Add an integration test that simulates a missing `sm_pct` dataset and asserts the pipeline raises the intended RuntimeError with a clear message.
- [ ] Implement `--allow-legacy-sm` CLI flag (opt-in) that enables a guarded fallback to the legacy `sm` product; emit a prominent runtime warning when used and document the risks.
- [ ] Implement an automated threshold-calibration helper in the pipeline (or a small CLI command) that computes recommended percentiles (10th, 25th, 50th) for a selected region/period and optionally writes suggested defaults to a config file.
- [ ] Add a small developer-facing command or test harness that runs the `uv` example locally against a small bounding box to validate end-to-end behavior in CI (mock network IO where appropriate).

Mark these as high-priority developer tasks; they are low-risk, improve robustness, and address recurring manual checks.
