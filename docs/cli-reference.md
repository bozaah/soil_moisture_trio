# CLI Reference

Run with: `uv run python main.py [OPTIONS]`

## Core Flags

| Flag | Default | Description |
|---|---|---|
| `--year INT` | 2024 | Data year for AWRAL and SILO |
| `--start-date DATE` | first timestep | Start of averaging window (YYYY-MM-DD) |
| `--end-date DATE` | start-date | End of averaging window (YYYY-MM-DD) |
| `--visualize` | off | Generate Folium HTML map |
| `--output-path PATH` | `classification_map.html` | Folium HTML output path |

## Bounding Box

| Flag | Default | Description |
|---|---|---|
| `--min-lat FLOAT` | -45.0 | |
| `--max-lat FLOAT` | -8.0 | |
| `--min-lon FLOAT` | 110.0 | |
| `--max-lon FLOAT` | 155.0 | |

## Output Artifacts

| Flag | Description |
|---|---|
| `--risk-output-prefix PATH` | Prefix for NetCDF + JSON (e.g., `outputs/risk_2024`) |
| `--risk-plot-path PATH` | Two-panel PNG output |
| `--diag-plot-path PATH` | Diagnostics PNG (stress histogram + scatter) |

## SILO Loader

| Flag | Default | Description |
|---|---|---|
| `--silo-variable NAME` | `max_temp`, `vp_deficit` | Repeatable; SILO variable names |
| `--no-silo-cog-loader` | — | Fall back to NetCDF downloads |
| `--silo-cache-dir PATH` | temp | Local cache for GeoTIFF downloads |
| `--silo-cache-max-mb INT` | 200 | Cache size limit in MB |
| `--silo-overview-level INT` | — | Lower-res read (e.g., 1, 2) for testing |
| `--silo-buffer-deg FLOAT` | 0.0 | Bounding box buffer in degrees |

## Example — WA October 2025

```bash
uv run python main.py \
  --year 2025 \
  --start-date 2025-10-01 \
  --end-date 2025-10-15 \
  --risk-output-prefix outputs/risk_2025oct_WA \
  --risk-plot-path outputs/risk_2025oct_WA.png \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --silo-cache-dir /tmp/silo_cache \
  --silo-cache-max-mb 200 \
  --min-lat -35 --max-lat -13 \
  --min-lon 112 --max-lon 129
```

## Environment

- Use `uv run ...` or activate `.venv` — do not install into system Python
- AWRAL data requires network access to `thredds.nci.org.au`
- SILO data via S3: no credentials required (`AWS_NO_SIGN_REQUEST=YES` set automatically)
