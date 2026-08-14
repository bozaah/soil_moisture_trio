# Changelog — Soil Moisture Trio

All notable changes per sprint/iteration. Format: `## [sprint] YYYY-MM-DD — Title`.

---

## [Phase 5] 2026-08-14 — Resumable SWAZ production command

### Added

- `slga.checkpoint` — credential-free compressed stripe arrays, deterministic manifests, SHA-256/identity verification, immutable atomic stripe directories, and exact contiguous stripe assembly
- `scripts/slga_build_swaz_artifact.py` — hard-scoped 156×186 SWAZ builder using 10-row resumable stripes, 10×10 target tiles, 256 MiB cache, and a default six-hour between-stripe work limit
- clean Git commit enforcement, contract-bound resume rejection, aggregate build metrics, and a checksummed `build_report.json` inside the immutable review bundle
- deterministic tests for checkpoint round-trip/assembly, identity/coordinate/checksum drift, failed-promotion cleanup, clean-worktree enforcement, runtime-stop messaging, and unknown checkpoint entries

### Decided

- repo-local ignored immutable bundle is the first review target; checkpoints are removed only after verified publication unless explicitly retained
- audited STAC/COG attempt/fetch/retry/cache/runtime/memory counters are sufficient; actual HTTP bytes remain explicitly unavailable
- publisher STAC multihashes plus strict source identity/profile checks are sufficient for Release 1; full COG downloads/hashes are not required
- the command is implemented but no SWAZ artifact was run or approved; external soil-science and distribution authority review remain gates

## [Phase 5] 2026-08-14 — Reviewed artifact schema and immutable bundle implementation

### Added

- direct mapped DES EV/10/90 means, mapped dispersion, valid area/coverage, and valid-DES-area shallow-than-1 m fractions
- mixed uncertainty-width mapped dispersion, valid area, and coverage so its intersection support is auditable
- canonical machine-readable storage-case component/interpretation definitions in NetCDF metadata
- immutable `write_soil_artifact_bundle()` staging and fail-if-present publication; rollback selects prior untouched bundles
- exact approved SWAZ footprint enforcement for artifact writing and deterministic schema/promotion failure tests

### Decided

- retain existing float dtypes, zlib level 4, and 64×64 chunk design
- retain artifact version label `v1` as requested, while keeping release approval explicitly separate from implementation status
- no production artifact was built and operational risk behavior remains unchanged

## [Phase 5] 2026-08-14 — Artifact schema and promotion review

### Reviewed

- retained the seven explicit storage scenarios, current float32/float64 choices, zlib level 4, and 64×64 chunk design as reasonable for the 156×186 SWAZ artifact
- identified missing direct DES EV/10/90, DES support/dispersion, and shallow-profile presentation as a Release 1 blocker
- identified that the standalone mixed-width proxy drops its own harmonised valid area, coverage, and mapped dispersion
- identified unsafe replacement semantics: a sidecar-promotion failure after replacing an existing artifact can destroy the prior release

### Required before `v1`

- approve and add direct DES/shallow-profile variables, mixed-width support variables, and machine-readable storage-case definitions
- publish to immutable fail-if-present versioned bundles and roll back by selecting a prior bundle, not overwriting files
- complete soil-science terminology/scenario review and distribution approval; no artifact was built or promoted

## [Phase 5] 2026-08-14 — Albany 100-cell production-tile comparison

### Verified

- the approved 10×10 Albany coastal window (100 cells) ran as four 5×5 tiles and as one 10×10 tile, each with a 256 MiB cache and exact warm verification
- four 5×5 tiles: 57.95 seconds cold, 72 logical reads/fetches, 144 MiB peak cache, ~402 MiB peak RSS, 16.58-second cache-only reverse pass
- one 10×10 tile: 56.09 seconds cold, 18 logical reads/fetches, 81 MiB peak cache, ~532 MiB peak RSS, 16.68-second cache-only repeat
- both runs had 18 successful STAC validations, no retries/failures/evictions, identical coverage/storage summaries (97/100 finite cells; coverage 0–1, mean 0.8526), and exact warm equality
- diagnostic outputs: `outputs/slga_b25b_albany_coastal_10x10_tiles_5x5_profiled.json` and `outputs/slga_b25b_albany_coastal_10x10_single_tile_profiled.json` (ignored by Git)

