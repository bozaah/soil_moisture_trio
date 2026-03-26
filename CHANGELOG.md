# Changelog — Soil Moisture Trio

All notable changes per sprint/iteration. Format: `## [sprint] YYYY-MM-DD — Title`.

---

## [Sprint 10] 2026-03-26 — Audit remediation pass 1

### Changed

- `tests/test_moisture_ranges.py` — replaced top-level remote access and `sys.exit()` behavior with a manual diagnostic test gated by `RUN_REMOTE_DIAGNOSTICS=1`, restoring clean default pytest collection
- `src/soil_moisture_trio/visualize.py` — fixed Folium rectangle generation to render every valid grid cell from centre coordinates; invalid `-1` sentinel cells now skip safely before `RiskLevel` coercion; summary panel now follows the shared runtime summary order
- `src/soil_moisture_trio/risk.py` — normalised the public summary contract: `critical/alert/watch/low` are the only risk buckets, and the top label is now `Critical` instead of `High`
- `tests/test_pipeline.py` — updated expected labels/keys to match the runtime contract and added assertions that the removed `elevated` bucket does not reappear
- `src/soil_moisture_trio/pipeline.py` — hardened the raster-band fallback by switching from band-label slicing to positional slicing when averaging a selected time window
- `main.py`, `src/soil_moisture_trio/pipeline.py`, `src/soil_moisture_trio/visualize.py`, `src/soil_moisture_trio/plot.py`, `scripts/render_bulletin.py` — replaced touched `print()` status output with `logging`
- `pyproject.toml` — replaced placeholder package description
- `src/soil_moisture_trio/data_sources.py` — made SILO cache directories bbox-aware to stop mixed-bounds cache collisions; added validation for empty target grids, inverted dates, partial `weather_tools` payloads, malformed stacks, and source-grid/coordinate mismatches
- `src/soil_moisture_trio/plot.py` — removed the legacy positional-argument shim from `save_risk_plot`
- `src/soil_moisture_trio/config.py` — removed unused legacy threshold fields from the runtime config surface and added `allow_legacy_sm` as the only explicit compatibility switch
- `main.py`, `src/soil_moisture_trio/pipeline.py` — added `--allow-legacy-sm` / `allow_legacy_sm`; the pipeline now hard-fails on decile `sm_pct` load errors by default and only falls back to the legacy raw-values `sm_pct` source when the opt-in flag is set, with a warning about scientific non-equivalence
- `pyproject.toml` — added a targeted pytest warning filter for the environment-specific `numpy.ndarray size changed...` RuntimeWarning so the default test gate is noise-free

### Added

- `tests/test_visualize.py` — regression test proving the Folium output renders all valid cells instead of dropping the outer row/column
- `sessions/2026-03-26-sprint10-audit-remediation.md` — sprint note for the first audit remediation pass
- `tests/test_data_sources.py` — regression coverage for bbox-scoped SILO cache directories and loader failure handling
- `tests/test_pipeline.py` — regression coverage for the explicit legacy soil-moisture fallback gate

### Verified

Default test baseline restored and expanded: `uv run pytest -q` now passes with `17 passed, 1 skipped`. Targeted regression checks also pass: `uv run pytest tests/test_pipeline.py tests/test_visualize.py -q` → `11 passed, 1 warning`; `uv run pytest tests/test_data_sources.py -q` → `4 passed`; `uv run pytest tests/test_pipeline.py -q` → `12 passed, 1 warning`.

---

## [Sprint 10] 2026-03-26 — Audit remediation pass 2: doc sync and metadata cleanup

### Changed

