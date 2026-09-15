# Session — 2026-08-14: B25b profiling instrumentation

## Goal

Implement the smallest credential-safe instrumentation increment needed before a larger representative SWAZ coastal/nodata pilot. Do not contact TERN or build an artifact.

## Assumptions and validity conditions

- A logical source read is one builder request for one approved layer/window. It is not equivalent to a COG `dataset.read()`, an HTTP request, a GDAL range request, or transferred bytes.
- A COG window-fetch attempt is one invocation of Rasterio `dataset.read()` by this reader. A completed fetch means that call returned; it still does not reveal the number or size of GDAL HTTP range requests.
- Reader metrics are cumulative for one `AuthenticatedCogReader`. A tiled build therefore records before/after snapshots and build-local deltas for monotonic counters.
- Cache peak bytes means the maximum retained NumPy window-cache bytes after LRU eviction, not total Python/GDAL memory.
- Per-tile elapsed time covers source retrieval/integration and fractional-overlap harmonisation for each successfully completed tile. A tile that raises before completion has no completed-tile metric.
- `ru_maxrss` is a process-lifetime high-water mark, not a clean build-only allocation measurement. It is converted to bytes only on platforms with a known Python/resource contract: bytes on macOS and KiB×1024 on Linux. Unknown platforms retain the raw value and report byte conversion unavailable.
- Actual HTTP transferred bytes remain unavailable unless GDAL exposes reliable telemetry or an external measurement is introduced. The diagnostic JSON must use `null` plus an explanation rather than an estimate.

## Implementation

### Reader metrics

`src/soil_moisture_trio/slga/cog.py` now exposes a frozen, credential-free `ReaderMetrics` snapshot containing:

- STAC request attempts, successes, retryable failures, terminal failures, exhausted outcomes, and catalogue-validation failures;
- COG access attempts, successes, retryable failures, terminal failures, and exhausted outcomes;
- attempted and completed Rasterio `dataset.read()` window fetches;
- cache hits, misses, evictions, entry count, current retained bytes, and peak retained bytes.

Retry counters are updated on the same control-flow paths that determine retry, terminal failure, or exhaustion. Exceptions continue to suppress low-level GDAL text that could contain scoped environment details.

### Build and tile metrics

`src/soil_moisture_trio/slga/tiling.py` records, through an optional callback, each completed tile’s:

- processing-order index;
- target row/column half-open extents;
- bounded source window;
- elapsed seconds from a monotonic clock.

`src/soil_moisture_trio/slga/builder.py` records reader snapshots before and after each build, computes build-local deltas for monotonic counters, and returns the ordered tile metrics with the artifact data. Existing cumulative convenience fields remain available for compatibility, while the pilot uses build-local deltas.

### Pilot output

`scripts/slga_tiled_pilot.py` now writes:

- before/after reader snapshots and build-local counter deltas;
- cache eviction and peak-retained-byte evidence;
- COG window-fetch attempts separately from completed fetches;
- per-tile elapsed/extent metrics for the primary and optional opposite-order builds;
- process peak RSS with raw units, normalised bytes where defensible, and explicit process-lifetime scope;
- `http_transfer_bytes: null` with an explicit unavailable explanation.

No credential values, authorization headers, or credential-bearing exception text are included.

## Tests

New or expanded deterministic mocked tests cover:

- STAC retry then success;
- exhausted STAC retries;
- COG access retry followed by one attempted/completed window fetch;
- cache hits, misses, LRU eviction, current bytes, and peak retained bytes;
- stable per-tile elapsed values under a mocked monotonic clock;
- build before/after snapshots and local deltas;
- macOS, Linux, unknown-platform, and invalid peak-RSS normalization.

Verification:

```text
uv lock --check                 -> succeeds
uv run pytest -q                -> 81 passed, 1 skipped
uv run ruff check .             -> All checks passed
focused ruff format --check     -> 9 files already formatted
git diff --check                -> passes
changed Markdown links          -> resolve
```

Repository-wide formatting was not changed; the known unrelated baseline remains outside this focused work.

## Scope preserved

- No authenticated SLGA request or pilot was run.
- No static artifact was built.
- The first artifact remains the approved 156×186 (29,016-cell) SWAZ rectangle; no full-WA static artifact will be built in this phase.
- Risk formula, thresholds, `risk_valid_mask`, `risk_map`, `stress_index`, summaries, and invalid-cell behavior remain unchanged.

## Next decision required

Before a live pilot, approve:

1. the exact representative SWAZ coastal/nodata coordinate footprint;
2. target-cell safety limit;
3. target tile shape;
4. cache budget;
5. maximum acceptable live runtime and whether to perform warm-cache opposite-order verification.

The approved Albany live pilot was subsequently completed and is recorded in [`2026-08-14-phase5-slga-albany-coastal-pilot.md`](2026-08-14-phase5-slga-albany-coastal-pilot.md). It distinguished measured values from extrapolation and did not infer HTTP bytes from logical reads or Rasterio window-fetch counts.
