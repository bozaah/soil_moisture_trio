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

## Current Priorities and Sequencing

The immediate scientific direction is soil-property stratification. Phase 5 adds interpretation and grouped summaries around the existing per-cell outputs; it must not change the stress formula, configured thresholds, risk classification, or invalid-cell handling.

### Now — Phase 5: soil-property stratification

- **B25 — Soil-property stratification (central scientific work):** integrate approved Soil and Landscape Grid of Australia (SLGA) soil-property layers, followed by approved WA-specific digital soil maps when available, and summarise existing drought-stress outputs by scientifically defensible soil groups or property bands. Phase 5 will use a deliberately narrow project-owned SLGA module rather than adding the general-purpose `SLGApy` package as a production dependency. `SLGApy` remains a useful reference and exploratory metadata tool. Decisions are recorded in `sessions/2026-05-11_ssa26-abstract-submission.md` and `sessions/2026-08-12-phase5-slga-planning.md`.

  - **B25a — Scientific product selection and data contract:** Release 1 will use exact, pinned SLGA **AWC v2** and **Depth of Soil (DES) v2** products. The authenticated source check is complete: AWC uses EV/05/95 and DES uses EV/10/90; all 18 corrected sources are pinned with published STAC multihashes in `manifests/slga_awc_des_sources_v1.json`. Derive a DES-capped modelled AWC storage-capacity metric over a maximum nominal depth of 0–100 cm, with mixed-quantile lower/upper uncertainty scenarios. Treat DES as mapped A- and B-horizon depth—not effective crop rooting depth—and do not infer current water storage, distance from wilting, or crop-specific PAWC from AWRA-L percentile plus AWC. Record full product identity, depth, units, component, DOI/version, native resolution, actual source CRS, nodata, checksum, source, citation, licence, and limitations. Build a canonical full-WA grid from authoritative AWRA-L coordinates and require exact runtime coordinate subsets; report valid source area against full target-cell area. Stratification bands/reference domain and minimum coverage threshold remain TBA. Karen Holmes and Dennis van Gool will be invited to review terminology, fitness for WA use, DES capping, uncertainty treatment, and eventual bands. Evidence and decisions: `docs/slga-evidence-review.md`.

  - **B25b — Minimal project-owned SLGA module (enabling work):** implement only the approved Phase 5 requirements, not a general SLGA client or CLI. Maintain the tracked full-ID approved-product catalogue; read spatial COG windows; use `TERN_API_KEY` without persisting credentials; preserve nodata; validate profiles and metadata; and return values plus provenance. Validation must account explicitly for the verified upstream caveats: AWC STAC omits nodata although its COGs define `65535`, and DES COG band descriptions contain stale `NAT` IDs while filenames/STAC IDs use `TRN`. Keep retrieval separate from DES-capped depth integration and area-weighted harmonisation in EPSG:3577. In the explicit builder, derive canonical full-WA cells from authoritative AWRA-L coordinates; at runtime require exact coordinate subsets. Report valid source area, full-cell area, coverage fraction, and mapped dispersion. Carry AWC 05/95 and DES 10/90 through as mixed-quantile lower/upper scenarios and an uncertainty-width proxy, not a formal integrated confidence interval. Build the static harmonised layers once through an explicit command and persist a versioned compressed NetCDF under `data/processed/slga_awral/`; operational runs read the immutable artifact and never silently refetch or rebuild it. Keep large artifacts out of Git while tracking the product/build contract and checksums. Put tunable runtime choices in `ClassifierConfig`, follow project cache conventions, declare direct raster dependencies, mock network access in unit tests, and gate authenticated live checks as opt-in integration tests.

  - **B14a — Generic grouped-summary framework (enabling work):** aggregate the existing `risk_map`, `stress_index`, and risk `valid_mask` against a grouping raster or polygon layer without reclassifying cells. Maintain a separate `soil_summary_mask = risk_valid_mask & acceptable_soil_coverage`; missing SLGA values must not turn otherwise valid risk cells into `-1`. Make all denominators explicit and report group cell counts, valid risk coverage, soil-data coverage, uncovered risk cells, risk-category counts/percentages, and appropriate continuous-stress statistics. Design the framework so administrative regions, NRM regions, and catchments can use it later.

  - **B25c — Initial SLGA stratified product:** implement AWC+DES soil-capacity summaries using the approved B25a contract and B25b static artifact. Do not attempt a comprehensive soil taxonomy. The initial banding method and fixed reference domain remain TBA and must be persisted once approved.

  - **B25d — Scientific and output validation:** prove that the numerical per-cell `risk_map`, `stress_index`, risk summary, and risk valid mask are unchanged; existing invalid cells remain `-1`/`NaN`; soil-summary exclusions are tracked separately; classified strata plus an explicit insufficient-soil-coverage group reconcile with all valid-risk cells; and material coverage gaps and uncertainty are visible. Record full product identity, source, version, component, depth, units, bands, analysis footprint, aggregation method, coverage rule, observed coverage, citation, and licence. Test nodata, partial coverage, non-overlap, grid/CRS mismatch, invalid metadata, authentication failure, version changes, and grouping edge cases.

### Next — scientifically and operationally important

- **B23 — Seasonal stress index calibration:** assess whether the current year-round Critical/Alert/Watch thresholds (0.85/0.60/0.35) create seasonal bias because VPD and temperature are systematically higher in summer. Any replacement thresholds must be configuration-driven and calibrated using the WA soil-moisture baseline together with historical SILO. Keep the current classification unchanged during Phase 5. Design decision logged in `sessions/2026-03-25-sprint7-persistent-cache-bulletin.md`.

- **B24 — Rangelands / multi-region support:** support a full-WA source download and cache from which SWAZ, rangelands, pastoral zones, and other approved boundaries can be clipped and masked consistently. Reuse the grouped-summary architecture where appropriate. The current per-boundary `--boundary-gpkg` workflow remains the operational default until this is implemented. Decision logged in `sessions/2026-03-25-sprint9-boundary-gpkg.md`.

### Later — useful extensions

- **B15 — Trend analysis:** compare scientifically comparable risk maps across years or seasons to detect drying trajectories. Requires stable run metadata, repeatable periods, and a retained archive of comparable outputs.

- **B16 — Persistent hotspot detection:** identify cells or groups that remain at elevated risk across consecutive, comparable windows. Define persistence and missing-period rules first; implement after the temporal foundations in B15.

### Conditional / parked

- **B20 — ML classifier:** do not replace the rule-based model unless independent labelled outcomes become available, such as historical expert labels, observed yield or pasture impacts, or defensible remote-sensing ground truth. Any future model requires independent train/test data, real observed predictors, spatial cross-validation, and comparison against the rule-based baseline.

### Engineering optimisation — evidence required

- **B19 — Async data loading:** consider concurrent loading for large-area or multi-year runs only after profiling demonstrates that loading is a material bottleneck. This is an engineering optimisation, not part of the Phase 5 scientific deliverable.

### Recently resolved foundations

- ~~**B17**~~ **RESOLVED (Sprint 13)** — A mocked orchestration test validates `run_pipeline()` through preparation, risk assessment, and NetCDF/JSON persistence without network access.

- ~~**B18**~~ **RESOLVED (Sprint 13)** — Regression coverage simulates a missing decile dataset through `prepare_data()` and asserts a clear `RuntimeError`.