### Decision

- 10×10 target tiles with a 256 MiB cache are the provisional SWAZ production candidate; compared with 5×5 tiles, source reads fell fourfold and retained cache fell 63 MiB at the cost of ~130 MiB more measured peak RSS
- the 156×186 SWAZ rectangle implies 304 target tiles and 5,472 logical source reads at this setting before exact-window cache reuse; this is a deterministic work count, not a runtime or HTTP-transfer estimate
- whole-build failure/restart planning, final schema/DES presentation, distribution/version promotion, and artifact approval remain gates

## [Phase 5] 2026-08-14 — Albany coastal multi-tile comparison

### Verified

- the same 25 Albany cells reran as nine 2×2 target tiles with a 256 MiB cache and 10-minute limit
- cold execution completed in 41.69 seconds: 162 logical reads resolved to 54 cache hits and 108 successful COG accesses/window fetches; all 18 STAC requests succeeded; no retries, terminal/exhausted failures, or evictions occurred
- peak source cache was 108 MiB and process-lifetime peak RSS was ~306 MiB; coverage and storage summaries matched the single-tile run
- reverse tile order was exactly equal and cache-only in 4.04 seconds with 162 hits and no STAC/COG access
- diagnostic output: `outputs/slga_b25b_albany_coastal_5x5_multitile_2x2_profiled.json` (ignored by Git)

### Decision

- 256 MiB is retained as the cache baseline for the next bounded profile; 2×2 tiles are correctness-safe but not a production recommendation because they increased logical reads ninefold
- a larger target-window tile/stripe profile remains required before SWAZ production settings or runtime estimates are approved

## [Phase 5] 2026-08-14 — Albany coastal/nodata profiling pilot

### Verified

- approved 5×5 Albany window (25 cells; latitude −34.90…−35.10, longitude 117.80…118.00) completed cold in 37.67 seconds using one target tile and a 256 MiB cache
- all 18 STAC requests, COG accesses, and COG window fetches succeeded without retries, terminal/exhausted failures, or cache evictions; retained/peak source cache was 36 MiB and process-lifetime peak RSS was ~288 MiB
- all seven storage cases were finite in 24/25 cells; source coverage ranged 0–1 with mean 0.6477, exercising expected coastal zero/partial support
- the warm repeat was exactly equal in 4.15 seconds with 18 cache hits and no STAC or COG access
- diagnostic output: `outputs/slga_b25b_albany_coastal_5x5_profiled.json` (ignored by Git); actual GDAL HTTP transferred bytes remain unavailable

### Limitations

- the user-selected single-tile layout minimized requests but could not test multi-tile seams, order, or cache pressure; reversing one tile is the same processing sequence
- no SWAZ-wide runtime extrapolation or production tile/cache recommendation is accepted from this pilot alone; no artifact was built and risk behavior remains unchanged

## [Phase 5] 2026-08-14 — B25b profiling instrumentation

### Added

- credential-free reader metrics separating STAC request attempts/outcomes, COG access attempts/outcomes, attempted/completed COG window fetches, and cache hits/misses/evictions/current/peak retained bytes
- per-build before/after reader snapshots, build-local counter deltas, and deterministic per-tile elapsed/extent metrics
- pilot reporting for platform-normalised process peak RSS and an explicit unavailable value for GDAL-level HTTP transferred bytes rather than an unsupported estimate
- mocked tests for retry success/exhaustion, COG retry/fetch distinctions, cache eviction/peak behavior, stable per-tile timing, and RSS unit conversion

### Scope boundary

- no authenticated pilot was run; representative SWAZ coastal/nodata footprint, target-cell limit, tile shape, cache budget, and maximum runtime still require approval
- no risk calculation, threshold, mask, summary, or operational output behavior changed

## [Phase 5] 2026-08-14 — Static artifact scope changed to SWAZ

### Changed

- superseded the planned full-WA Phase 5 static soil artifact with a SWAZ-only first artifact
- pinned the exact canonical footprint to descending latitude centres −27.45…−35.20 and ascending longitude centres 114.05…123.30, shape 156×186 (29,016 cells), covering the approved boundary’s +0.1° operational bbox
- renamed the provisional production artifact to `slga_awc_des_awral_swaz_0p05deg_v1.nc` and aligned active architecture, methodology, source, CLI, evidence, builder-contract, backlog, and local-data documentation
- retained the boundary polygon as a later runtime mask; static soil coverage and area continue to use full AWRA-L cell denominators

