# B25b SLGA-to-AWRA-L builder contract

Status: implemented prototype contract for review. Canonical-grid validation, the provisional artifact writer/runtime loader, and bounded target-cell tiling are implemented and tested on local synthetic/small-window data. This contract does **not** approve the planned SWAZ artifact, soil-stratification bands, or operational integration. A full-WA static artifact is not planned for this phase.

## 1. Scope and invariants

The explicit builder derives static soil-context layers from the 18 sources pinned in `manifests/slga_awc_des_sources_v1.json`. It may run only when every requested source matches that manifest. It must never discover a shorthand product, substitute a version, or upgrade a source.

The builder and runtime soil loader are separate from drought-risk calculation. They must not change `risk_valid_mask`, `risk_map` (`-1` for invalid cells), `stress_index` (`NaN` for invalid cells), risk thresholds, weights, or existing summaries. Operational code reads an approved immutable artifact; it never fetches or rebuilds SLGA data.

Release 1 inputs are:

- AWC v2 EV/05/95 at 0–5, 5–15, 15–30, 30–60, and 60–100 cm;
- DES v2 EV/10/90 at 0–200 cm.

DES means mapped A- and B-horizon depth, not effective rooting depth. Derived storage is modelled capacity context, not current water storage, crop-specific PAWC, or independent validation of AWRA-L.

## 2. Module boundaries

The narrow project-owned package is split by responsibility:

- `slga.catalogue`: load and strictly validate the tracked manifest; catalogue keys are full product IDs only.
- `slga.cog`: authenticate, validate STAC/COG identity and profile, calculate an expanded pixel window, and return masked native-grid values plus provenance. It performs no depth integration or resampling.
- `slga.integration`: validate common native grids and lower/EV/upper ordering, then calculate DES-capped storage cases on that grid.
- `slga.harmonise`: construct target-cell edges and perform fractional-overlap area aggregation in EPSG:3577.
- `slga.artifact`: write a versioned NetCDF and deterministic sidecar manifest; load only exact canonical-coordinate subsets.
- An explicit builder entry point may orchestrate these modules. The normal drought pipeline must not call source retrieval or build functions.

Default unit tests mock network access. Any authenticated live probe is opt-in and window-limited.

## 3. Source identity, authentication, and drift

`TERN_API_KEY` is the only credential source. HTTP Basic authentication uses username `apikey` and the environment value as password. Credentials must remain inside a scoped request/GDAL environment and must not occur in URLs, manifests, cache keys, logs, exception text, or test fixtures. A missing or empty key fails before network access.

For each source, validate the pinned URL and STAC item ID, product/version/DOI contract, component, depth, published STAC multihash, file size, COG driver/count/dtype, CRS, transform, shape, units, nodata, and `AREA_OR_POINT=Area`. Manifest/COG transform and bounds values use absolute tolerance `1e-12°`; the published STAC `bbox`, which is serialized at 7 decimal places, uses absolute tolerance `5e-8°`. A mismatch fails; no fallback source is attempted.

Only these upstream exceptions are allowed:

1. AWC STAC may omit nodata while the COG must report `65535`.
2. A DES COG band description may contain the corresponding stale `NAT` ID while its filename and STAC item ID must match the pinned `TRN` ID.

Any broader missing field or mismatch is an error. Published STAC multihashes are recorded as publisher metadata; they are not represented as independently verified full-object hashes.

Authenticated access uses bounded attempts (default 3) with deterministic backoff delays of 0.5 and 1.0 seconds for retryable transport/server failures. Authentication/authorisation failures, 404, metadata mismatch, and malformed responses are not retried as alternate products.

## 4. Native COG windows and validity

Bounds are supplied in EPSG:4326 as `(west, south, east, north)` with finite values and strict west/east and south/north ordering. Non-overlap with the pinned source bounds fails clearly.

