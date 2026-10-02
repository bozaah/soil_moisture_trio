# 2026-09-14 — SWAZ review artifact built, coverage checked, run-oriented soil context loader

Rodrigo ran the review-only SWAZ build under the [08-31 waiver](2026-08-31-swaz-review-build-waiver.md), then approved two review-independent code items: a coverage check of the artifact against the March 2026 risk runs, and a loader that returns soil context in a run's coordinate order. Starting commit: `42096ae`, clean `dev`. Ending commit: `38bfab0`.

## Build

Prerequisites checked before the run: worktree clean, `data/source_inputs/sm_pct_2025.nc` SHA-256 matched the pinned manifest, `TERN_API_KEY` set and the TERN host answering, no prior bundle or checkpoints under `data/processed/slga_awral/`.

Command: `uv run python -m scripts.slga_build_swaz_artifact --awral-grid-input data/source_inputs/sm_pct_2025.nc --max-runtime-seconds 21600`.

Result: 16 stripes of 10 rows, 225–419 s each, build work 5,847 s (1 h 37 min), peak RSS 1.07 GB. All 18 AWC/DES sources retrieved, 5,472 COG window fetches, zero retryable or terminal failures. Checkpoints removed after verified publication. Completed 2026-09-14 02:55 UTC.

Bundle: `data/processed/slga_awral/slga_awc_des_awral_swaz_0p05deg_v1/` (NetCDF 3.1 MB, sidecar, `build_report.json`). Artifact SHA-256 `63b0e8d97b278699eb319686eb39604098a5ee3fb3269fb15bce30a7a4c4b266`, builder commit `42096ae`. Grid 156 × 186 = 29,016 cells, latitude −27.45 to −35.2, longitude 114.05 to 123.3, `storage_case` 7, `des_component` 3. Variable ranges: `awc_storage_capacity_mm` 0–281, `depth_of_soil_m` 0–2.16. 79.6% of cells carry soil values.

Cache counters read `cache_hits 0, cache_misses 5472, cache_evictions 5416`. This is expected for a single pass: 5,472 = 304 tiles (16 × 19) × 18 sources, each window fetched once. The cache pays off only on resume or repeat runs. Not a defect.

The bundle is gitignored and exists only on Rodrigo's machine. Backup outside Git is still owed.

## Coverage check against the March 2026 risk runs

Session-local script, not committed. Compared the artifact against `outputs/risk_2026_mar_SWAZ` and `outputs/risk_2026_mar_SWAZ_boundary_2026-03-26` (same 156 × 186 grid, polygon-masked, 9,625 and 9,650 valid cells).

- 100% of risk-valid cells carry finite AWC and DES values, except one coastal cell at −35.05, 116.90 in the boundary run.
- The 20.4% of the rectangle without soil values lies entirely outside the risk domain (ocean in the buffered rectangle).
- `source_coverage_fraction` inside the domain: ≥0.5 covers 99.5% of risk cells, ≥0.8 covers 97.7%, ≥0.95 covers 94.6%, 1.0 covers 86.2%.

Consequence for B25a: the minimum-coverage rule affects the coastal fringe only. It is still Karen and Dennis's call.

## Run-oriented soil context loader

`load_soil_context(bundle_dir, run_latitude, run_longitude)` added to `src/soil_moisture_trio/slga/artifact.py`. It resolves artifact and sidecar from a bundle directory, accepts run coordinates in either order (pipeline `lats` are ascending, the artifact is stored descending), matches in artifact order through the existing verifying loader (checksum, sidecar and schema checks unchanged), flips the result back, and fails unless the returned coordinates equal the run's element for element.

Tests in `tests/test_slga_artifact.py`: four orientation round trips on a synthetic bundle with value checks against the native load, rejection of strided and single-value requests, and one test against the real bundle and the March boundary risk grid that skips when either file is absent. The real-bundle test ran locally and passed.

No `main.py` or pipeline change. Operational runs still do not load soil context. Risk outputs untouched.

Integration note: a probe that held two NetCDF datasets open in one process alongside the loader's own open segfaulted once. Integration code should use context managers and copy coordinate arrays out.

## Verification

- `uv run pytest -q`: 172 passed, 1 authenticated SLGA test skipped. Ruff clean.
- Committed by Rodrigo 2026-09-15 07:02 as `38bfab0`, pushed to `origin/dev` 2026-09-15.

## Remaining review-independent work, in order

1. B14a grouping-agnostic summary framework: risk NetCDF plus any integer grouping raster on the same grid, reporting counts, coverage, uncovered cells, category proportions and stress statistics with explicit denominators. Design check with Rodrigo first.
2. Reconciliation tests shipped with it: strata plus uncovered cells equal the valid-risk domain, and `risk_map`, `stress_index` and the valid mask are unchanged with and without soil context.
3. Bundle backup outside Git.

What waits for the review: band definitions, reference domain, minimum coverage threshold (B25c), and any figure claiming soil stratification. Scope unchanged: review input for Karen Holmes and Dennis van Gool only, no distribution, promotion or operational use.
