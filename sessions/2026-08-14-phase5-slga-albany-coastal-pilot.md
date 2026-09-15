# Session — 2026-08-14: authenticated Albany coastal/nodata profiling pilot

## Goal

Use the new credential-safe instrumentation on one user-approved representative SWAZ coastal/nodata window. Preserve explicit safety limits, do not write a static artifact, and do not generalise beyond measured conditions.

## User-approved run contract

```text
footprint:       Albany coast
latitude:        −34.90 through −35.10, descending
longitude:       117.80 through 118.00, ascending
target cells:    5×5 = 25
target tile:     5×5 (one tile)
cache budget:    256 MiB
external limit:  10 minutes
warm repeat:     yes
```

The single-tile choice deliberately minimised logical reads. It cannot test cross-tile seams or meaningful tile order. The requested “opposite order” warm repeat processes the same single tile; it remains useful for cache-only exact-equality verification but is not additional order evidence.

`TERN_API_KEY` was read only from the environment by `AuthenticatedCogReader`. It was not printed, logged, persisted, included in URLs/cache keys, or written to the diagnostic output.

## Invocation

```bash
uv run python -m scripts.slga_tiled_pilot \
  --awral-grid-input data/source_inputs/sm_pct_2025.nc \
  --latitude-first -34.90 \
  --latitude-last -35.10 \
  --longitude-first 117.80 \
  --longitude-last 118.00 \
  --tile-rows 5 \
  --tile-cols 5 \
  --cache-mb 256 \
  --max-target-cells 25 \
  --verify-opposite-order \
  --output-json outputs/slga_b25b_albany_coastal_5x5_profiled.json
```

The coding harness enforced a 600-second external timeout. The diagnostic JSON is excluded from Git.

## Observed cold-pass metrics

| Metric | Observed |
|---|---:|
| elapsed | 37.6739 s |
| completed tiles | 1 |
| logical layer/window reads | 18 |
| STAC attempts / successes | 18 / 18 |
| COG access attempts / successes | 18 / 18 |
| Rasterio window-fetch attempts / completed | 18 / 18 |
| retryable / terminal / exhausted failures | 0 / 0 / 0 |
| cache misses / hits / evictions | 18 / 0 / 0 |
| retained and peak source cache | 37,748,736 bytes (36 MiB) |
| process-lifetime peak RSS | 302,039,040 bytes (~288 MiB, macOS) |
| instrumented source window | rows 29,848:30,151; columns 5,729:6,032 |
| actual HTTP transferred bytes | unavailable |

The source-window metric is the unaligned bounded window supplied by tiling. Cache bytes show the retained block-aligned NumPy arrays; they are not HTTP byte counts or total GDAL memory.

## Coastal/nodata behavior

All seven storage cases had identical coverage-summary ranges:

```text
coverage minimum: 0.0
coverage maximum: 1.0
coverage mean:    0.6477091068
```

Each storage case was finite in 24 of 25 target cells. The zero-coverage cell remained `NaN` for storage while coverage remained explicitly 0. Partial coverage was retained against the full target-cell denominator and was not interpolated or silently relabelled as complete support.

Observed expected-value storage among the 24 finite cells:

```text
minimum: 68.1289 mm
mean:    106.0134 mm
maximum: 123.3016 mm
```

These are modelled capacity values for this bounded window, not current water storage, paddock PAWC, or a SWAZ distribution estimate.

## Warm-cache repeat

```text
elapsed:                  4.1495 s
cache hits:               18
cache misses/evictions:   0 / 0
STAC requests:            0
COG accesses/fetches:     0 / 0
artifact arrays:          exactly equal
```

This verifies cache-only repeatability for the same single source window. It does not add multi-tile seam or order evidence.

## User-approved multi-tile comparison

The user then approved the same 25 cells with 2×2 target tiles, producing nine disjoint tiles, retaining the 256 MiB cache and 10-minute limit, and enabling a meaningful reverse-order check.

