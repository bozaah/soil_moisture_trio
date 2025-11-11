## Soil Moisture Trio

This project trains a CatBoost classifier to label Australian grid cells as **dry** or **wet** based on soil moisture, SILO temperature, NDVI (placeholder), and VPD. The CLI in `main.py` handles data prep, training/testing, risk scoring, and optional Folium/PNG exports.

### Weather data sourcing

- **Soil moisture** is still streamed from the BoM AWRAL NetCDF feed on NCI.
- **SILO variables** (max temperature, VPD, etc.) now default to the `weather_tools` GeoTIFF/COG loader so we only download the requested bounding box. This slashes runtime and bandwidth when focusing on portions of Australia, while keeping a config flag to fall back to the legacy NetCDF files.
- Configure the loader via the new `ClassifierConfig` fields or CLI flags:
  - `--silo-variable` (repeatable) controls which SILO variables/presets to request. The defaults are `max_temp` and `vp_deficit`.
  - `--silo-cache-dir` and `--silo-cache-max-mb` enable a thin on-disk cache; omit the dir to keep using the temp-space cache managed by `weather_tools`.
  - `--silo-overview-level` and `--silo-buffer-deg` tune the COG subsetting resolution and spatial buffer.
  - `--no-silo-cog-loader` reverts to the older NetCDF-based loader if needed.
  - `--min-lat/--max-lat/--min-lon/--max-lon` let you focus on any bounding box (e.g., Western Australia) without editing code.

Example run that keeps everything in temp storage but requests rainfall as an extra feature:

```bash
.venv/bin/python main.py \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --silo-variable daily_rain \
  --year 2024 \
  --start-date 2024-01-01 \
  --end-date 2024-03-31
```

`weather_tools` and its transitive dependencies (e.g., `shapely`) are now listed in `pyproject.toml` / `requirements.txt`. Re-run `uv pip compile` after changing dependencies to keep those files in sync.