The geometric intersection is converted to a source pixel window and expanded by exactly one native pixel on each available side. The expansion supports later edge-overlap calculations; reads remain clamped to dataset bounds. Boundless reads and overview reads are forbidden for the deterministic build. Returned transforms describe the expanded full-resolution window.

AWC `65535` and DES `NaN` are converted to a boolean invalid mask and floating-point `NaN` values. Valid values must be finite and non-negative. Unexpected dtype, units, nodata, CRS, shape, transform, or grid alignment fails. Positive plausibility limits are warning-only pending pilot review; DES values above 1 m remain valid.

All 18 arrays used together must have identical full-resolution CRS, transform, shape, and read window. Partial source availability is not silently reduced to a smaller common window.

## 5. Native-grid depth integration

Nominal AWC layers have top/bottom depths in millimetres:

```text
0–50, 50–150, 150–300, 300–600, 600–1000
```

For a DES value `d` metres, represented depth is `D = min(d × 1000, 1000)` mm and represented thickness for layer `i` is:

```text
t_i = clip(D - layer_top_i, 0, layer_bottom_i - layer_top_i)
storage_mm = sum((AWC_i_percent / 100) * t_i)
```

DES must be finite and non-negative. DES greater than 1 m is valid and capped at 1 m. An AWC value is required only when its represented thickness is greater than zero. Required nodata produces output nodata; nodata wholly below the represented profile does not invalidate the result. A valid zero-depth DES produces zero represented storage.

The prototype exposes component effects separately before presenting mixed scenarios:

| Storage case | AWC component | DES component | Interpretation |
|---|---|---|---|
| `ev` | EV | EV | primary expected-value case |
| `awc05_des_ev` | 05 | EV | AWC-only lower component |
| `awc95_des_ev` | 95 | EV | AWC-only upper component |
| `awc_ev_des10` | EV | 10 | DES-only lower component |
| `awc_ev_des90` | EV | 90 | DES-only upper component |
| `mixed_lower_awc05_des10` | 05 | 10 | provisional mixed-quantile lower scenario |
| `mixed_upper_awc95_des90` | 95 | 90 | provisional mixed-quantile upper scenario |

The mixed width is upper minus lower and is an uncertainty-width proxy, not a confidence interval. For cells where all required inputs exist, AWC 05 ≤ EV ≤ 95 and DES 10 ≤ EV ≤ 90 are required. Derived lower ≤ EV ≤ upper is also required within absolute tolerance `1e-9` mm; violation fails.

## 6. Canonical AWRA-L grid

The canonical coordinates come from one explicitly supplied AWRA-L NetCDF input pinned in `manifests/awral_v7_grid_source_v1.json`: the completed 2025 Bureau of Meteorology AWRA-L v7 historical-v1 daily root-zone soil-moisture decile file hosted by NCI (`sm_pct_2025.nc`). The contract records the public FileServer and OPeNDAP URLs, collection/product/version, `latitude`/`longitude` coordinate names, 312,193,677-byte size, independently computed SHA-256 `353af96c7826111a54e189120ed6e1dcb6f9d2a1a0d6966c286aae4f4429095b`, coordinate attributes, dimensions, endpoints, orientation, and normalised float64 coordinate hashes. The remote annual object is not assumed immutable: only an explicit local byte copy matching the pinned filename, size, and SHA-256 is accepted. The builder never silently downloads it. The current local monthly WA subset remains non-authoritative because it lacks sufficient provenance metadata.

The Zenodo record cited in the evidence review corroborates the 681×841 coordinate grid but is not canonical: it is a third-party republication and its record metadata does not identify AWRA-L v7. The NCI source is the exact operational product lineage used by this project.

The approved initial artifact footprint is the inclusive exact canonical subset with latitude centres −27.45 through −35.20 in source-descending order and longitude centres 114.05 through 123.30 in source-ascending order: 156×186 = 29,016 cells. This rectangle contains the canonical cell centres within the approved SWAZ boundary’s +0.1° operational bbox, derived from its EPSG:4326 bounds west 114.10831281, south −35.13552459, east 123.24668541, and north −27.52350348. The boundary polygon is applied later as a runtime mask and does not alter static full-cell denominators. Selection is exact and contiguous; coordinate values are not rounded or tolerance-matched.

