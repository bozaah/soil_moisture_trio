# Session — 2026-08-12: B25b deterministic contract and small-window prototype

## Goal

Define the deterministic B25b builder contract and implement a narrow small-window AWC+DES prototype against the corrected 18-source manifest, without changing drought-risk calculations or building a full-WA artifact.

## Assumptions and validity conditions

- `manifests/slga_awc_des_sources_v1.json` is the only approved source catalogue; full product IDs are required and no shorthand/version substitution is allowed.
- The prototype is valid only for small full-resolution windows where every requested STAC/COG identity and profile matches the pinned contract and all native grids align.
- `TERN_API_KEY` is read only from the environment and used through scoped HTTP Basic/GDAL configuration. Its value is not persisted or logged.
- Source nodata and zero/partial overlap are expected data states. Authentication failure, metadata drift, malformed/negative valid values, uncertainty-ordering failure, grid/CRS mismatch, and malformed target coordinates are explicit failures.
- DES values above 1 m are valid and capped at 1 m only for the primary integration. Missing AWC below a shallower represented DES profile does not invalidate storage; missing required AWC does.
- The existing local monthly AWRA-L WA subset confirms coordinate orientation/spacing but has no sufficient global provenance attributes. It was not declared the authoritative canonical grid.

## Contract

Added `docs/slga-builder-contract.md`, defining:

- catalogue, COG retrieval, integration, harmonisation, artifact, and runtime-loader boundaries;
- source identity/profile checks and the two narrow upstream exceptions;
- one-pixel window expansion, bounded retries, nodata semantics, and hard failures;
- native five-layer storage integration and seven explicit storage cases;
- 0.05° centre/edge validation and exact runtime coordinate subsets;
- EPSG:3577 fractional overlap, full-cell coverage denominator, area-weighted mean, and mapped prediction standard deviation;
- provisional NetCDF schema, dtypes, compression/chunking, atomic writes, sidecar canonicalisation, and checksum procedure;
- full-WA review gates and unresolved science decisions that must not be invented in B25b.

## Implementation

Added the narrow package `src/soil_moisture_trio/slga/`:

- `catalogue.py` strictly loads the exact AWC v2/DES v2 manifest and validates public STAC fields, publisher multihashes, sizes, DOI/citation, components, depths, units, grid, and nodata contract.
- `cog.py` performs credential-gated STAC and full-resolution COG window access with bounded retries, one-pixel expansion, strict COG validation, nodata normalisation, and common-window checks. It permits only AWC's omitted STAC nodata and DES's stale COG `NAT` description.
- `integration.py` calculates DES-capped storage on the common native grid. It exposes EV, AWC-only lower/upper, DES-only lower/upper, and provisional mixed lower/upper cases plus mixed width.
- `harmonise.py` constructs validated target edges, transforms source/target footprints to EPSG:3577, intersects in stable source row-major order, and reports variable-specific mean, mapped prediction standard deviation, valid source area, full-cell area, and coverage. Target boundaries are split at native source grid lines so coincident boundaries share vertices.
- Runtime coordinate helper accepts only exact contiguous canonical subsets.

Rasterio and pyproj were added as direct dependencies. Shapely and NumPy were already direct dependencies.

## Tests

Added deterministic tests covering:

- manifest identity/version/layer-set/checksum drift and rejection of shorthand IDs;
- STAC identity and the narrow AWC nodata exception;
- missing credentials before network access;
- malformed bounds, one-pixel window expansion, non-overlap, stale DES `NAT`, CRS mismatch, nodata, negative and infinite values;
- thickness integration, DES >1 m capping, shallow-profile nodata, zero depth, separate uncertainty effects, malformed values, and lower ≤ EV ≤ upper ordering;
- coordinate spacing/orientation, complete/partial/zero overlap, variable-specific nodata coverage, mapped dispersion, CRS/grid mismatch, exact subsets, and repeatability;
- one default-skipped live AWC probe gated by `RUN_SLGA_LIVE_TESTS=1` and `TERN_API_KEY`.

Default tests do not access the network.

## Live prototype result

A fresh authenticated read used bounds `(116.0, -32.0, 116.005, -31.995)`.

- all 18 pinned sources passed STAC and COG validation;
- every expanded source window was 9×9 and grids aligned;
- all 81 native pixels were finite for all seven integrated storage cases;
- EV storage ranged from 117.5 to 133.5 mm in the probe;
- the first synthetic 0.05° target cell had mapped EV storage 124.4320667476 mm and source coverage 0.0225006023;
- mixed lower/upper mapped values for that cell were 78.7691716901 and 169.9628603634 mm;
- no minimum coverage threshold was applied or inferred.

This proves small-window access/profile consistency and the prototype path. It does not prove full-WA completeness, scalable performance, field accuracy, or scientific fitness.

## Verification

```text
uv lock --check       -> succeeds
uv run pytest -q      -> 54 passed, 1 skipped
uv run ruff check .   -> All checks passed!
git diff --check      -> passes
```

Existing risk code, configuration, thresholds, masks, outputs, and tests were not changed.

## Remaining work

B25b remains open. Before a full-WA build:

1. Pin an authoritative full-WA AWRA-L coordinate source/version and immutable checksum.
2. Implement and review the deterministic artifact writer/runtime loader described by the contract.
3. Review a scalable tiled overlap strategy while preserving the prototype's numerical rules.
4. Decide builder cache and independent full-source checksum policy.
5. Review final schema/chunking and DES uncertainty presentation.
6. Obtain external soil-science review before approving coverage thresholds, strata, or operational summaries.

No static artifact or `data/processed/slga_awral/` directory was created.
