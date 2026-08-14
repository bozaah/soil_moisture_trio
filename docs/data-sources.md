# Data Sources

## AWRAL Soil Moisture — Operational Product

The pipeline's primary soil-moisture input is the AWRA-L v7 `sm_pct` decile product served from NCI THREDDS.

- Source: NCI THREDDS OPeNDAP
- Operational URL pattern:
  `https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/deciles/day/sm_pct_{YEAR}.nc`
- Variable: `sm_pct`
- Units: percentile rank `0–1`
- Grid: daily `(time, latitude, longitude)` at 0.05° resolution
- Pipeline handling: the selected date window is averaged down to a 2D `(lat, lon)` grid

`_normalize_sm_pct_decile()` retains a defensive `max > 1.1` check and converts to `0–1` if needed, but the expected operational behavior is already `0–1`.

### Required Percentile-Rank Product

The decile product is mandatory because the risk model is calibrated for spatially and seasonally normalised percentile ranks. If the product cannot be loaded, the pipeline raises a clear `RuntimeError` and does not substitute a raw soil-moisture product with different scientific meaning.

### Calibration Baseline

A local WA monthly decile subset may be used for calibration and diagnostics:

- File: `data/awral_decile_sm_pct_WA_monthly.nc`
- Coverage: WA subset
- Period: January 1911 to February 2026
- Use: reference analysis and threshold sanity checks, not routine operational loading
- Version control: excluded because it is approximately 793 MB; see [`data/README.md`](../data/README.md)

### Canonical Static-Soil Grid Input

The explicit Phase 5 SLGA artifact builder uses the completed 2025 Bureau-produced AWRA-L v7 daily `sm_pct` decile file at NCI as its authoritative coordinate input. `manifests/awral_v7_grid_source_v1.json` pins:

- filename `sm_pct_2025.nc` and the exact operational NCI FileServer/OPeNDAP path;
- product lineage `historical/v1/AWRALv7/processed/deciles/day`;
- byte size `312193677` and independently computed SHA-256 `353af96c7826111a54e189120ed6e1dcb6f9d2a1a0d6966c286aae4f4429095b`;
- float64 `latitude` (681 descending centres, −10 to −44) and `longitude` (841 ascending centres, 112 to 154), coordinate attributes, spacing, and coordinate-value hashes;
- approved full-WA artifact subset: exact inclusive latitude −13…−35 and longitude 112…129, shape 441×341 (150,381 cells).

The remote annual object is not treated as immutable merely because its URL is stable. The builder accepts only an explicitly supplied local file matching the pinned filename, size, full-file SHA-256, schema, and coordinates; it performs no implicit download. The local monthly WA calibration subset is not a substitute. Zenodo record 10689080 corroborates the grid dimensions/coordinates but is a third-party republication without explicit AWRA-L v7 identity in its record metadata, so it is not the canonical source.

## SLGA AWC and Depth of Soil — Phase 5 Static Context

Phase 5 uses an approved, tracked set of static Soil and Landscape Grid of Australia model predictions:

- AWC v2 EV/05/95 at 0–5, 5–15, 15–30, 30–60, and 60–100 cm;
- Depth of Soil (DES) v2 EV/10/90 at 0–200 cm.

`manifests/slga_awc_des_sources_v1.json` pins all 18 full product identifiers, URLs, profiles, DOI/version metadata, published STAC multihashes, and source sizes. The builder allows only two verified upstream metadata exceptions: AWC STAC omits the COG nodata value `65535`, and DES COG band descriptions retain stale `NAT` identifiers while filenames and STAC IDs use `TRN`.

Authenticated source reads require `TERN_API_KEY`. Credentials are scoped to HTTP Basic/GDAL access and are not persisted or logged. The narrow prototype reads bounded full-resolution COG windows, preserves nodata, integrates a DES-capped nominal 0–100 cm AWC storage-capacity metric, and harmonises it to canonical AWRA-L cells using fractional overlap in EPSG:3577.

These layers are modelled static soil context, not observed paddock PAWC, current water storage, crop-specific effective rooting depth, or independent validation of AWRA-L. AWC and AWRA-L have shared soil-map/pedotransfer ancestry. No approved full-WA artifact exists yet, and operational drought runs do not contact TERN or load SLGA data. See [`slga-evidence-review.md`](slga-evidence-review.md) and [`slga-builder-contract.md`](slga-builder-contract.md).

## SILO Temperature and VPD

SILO provides the two atmospheric inputs used by the composite stress index.

| SILO variable | Internal name | Units | Role |
|---|---|---|---|
| `max_temp` | `temperature` | °C | Heat stress component |
| `vp_deficit` | `vpd` | hPa | Atmospheric dryness component |

### Primary Path: weather_tools COG Loader

`WeatherToolsSiloLoader` wraps `weather_tools.silo_geotiff.download_geotiff()` and is the default loading path (`use_silo_cog_loader=True`).

Behavior:

- Requests only the selected variables and date range.
- Builds a polygon from the requested bbox, optionally expanded by `silo_buffer_degrees`.
- Reads GeoTIFF subsets, reduces the time stack with `np.nanmean`, and regrids to the target AWRAL coordinates using nearest-neighbor interpolation.
- Returns explicit `time_start` / `time_end` metadata for the requested SILO window.

### Fallback Path: SILO NetCDF

If the COG loader fails, or if the run is started with `--no-silo-cog-loader`, the pipeline falls back to the annual SILO NetCDF files on public AWS S3:

- `https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/max_temp/{YEAR}.max_temp.nc`
- `https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/vp_deficit/{YEAR}.vp_deficit.nc`

The pipeline sets `AWS_NO_SIGN_REQUEST=YES` automatically for these public buckets.

## SILO Cache Layout

The default cache root is:

```text
~/.cache/soil_moisture_trio/silo
```

The loader now scopes cached GeoTIFFs into a bbox-specific subdirectory:

```text
~/.cache/soil_moisture_trio/silo/bbox_<hash>/
```

This means:

- repeated runs for the same bounds reuse the same cache contents
- different bounding boxes do not collide inside the same cache root
- cache pruning still applies across the full cache tree via `silo_cache_max_size_mb`

Override the cache root with:

```bash
--silo-cache-dir /path/to/custom/silo_cache
```

## Operational Constraints

- SILO is typically available with a 1 to 2 day lag. Set `--end-date` no later than today minus two days for live runs.
- All three inputs must overlap in space and time. If any of soil moisture, temperature, or VPD is missing at a cell, that cell is marked invalid and excluded from summaries.
- The pipeline requires `max_temp` and `vp_deficit` to be present in the SILO payload. Missing variables raise a clear `ValueError`.