```text
cold elapsed:             41.6871 s
completed tiles:          9
logical reads:            162
cache hits/misses:        54 / 108
COG access attempts:      108
window fetches:           108
STAC requests:            18
retry/failure outcomes:   0
cache evictions:          0
retained/peak cache:      113,246,208 bytes (108 MiB)
process peak RSS:         321,241,088 bytes (~306 MiB)
warm reverse elapsed:     4.0373 s
warm cache hits:          162
warm source access:       0
reverse-order arrays:     exactly equal
```

Coverage and storage summaries matched the single-tile run. This supplies real coastal seam/order evidence and demonstrates that the 256 MiB cache held the measured nine-tile working set without eviction. The ninefold increase in logical reads (18 to 162) and sixfold increase in cold COG fetches (18 to 108) show that 2×2 target tiles are too fine to adopt as a production recommendation without broader profiling, even though observed cold elapsed time rose by only about four seconds between these two separate runs.

Output: `outputs/slga_b25b_albany_coastal_5x5_multitile_2x2_profiled.json` (ignored by Git).

## User-approved 100-cell tile-size comparison

The user approved a larger Albany coastal window with 100 target cells (latitude −34.65…−35.10, longitude 117.55…118.00), first as four 5×5 tiles and then as one 10×10 tile. Both used a 256 MiB cache, 100-cell cap, 15-minute limit, and warm verification.

| Metric | Four 5×5 tiles | One 10×10 tile |
|---|---:|---:|
| cold elapsed | 57.9496 s | 56.0909 s |
| logical reads/fetches | 72 | 18 |
| STAC requests | 18 | 18 |
| retries/failures/evictions | 0 | 0 |
| peak cache | 150,994,944 B (144 MiB) | 84,934,656 B (81 MiB) |
| process peak RSS | 421,855,232 B (~402 MiB) | 557,514,752 B (~532 MiB) |
| warm elapsed | 16.5842 s | 16.6836 s |
| warm source access | 0 | 0 |
| warm equality | exact | exact |

Both runs had identical storage and coverage summaries: all seven cases were finite in 97/100 cells; coverage ranged 0–1 with mean 0.8525609695. Actual HTTP bytes remained unavailable.

The 10×10 tile reduced source reads fourfold and retained cache by 63 MiB while completing about 1.86 seconds faster. Its cost was about 130 MiB greater measured process peak RSS, caused by retaining and processing a larger integrated source window. Under these measured conditions, that trade-off favors 10×10 target tiles on a machine with a conservative memory allowance above the observed ~532 MiB high-water mark.

Outputs (ignored by Git):

- `outputs/slga_b25b_albany_coastal_10x10_tiles_5x5_profiled.json`
- `outputs/slga_b25b_albany_coastal_10x10_single_tile_profiled.json`

## Interpretation and limits

The Albany run series successfully exercised coastal zero/partial source support, all 18 pinned sources, all seven storage cases, the new retry/cache/tile/RSS metrics, multi-tile seam/order invariance, and exact warm-cache equality. It supports 10×10 target tiles and a 256 MiB cache as the provisional SWAZ production candidate under measured conditions.

It does **not** establish:

- whole-SWAZ cache reuse, eviction behavior, runtime, or peak memory;
- GDAL HTTP range-request count or transferred bytes;
- SWAZ-wide source completeness or scientific fitness;
- an approved artifact, coverage threshold, soil band, or operational summary.

A linear sample-to-29,016-cell runtime extrapolation would be misleading because remote-source latency, exact-window reuse, cache eviction, and geometry work do not scale linearly. The exact SWAZ footprint partitions into 16×19 = 304 target tiles at 10×10, implying 5,472 logical layer-window reads before exact-window reuse. This is a deterministic work count, not a runtime or HTTP-transfer estimate.

## Recommendation

Use 10×10 target tiles and a 256 MiB reader cache as the provisional SWAZ build setting. Plan for a process memory allowance comfortably above the measured ~532 MiB high-water mark; at least 1 GiB is a prudent operational floor, not a measured requirement. Add explicit whole-build elapsed limits and failure/restart behavior before starting the long SWAZ build.

Do not build the 29,016-cell SWAZ artifact until final schema/DES presentation review, distribution/version promotion, and failure/restart decisions are complete.
