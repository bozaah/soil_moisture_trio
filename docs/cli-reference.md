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
| `--output-dir DIR` | Directory for all run outputs. When set, `--risk-output-prefix` and `--risk-plot-path` are treated as basenames within this directory. Recommended for keeping runs isolated. |
| `--risk-output-prefix PATH` | Prefix (or basename with `--output-dir`) for NetCDF + JSON outputs |
| `--risk-plot-path PATH` | Path (or basename with `--output-dir`) for two-panel risk PNG |

## SILO Loader

| Flag | Default | Description |
|---|---|---|
| `--silo-variable NAME` | `max_temp`, `vp_deficit` | Repeatable; SILO variable names |
| `--no-silo-cog-loader` | — | Fall back to NetCDF downloads |
| `--silo-cache-dir PATH` | temp | Local cache for GeoTIFF downloads |
| `--silo-cache-max-mb INT` | 200 | Cache size limit in MB |
| `--silo-overview-level INT` | — | Lower-res read (e.g., 1, 2) for testing |
| `--silo-buffer-deg FLOAT` | 0.0 | Bounding box buffer in degrees |

## Example — SWAZ March 2026

```bash
uv run python main.py \
  --year 2026 \
  --start-date 2026-03-01 \
  --end-date 2026-03-23 \
  --output-dir outputs/risk_2026_mar_SWAZ \
  --risk-output-prefix risk_2026_mar_SWAZ \
  --risk-plot-path risk_2026_mar_SWAZ.png \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --silo-cache-dir ~/.cache/soil_moisture_trio/silo_swaz \
  --min-lat -35 --max-lat -27 \
  --min-lon 114 --max-lon 123
```

Then render the bulletin:

```bash
uv run python scripts/render_bulletin.py \
  --summary-json outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ_summary.json \
  --map-png outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ.png \
  --output outputs/risk_2026_mar_SWAZ/bulletin_2026_mar_SWAZ.md
```

## Environment

- Use `uv run ...` or activate `.venv` — do not install into system Python
- AWRAL data requires network access to `thredds.nci.org.au`
- SILO data via S3: no credentials required (`AWS_NO_SIGN_REQUEST=YES` set automatically)
