# Soil Moisture Trio

A rule-based drought risk monitoring pipeline for the Australian landscape. Combines AWRA-L soil moisture decile ranks, SILO maximum temperature, and SILO vapour pressure deficit into a composite stress index, then assigns categorical risk levels to each grid cell.

## Outputs

| Artifact | Format | Description |
| --- | --- | --- |
| Risk map | NetCDF | `RiskLevel` per cell: Low / Watch / Alert / Critical |
| Summary | JSON | Cell counts and percentages per risk band |
| Risk plot | PNG | Two-panel: categorical map + continuous stress index |
| Bulletin | Markdown | Policy-ready bulletin rendered from summary JSON |

## Requirements

- Python 3.12 via [`uv`](https://docs.astral.sh/uv/)
- Network access to NCI THREDDS (AWRAL `sm_pct`) and AWS S3 / `weather_tools` (SILO)

## Setup

```bash
uv sync
```

## Quick Start — WA Southwest Agricultural Zone

The boundary file is locally supplied and intentionally not redistributed. Obtain the approved DPIRD boundary and place it at `data/south_west_agricultural_boundary.gpkg`; see [`data/README.md`](data/README.md).

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
4. **Output** — NetCDF risk map, JSON summary, PNG figures, and optional bulletin

Full pipeline detail: [docs/architecture.md](docs/architecture.md) | Methodology: [docs/technical_report.md](docs/technical_report.md)

## Phase 5 Development Status

A separate, non-operational SLGA prototype now supports pinned AWC v2 and Depth of Soil v2 source validation, authenticated bounded COG reads, DES-capped storage-capacity integration, EPSG:3577 fractional-overlap harmonisation, tiled processing, and reviewed v1-candidate static-artifact I/O with direct DES context and immutable bundle publication. It has passed deterministic tests, a bounded authenticated 3×3 inland SWAZ multi-tile pilot, and a 5×5 Albany coastal/nodata pilot with exact warm-cache equality.

The first static soil artifact is now scoped to the SWAZ buffered operational rectangle (29,016 canonical AWRA-L cells), not full WA. It has not yet been built or approved, and no soil-stratified risk summary exists. The operational drought pipeline, risk formula, thresholds, valid mask, and outputs remain unchanged and do not fetch or load SLGA data. See [docs/slga-builder-contract.md](docs/slga-builder-contract.md) and [docs/backlog.md](docs/backlog.md).

## Project Structure

```text
src/soil_moisture_trio/
  config.py        ClassifierConfig — all tunable parameters (Pydantic)
  pipeline.py      DryWetClassifierPipeline — data loading and risk assessment
  data_sources.py  WeatherToolsSiloLoader — SILO COG fetcher + persistent cache
  risk.py          Composite stress index, RiskLevel enum, NetCDF/JSON output
  plot.py          PNG outputs
  slga/            Phase 5 static-soil prototype; separate from risk runtime
templates/         Jinja2 output templates
scripts/           Standalone utilities (bulletin renderer and bounded SLGA pilot)
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
| `dryness_weight` / `vpd_weight` / `temperature_weight` | 0.60 / 0.25 / 0.15 | Validated to sum to 1 |
| `watch_risk_threshold` / `alert_risk_threshold` / `critical_risk_threshold` | 0.35 / 0.60 / 0.85 | Validated in strictly increasing order |
| `silo_cache_dir` | `~/.cache/soil_moisture_trio/silo` | Persistent tile cache; created automatically |

## SILO Cache

SILO GeoTIFF tiles are cached under `~/.cache/soil_moisture_trio/silo` by default and persist across runs. The loader now creates bbox-scoped subdirectories inside that cache root, so repeated runs for the same bounds reuse tiles without cross-bbox collisions.

## Verification

```bash
uv sync --frozen --group dev
uv run pytest -q
uv run ruff check
```

The networked moisture-range utility is intentionally outside the test suite:

```bash
uv run python scripts/moisture_ranges_diagnostic.py
```

## Docs

| Doc | Contents |
| --- | --- |
| [docs/technical_report.md](docs/technical_report.md) | Full methodology: data sources, stress index, thresholds, scientific rationale |
| [docs/architecture.md](docs/architecture.md) | Pipeline flow, data contract, spatial handling |
| [docs/data-sources.md](docs/data-sources.md) | AWRAL/SILO sources, units, cache |
| [docs/cli-reference.md](docs/cli-reference.md) | All operational CLI flags |
| [docs/slga-evidence-review.md](docs/slga-evidence-review.md) | Soil-property evidence, product selection, and scientific limits |
| [docs/slga-builder-contract.md](docs/slga-builder-contract.md) | B25b source, harmonisation, artifact, and failure contract |
| [docs/backlog.md](docs/backlog.md) | Open issues and next steps |
| [CHANGELOG.md](CHANGELOG.md) | Per-sprint changes |