Coordinates are one-dimensional finite float64 cell centres. Latitude may arrive descending and longitude ascending; their original values and orientation are persisted. Each axis must be strictly monotonic, unique, and regularly spaced. Nominal spacing is 0.05° and is accepted only when every step is within absolute tolerance `1e-10°` of the median and the median is within `1e-10°` of 0.05°. No coordinate is rounded or regenerated.

Interior cell edges are adjacent-centre midpoints. Exterior edges are extrapolated by half the adjacent spacing. This requires at least two coordinates per axis. Cell polygons use these edges regardless of coordinate orientation.

Runtime loading accepts only a contiguous ordered subset of persisted coordinate values. Matching is exact after dtype conversion to float64 (`np.array_equal`); nearest-neighbour, tolerance matching, coordinate rounding, and re-harmonisation are forbidden. Missing, reordered, duplicated, or off-grid coordinates fail.

The pinned source and approved footprint remain review gates for final promotion, but their identities are now explicit and implemented. Synthetic coordinates may be used by the small-window prototype and tests.

## 7. Fractional-overlap harmonisation

Source pixel and target-cell footprints are transformed from EPSG:4326 to Australian Albers EPSG:3577 with `always_xy=True`. The pinned source spacing must not exceed `0.005°`. Before transformation, each target-cell edge is split at every native source-grid line it crosses; an endpoint within `1e-10°` of a source-grid line is snapped to that line. Source pixels retain their four native corners. Coincident source/target boundaries therefore use identical geographic vertices rather than independent approximations of the projected curve, while non-coincident target edges are still segmented at no more than native-pixel spacing. Invalid or non-positive-area geometries fail.

For each target cell, intersect all candidate source pixels in stable source row-major order. An overlap contributes only when its EPSG:3577 area exceeds `1e-6 m²`. Edge-touching zero-area intersections do not contribute. Areas and statistics are accumulated in float64.

For each mapped variable/case:

- `full_cell_area_m2` is the area of the complete target cell, independent of source validity and regional boundaries;
- `valid_source_area_m2` is the sum of source-pixel overlap area where that variable is valid;
- `source_coverage_fraction = valid_source_area_m2 / full_cell_area_m2`;
- mapped mean is `sum(area × value) / valid_source_area_m2`;
- mapped dispersion is the area-weighted population standard deviation, `sqrt(sum(area × (value - mean)^2) / valid_source_area_m2)`; it is exactly zero when all contributing mapped predictions are identical.

Coverage is variable-specific; common nodata footprints must not be assumed. Floating-point coverage values within `1e-12` of 0 or 1 are snapped to those bounds; values outside `[−1e-12, 1+1e-12]` fail. No minimum acceptable coverage threshold is invented. Zero overlap/zero valid area yields mean and dispersion `NaN`, valid area 0, and coverage 0. Partial coverage remains a reported value and is not renormalised to imply full-cell support.

Regional or coastal polygons do not change the static full-cell denominator. They are applied only by later grouped-summary logic.

The original overlap engine remains correctness-first and limited to small windows. `slga.tiling` partitions target cells into disjoint tiles, derives a one-native-pixel-halo source window for each tile, and delegates source loading through a bounded reader callback. Global source row/column offsets are carried into geometry construction so source vertices and target-edge splitting are identical regardless of tile boundaries. `slga.builder` supplies the callback by reading all 18 exact common-grid windows, integrating them natively, and returning the seven cases plus mixed width. `AuthenticatedCogReader` aligns reads to internal COG blocks and retains them in a bounded in-memory LRU cache. Tests prove exact numerical equality with the untiled engine across multiple tile shapes and forward/reverse tile processing, including variable-specific nodata and no-overlap windows. Each target cell is assigned once; source-pixel overlap fractions may legitimately contribute to adjacent target cells but are not duplicated within a target-cell accumulation.

