# Session — 2026-08-12: Phase 5 authenticated SLGA manifest verification

## Goal

Live-verify the exact AWC v2 and DES v2 source manifest against TERN before designing the static full-WA SLGA-to-AWRA-L builder.

## Assumptions and scope

- This was a read-only, authenticated, one-window probe.
- `TERN_API_KEY` was read from the environment and was neither logged nor persisted.
- No full source layer, static artifact, or operational risk output was downloaded or created.
- No missing product could be silently substituted.
- Verification covered URL availability, STAC identity, source size/checksum metadata, COG profile, CRS/grid, units, nodata, overviews, a small SWAZ data window, and lower/EV/upper ordering.

## Material manifest correction

The provisional evidence review incorrectly listed DES v2 uncertainty components as `05` and `95`.

Authenticated checks established that:

- `DES_000_200_05_N_P_AU_TRN_C_20190901` returns HTTP 404;
- `DES_000_200_95_N_P_AU_TRN_C_20190901` returns HTTP 404;
- the authoritative DES v2 directory contains only `EV`, `10`, and `90` COGs and STAC sidecars;
- DES STAC metadata identifies these as the 10th- and 90th-percentile confidence limits.

The corrected Release 1 source set is therefore:

- AWC v2: EV/05/95 at 0–5, 5–15, 15–30, 30–60, and 60–100 cm (15 layers);
- DES v2: EV/10/90 at 0–200 cm (3 layers).

The combined lower/upper storage products will consequently be **mixed-quantile uncertainty scenarios**, not a formal confidence interval.

## Verification result

All 18 corrected sources passed the core live checks:

- HTTP 200 and byte-range access;
- matching STAC item and COG filename identity;
- published STAC multihash and file size available;
- Cloud-Optimised GeoTIFF with internal overviews;
- one band on a common EPSG:4326 grid;
- shape 40,800 rows × 49,200 columns;
- 3 arc-second resolution;
- bounds 112.999583333°E to 153.999583334°E and −44.000416667° to −10.000416666°;
- identical transform across all layers;
- AWC `uint16`, units `Percent`, nodata `65535`;
- DES `float32`, units `metres`, nodata `NaN`;
- finite values in the test window near 116°E, 32°S;
- lower ≤ EV ≤ upper for all five AWC depths and DES.

The exact IDs, URLs, published STAC multihashes, file sizes, and common profile are now tracked in:

```text
manifests/slga_awc_des_sources_v1.json
```

## Upstream metadata caveats

Two upstream inconsistencies are reproducible and must be handled explicitly rather than treated as arbitrary profile failures:

1. AWC STAC `raster:bands` omits nodata, while each live AWC COG defines nodata as `65535`.
2. DES COG band descriptions contain stale `NAT` identifiers, while the live filenames and STAC item IDs use the pinned `TRN` identifiers.

The builder should validate source identity primarily from the pinned URL, STAC item ID, DOI/version contract, multihash, size, grid/profile, units, and nodata. It should allow only these documented upstream exceptions and fail on new mismatches.

## Range-contract correction

The earlier approximate source ranges are not suitable as hard rejection limits:

- official AWC STAC maxima reach 71% in an upper uncertainty layer;
- DES EV reaches 2.41 m, DES10 reaches 2.24 m, and DES90 reaches 2.75 m.

DES remains capped at 1 m for the primary 0–100 cm integration. Builder validation should reject malformed dtype/units/nodata and non-finite or negative valid values, while treating scientifically unusual positive values as warnings until full-WA pilot distributions are reviewed.

## Files changed

- `manifests/slga_awc_des_sources_v1.json` — added the tracked, live-verified source manifest.
- `docs/slga-evidence-review.md` — corrected DES uncertainty components, range handling, and implementation steps.
- `docs/backlog.md` — recorded B25a verification completion and B25b metadata requirements.
- `data/README.md` — linked the tracked source manifest.
- `AGENTS.md` / `CHANGELOG.md` — updated project history.

## Conditions and limitations

- A small-window read proves source accessibility and profile consistency, not full-WA data completeness or scientific fitness.
- Published STAC multihashes were recorded but the multi-gigabyte source objects were not independently downloaded and re-hashed in full.
- No area-weighted EPSG:3577 harmonisation, DES capping, canonical AWRA-L grid derivation, or artifact schema was implemented.
- Soil bands, reference domain, minimum acceptable source coverage, DES uncertainty treatment, and external review remain unresolved.
- Existing risk code, thresholds, masks, and outputs were unchanged.

## Next step

Design the explicit B25b build contract and a deterministic small-window AWC+DES prototype using the corrected manifest. The design must define canonical AWRA-L cell construction, source-window/checksum handling, DES-capped depth integration, EPSG:3577 fractional-overlap aggregation, output schema, failure behavior, and tests before a full-WA build is attempted.
