# Backlog & Development TODOs

Items are grouped by theme. See `CHANGELOG.md` for what was done each sprint.

---

## High Priority (scientific correctness)

- ~~**B1**~~ **RESOLVED (Sprint 6)** — Switched pipeline from raw `sm_pct` (values/day) to AWRAL percentile rank (deciles/day). This removed the gross over-classification caused by fixed raw thresholds. Jan–Mar 2026 WA: Critical 1.1%, Alert 6.8%, Watch 12.3%, Low 79.9% (was Critical 47.1% with old raw product). See `docs/technical_report.md`.

- ~~**B3**~~ **RESOLVED (Sprint 6)** — Decile product is the calibration. No separate helper needed; percentile rank thresholds (≤0.10 Critical, 0.10–0.20 Alert, 0.20–0.30 Watch, ≥0.30 Low) have stable climatological meaning across all locations and seasons. Calibration baseline: `data/awral_decile_sm_pct_WA_monthly.nc` (1911–2026).

---

## Medium Priority (robustness & reproducibility)

- ~~**B21**~~ **RESOLVED (Sprint 7)** — `silo_cache_dir` now defaults to `~/.cache/soil_moisture_trio/silo`. Directory is created automatically on first run. Prior default `None` (→ `save_to_disk=False`) meant SILO GeoTIFFs were not retained across sessions. No migration needed — prior runs used `save_to_disk=False` and left no managed cache files.

- ~~**B5**~~ **RESOLVED** — Runtime paths now use `logging` rather than `print()` in `main.py`, `pipeline.py`, `data_sources.py`, and bulletin rendering.

- ~~**B7**~~ **RETIRED (Sprint 12)** — The temporary `--allow-legacy-sm` compatibility path was removed. The pipeline now requires the scientifically calibrated AWRA-L percentile-rank product and fails clearly when it is unavailable.

- ~~**B8**~~ **RESOLVED (Sprint 11)** — `_load_real_netcdf` now selects raster time windows positionally with `isel(band=slice(start_idx, stop_idx))`, avoiding dependence on non-sequential band labels.

- ~~**B22**~~ **RESOLVED (Sprint 9)** — `WeatherToolsSiloLoader` now scopes cached GeoTIFFs into bbox-hashed subdirectories under the configured cache root, preventing cross-bbox collisions within a shared cache directory.

---

## Low Priority (code quality & docs)

- ~~**B9**~~ **RESOLVED** — `_compute_risk_map()` now correctly declares `Tuple[np.ndarray, np.ndarray]`.

- ~~**B10**~~ **RESOLVED (Sprint 13)** — Stress weights and risk-band thresholds are exposed through `ClassifierConfig`, validated as a unit, and persisted with outputs.

- ~~**B12**~~ **RESOLVED (Sprint 11)** — The networked moisture-range diagnostic now lives at `scripts/moisture_ranges_diagnostic.py`; default pytest collection contains deterministic tests only.

---

## Future / Backlog

- **B14** — Regional aggregation: aggregate risk map to administrative units (e.g., NRM regions, catchments) for decision-support outputs.

- **B15** — Trend analysis: compare risk maps across multiple years/seasons to detect drying trends.

- **B16** — Hotspot detection: identify persistent high-risk cells across consecutive time windows.

- ~~**B17**~~ **RESOLVED (Sprint 13)** — A mocked orchestration test validates `run_pipeline()` through preparation, risk assessment, and NetCDF/JSON persistence without network access.

- ~~**B18**~~ **RESOLVED (Sprint 13)** — Regression coverage simulates a missing decile dataset through `prepare_data()` and asserts a clear `RuntimeError`.

- **B19** — Async data loading: integrate the pattern from `example_dataloader.py` into `DryWetClassifierPipeline` for large-area or multi-year runs.

- **B20** — ML classifier: only consider replacing the rule-based risk model when independent labelled data exists (historical expert labels or remote-sensing ground truth). Any future model requires independent train/test data, spatial cross-validation, and real observed predictors.

- **B23** — Seasonal stress index thresholds (Option C): replace the current year-round default Critical/Alert/Watch thresholds (0.85/0.60/0.35) with season-specific configured values calibrated so that the long-run proportion of cells in each category is stable across months. Motivation: atmospheric VPD and temperature are systematically higher in summer, which means the current defaults are implicitly stricter in winter/spring than summer. Requires a calibration pass using the WA monthly baseline (`data/awral_decile_sm_pct_WA_monthly.nc`) together with historical SILO. Design decision logged in `sessions/2026-03-25-sprint7-persistent-cache-bulletin.md`.

- **B24** — Rangelands / multi-region support (Option A): download a full-WA rectangle once and cache it at that scale; downstream runs (SWAZ, rangelands, pastoral zones) clip/mask from the single cache using their respective boundary files. This would reduce repeated downloads across overlapping WA regions and enable a consistent multi-region monitoring product from one set of inputs. The current `--boundary-gpkg` approach (Option B, Sprint 9) remains the operational default until this is implemented. Decision logged in `sessions/2026-03-25-sprint9-boundary-gpkg.md`.

- **B25** — Soil-property stratification: integrate SLGA v2 soil property layers, followed by approved WA-specific digital soil maps when available, and summarise drought stress by scientifically defensible soil groups or property bands. Define the soil data contract, spatial alignment, missing-data behavior, and validation criteria before implementation. Planned direction recorded in `sessions/2026-05-11_ssa26-abstract-submission.md`.
