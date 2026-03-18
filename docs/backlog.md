# Backlog & Development TODOs

Items are grouped by theme. See `CHANGELOG.md` for what was done each sprint.

---

## High Priority (scientific correctness)

- **B1** — Lower `moisture_threshold` or implement percentile-based calibration. The default 0.25 (and `main.py`'s hardcoded 0.2) labels >75% of Australian cells as "dry" given AWRAL `sm_pct` distributions. See `docs/thresholds.md`.

- **B3** — Implement automated threshold-calibration helper:
  - Loads multi-year AWRAL baseline for a region/season
  - Computes 10th, 25th, 50th percentile of `sm_pct`
  - Writes suggested defaults to a config file
  - Expose as a CLI command (e.g., `uv run python main.py calibrate --years 2010-2020`)

---

## Medium Priority (robustness & reproducibility)

- **B5** — Replace `print()` with `logging` at INFO level throughout `pipeline.py` and `data_sources.py`. Add module-level logger. This allows silencing in production and structured log capture in CI.

- **B7** — Add `--allow-legacy-sm` CLI flag (opt-in fallback to legacy `sm` product) with prominent runtime warning. Document unit risks.

- **B8** — Fix `_load_real_netcdf` band-slice path: the `slice(band_values[start_idx], band_values[stop_idx-1])` construction is likely wrong for COG files where band coords are not sequential integers.

---

## Low Priority (code quality & docs)

- **B9** — Fix `_compute_risk_map` return type annotation (`→ np.ndarray` should be `→ tuple[np.ndarray, np.ndarray]`).

- **B10** — Expose stress index weights (0.6/0.25/0.15) via `ClassifierConfig` fields.

- **B12** — Move `tests/test_moisture_ranges.py` to `scripts/` or `tools/` — it is a standalone diagnostic script with top-level `sys.exit()` that breaks pytest collection.

---

## Future / Backlog

- **B14** — Regional aggregation: aggregate risk map to administrative units (e.g., NRM regions, catchments) for decision-support outputs.

- **B15** — Trend analysis: compare risk maps across multiple years/seasons to detect drying trends.

- **B16** — Hotspot detection: identify persistent high-risk cells across consecutive time windows.

- **B17** — Integration test: mock remote reads and validate full pipeline end-to-end for a small bounding box in CI.

- **B18** — Integration test: simulate missing `sm_pct` dataset and assert pipeline raises clear `RuntimeError`.

- **B19** — Async data loading: integrate the pattern from `example_dataloader.py` into `DryWetClassifierPipeline` for large-area or multi-year runs.

- **B20** — ML classifier (Option C): when independent labelled data exists (historical expert labels or remote-sensing ground truth), replace `classify_grid()` with a proper spatial ML pipeline — independent train/test data, spatial cross-validation, real NDVI feature. Decision logged in `sessions/2026-03-18-session-02.md`.