- `README.md` — removed the stale B22 workaround note and documented the current bbox-scoped SILO cache layout
- `docs/architecture.md` — rewritten to describe the real runtime flow, current output contract, polygon masking, and bbox-scoped cache behavior
- `docs/data-sources.md` — rewritten to match the decile-first AWRAL path, opt-in legacy fallback, weather-tools primary loader, NetCDF fallback, and current cache layout
- `docs/thresholds.md` — rewritten to separate the retained `classify_grid()` binary rule from the operational `risk.py` stress-index path and to document `moisture_threshold=0.50`
- `docs/risk-model.md` — removed obsolete CatBoost/ML language and documented the direct risk-computation path
- `docs/technical_report.md` — corrected stale config references, updated the dryness-zero condition to `sm_pct >= 0.50`, documented `--boundary-gpkg` masking, refreshed the SILO cache note, and removed the outdated logging limitation
- `docs/cli-reference.md` — updated for `--allow-legacy-sm`, `--use-silo-cog-loader`, the real cache default, and the SILO lag note
- `docs/backlog.md` — marked B5, B7, B9, and B22 resolved; reworded B24 now that B22 is already closed
- `AGENTS.md` — updated the cache note and session-history links to reflect current repo state

### Added

- `sessions/2026-03-26-sprint10-doc-sync.md` — session note covering the documentation reconciliation pass and remaining gaps

### Verified

Targeted stale-pattern scan across `README.md`, `docs/`, and `src/` returned clean for the obsolete ML/cache/config narratives addressed in this pass. Targeted regression gate also passed: `uv run pytest tests/test_data_sources.py tests/test_pipeline.py -q` → `16 passed in 2.40s`.

---

## [Sprint 10] 2026-03-26 — Verification pass 3: lint baseline and live SWAZ run

### Changed

- `pyproject.toml` — added `ruff` to the `dev` dependency group so linting runs through the repo-managed `uv` environment
- `src/soil_moisture_trio/plot.py` — renamed two ambiguous loop variables to satisfy `ruff` rule `E741`

### Added

- `sessions/2026-03-26-sprint10-live-verification.md` — session note covering the lint restore and fresh operational verification run

### Verified

Lint baseline restored: `uv run ruff check` now passes cleanly. Fresh live SWAZ boundary run also completed for `2026-03-01` to `2026-03-24` using `data/south_west_agricultural_boundary.gpkg`, producing `0` Critical, `1,486` Alert, `4,400` Watch, and `3,764` Low valid cells across `9,650` in-boundary valid cells, with outputs written to `outputs/risk_2026_mar_SWAZ_boundary_2026-03-26/`.

---

## [Sprint 9] 2026-03-25 — Boundary GeoPackage integration

### Added

- `config.py` — `boundary_gpkg: Optional[Path]` field; when set, bbox is derived from the file's bounds (+0.1° buffer) and cells outside the polygon are masked as invalid
- `pipeline.py` — `_derive_bounds_from_gpkg()`: reads gpkg at pipeline init, reprojects to EPSG:4326, extracts bounds, returns `config.model_copy(update=...)` so all downstream methods use the correct bbox automatically; `_build_polygon_mask()`: vectorised `shapely.contains_xy` test of cell centres against the union of all boundary features; applied in `prepare_data()` after NaN masking
- `plot.py` — `boundary_gpkg` parameter added to `save_risk_plot`; overlays boundary as black polygon outline on both map panels when provided
- `main.py` — `--boundary-gpkg` flag; replaces need for manual `--min-lat/max-lat/min-lon/max-lon` when using a boundary file
- `pyproject.toml` — `geopandas`, `matplotlib-scalebar` added as dependencies
- `sessions/2026-03-25-sprint9-boundary-gpkg.md` — sprint notes: architecture decision (Option B vs A), implementation details, verification table
- `docs/backlog.md` — B24 added (Option A: full-WA download + multi-region clip for rangelands, pending B22 fix)

### Verified

March 2026 SWAZ boundary run: Critical 0.07% (7 cells), Alert 15.48% (1,490), Watch 45.97% (4,425), Low 38.47% (3,703), valid 9,625 cells. The 405 "Critical" cells from the prior bbox-only run were rangelands outside the agricultural boundary — correctly excluded. 11 unit tests pass.

### Added to backlog

- **B24** — Option A (full WA download, multi-region clip): enables rangelands outputs alongside agricultural zone from one cache; requires B22 fix first.

---

## [Sprint 8] 2026-03-25 — Plot fixes, output subdirectory, bulletin PNG path

### Changed

