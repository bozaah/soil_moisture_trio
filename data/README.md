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

Phase 5 has implemented the bounded retrieval, integration, harmonisation, and provisional artifact I/O foundations for static SLGA AWC v2 and Depth of Soil (DES) v2 layers. The first artifact is scoped to SWAZ rather than full WA; no approved artifact exists yet, and the operational drought pipeline does not currently load soil context. The planned production layout is:

```text
data/processed/slga_awral/
  slga_awc_des_awral_swaz_0p05deg_v1/
    slga_awc_des_awral_swaz_0p05deg_v1.nc
    slga_awc_des_awral_swaz_0p05deg_v1.manifest.json
    build_report.json
```

The compressed NetCDF will contain DES-capped modelled AWC storage capacity, lower/upper uncertainty scenarios, source coverage, and mapped within-cell dispersion on the canonical AWRA-L cells covering SWAZ. The canonical input contract is tracked at [`../manifests/awral_v7_grid_source_v1.json`](../manifests/awral_v7_grid_source_v1.json): it pins the completed 2025 Bureau-produced AWRA-L v7 operational decile file at NCI by filename, byte size, independent SHA-256, schema, and coordinate hashes. The approved initial artifact footprint is the exact 156×186 contiguous source-coordinate subset with descending latitude centres −27.45 through −35.20 and ascending longitude centres 114.05 through 123.30 (29,016 cells). This rectangle covers the approved SWAZ boundary’s +0.1° operational bbox; the polygon remains a runtime mask and does not redefine static full-cell denominators. The explicit builder requires a matching local `sm_pct_2025.nc`; it never downloads it implicitly. SWAZ operational runs select exact coordinate subsets and do not trigger re-harmonisation. Future regions require a separately reviewed artifact scope and version. It is a static soil-context artifact and must not contain run-specific risk output.

Large derived files remain excluded from Git. The live-verified source catalogue is tracked at [`../manifests/slga_awc_des_sources_v1.json`](../manifests/slga_awc_des_sources_v1.json); it pins AWC EV/05/95 and DES EV/10/90 full identifiers, URLs, profiles, published STAC multihashes, and source sizes. The prototype transformation and output contract is tracked at [`../docs/slga-builder-contract.md`](../docs/slga-builder-contract.md). Reproducibility also requires an explicit build command, output checksums, and complete transformation metadata. Operational runs must fail clearly when the approved artifact is absent or incompatible; they must not silently download, rebuild, or substitute a newer SLGA product.

The reviewed v1 candidate schema now includes direct DES EV/10/90 context, shallow-than-1 m fractions, mixed-width support, and machine-readable case definitions. Immutable bundle publication is fail-if-present and preserves prior bundles for rollback; the sidecar checksum-records the build report. The explicit builder uses credential-free checksum-bound 10-row checkpoints under `.slga_awc_des_awral_swaz_0p05deg_v1.checkpoints/` and removes them only after successful verified publication unless asked to retain them. Bounded Albany coastal/nodata profiling supports 10×10 target tiles with a 256 MiB cache as the provisional SWAZ build setting, but the artifact remains unapproved until whole-build failure/restart planning, external soil-science review, distribution approval, and an explicit build command are complete.
