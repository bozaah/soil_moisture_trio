# Data Sources

## AWRAL Soil Moisture — Decile Product (`sm_pct`)

- **Source:** NCI THREDDS OPeNDAP
- **Operational URL (daily, per year):** `https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/deciles/day/sm_pct_{YEAR}.nc`
- **Calibration URL (monthly, 1911–2026):** `https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/deciles/month/sm_pct.nc`
- **Variable:** `sm_pct` (confirmed via OPeNDAP probe 2026-03-23)
- **Units:** `relative` — percentile rank 0–1, calibrated against the full 1911–present historical record for each location and day-of-year
- **Pipeline handling:** No unit conversion needed (always 0–1). A defensive `max > 1.1` check is retained; it will warn if triggered but should never fire on the decile product.

| Product | Dimensions | Size (full Australia) |
|---|---|---|
| Daily decile (one year) | (366, 681, 841) | ~838 MB |
| Monthly decile (1911–2026) | (1382, 681, 841) | ~3 GB |
| Monthly decile — WA subset | (1382, 441, 341) | ~831 MB |

WA calibration baseline downloaded to `data/awral_decile_sm_pct_WA_monthly.nc` (download: ~5.3 min via OPeNDAP decade-chunked).

- **Required:** Yes. Pipeline raises `RuntimeError` if `sm_pct` load fails.
- **Dimensions:** `(time, latitude, longitude)` → averaged over requested window → 2D `(lat, lon)`

### Migration note (Sprint 5 → Sprint 6)

Previously used `processed/values/day/sm_pct_{YEAR}.nc` (raw volumetric fraction, units varied by year). Switched to `processed/deciles/day/sm_pct_{YEAR}.nc` to resolve B1 (over-classification) and B3 (calibration). The raw-values URL unit table (2025: 0–100, 2026: 0–1) is no longer relevant.

## SILO Variables

- **Primary loader:** `weather_tools` COG (GeoTIFF) subsetter (`use_silo_cog_loader=True` by default)
- **Fallback:** Direct SILO NetCDF from AWS S3 (`--no-silo-cog-loader`)
- **NetCDF URL pattern (fallback):**
  - `https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/max_temp/{YEAR}.max_temp.nc`
  - `https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/vp_deficit/{YEAR}.vp_deficit.nc`

### Variables used

| SILO name | Internal name | Units | Role |
|---|---|---|---|
| `max_temp` | `temperature` | °C | Heat stress proxy |
| `vp_deficit` | `vpd` | hPa | Atmospheric dryness stressor |

### COG Loader Details (`WeatherToolsSiloLoader`)

- Calls `weather_tools.silo_geotiff.download_geotiff()` with a bounding-box polygon
- Optional `buffer_degrees` expands the bbox for border effects
- Downloaded tiles cached locally; cache pruned to `silo_cache_max_size_mb` (default 200 MB) by LRU
- Multiple dates stacked → averaged via `np.nanmean` across time axis
- Regridded to AWRAL lat/lon grid via nearest-neighbour interpolation

### SILO GeoTIFF Cache

By default, tiles are cached to the system temp directory:

```
/var/folders/<hash>/T/weather_tools_cache/geotiff/{variable}/{year}/{YYYYMMDD}.{variable}.tif
```

**This location is not persistent** — the OS can clear it on reboot. For reproducible multi-run workflows, specify a persistent directory:

```bash
--silo-cache-dir /path/to/persistent/silo_cache
```

Observed cache sizes from production runs (WA bbox, COG subsets):

| Period | Variables | Files | Size |
|---|---|---|---|
| Q2 2025 (91 days) | max_temp + vp_deficit | 182 | ~40 MB |
| Jan–Mar 2026 (74 days) | max_temp + vp_deficit | 148 | ~36 MB |
| Combined on disk | | 330 | ~76 MB |

Cache is keyed by `{variable}/{year}/{date}` — re-running the same period hits cache instantly (0 downloads).

## Accessing Data

Requires network access to NCI THREDDS (OPeNDAP) and either AWS S3 or `weather_tools` API. The pipeline sets `AWS_NO_SIGN_REQUEST=YES` for public S3 buckets. No authentication is needed for AWRAL historical data.