- `scripts/render_bulletin.py` — bulletin now embeds PNG as a path relative to the bulletin file's parent directory (fixes VSCode preview — was resolving `outputs/outputs/foo.png`); `_relative_png()` helper added; falls back to original path if relative resolution fails
- `src/soil_moisture_trio/plot.py` (`save_risk_plot`) — added y-axis south buffer (`max(cell_height, 0.3)°`) to stop southernmost cells being clipped by `pcolormesh`; `0.1°` north buffer added for symmetry
- `src/soil_moisture_trio/plot.py` (`plot_dryness_diagnostics`) — left histogram panel changed from Dryness–Stress Index distribution to Soil Moisture Percentile Rank distribution; more useful diagnostic: shows how cells sit relative to historical climatology
- `main.py` — `--output-dir` flag added; when set, `--risk-output-prefix` and `--risk-plot-path` are treated as basenames within the specified directory; `stress_diagnostics.png` follows automatically (derived from plot path)

### Added

- `sessions/2026-03-25-sprint8-plot-output-fixes.md` — sprint notes: root cause and fix for each of the four issues

### Verified

March 2026 SWAZ (1–23 Mar, lat −35 to −27, lon 114–123): Critical 1.69%, Alert 15.65%, Watch 43.25%, Low 39.41%. All outputs in `outputs/risk_2026_mar_SWAZ/`. Bulletin PNG renders in VSCode preview. 11 unit tests pass.

---

## [Sprint 7] 2026-03-25 — Persistent SILO cache, bulletin template, threshold recalibration

### Changed

- `config.py` — `silo_cache_dir` default changed from `None` to `~/.cache/soil_moisture_trio/silo`; directory is created automatically on first run; prior default (`None` → `save_to_disk=False`) caused GeoTIFFs to be discarded after each run
- `config.py` — `moisture_threshold` 0.30 → 0.50; dryness factor now measures departure below the climatological median (consistent with BoM anomaly framing) rather than departure below the 30th-percentile Watch/Low boundary; validated against March 2026 SWAZ (Critical 1.7%, Alert 15.6% — within target <10%/<25%)
- `docs/data-sources.md` — SILO cache section updated to document the new persistent default and override instructions
- `docs/backlog.md` — B21 resolved (persistent cache); B22 added (cache-bbox shape mismatch bug); B23 added (seasonal stress index thresholds, future work)
- `docs/technical_report.md` — Section 2 reframed as "Soil Moisture Percentile Rank — Interpretation Reference" with explicit note that it does not drive `risk.py`; Section 3 expanded with §3.5 (scientific rationale for thresholds and weights, including new dryness reference point subsection with calibration note); version updated to Sprint 7

### Added

- `templates/bulletin_template.j2` — Jinja2 Markdown bulletin template: header, key finding sentence, risk summary table, map embed, methodology note, caveats
- `scripts/render_bulletin.py` — standalone CLI renderer: `--summary-json`, `--map-png`, `--output`; renders the template from a risk summary JSON; handles `< 0.1%` display for near-zero values; strips ISO timestamp from date fields
- `sessions/2026-03-25-sprint7-persistent-cache-bulletin.md` — sprint notes: discrepancy log, threshold recalibration decisions, validation table

### Resolved

- **B21** — `silo_cache_dir` now persistent by default; no explicit `--silo-cache-dir` needed for standard runs.

### Added to backlog

- **B22** — SILO cache key does not include bounding box; mixed-bbox runs in one cache dir cause `np.stack` shape mismatch. Workaround: use `--silo-cache-dir` per bbox.
- **B23** — Seasonal stress index thresholds (Option C): replace fixed 0.85/0.60/0.35 thresholds with season-calibrated values to stabilise the proportion of cells in each category across months.

### Verified

March 2026 SWAZ (1–23 Mar, lat −35 to −27, lon 114–123): Critical 1.7%, Alert 15.6%, Watch 43.3%, Low 39.4% (target: Critical <10%, Alert <25%). 11 unit tests pass.

---

## [Sprint 6] 2026-03-23 — Decile calibration: switch to AWRAL percentile rank product

### Changed