A live 3×3 SWAZ pilot split into six 1×2 tiles issued 108 logical layer-window reads. The instrumented run required 72 COG window fetches and reused 36 cached windows, completed in 58.36 seconds (fresh-run range 44.66–71.02 seconds), retained ~84.9 MB of cache, and reported ~282 MB peak RSS on macOS. A reverse-order pass from the same cache used 108 cache hits, made no COG fetches, completed in 1.40 seconds, and every artifact array was exactly equal. This validates bounded orchestration and real-source tile-order invariance at tiny scale only.

A subsequent authenticated 5×5 Albany coastal/nodata pilot used one target tile and a 256 MiB cache. Its cold pass completed in 37.67 seconds with 18 logical reads, 18 successful STAC requests, 18 successful COG accesses, 18 attempted/completed COG window fetches, no retry/terminal/exhausted failures, no evictions, 36 MiB retained/peak source cache, and about 288 MiB process-lifetime peak RSS. Source coverage ranged from 0 to 1 (mean 0.6477), and 24 of 25 cells had finite storage for every case. A warm repeat was exactly equal in 4.15 seconds with 18 cache hits and no STAC/COG access. Because there was only one tile, reversing order repeated the same tile and supplied no new seam or order evidence. Actual HTTP transferred bytes remained unavailable.

A user-approved comparison reran the same 25 Albany cells as nine 2×2 tiles with the same 256 MiB cache. It completed cold in 41.69 seconds: 162 logical reads resolved to 54 cache hits and 108 successful COG accesses/window fetches, with 18 successful STAC requests, no retry/terminal/exhausted failures, no evictions, 108 MiB peak source cache, and about 306 MiB process-lifetime peak RSS. Reverse order was exactly equal and cache-only in 4.04 seconds with 162 hits and no source access. Coverage and storage summaries matched the single-tile run. This supplies real coastal seam/order evidence and shows that 256 MiB contains the measured nine-tile working set; it does not make 2×2 a production recommendation because logical reads increased ninefold.

The reader now exposes credential-free cumulative metrics that separately report STAC request attempts/successes/retryable/terminal/exhausted/validation failures; COG access attempts/successes/retryable/terminal/exhausted failures; attempted and completed `dataset.read()` window fetches; and cache hits, misses, evictions, current entries/bytes, and peak retained bytes. Each tiled build records reader snapshots before and after, counter deltas for that build, and elapsed time plus target/source extents for every completed tile. The pilot reports a process-lifetime peak-RSS high-water mark with explicit platform-unit conversion. Rasterio/GDAL still does not expose defensible HTTP transferred-byte counts through this instrumentation, so the pilot records transferred bytes as unavailable rather than estimating them. A final controlled Albany comparison expanded the footprint to 10×10 target cells. Four 5×5 tiles completed cold in 57.95 seconds with 72 logical reads/fetches, 144 MiB peak cache, and about 402 MiB peak RSS. One 10×10 tile completed cold in 56.09 seconds with 18 reads/fetches, 81 MiB peak cache, and about 532 MiB peak RSS. Both runs had no retries/failures/evictions, identical coverage/storage summaries (97/100 finite storage cells; coverage 0–1, mean 0.8526), and exact cache-only warm repeats in about 16.6 seconds. On this evidence, 10×10 target tiles with a 256 MiB cache are the provisional SWAZ production candidate: source reads fell fourfold and cache retention fell 63 MiB, while measured peak process memory increased by about 130 MiB.

The candidate is valid only under the measured Albany conditions. The 156×186 SWAZ footprint partitions into 16×19 = 304 such tiles, or 5,472 logical layer-window reads before any exact-window cache reuse. That count is deterministic; runtime and HTTP transfer are not. No linear runtime extrapolation is accepted as a production forecast.

