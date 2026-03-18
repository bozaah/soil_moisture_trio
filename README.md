# Soil Moisture Trio

A machine learning pipeline that classifies Australian grid cells as **dry** or **wet** using AWRAL soil moisture, SILO temperature, and SILO vapour pressure deficit. Produces categorical risk maps for decision support.

## Outputs

| Artifact | Format | Description |
| --- | --- | --- |
| Risk map | NetCDF | `RiskLevel` per cell: Low / Watch / Alert / Critical |
| Summary | JSON | Cell counts and percentages per risk band |
| Risk plot | PNG | Two-panel: categorical map + continuous stress index |
| Interactive map | HTML | Optional Folium map (pass `--visualize`) |

## Requirements

- Python 3.12 via [`uv`](https://docs.astral.sh/uv/)
- Network access to NCI THREDDS (AWRAL `sm_pct`) and AWS S3 / `weather_tools` (SILO)

## Setup

```bash
uv sync
```

## Quick Start

```bash
uv run python main.py \
  --year 2025 \
  --start-date 2025-10-01 \
  --end-date 2025-10-15 \
  --risk-output-prefix outputs/risk_2025oct_WA \
  --risk-plot-path outputs/risk_2025oct_WA.png \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --min-lat -35 --max-lat -13 \
  --min-lon 112 --max-lon 129
```

See [docs/cli-reference.md](docs/cli-reference.md) for all flags.

## How It Works

1. **Load** — AWRAL `sm_pct` (fraction 0–1) + SILO `max_temp` and `vp_deficit`, clipped to bounds and averaged over the requested time window
2. **Label** — rule-based dry/wet labels from soil moisture, temperature, and VPD thresholds
3. **Train** — CatBoost classifier on valid (non-NaN) grid cells
4. **Predict** — classify full grid; ocean/missing cells encoded as `-1`
5. **Risk** — physics-based dryness stress index → categorical risk map

Full pipeline detail: [docs/architecture.md](docs/architecture.md)

## Project Structure

```text
src/soil_moisture_trio/
  config.py        ClassifierConfig — all tunable parameters (Pydantic)
  pipeline.py      DryWetClassifierPipeline — data loading, ML, prediction
  data_sources.py  WeatherToolsSiloLoader — SILO COG fetcher + cache
  risk.py          Stress index, RiskLevel enum, NetCDF/JSON output
  plot.py          PNG outputs
  visualize.py     Folium HTML map
tests/             pytest suite (mocks network I/O)
docs/              Reference documentation
sessions/          Per-session notes and working log
```

## Configuration

All thresholds and hyperparameters live in `ClassifierConfig` (`src/.../config.py`). Key defaults:

| Parameter | Default | Note |
| --- | --- | --- |
| `moisture_threshold` | 0.25 | **Likely needs lowering** for your dataset — see [docs/thresholds.md](docs/thresholds.md) |
| `temp_threshold` | 30.0 °C | Dry label trigger |
| `vpd_threshold` | 20.0 hPa | Dry label trigger |
| `catboost_iterations` | 30 | Override via `--catboost-iterations` |

## Tests

```bash
uv run pytest tests/test_pipeline.py tests/test_data_sources.py -q
```

> `tests/test_moisture_ranges.py` is a diagnostic script — run it directly, not via pytest.

## Docs

| Doc | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | Pipeline flow, data contract, spatial handling |
| [docs/data-sources.md](docs/data-sources.md) | AWRAL/SILO sources, units, placeholders |
| [docs/thresholds.md](docs/thresholds.md) | Threshold guidance and calibration strategy |
| [docs/cli-reference.md](docs/cli-reference.md) | All CLI flags |
| [docs/risk-model.md](docs/risk-model.md) | Stress index formula, risk bands |
| [docs/backlog.md](docs/backlog.md) | Open issues and next steps |
| [CHANGELOG.md](CHANGELOG.md) | Per-sprint changes |
