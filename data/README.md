# Local data

Files in this directory are intentionally excluded from Git unless explicitly allow-listed.

## Operational boundary

The documented SWAZ workflow requires:

```text
data/south_west_agricultural_boundary.gpkg
```

This is the DPIRD South West Agricultural Boundary in EPSG:28350 (GDA94 / MGA zone 50). Obtain the approved boundary through the relevant DPIRD data custodian and place it at the path above. The repository does not currently redistribute it because its publication provenance and licence have not been recorded.

The pipeline reprojects the boundary to EPSG:4326, derives a buffered bounding box, and masks cells whose centres fall outside the polygon.

## Calibration baseline

Historical calibration work may use:

```text
data/awral_decile_sm_pct_WA_monthly.nc
```

This approximately 793 MB file is a local WA subset of the AWRA-L v7 monthly soil-moisture percentile-rank product covering 1911–2026. It is not needed for routine operational runs and is not stored in Git.

See [`../docs/data-sources.md`](../docs/data-sources.md) for source details.

## Static SLGA-derived layers — Phase 5 prototype

Phase 5 has implemented the bounded retrieval, integration, harmonisation, and provisional artifact I/O foundations for static SLGA AWC v2 and Depth of Soil (DES) v2 layers. No approved full-WA artifact exists yet, and the operational drought pipeline does not currently load soil context. The planned production layout is:

```text
data/processed/slga_awral/
  slga_awc_des_awral_wa_0p05deg_v1.nc
  slga_awc_des_awral_wa_0p05deg_v1.manifest.json
```

The compressed NetCDF will contain DES-capped modelled AWC storage capacity, lower/upper uncertainty scenarios, source coverage, and mapped within-cell dispersion on a canonical full-WA AWRA-L grid derived from authoritative coordinates. The canonical input contract is tracked at [`../manifests/awral_v7_grid_source_v1.json`](../manifests/awral_v7_grid_source_v1.json): it pins the completed 2025 Bureau-produced AWRA-L v7 operational decile file at NCI by filename, byte size, independent SHA-256, schema, and coordinate hashes. The approved artifact footprint is the exact 441×341 contiguous source-coordinate subset with latitude −13 through −35 and longitude 112 through 129. The explicit builder requires a matching local `sm_pct_2025.nc`; it never downloads it implicitly. Operational SWAZ and future regional runs select exact coordinate subsets; boundaries do not trigger re-harmonisation. It is a static soil-context artifact and must not contain run-specific risk output.

Large derived files remain excluded from Git. The live-verified source catalogue is tracked at [`../manifests/slga_awc_des_sources_v1.json`](../manifests/slga_awc_des_sources_v1.json); it pins AWC EV/05/95 and DES EV/10/90 full identifiers, URLs, profiles, published STAC multihashes, and source sizes. The prototype transformation and output contract is tracked at [`../docs/slga-builder-contract.md`](../docs/slga-builder-contract.md). Reproducibility also requires an explicit build command, output checksums, and complete transformation metadata. Operational runs must fail clearly when the approved artifact is absent or incompatible; they must not silently download, rebuild, or substitute a newer SLGA product.

The artifact schema and filename are implemented provisionally for testing but remain unapproved until larger coastal/nodata profiling, schema and DES-presentation review, and artifact version promotion are complete.