The user approved a resumable production command using 10-row stripes across all 186 columns; each stripe contains 10×10 target tiles and the final stripe contains six rows. Each completed stripe is serialized into a new atomic directory containing compressed arrays and a JSON manifest with SHA-256, exact coordinates, grid/source/artifact contract hashes, code identity, tile/cache settings, source retrieval timestamps, and reader/tile metrics. Checkpoints contain no credentials. Resume accepts only exact identity/checksum matches and rejects drift, gaps, unexpected files, or corrupt arrays. A default six-hour work limit is checked between stripes; completed stripes survive timeout/failure. Exact stripe assembly must reconcile all canonical coordinates before immutable bundle writing. The build requires a clean Git worktree, publishes a checksummed build report inside the bundle, and removes checkpoints only after verified publication unless retention is requested. No SWAZ-wide runtime extrapolation is accepted from either small pilot.

## 8. Artifact schema and deterministic writing

`slga.artifact` implements the reviewed v1 candidate schema with atomic temporary writes, close-then-validate, compression/chunking, complete embedded source/grid contract JSON, post-close SHA-256, and deterministic sidecar JSON. It has been exercised with deterministic synthetic artifacts; no approved production artifact exists.

Immutable bundle layout:

```text
data/processed/slga_awral/slga_awc_des_awral_swaz_0p05deg_v1/
  slga_awc_des_awral_swaz_0p05deg_v1.nc
  slga_awc_des_awral_swaz_0p05deg_v1.manifest.json
```

Dimensions are `latitude`, `longitude`, `storage_case` (the seven ordered labels in Section 5), and `des_component` (`EV`, `10`, `90`). Variables are:

- `awc_storage_capacity_mm(storage_case, latitude, longitude)` — float32, `NaN` nodata;
- `mapped_prediction_sd_mm(storage_case, latitude, longitude)` — float32, `NaN` nodata;
- `valid_source_area_m2(storage_case, latitude, longitude)` — float64;
- `source_coverage_fraction(storage_case, latitude, longitude)` — float32;
- `full_cell_area_m2(latitude, longitude)` — float64;
- `mixed_uncertainty_width_mm(latitude, longitude)` — float32, `NaN` nodata;
- `mixed_uncertainty_width_mapped_prediction_sd_mm(latitude, longitude)` — float32, `NaN` nodata;
- `mixed_uncertainty_width_valid_source_area_m2(latitude, longitude)` — float64;
- `mixed_uncertainty_width_source_coverage_fraction(latitude, longitude)` — float32;
- `depth_of_soil_m(des_component, latitude, longitude)` — float32, `NaN` nodata;
- `depth_of_soil_mapped_prediction_sd_m(des_component, latitude, longitude)` — float32, `NaN` nodata;
- `depth_of_soil_valid_source_area_m2(des_component, latitude, longitude)` — float64;
- `depth_of_soil_source_coverage_fraction(des_component, latitude, longitude)` — float32;
- `depth_of_soil_shallower_than_1m_fraction(des_component, latitude, longitude)` — float32, `NaN` nodata, with valid DES area as denominator.

The direct DES fields are mapped A- and B-horizon depth context, not effective rooting depth. The mixed width retains its own intersection support. Canonical machine-readable storage-case definitions record each AWC/DES component and interpretation. These additions do not change risk outputs. The user chose to retain version label `v1`; implementation does not itself constitute release approval.

NetCDF data variables use zlib compression level 4 with shuffle enabled. Variables with `storage_case` or `des_component` use chunks `(1, 64, 64)`; two-dimensional grid variables use `(64, 64)`, truncated at array edges. Coordinates remain float64 and uncompressed. Fill values are explicit (`NaN` for floating mapped values; no sentinel is shared with risk output). Global metadata includes contract/artifact versions, creation timestamp in UTC, canonical-grid provenance, EPSG codes, formula, tolerances, ordered cases, source-manifest ID and SHA-256, each source record, publisher multihashes, licences/citations, and scientific limitations. The artifact contains no risk variables.