### Scope boundary

- no full-WA static SLGA artifact will be built in this phase; future rangelands or multi-region support requires a separately reviewed scope and artifact version
- no artifact was built and no risk calculation, threshold, mask, summary, or operational output behavior changed

## [Phase 5] 2026-08-12 — B25b documentation synchronization

### Changed

- active README, architecture, data-source, CLI, technical-report, local-data, and SLGA evidence documentation now distinguish the implemented B25b prototype foundations from the absent production full-WA artifact and absent operational soil summaries
- `docs/slga-evidence-review.md` now records the implemented catalogue, COG retrieval, integration, harmonisation, tiling, provisional artifact I/O, tests, and 3×3 authenticated pilot instead of describing them as design-only future work
- remaining gates are aligned across active docs: larger coastal/nodata and transfer/cache profiling, full-WA performance review, final schema/DES presentation approval, artifact distribution/version promotion, grouped-summary reconciliation, and soil-science review

### Verified

- documentation-only diff; no source, configuration, tests, manifests, risk calculations, thresholds, masks, summaries, or generated products changed
- fresh pre-edit baseline remained `77 passed, 1 skipped`; `uv lock --check` and `uv run ruff check .` passed
- repository-wide `uv run ruff format --check .` still reports 10 pre-existing non-SLGA files that would be reformatted; this pass does not modify them or claim a clean formatting baseline

## [Phase 5] 2026-08-12 — Canonical AWRA-L grid and deterministic artifact foundations

### Added

- `manifests/awral_v7_grid_source_v1.json` — pins the completed 2025 Bureau-produced AWRA-L v7 operational decile file at NCI by exact path, 312,193,677-byte size, independent SHA-256, schema, dimensions, coordinate metadata, orientation, and coordinate-value hashes
- `slga.grid` — validates an explicit local canonical NetCDF byte-for-byte and preserves exact float64 source coordinates; no implicit download or coordinate regeneration
- `slga.artifact` — provisional compressed v1 NetCDF writer, close-then-validate atomic promotion, deterministic sidecar, full provenance, and credential-free checksum/schema-verifying exact-subset loader
- `slga.tiling` — bounded target-tile/source-window orchestration with one-native-pixel halos and global source offsets so geometry is invariant across tile boundaries
- `slga.builder` / `scripts/slga_tiled_pilot.py` — exact 18-source tiled retrieve/integrate/harmonise orchestration, block-aligned bounded LRU caching, pilot safety limits, metrics, and opposite-order equality verification
- deterministic tests for missing/corrupt/mismatched grid inputs, artifact schema/version/checksum/source-contract drift, interrupted writes, exact runtime subsets, credential-free loading, UTC timestamp compatibility, reproducibility, bounded cache/window behavior, no overlap, full 18-source orchestration, and tile shape/order invariance

### Decided

- the canonical source is the exact operational Bureau/NCI AWRA-L v7 lineage, not the third-party Zenodo republication; the stable remote URL alone is not considered immutable, so only bytes matching the tracked independent SHA-256 are accepted
- the builder will receive the large canonical source explicitly, while runtime loading depends only on the approved static artifact, sidecar, and tracked compact contracts
- the full-WA artifact footprint is the exact 441×341 AWRA-L subset latitude −13…−35 and longitude 112…129; the implemented schema remains unchanged and provisional during pilots

### Verified

- the independently downloaded NCI input validates as 681 descending latitude centres (−10 to −44) × 841 ascending longitude centres (112 to 154) at nominal 0.05° spacing
- tiled and untiled harmonisation are exactly equal across multiple tile shapes and forward/reverse processing, including variable-specific nodata and no-overlap windows; complete valid area reconciles to target-cell area without cross-tile duplication
- an authenticated 3×3-cell SWAZ pilot split into six tiles issued 108 logical reads, required 72 COG fetches with 36 cache hits, and completed an instrumented run in 58.36 seconds at ~282 MB peak RSS and ~84.9 MB retained cache; all seven cases were finite with 0.9861–1.0 coverage, and a reverse-order pass used 108 cache hits, no COG fetches, and was exactly equal in 1.40 seconds
- `uv run pytest -q` → `77 passed, 1 skipped`; live-reader `+00:00` retrieval timestamps are accepted as timezone-aware UTC by the artifact writer; no production full-WA artifact was built and no risk modules, calculations, thresholds, masks, summaries, or outputs were changed

