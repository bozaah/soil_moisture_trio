# Soil Moisture Trio

A rule-based drought risk monitoring pipeline for the Australian landscape. Combines AWRA-L soil moisture decile ranks, SILO maximum temperature, and SILO vapour pressure deficit into a composite stress index, then assigns categorical risk levels to each grid cell.

## Outputs

| Artifact | Format | Description |
| --- | --- | --- |
| Risk map | NetCDF | `RiskLevel` per cell: Low / Watch / Alert / Critical |
| Summary | JSON | Cell counts and percentages per risk band |
| Risk plot | PNG | Two-panel: categorical map + continuous stress index |
| Bulletin | Markdown | Policy-ready bulletin rendered from summary JSON |
| Interactive map | HTML | Optional Folium map (pass `--visualize`) |

## Requirements

- Python 3.12 via [`uv`](https://docs.astral.sh/uv/)
- Network access to NCI THREDDS (AWRAL `sm_pct`) and AWS S3 / `weather_tools` (SILO)

## Setup

```bash
uv sync
```

## Quick Start — WA Southwest Agricultural Zone

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

Then render a bulletin (all files in the same run directory):

```bash
uv run python scripts/render_bulletin.py \
  --summary-json outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ_summary.json \
  --map-png outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ.png \
  --output outputs/risk_2026_mar_SWAZ/bulletin_2026_mar_SWAZ.md \
  --region "South West Agricultural Zone"
```

See [docs/cli-reference.md](docs/cli-reference.md) for all flags.

## How It Works

1. **Load** — AWRAL `sm_pct` percentile rank (0–1) + SILO `max_temp` and `vp_deficit`, clipped to bounds and averaged over the requested time window
2. **Risk** — composite stress index: 60% soil moisture deficit (departure below median) + 25% VPD + 15% temperature, normalised against agronomic critical thresholds
3. **Classify** — stress index thresholds assign each cell to Low / Watch / Alert / Critical; ocean and missing-data cells are masked (`-1`)
4. **Output** — NetCDF risk map, JSON summary, PNG figure, optional bulletin and Folium map

Full pipeline detail: [docs/architecture.md](docs/architecture.md) | Methodology: [docs/technical_report.md](docs/technical_report.md)

## Project Structure

```text
src/soil_moisture_trio/
  config.py        ClassifierConfig — all tunable parameters (Pydantic)
  pipeline.py      DryWetClassifierPipeline — data loading and risk assessment
  data_sources.py  WeatherToolsSiloLoader — SILO COG fetcher + persistent cache
  risk.py          Composite stress index, RiskLevel enum, NetCDF/JSON output
  plot.py          PNG outputs
  visualize.py     Folium HTML map
templates/         Jinja2 output templates
scripts/           Standalone utilities (bulletin renderer)
tests/             pytest suite (mocks network I/O)
docs/              Reference documentation
sessions/          Per-session notes and working log
```

## Configuration

All thresholds live in `ClassifierConfig` (`src/.../config.py`). Key defaults:

| Parameter | Default | Note |
| --- | --- | --- |
| `moisture_threshold` | 0.50 | Dryness reference — departure below climatological median |
| `critical_temp_threshold` | 40.0 °C | Normalisation ceiling for temperature factor |
| `critical_vpd_threshold` | 32.0 hPa | Normalisation ceiling for VPD factor (3.2 kPa) |
| `silo_cache_dir` | `~/.cache/soil_moisture_trio/silo` | Persistent tile cache; created automatically |

## SILO Cache

SILO GeoTIFF tiles are cached to `~/.cache/soil_moisture_trio/silo` by default and persist across runs. Re-running the same period and bounding box incurs zero downloads.

> **Note (B22):** The cache key does not include the bounding box. Runs with different bounding boxes must use separate cache directories via `--silo-cache-dir`. See [docs/backlog.md](docs/backlog.md).

## Tests

```bash
uv run pytest tests/test_pipeline.py tests/test_data_sources.py -q
```

> `tests/test_moisture_ranges.py` is a diagnostic script — run it directly, not via pytest.

## Docs

| Doc | Contents |
| --- | --- |
| [docs/technical_report.md](docs/technical_report.md) | Full methodology: data sources, stress index, thresholds, scientific rationale |
| [docs/architecture.md](docs/architecture.md) | Pipeline flow, data contract, spatial handling |
| [docs/data-sources.md](docs/data-sources.md) | AWRAL/SILO sources, units, cache |
| [docs/cli-reference.md](docs/cli-reference.md) | All CLI flags |
| [docs/backlog.md](docs/backlog.md) | Open issues and next steps |
| [CHANGELOG.md](CHANGELOG.md) | Per-sprint changes |
