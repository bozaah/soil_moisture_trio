# B25b SLGA-to-AWRA-L builder contract

Status: prototype contract for review. This contract governs the deterministic B25b small-window implementation. It does **not** approve a full-WA artifact, soil-stratification bands, or operational integration.

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

The full-WA canonical coordinates must come from one explicitly supplied, immutable AWRA-L NetCDF coordinate input. The eventual approved contract must pin its public source URL, AWRA-L product/version, coordinate variable names, byte size, and SHA-256. The builder does not silently download that input. The current local monthly WA subset lacks sufficient provenance metadata and is not declared authoritative by this contract.

Coordinates are one-dimensional finite float64 cell centres. Latitude may arrive descending and longitude ascending; their original values and orientation are persisted. Each axis must be strictly monotonic, unique, and regularly spaced. Nominal spacing is 0.05° and is accepted only when every step is within absolute tolerance `1e-10°` of the median and the median is within `1e-10°` of 0.05°. No coordinate is rounded or regenerated.

Interior cell edges are adjacent-centre midpoints. Exterior edges are extrapolated by half the adjacent spacing. This requires at least two coordinates per axis. Cell polygons use these edges regardless of coordinate orientation.

Runtime loading accepts only a contiguous ordered subset of persisted coordinate values. Matching is exact after dtype conversion to float64 (`np.array_equal`); nearest-neighbour, tolerance matching, coordinate rounding, and re-harmonisation are forbidden. Missing, reordered, duplicated, or off-grid coordinates fail.

The exact canonical source/version remains a review gate before a full-WA build. Synthetic coordinates may be used by the small-window prototype and tests.

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

The prototype overlap engine is correctness-first and limited to small windows. Full-WA performance and tiling must be reviewed before artifact production without changing these numerical rules.

## 8. Artifact schema and deterministic writing

Provisional artifact path:

```text
data/processed/slga_awral/slga_awc_des_awral_wa_0p05deg_v1.nc
```

Dimensions are `latitude`, `longitude`, and `storage_case` (the seven ordered labels in Section 5). Provisional variables are:

- `awc_storage_capacity_mm(storage_case, latitude, longitude)` — float32, `NaN` nodata;
- `mapped_prediction_sd_mm(storage_case, latitude, longitude)` — float32, `NaN` nodata;
- `valid_source_area_m2(storage_case, latitude, longitude)` — float64;
- `source_coverage_fraction(storage_case, latitude, longitude)` — float32;
- `full_cell_area_m2(latitude, longitude)` — float64;
- `mixed_uncertainty_width_mm(latitude, longitude)` — float32, `NaN` nodata.

A later reviewed schema may add separately aggregated DES variables without changing risk outputs. Variable names may not be silently changed after artifact version `v1` is approved.

NetCDF data variables use zlib compression level 4 with shuffle enabled. Float32 storage/dispersion/coverage variables use chunks `(1, 64, 64)`; float64 area variables use `(64, 64)`, truncated at array edges. Coordinates remain float64 and uncompressed. Fill values are explicit (`NaN` for floating mapped values; no sentinel is shared with risk output). Global metadata includes contract/artifact versions, creation timestamp in UTC, canonical-grid provenance, EPSG codes, formula, tolerances, ordered cases, source-manifest ID and SHA-256, each source record, publisher multihashes, licences/citations, and scientific limitations. The artifact contains no risk variables.

Deterministic checksums are calculated only after closing files. The sidecar JSON is UTF-8, sorted by key, indented by two spaces, terminated by one newline, and records artifact filename, byte size, SHA-256, builder version/commit, contract version, canonical-grid identity/SHA-256, source-manifest identity/SHA-256, and source retrieval timestamps. Its own checksum is not recursively embedded.

Byte-identical NetCDF output across library/platform versions is not promised. Reproducibility acceptance requires equal schema/metadata (excluding declared creation/retrieval timestamps), exact masks/coordinates/areas where specified, and numerical equality within the contract tolerances; each produced byte stream receives its actual SHA-256.

Writes use a temporary file in the destination directory, validate the closed file, then atomically replace the destination. Failure leaves no apparently complete final artifact.

## 9. Runtime loader contract

The runtime loader:

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

The B25b prototype is valid only for a tiny deterministic window where all requested COGs pass pinned identity/profile checks and source arrays share the native grid. It demonstrates window retrieval, native integration, and fractional-overlap behaviour—not full-Australia completeness, full-WA performance, paddock accuracy, scientific fitness, or approved soil bands.

Before a full-WA artifact build, review and pin:

- the authoritative canonical AWRA-L coordinate source/version and immutable grid checksum;
- final artifact variables/schema/chunking after inspecting prototype outputs;
- scalable tiling/performance while preserving numerical rules;
- builder cache policy and whether independent full-object source checksums are required;
- DES uncertainty presentation;
- external soil-science fitness and terminology review.

Minimum acceptable coverage, coastal/polygon summary denominator policy, stratification bands/reference domain, and uncertainty-width thresholds remain explicitly unresolved and are not B25b constants.