- `pipeline.py` — swapped AWRAL soil moisture URL from `processed/values/day/sm_pct_{year}.nc` to `processed/deciles/day/sm_pct_{year}.nc`; updated load messages to reflect decile product; retained defensive `max > 1.1` check (now warns rather than silently converting)
- `config.py` — `moisture_threshold` 0.25 → 0.30 (Watch/Low boundary in percentile rank); `alert_moisture_threshold` 0.18 → 0.20 (Alert/Watch boundary); `watch_margin` 0.08 → 0.10; updated field descriptions to say "percentile rank" throughout
- `main.py` — removed hardcoded `moisture_threshold=0.2` override; config default now applies
- `docs/thresholds.md` — rewritten for decile product; B1/B3 marked resolved; Jan–Mar 2026 calibration stats included
- `docs/data-sources.md` — AWRAL section updated with decile URL, full product table, migration note
- `docs/backlog.md` — B1 and B3 marked resolved
- `risk.py` — `_compute_risk_map()` and `assess_risk_levels()` now accept `valid_mask` (boolean array) instead of `classification_grid`; `pipeline.assess_risk()` uses `valid_mask_grid` directly — `classify_grid()` is no longer called in the main pipeline flow (retained as a standalone diagnostic utility)
- `main.py` — removed `pipeline.classify_grid()` call; `assess_risk()` now takes no arguments
- `docs/technical_report.md` — full rewrite for scientist/policy-maker audience; documents decile methodology, stress index formula with probabilistic dryness interpretation, before/after calibration table, and all outputs

### Added

- `data/awral_decile_sm_pct_WA_monthly.nc` — WA monthly decile subset (1911–2026, 441×341, 1382 months, ~831 MB) downloaded via OPeNDAP decade-chunked in 5.3 min
- `outputs/decile_calibration_jan-mar-2026.png` — exploratory calibration plots (mean rank map, category map, distribution histogram)
- `sessions/2026-03-23-decile-calibration.md` — sprint notes

### Resolved

- **B1** — `moisture_threshold=0.25` over-classifying dry cells. The decile product is spatially and seasonally normalised by construction; `moisture_threshold=0.30` now means the true 30th percentile everywhere.
- **B3** — Calibration helper. Decile product *is* the calibration; no separate step needed.

### Verified

Step 0 OPeNDAP probe confirmed variable name is `sm_pct` (units: `relative`, shape `(366, 681, 841)` for 2024 daily). Jan–Mar 2026 WA calibration: Critical 1.1%, Alert 6.8%, Watch 12.3%, Low 79.9% — compared to 47.1%/29.5%/9.4%/14.1% with old raw product. Historical Jan–Mar mean rank = 0.500 (confirms decile centred on median). 11 unit tests pass.

---

## [Sprint 4] 2026-03-18 — Remove CatBoost; rule-based classifier

### Changed

- `pipeline.py` — removed CatBoost entirely; replaced `build_model/train/evaluate/predict_grid` with `classify_grid()` (deterministic threshold rule: dry if `sm < moisture_threshold AND (temp > temp_threshold OR vpd > vpd_threshold)`)
- `pipeline.py` — removed synthetic `ndvi`, `ndwi`, `fire_index` from `_load_all_real_data()`; `prepare_data()` now only builds `valid_mask_grid`, no train/test split
- `config.py` — removed `ndvi_threshold`, `lr`, `epochs`, `batch_size`, `catboost_iterations`, `catboost_depth`, `catboost_learning_rate`
- `main.py` — removed CatBoost CLI flags and train/evaluate steps; pipeline is now load → classify → risk
- `pyproject.toml` — removed `catboost` dependency; added `scipy` (direct, was catboost transitive) and `pytest` to `dev` group
- `tests/test_pipeline.py` — replaced ML-specific tests with `test_classify_grid_shape_and_values` and `test_classify_grid_dry_rule`; renamed `test_prepare_data_replaces_nan` → `test_prepare_data_excludes_nan_cells`
- `docs/cli-reference.md` — removed Model Tuning section
- `docs/backlog.md` — closed B2/B4/B6/B11/B13 (resolved); added B20 for future proper ML design

### Decision

CatBoost was learning to reproduce its own labels (tautology), NDVI was random noise, and the classification output was only used as a valid-cell mask — adding zero informational value. Removed in favour of an honest deterministic rule. Future ML (B20) requires independent labelled data and spatial CV before reintroduction.