### Remaining gates

- approve final v1 variables/chunking and DES uncertainty presentation after pilot inspection
- profile larger representative coastal/nodata tiles with measured HTTP transfer/retry/cache behavior and full-WA memory/runtime estimates
- decide artifact distribution/version promotion, then perform and review the explicit full-WA build

## [Phase 5] 2026-08-12 — Deterministic B25b contract and small-window prototype

### Added

- `docs/slga-builder-contract.md` — deterministic source, integration, harmonisation, artifact, checksum, runtime-subset, and failure contract with unresolved science decisions kept explicit
- `src/soil_moisture_trio/slga/` — narrow modules for strict full-ID catalogue/STAC validation, authenticated COG window reads, native-grid DES-capped storage integration, and EPSG:3577 fractional-overlap aggregation
- deterministic tests for source/version drift, missing credentials, the two approved upstream metadata exceptions, nodata, malformed values, uncertainty ordering, partial/non-overlap, CRS/grid mismatch, exact coordinate subsets, and reproducibility
- one opt-in authenticated AWC window test gated by `RUN_SLGA_LIVE_TESTS=1` and `TERN_API_KEY`

### Changed

- `pyproject.toml` / `uv.lock` — declared Rasterio and pyproj as direct runtime dependencies because project code imports them directly
- B25b storage cases expose AWC-only and DES-only uncertainty effects separately from provisional mixed AWC05+DES10 / AWC95+DES90 scenarios

### Verified

- a fresh authenticated 9×9 native-window prototype validated all 18 pinned AWC/DES sources, integrated all seven storage cases, and mapped them to a synthetic 0.05° target window with explicit ~2.25% source coverage
- `uv lock --check` succeeds; `uv run pytest -q` → `54 passed, 1 skipped`; `uv run ruff check .` and `git diff --check` pass
- existing risk modules, thresholds, masks, summaries, and outputs are unchanged; no full-WA artifact was built

### Remaining gates

- pin the authoritative canonical full-WA AWRA-L coordinate source and checksum
- implement/review deterministic artifact writing and runtime loading, then address scalable full-WA tiling without changing the numerical contract
- obtain the planned soil-science review before bands, coverage thresholds, or operational soil summaries are approved

## [Phase 5] 2026-08-12 — Authenticated SLGA source-manifest verification

### Added

- `manifests/slga_awc_des_sources_v1.json` — live-verified full-ID source catalogue for 15 AWC v2 and 3 DES v2 layers, including URLs, profiles, published STAC multihashes, and file sizes
- `sessions/2026-08-12-phase5-slga-manifest-verification.md` — verification evidence, upstream metadata caveats, and corrected next-step contract

### Corrected

- DES v2 uncertainty components are 10th/90th percentiles (`10`/`90`), not the unavailable `05`/`95` identifiers in the provisional evidence review
- combined AWC/DES lower and upper products are now described as mixed-quantile uncertainty scenarios rather than a formal integrated confidence interval
- source-range handling now reflects live STAC statistics; approximate AWC 0–25% and DES 0–2 m expectations are not hard rejection limits

### Verified

- all 18 corrected COGs support authenticated byte-range reads and share the expected EPSG:4326 3 arc-second grid, transform, bounds, units, and COG structure
- lower ≤ EV ≤ upper ordering holds in the test window for all five AWC depths and DES
- AWC COG nodata is `65535`; DES COG nodata is `NaN`
- documented two upstream exceptions for builder validation: AWC STAC omits nodata, and DES internal band descriptions retain stale `NAT` IDs while filenames/STAC IDs use `TRN`

## [Sprint 13] 2026-08-12 — Validated risk configuration and documentation consolidation

### Changed

