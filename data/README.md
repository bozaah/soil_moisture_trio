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