### Verified

Q2 2025 WA run confirmed no regression: grid dimensions (150,381 cells), ocean mask (58,190 invalid, 38.70%), and all 4 risk levels present match pre-refactor Oct 2025 WA baseline exactly. SILO cache hit on second run (0 new downloads).

---

## [Sprint 5] 2026-03-18 — Production runs, cache documentation

### Runs completed

- Q2 2025 WA (Apr–Jun, 91 days) — regression baseline confirmed post-CatBoost removal
- Jan–Mar 2026 WA (74 days) — first 2026 YTD run; pipeline and AWRAL 2026 data confirmed live

### Added

- `docs/data-sources.md` — SILO GeoTIFF cache location, size estimates, persistence warning; AWRAL unit-by-year table
- `sessions/2026-03-18_q2-wa-verification.md` — Q2 2025 regression checks
- `sessions/2026-03-18_2026-ytd-run.md` — Jan–Mar 2026 run + AWRAL unit change finding
- `.markdownlint.json` — project-wide lint config suppressing MD013/MD024/MD040/MD060

### Finding

`sm_pct_2026.nc` is already in fraction (0–1) scale; `sm_pct_2025.nc` was in percent (0–100). Pipeline heuristic handles this automatically — verify on each new year.

---

## [Sprint 3] 2026-03-18 — Docs hygiene, sessions structure, code audit

### Added

- `sessions/` directory with per-session notes and this CHANGELOG
- `docs/` directory with detailed reference docs (architecture, data sources, thresholds, CLI, risk model, backlog)
- `sessions/2026-03-18-session-01.md` — code audit findings for this sprint

### Changed

- `AGENTS.md` slimmed to a lean index; detailed content moved to `docs/`

### Identified Issues (no code changes this sprint — see session notes)

- `test_moisture_ranges.py` is a standalone diagnostic script in `tests/` and breaks pytest collection; should be relocated
- `moisture_threshold=0.25` default (and `0.2` in `main.py`) is too high for AWRAL `sm_pct` data
- NDVI/NDWI/fire_index are still random synthetic values — noisy ML features
- No `np.random.seed` set when generating synthetic grid variables → non-reproducible runs
- Sequential 80/20 train/test split on flattened spatial grids introduces geographic bias

---

## [Sprint 2] 2025-11-12 — Real data, risk layer, diagnostics

### Added

- `TECHNICAL_REPORT.md` — data sources, thresholds, CatBoost design, outputs
- `src/soil_moisture_trio/risk.py` — physics-based dryness stress index + `RiskLevel` enum
- `src/soil_moisture_trio/plot.py` — two-panel PNG + diagnostic scatter/histogram
- `src/soil_moisture_trio/data_sources.py` — `WeatherToolsSiloLoader` wrapping `weather_tools`
- `assess_risk()` on pipeline returning `risk_map`, `summary`, `stress_index`
- CLI flags: `--year`, `--start-date`, `--end-date`, `--risk-output-prefix`, `--risk-plot-path`, `--catboost-*`

### Changed

- Retired all synthetic data code paths; `prepare_data()` always calls `_load_all_real_data()`
- AWRAL `sm_pct` is now the sole soil moisture source (no legacy `sm` fallback)
- Added unit detection: divides by 100 only when `max > 1.1`
- Lat/lon alignment bug fixed in diagnostics scatter
- `assess_risk_levels()` now returns 3-tuple `(risk_map, summary, stress_index)`

---

## [Sprint 1] 2025-10 — CatBoost, refactor, real data integration

### Added

- `pytest` test suite; tests mock `_load_all_real_data` for speed
- `ClassifierConfig` Pydantic model for validated config
- `src/soil_moisture_trio/` package structure (`config`, `pipeline`, `visualize`)
- CatBoost classifier replacing MLP

### Changed

- `main.py` converted to thin `argparse` CLI orchestrator
- SILO `tmax`/`vpd` integrated from AWS S3 NetCDF and COG (weather_tools)
- Grids clipped to Australian bounds; latitudes sorted south-to-north
