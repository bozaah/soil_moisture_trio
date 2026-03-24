# Changelog — Soil Moisture Trio

All notable changes per sprint/iteration. Format: `## [sprint] YYYY-MM-DD — Title`.

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
