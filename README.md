# Soil Moisture Trio

A deterministic drought-risk pipeline combining AWRA-L soil-moisture percentile ranks, SILO maximum temperature and vapour-pressure deficit. It produces Low / Watch / Alert / Critical risk maps, summary JSON, PNG figures and Markdown bulletins.

The separate SLGA static-soil builder is experimental. Operational runs do not load soil context. Current work and approval boundaries live in the [backlog](docs/backlog.md).

## Setup

Requires Python 3.12+, `uv`, and network access to NCI THREDDS and public SILO S3 for live runs.

```bash
uv sync --frozen --group dev
```

## Quick start: SWAZ

Obtain the approved DPIRD boundary and place it at `data/south_west_agricultural_boundary.gpkg`. It is locally supplied, not redistributed. See [local data](data/README.md).

```bash
uv run python main.py \
  --year 2026 \
  --start-date 2026-03-01 \
  --end-date 2026-03-23 \
  --output-dir outputs/risk_2026_mar_SWAZ \
  --risk-output-prefix risk_2026_mar_SWAZ \
  --risk-plot-path risk_2026_mar_SWAZ.png \
  --boundary-gpkg data/south_west_agricultural_boundary.gpkg
```

Then render a bulletin:

```bash
uv run python scripts/render_bulletin.py \
  --summary-json outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ_summary.json \
  --map-png outputs/risk_2026_mar_SWAZ/risk_2026_mar_SWAZ.png \
  --output outputs/risk_2026_mar_SWAZ/bulletin_2026_mar_SWAZ.md \
  --region "South West Agricultural Zone"
```

The default cache persists under `~/.cache/soil_moisture_trio/silo/`, keyed by bounds, buffer and overview. Every requested day must be present. Missing files fail the run, a missing daily value invalidates that cell, and COG errors do not silently switch data sources. For live runs, keep the end date at least two days behind today. Full input rules: [data sources](docs/data-sources.md).

## Verification

```bash
uv run --frozen pytest -q
uv run --frozen ruff check
```

Default tests avoid source-service access. The authenticated SLGA check is opt-in. Tests verify implementation, not independent drought-impact skill. `data/` and `outputs/` are gitignored and need backup outside Git.

## Where things live

| Path | Purpose |
|---|---|
| `main.py` | CLI and `run_pipeline(ClassifierConfig(...), output_dir=..., ...)` |
| `src/soil_moisture_trio/{config,pipeline,data_sources,risk,plot}.py` | Validated configuration, daily inputs, risk calculation and figures |
| `src/soil_moisture_trio/slga/` | Separate static-soil retrieval, harmonisation, artifact I/O and checkpoints |
| `scripts/` | Bulletin renderer, moisture diagnostic, bounded SLGA pilot and explicit builder |
| `tests/` | Deterministic regression, failure-path and orchestration tests |

Use the [CLI reference](docs/cli-reference.md) for all flags and build commands, [architecture](docs/architecture.md) for data flow, and [technical report](docs/technical_report.md) for risk methodology. Soil requirements belong to the [evidence review](docs/slga-evidence-review.md) and [builder contract](docs/slga-builder-contract.md). Historical evidence stays in [CHANGELOG](CHANGELOG.md) and `sessions/`.
