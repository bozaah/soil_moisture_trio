# Backlog & Development TODOs

Items are grouped by theme. See `CHANGELOG.md` for what was done each sprint.

---

## High Priority (scientific correctness)

- ~~**B1**~~ **RESOLVED (Sprint 6)** — Switched pipeline from raw `sm_pct` (values/day) to AWRAL percentile rank (deciles/day). `moisture_threshold=0.30` now maps to the true 30th percentile for each location/season. Jan–Mar 2026 WA: Critical 1.1%, Alert 6.8%, Watch 12.3%, Low 79.9% (was Critical 47.1% with old raw product). See `docs/thresholds.md`.

- ~~**B3**~~ **RESOLVED (Sprint 6)** — Decile product is the calibration. No separate helper needed; percentile rank thresholds (≤0.10 Critical, 0.10–0.20 Alert, 0.20–0.30 Watch, ≥0.30 Low) have stable climatological meaning across all locations and seasons. Calibration baseline: `data/awral_decile_sm_pct_WA_monthly.nc` (1911–2026).

---

## Medium Priority (robustness & reproducibility)

- ~~**B21**~~ **RESOLVED (Sprint 7)** — `silo_cache_dir` now defaults to `~/.cache/soil_moisture_trio/silo`. Directory is created automatically on first run. Prior default `None` (→ `save_to_disk=False`) meant SILO GeoTIFFs were not retained across sessions. No migration needed — prior runs used `save_to_disk=False` and left no managed cache files.

- **B5** — Replace `print()` with `logging` at INFO level throughout `pipeline.py` and `data_sources.py`. Add module-level logger. This allows silencing in production and structured log capture in CI.

- **B7** — Add `--allow-legacy-sm` CLI flag (opt-in fallback to legacy `sm` product) with prominent runtime warning. Document unit risks.

- **B8** — Fix `_load_real_netcdf` band-slice path: the `slice(band_values[start_idx], band_values[stop_idx-1])` construction is likely wrong for COG files where band coords are not sequential integers.

- **B22** — SILO cache key does not include bounding box. When the same cache directory is used for runs with different bounding boxes, cached tiles from the larger-bbox run are served to the smaller-bbox run, causing a shape mismatch crash in `np.stack`. Workaround: use `--silo-cache-dir` to point different-bbox runs at separate directories. Fix: incorporate bbox hash into the cache filename or directory structure in `WeatherToolsSiloLoader`.

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

- **B20** — ML classifier: when independent labelled data exists (historical expert labels or remote-sensing ground truth), replace `classify_grid()` with a proper spatial ML pipeline — independent train/test data, spatial cross-validation, real NDVI feature. Decision logged in `sessions/2026-03-18-session-02.md`.

- **B23** — Seasonal stress index thresholds (Option C): replace the fixed Critical/Alert/Watch thresholds (0.85/0.60/0.35) with season-specific values calibrated so that the long-run proportion of cells in each category is stable across months. Motivation: atmospheric VPD and temperature are systematically higher in summer, which means the current fixed thresholds are implicitly stricter in winter/spring than summer. Requires a calibration pass using the WA monthly baseline (`data/awral_decile_sm_pct_WA_monthly.nc`) together with historical SILO. Design decision logged in `sessions/2026-03-25-sprint7-persistent-cache-bulletin.md`.

- **B24** — Rangelands / multi-region support (Option A): download a full-WA rectangle once and cache it at that scale; downstream runs (SWAZ, rangelands, pastoral zones) clip/mask from the single cache using their respective boundary files. This removes the per-bbox cache fragmentation (B22) and enables a consistent multi-region monitoring product from one set of downloads. Prerequisite: fix B22 (bbox-aware cache key) to prevent shape-mismatch crashes when bbox varies. Current `--boundary-gpkg` approach (Option B, Sprint 9) is the operational default until this is implemented. Decision logged in `sessions/2026-03-25-sprint9-boundary-gpkg.md`.
