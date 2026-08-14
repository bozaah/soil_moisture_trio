# CLI Reference

Run with: `uv run python main.py [OPTIONS]`

## Core Flags

| Flag | Default | Description |
|---|---|---|
| `--year INT` | 2024 | Data year for AWRAL and SILO |
| `--start-date DATE` | first timestep | Start of averaging window (YYYY-MM-DD) |
| `--end-date DATE` | start-date | End of averaging window (YYYY-MM-DD) |

## Risk Model

| Flag | Default | Description |
|---|---:|---|
| `--dryness-weight FLOAT` | 0.60 | Soil-moisture deficit weight |
| `--vpd-weight FLOAT` | 0.25 | VPD stress weight |
| `--temperature-weight FLOAT` | 0.15 | Temperature stress weight |
| `--watch-risk-threshold FLOAT` | 0.35 | Minimum stress index for Watch |
| `--alert-risk-threshold FLOAT` | 0.60 | Minimum stress index for Alert |
| `--critical-risk-threshold FLOAT` | 0.85 | Minimum stress index for Critical |

Weights must be between 0 and 1 and sum to 1. Risk thresholds must be between 0 and 1 and satisfy `watch < alert < critical`. Defaults should be retained for operational products unless a scientifically reviewed calibration specifies otherwise.

## Boundary / Bounding Box

| Flag | Default | Description |
|---|---|---|
| `--boundary-gpkg PATH` | — | GeoPackage boundary file. Derives bbox automatically (+0.1° buffer) and masks cells outside the polygon. Replaces manual `--min-lat/max-lat/min-lon/max-lon` for boundary-defined regions. |
| `--min-lat FLOAT` | -45.0 | Manual override; ignored when `--boundary-gpkg` is set |
| `--max-lat FLOAT` | -8.0 | |
| `--min-lon FLOAT` | 110.0 | |
| `--max-lon FLOAT` | 155.0 | |

Date windows must satisfy `start <= end`. Manual bounds must satisfy `min_lat < max_lat` and `min_lon < max_lon`; invalid configuration fails before remote loading.

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
| `--use-silo-cog-loader` | auto/default on | Explicitly prefer the `weather_tools` GeoTIFF path |
| `--no-silo-cog-loader` | — | Fall back to NetCDF downloads |
| `--silo-cache-dir PATH` | `~/.cache/soil_moisture_trio/silo` | Cache root for GeoTIFF downloads; bbox-specific subdirectories are created automatically |
| `--silo-cache-max-mb INT` | 200 | Cache size limit in MB |
| `--silo-overview-level INT` | — | Lower-res read (e.g., 1, 2) for testing |
| `--silo-buffer-deg FLOAT` | 0.0 | Bounding box buffer in degrees |

## Example — SWAZ March 2026

This example requires the locally supplied DPIRD boundary at `data/south_west_agricultural_boundary.gpkg`; see [`data/README.md`](../data/README.md).

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
  --boundary-gpkg data/south_west_agricultural_boundary.gpkg
```

Then render the bulletin:

```bash
uv run python scripts/render_bulletin.py \
  --summary-json outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ_summary.json \
  --map-png outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ.png \
  --output outputs/risk_2026_mar_SWAZ/bulletin_2026_mar_SWAZ.md \
  --region "South West Agricultural Zone"
```

## Bulletin Renderer (`scripts/render_bulletin.py`)

| Flag | Default | Description |
|---|---|---|
| `--summary-json PATH` | required | Path to `*_summary.json` produced by the pipeline |
| `--map-png PATH` | — | Risk map PNG to embed (path made relative to output dir automatically) |
| `--output PATH` | required | Output Markdown path |
| `--region TEXT` | `"Western Australia"` | Region label used in the bulletin title and text |

## Phase 5 SLGA Development Utilities

The operational `main.py` CLI has no SLGA flags. It does not retrieve, rebuild, or load soil layers. The bounded authenticated pilot at `scripts/slga_tiled_pilot.py` is development-only, requires an exact locally supplied canonical AWRA-L grid input plus `TERN_API_KEY`, enforces a target-cell safety limit, and writes diagnostic JSON rather than an approved artifact. Its diagnostics separate logical reads, STAC and COG attempts/outcomes, completed COG window fetches, cache hits/misses/evictions/current/peak bytes, per-tile elapsed time, and process peak RSS. Rasterio/GDAL HTTP transferred-byte counts are explicitly reported as unavailable rather than estimated.

Do not use the pilot as an operational build command. The explicit reviewed builder is:

```bash
uv run python -m scripts.slga_build_swaz_artifact \
  --awral-grid-input data/source_inputs/sm_pct_2025.nc \
  --max-runtime-seconds 21600
```

It is hard-scoped to the exact 156×186 SWAZ footprint, 10-row resumable stripes, 10×10 target tiles, and a 256 MiB cache. It requires a clean Git worktree so the sidecar identifies exact committed code. Completed stripe directories are atomic, checksum-verified, credential-free, and contract-bound; incompatible resume state fails. The six-hour limit is checked between completed stripes, which remain for the next `--resume` invocation. After exact assembly, the command publishes a fail-if-present repo-local immutable bundle containing NetCDF, sidecar, and checksummed `build_report.json`; checkpoints are removed only after verified publication unless `--keep-checkpoints` is set.

The command is implemented but must not be run until external soil-science and distribution review explicitly approves the SWAZ review build. A full-WA static artifact will not be built in this phase. See [`slga-builder-contract.md`](slga-builder-contract.md).

## Environment

- Use `uv run ...` or activate `.venv` — do not install into system Python
- AWRAL data requires network access to `thredds.nci.org.au`
- SILO data via S3: no credentials required (`AWS_NO_SIGN_REQUEST=YES` set automatically)
- For live runs, keep `--end-date` at most 2 days behind today because SILO publication lags
