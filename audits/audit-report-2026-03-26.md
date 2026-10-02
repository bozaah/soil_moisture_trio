# Audit Report - 2026-03-26

## Assumptions
- Scientific methodology and threshold rationale are treated as accepted unless code behavior diverges from the documented model or output contract.
- This audit is based on static review plus targeted local verification; it does not validate live end-to-end remote data retrieval beyond the observed pytest collection failure against NCI THREDDS.
- Existing backlog items are not assumed harmless; they are only treated as verified findings here when supported by current code or runtime evidence.

## Scope
- In scope:
  - `main.py`
  - `src/soil_moisture_trio/`
  - `tests/`
  - `pyproject.toml`
  - Repo docs where they define operational behavior or public output semantics
- Out of scope:
  - Re-calibration of scientific thresholds
  - Full live-data operational run across THREDDS/SILO
  - Performance profiling on production-scale WA workloads

## Verification Status
- Static review of core runtime modules, CLI, tests, selected docs, and packaging metadata.
- Verified command: `uv run pytest -q` fails during test collection.
- Verified command: `uv run pytest tests/test_pipeline.py tests/test_data_sources.py -q` passes (`11 passed, 1 warning in 1.41s`).
- Verified minimal Folium reproduction: a `3x3` risk grid renders only `4` rectangles, confirming the interactive map currently drops the outer row and column.

