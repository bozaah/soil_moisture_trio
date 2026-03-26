# Backlog & Development TODOs

Items are grouped by theme. See `CHANGELOG.md` for what was done each sprint.

---

## High Priority (scientific correctness)

- ~~**B1**~~ **RESOLVED (Sprint 6)** — Switched pipeline from raw `sm_pct` (values/day) to AWRAL percentile rank (deciles/day). This removed the gross over-classification caused by fixed raw thresholds. Jan–Mar 2026 WA: Critical 1.1%, Alert 6.8%, Watch 12.3%, Low 79.9% (was Critical 47.1% with old raw product). See `docs/thresholds.md`.

- ~~**B3**~~ **RESOLVED (Sprint 6)** — Decile product is the calibration. No separate helper needed; percentile rank thresholds (≤0.10 Critical, 0.10–0.20 Alert, 0.20–0.30 Watch, ≥0.30 Low) have stable climatological meaning across all locations and seasons. Calibration baseline: `data/awral_decile_sm_pct_WA_monthly.nc` (1911–2026).

---

## Medium Priority (robustness & reproducibility)

- ~~**B21**~~ **RESOLVED (Sprint 7)** — `silo_cache_dir` now defaults to `~/.cache/soil_moisture_trio/silo`. Directory is created automatically on first run. Prior default `None` (→ `save_to_disk=False`) meant SILO GeoTIFFs were not retained across sessions. No migration needed — prior runs used `save_to_disk=False` and left no managed cache files.

- ~~**B5**~~ **RESOLVED** — Runtime paths now use `logging` rather than `print()` in `main.py`, `pipeline.py`, `data_sources.py`, and bulletin rendering.

- ~~**B7**~~ **RESOLVED** — `--allow-legacy-sm` is now implemented as an explicit opt-in fallback to the legacy raw-values AWRAL product, with warnings in both code and docs.

- **B8** — Fix `_load_real_netcdf` band-slice path: the `slice(band_values[start_idx], band_values[stop_idx-1])` construction is likely wrong for COG files where band coords are not sequential integers.

- ~~**B22**~~ **RESOLVED (Sprint 9)** — `WeatherToolsSiloLoader` now scopes cached GeoTIFFs into bbox-hashed subdirectories under the configured cache root, preventing cross-bbox collisions within a shared cache directory.

---

## Low Priority (code quality & docs)

- ~~**B9**~~ **RESOLVED** — `_compute_risk_map()` now correctly declares `Tuple[np.ndarray, np.ndarray]`.

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

- **B24** — Rangelands / multi-region support (Option A): download a full-WA rectangle once and cache it at that scale; downstream runs (SWAZ, rangelands, pastoral zones) clip/mask from the single cache using their respective boundary files. This would reduce repeated downloads across overlapping WA regions and enable a consistent multi-region monitoring product from one set of inputs. The current `--boundary-gpkg` approach (Option B, Sprint 9) remains the operational default until this is implemented. Decision logged in `sessions/2026-03-25-sprint9-boundary-gpkg.md`.