- `ClassifierConfig` — added configurable stress weights and Watch/Alert/Critical thresholds; validates weights sum to 1, thresholds are strictly ordered, dates are not inverted, and spatial minimums are below maximums
- `risk.py` — uses config-driven weights and bands, writes `NaN` to continuous stress outside `valid_mask`, and persists model parameters in NetCDF/JSON outputs
- `pipeline.py` / `data_sources.py` — reject inverted time and spatial ranges instead of silently coercing or forwarding them
- `main.py` — exposes weight and risk-threshold CLI flags and passes model metadata into persisted outputs
- bulletin rendering — reads and validates saved model metadata so methodology text reflects the actual run configuration
- `docs/technical_report.md` — became the canonical methodology and threshold reference; architecture, CLI, README, and backlog were aligned with validated configuration and output metadata

### Removed

- `docs/risk-model.md` and `docs/thresholds.md`; their non-duplicated content is consolidated into `docs/technical_report.md`

### Added

- validation tests for weights, risk thresholds, dates, and spatial bounds
- regression coverage for polygon stress masking, missing decile data through `prepare_data()`, saved model metadata, model-aware bulletin text, and fresh mocked `run_pipeline()` orchestration

### Resolved

- B10 — configurable weights and risk bands
- B17 — mocked end-to-end orchestration test
- B18 — missing-decile failure regression

### Verified

- `uv run pytest -q` → `26 passed`
- `uv run ruff check` → `All checks passed!`
- CLI smoke test confirms all six model-configuration flags are exposed

---

## [Sprint 12] 2026-08-12 — Runtime surface trim

### Changed

- `src/soil_moisture_trio/pipeline.py` / `config.py` — removed the scientifically non-equivalent raw soil-moisture fallback; AWRA-L `sm_pct` percentile ranks are now mandatory and source failures raise a clear `RuntimeError`
- `main.py` — removed `--allow-legacy-sm`, `--visualize`, `--output-path`, and their programmatic arguments; the supported output surface is NetCDF, JSON, PNG diagnostics, and Markdown bulletin
- `scripts/moisture_ranges_diagnostic.py` — switched the manual network diagnostic from the retired raw-values product to the required decile product and added 0–1 range validation
- active README and reference docs — removed compatibility and Folium instructions while retaining the SILO COG-to-NetCDF fallback

### Removed

- `src/soil_moisture_trio/visualize.py` and `tests/test_visualize.py`
- Folium and its transitive `branca` / `xyzservices` packages from the locked environment
- unused `RISK_SUMMARY_ORDER` constant
- legacy fallback normalization, config, CLI wiring, and fallback-specific test

### Verified

- `uv sync --frozen --group dev` → clean locked dependency sync
- `uv run pytest -q` → `14 passed`
- `uv run ruff check` → `All checks passed!`
- CLI smoke test confirms removed flags are absent and SILO fallback flags remain present

---

## [Sprint 11] 2026-08-12 — Reproducibility cleanup and single risk surface

### Changed

- `.gitignore` — replaced broad rules that hid the test suite and lockfile; deterministic tests, `uv.lock`, Markdown lint configuration, CI, and `data/README.md` are now visible to version control while large data and generated outputs remain ignored
- `pyproject.toml` / `uv.lock` — made the uv lockfile the reproducible dependency contract; added direct runtime dependencies (`jinja2`, `matplotlib`, `netcdf4`, `pandas`), removed unused `fsspec` and `matplotlib-scalebar`, and retained SciPy after fresh-sync tests proved it is required by xarray interpolation
- `requirements.txt` — removed the stale generated manifest that still included CatBoost
- `src/soil_moisture_trio/pipeline.py` / `config.py` — removed the unused `classify_grid()` binary surface and its exclusive `temp_threshold` / `vpd_threshold` settings; operational outputs now have one documented risk decision surface
- `tests/test_moisture_ranges.py` — moved out of pytest collection and replaced by `scripts/moisture_ranges_diagnostic.py`
- README and reference docs — documented local data provisioning, fresh-clone verification, the single operational risk surface, and resolved backlog items B8/B12

### Added

- `.github/workflows/ci.yml` — fresh locked dependency install, pytest, and Ruff checks on pushes and pull requests
- `data/README.md` — provisioning notes for the non-redistributed SWAZ boundary and large AWRA-L calibration baseline
- tracked data-source and Folium regression tests that had previously been hidden by `.gitignore`
- positional raster-band regression coverage for non-sequential band labels

### Verified

- `uv lock --check` → lockfile current
- `uv sync --frozen --group dev` → clean locked dependency sync
- `uv run pytest -q` → `16 passed`
- `uv run ruff check` → `All checks passed!`

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