Deterministic checksums are calculated only after closing files. The sidecar JSON is UTF-8, sorted by key, indented by two spaces, terminated by one newline, and records artifact filename, byte size, SHA-256, builder version/commit, contract version, canonical-grid identity/SHA-256, source-manifest identity/SHA-256, and source retrieval timestamps. Its own checksum is not recursively embedded.

Byte-identical NetCDF output across library/platform versions is not promised. Reproducibility acceptance requires equal schema/metadata (excluding declared creation/retrieval timestamps), exact masks/coordinates/areas where specified, and numerical equality within the contract tolerances; each produced byte stream receives its actual SHA-256.

Low-level writes now fail if either final file already exists. `write_soil_artifact_bundle()` writes and verifies both files in a new staging directory, validates the sidecar against the closed NetCDF and tracked contracts, then renames the complete directory to a new fail-if-present immutable bundle path on the same filesystem. Failed staging or promotion is cleaned without touching any prior bundle. Rollback selects a prior immutable bundle; it never overwrites that bundle.

## 9. Runtime loader contract

The credential-free `slga.artifact.load_soil_artifact()` implementation:

1. requires an explicit approved artifact path and sidecar;
2. verifies artifact version, filename, size, SHA-256, schema, source-manifest identity, and required metadata before returning data;
3. returns only exact contiguous coordinate subsets as defined in Section 6;
4. exposes soil values and coverage separately from the risk mask;
5. fails clearly if the artifact is absent, corrupt, incompatible, or does not cover the requested coordinates.

It never downloads SLGA/AWRA-L data, rebuilds an artifact, substitutes a file, or changes risk cells.

## 10. Explicit failure behaviour

The prototype fails rather than guessing on:

- missing/empty credentials or authentication/authorisation failure;
- source 404, non-range-capable/unreadable COG, malformed STAC JSON, or exhausted retry budget;
- unknown/full-ID mismatch, duplicate catalogue record, source version/DOI/component/depth/checksum/size mismatch;
- any metadata discrepancy except the two narrow documented upstream exceptions;
- malformed/non-finite bounds, non-overlap, unexpected CRS/grid/window alignment, or mixed native grids;
- malformed dtype/units/nodata; negative valid AWC/DES; non-finite valid values;
- lower/EV/upper ordering failure;
- malformed target coordinates, unsupported spacing, invalid geometry/area, or coverage outside tolerance;
- output schema/checksum mismatch or non-exact runtime coordinates.

Source nodata, target-cell partial coverage, and zero valid overlap are expected data states represented as documented; they are not converted to invented values. Scientifically unusual positive values emit warnings but are not rejected pending pilot review.

## 11. Prototype validity and review gates

The B25b implementation is validated on synthetic grids and authenticated SWAZ windows up to 100 target cells where all requested COGs pass pinned identity/profile checks and source arrays share the native grid. It demonstrates retrieval, native integration, fractional-overlap behaviour, coastal nodata handling, tile-order equality, reviewed schema writing/loading, and immutable bundle mechanics—not SWAZ-wide completeness or performance, paddock accuracy, scientific fitness, or approved soil bands.

Before the SWAZ artifact build:

- revalidate the pinned authoritative AWRA-L v7 input, tracked 18-source manifest, approved boundary hash, and exact 156×186 footprint;
- retain the user-approved v1 candidate schema/chunking and provisional 10×10 target-tile / 256 MiB cache choice unless new evidence triggers a versioned contract change;
- define and approve whole-SWAZ elapsed, failure, cleanup, and restart/resume behavior;
- decide whether external HTTP byte measurement or independent full-object source checksums are required;
- approve the internal distribution location, bundle review authority, and rollback procedure;
- complete external soil-science fitness, terminology, direct-DES, and uncertainty-scenario review.

Minimum acceptable coverage, coastal/polygon summary denominator policy, stratification bands/reference domain, and uncertainty-width thresholds remain explicitly unresolved and are not B25b constants.