## Findings
### High
- **Pytest collection is broken by a networked diagnostic script under `tests/`** (Area: Bug/Robustness)
  - Evidence:
    - [`tests/test_moisture_ranges.py`#L1](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/tests/test_moisture_ranges.py#L1) contains top-level executable code, opens a remote THREDDS URL, prints, and calls `sys.exit()`.
    - Verified `uv run pytest -q` fails with `SystemExit: 2` after an NCI authorization failure during collection.
    - [`docs/backlog.md`#L31](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/docs/backlog.md#L31) already tracks this as B12.
  - Impact:
    - The default test command is not reliable in CI or local development.
    - Collection can fail before any real tests run, masking regressions in runtime code.
  - Conditions/Works when:
    - Works only when this file is excluded from pytest collection or run manually as a script.
  - Non-happy-path cases:
    - Offline development, transient THREDDS auth issues, or any collection environment without remote access causes an immediate failure.
  - Verification status:
    - Static review plus observed runtime failure.
  - Recommendation:
    - Move this file out of `tests/` into `scripts/` or `tools/`, or guard it behind `if __name__ == "__main__":` and remove `sys.exit()` from import time.

### Medium
- **Interactive Folium map omits the last latitude row and longitude column** (Area: Bug/UI-UX)
  - Evidence:
    - [`src/soil_moisture_trio/visualize.py`#L58](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/visualize.py#L58) iterates `range(len(lats) - 1)` and `range(len(lons) - 1)`, while the rest of the pipeline treats `lats`/`lons` as cell-center coordinates.
    - The same function also requires `risk_map.shape == (len(lats), len(lons))` at [`src/soil_moisture_trio/visualize.py`#L50](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/visualize.py#L50), confirming the coordinates are not grid edges.
    - Verified reproduction: a `3x3` grid produced only `4` `L.rectangle(...)` objects in the generated HTML.
  - Impact:
    - The optional HTML map under-reports affected area and can mislead operational users at the domain boundary.
  - Conditions/Works when:
    - Only works accidentally for degenerate cases where omitted edge cells are not important.
  - Non-happy-path cases:
    - Any boundary-masked or regional run loses the easternmost and northern/southern outer cells from the displayed product.
  - Verification status:
    - Static review plus targeted runtime reproduction.
  - Recommendation:
    - Derive rectangle bounds from cell centers, including inferred outer edges, or switch to an image/raster overlay approach that uses the full grid.

- **Public risk-summary contract has drifted across runtime, visualization, and tests** (Area: Bug/UI-UX)
  - Evidence:
    - Runtime summary emits `low/watch/alert/critical` from [`src/soil_moisture_trio/risk.py`#L131](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/risk.py#L131).
    - The interactive summary panel still looks for `elevated` instead of `alert` at [`src/soil_moisture_trio/visualize.py`#L12](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/visualize.py#L12), so Alert is omitted from the HTML summary.
    - `RiskLevel.CRITICAL` is labeled `"High"` in [`src/soil_moisture_trio/risk.py`#L26](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/risk.py#L26), while README, bulletin template, and docs present the public label as `Critical`.
    - [`tests/test_pipeline.py`#L190](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/tests/test_pipeline.py#L190) still uses legacy labels and an `elevated` key in its fixture, so tests do not protect the current public contract.
  - Impact:
    - User-facing outputs are internally inconsistent, and test fixtures normalize stale semantics instead of catching them.
  - Conditions/Works when:
    - Works only if downstream consumers ignore labels and rely purely on integer codes.
  - Non-happy-path cases:
    - HTML products and copied summary payloads can silently omit Alert or present mismatched terminology.
  - Verification status:
    - Static review.
  - Recommendation:
    - Define one canonical output schema for labels/keys, update all emitters and consumers to that schema, and add tests that assert the exact summary keys and labels.

- **NetCDF band slicing fallback is still fragile on raster-backed time windows** (Area: Bug/Robustness)
  - Evidence:
    - [`src/soil_moisture_trio/pipeline.py`#L164](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/pipeline.py#L164) builds `slice(band_values[start_idx], band_values[stop_idx - 1])` and selects by band coordinate instead of stable positional indexing.
    - [`docs/backlog.md`#L23](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/docs/backlog.md#L23) already flags this as B8.
  - Impact:
    - If band coordinates are non-sequential or not aligned with positional time indices, the fallback path can select the wrong bands or an empty span.
  - Conditions/Works when:
    - Works when raster `band` coordinates happen to be sequential and aligned with the external metadata dataset.
  - Non-happy-path cases:
    - Alternate COG layouts or nontrivial band coordinate values can corrupt time averaging without an obvious error.
  - Verification status:
    - Static review only.
  - Recommendation:
    - Use positional slicing with `isel(band=slice(start_idx, stop_idx))`, and add a regression test for non-identity band coordinates.

### Low
- **Production paths still use `print()` for operational status and warnings** (Area: Robustness/Maintainability)
  - Evidence:
    - `print()` remains in [`src/soil_moisture_trio/pipeline.py`#L24](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/pipeline.py#L24), [`src/soil_moisture_trio/plot.py`#L180](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/plot.py#L180), [`src/soil_moisture_trio/visualize.py`#L82](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/visualize.py#L82), [`main.py`#L81](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/main.py#L81), and [`scripts/render_bulletin.py`#L59](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/scripts/render_bulletin.py#L59).
    - [`src/soil_moisture_trio/data_sources.py`#L15](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/data_sources.py#L15) already defines a module logger, but the pipeline stack does not use the same pattern.
  - Impact:
    - Harder to control verbosity, route logs in CI, or preserve structured operational traces.
  - Conditions/Works when:
    - Works for ad hoc CLI use where stdout is the only observer.
  - Non-happy-path cases:
    - Mixed stdout output complicates automation, batch runs, and future service integration.
  - Verification status:
    - Static review.
  - Recommendation:
    - Standardize on module loggers and reserve stdout for explicit user-requested report output only.

- **Package metadata and some compatibility shims still look transitional rather than production-owned** (Area: Maintainability/Slop Cleanup)
  - Evidence:
    - [`pyproject.toml`#L4](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/pyproject.toml#L4) still uses the placeholder description `"Add your description here"`.
    - [`src/soil_moisture_trio/plot.py`#L39](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/plot.py#L39) contains a legacy positional-signature shim without tests that justify keeping the extra branch.
    - [`docs/technical_report.md`#L247](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/docs/technical_report.md#L247) documents multiple orphaned config fields retained from older classifier behavior.
  - Impact:
    - Increases the chance of future confusion, weakens ownership signals, and leaves stale branches that are unlikely to be exercised intentionally.
  - Conditions/Works when:
    - Harmless while the code remains developer-operated and downstream callers are tightly controlled.
  - Non-happy-path cases:
    - New contributors or automation may mistake stale compatibility code and placeholder metadata for supported surface area.
  - Verification status:
    - Static review.
  - Recommendation:
    - Remove or explicitly deprecate legacy branches, replace placeholder metadata, and either delete or clearly quarantine unused config surface.

## UI/UX Opportunities
- Make HTML summary ordering and labels match the Markdown bulletin and JSON summary exactly so operators are not reconciling multiple vocabularies.
- Add a lightweight golden-file or structural HTML test for the Folium output so optional visualization regressions are caught automatically.

## Unverified / Needs Follow-up
- Bounding-box cache contamination (B22) appears to remain a real operational risk but was not re-executed during this audit.
- Seasonal threshold calibration (B23) is scientifically important but outside this code-quality-focused pass.
- The `numpy.ndarray size changed` warning seen during targeted pytest likely reflects an environment/binary compatibility issue, but I did not isolate it further.

## Next Steps
- 1. Remove or relocate `tests/test_moisture_ranges.py` so `uv run pytest -q` becomes a valid default gate.
- 2. Fix the Folium renderer to consume full-grid cell centers correctly and add a regression test that counts rendered cells for a small known grid.
- 3. Normalize summary keys and labels across `risk.py`, `visualize.py`, tests, bulletin content, and docs; add explicit contract assertions.
- 4. Replace `print()` with `logging` through the pipeline/plot/CLI path and define a single logging policy for command-line runs.
- 5. Clean up low-signal transitional residue: placeholder package metadata, unsupported legacy compatibility branches, and unused config surface that no longer reflects the production model.
