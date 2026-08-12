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

### Decile vs Legacy Raw-Values Product

The decile product is the default and scientifically preferred path. If that load fails, the pipeline raises a `RuntimeError` unless the operator explicitly enables:

```bash
--allow-legacy-sm
```

That flag allows fallback to:

`https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/values/day/sm_pct_{YEAR}.nc`

Important caveat: the legacy raw-values product is compatibility-only. The current thresholds and stress-index interpretation are calibrated for percentile-rank inputs, not raw volumetric values.

### Calibration Baseline

A local WA monthly decile subset may be used for calibration and diagnostics:

- File: `data/awral_decile_sm_pct_WA_monthly.nc`
- Coverage: WA subset
- Period: January 1911 to February 2026
- Use: reference analysis and threshold sanity checks, not routine operational loading
- Version control: excluded because it is approximately 793 MB; see [`data/README.md`](../data/README.md)

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
