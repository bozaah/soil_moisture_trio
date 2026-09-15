# 2026-09-11 — Input contracts, builder verification and smaller entry docs

Rodrigo approved tightening in this order: operational input contracts, builder orchestration tests, then documentation/configuration duplication. Starting commit: `f1ba7aa`, clean `dev`, one ahead of locally recorded `origin/dev`. No live source downloads or SWAZ artifact build.

## Input changes

Operational inputs now require a common complete daily window within the retrieval year. NetCDF dates must be unique, ordered daily midnights. Missing days fail, and any missing/nonfinite daily value invalidates that cell rather than producing a mean over fewer days. Metadata must match, not describe the union of different windows.

AWRA-L requires the pinned product's `units="relative"` and daily percentile values in `[0, 1]`, or NaN for missing data. Removed magnitude-based percent conversion. The local 2025 canonical input confirms the units attribute. Checks occur before averaging, so one outlier cannot be hidden by the mean or rescale other cells.

The pinned `weather_tools` stack reader silently omits failed files. The wrapper now requests file paths, verifies each expected date/variable filename, and reads every day without suppressing errors. Daily grids must agree. COG retrieval remains the default, but failures no longer switch automatically to NetCDF. The explicit NetCDF path checks its own coordinates against AWRA-L before combining arrays. Operational variables must be exactly `max_temp` and `vp_deficit`, not the old `vp` alias.

Cache identity now includes exact bounds, buffer and overview because cached files are already clipped/resampled. Old bbox-only entries are not reused. Existing cache pruning still applies. The unused local-raster/first-band compatibility branch was removed, not replaced with another fallback.

The risk formula, weights and category thresholds are unchanged. Complete-cell means retain source precision. Historical results have not been regenerated: runs that previously averaged incomplete inputs may now fail or exclude more cells.

## Builder verification

New tests drive `scripts/slga_build_swaz_artifact.py:main()` through timeout, source interruption and publication interruption, then resume. They exercise real checkpoint files, identity rejection, assembly, immutable NetCDF/sidecar/build-report publication, runtime loading and cleanup. Resumed numerical outputs must equal an uninterrupted synthetic build. Source retrieval and the footprint are synthetic, so this is not a whole-SWAZ resource or live-service test.

The first test run exposed a startup defect: `importlib.metadata.version("soil-moisture-trio")` failed under the documented source-only uv environment. The builder now reads the tracked project version from `pyproject.toml`. Checkpoint identity still binds to the entire clean commit. No artifact-schema, soil-algorithm or release-gate change.

## Simplification

`run_pipeline` now takes one validated `ClassifierConfig` plus separate output options. Existing CLI flag names remain. CLI tests check defaults, explicit loader selection, every parameter mapping and invalid configuration before loading. Direct Python callers must adopt the config-object signature.

README and AGENTS point to task-specific docs instead of repeating configuration tables, commands and session indexes. The backlog holds open work and links to contracts/history instead of duplicating pilot measurements. The evidence review and historical session records remain. Tests bound AGENTS/backlog word counts and check active local Markdown links.

## Verification

- `uv run --frozen pytest -q`: 166 passed, 1 authenticated SLGA test skipped, 2.90 seconds.
- `uv run --frozen ruff check` and `git diff --check`: passed. Both operational and builder CLI help commands ran successfully.
- Complete NetCDF means match the previous xarray averaging precision for float32/float64 across all three variables. A fixed reference checks default risk categories. A local-raster test exercises the pinned `weather_tools.read_cog` implementation, including nodata, without network access.
- The risk module and entire SLGA library have no diff. Only the builder entrypoint's version lookup changed on the soil side.
- The operational entrypoint/config/loader/pipeline total shrank from 942 to 666 lines. README + AGENTS + backlog shrank from 4,308 to 1,473 words. Historical evidence and the soil evidence review were not rewritten.
- Independent review attempted with configured Codex `gpt-5.6-sol`, high effort, read-only. It timed out after 240 seconds without a report. It is not counted as verification and was not retried.

No claim of live-data readiness or independent scientific validation follows from these tests. Commit the completed work before attempting the clean-worktree review builder, and retain that commit through any resume.
