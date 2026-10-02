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

Run the classifier for a recent 50-day window. Keep the end date at least two days behind today for SILO publication lag.

```bash
uv run python main.py \
  --year 2026 \
  --start-date 2026-07-25 \
  --end-date 2026-09-13 \
  --output-dir outputs/risk_2026_jul25-sep13_SWAZ_boundary \
  --risk-output-prefix risk_2026_jul25-sep13_SWAZ_boundary \
  --risk-plot-path risk_2026_jul25-sep13_SWAZ_boundary.png \
  --boundary-gpkg data/south_west_agricultural_boundary.gpkg
```

Then render a bulletin:

```bash
uv run python -m scripts.render_bulletin \
  --summary-json outputs/risk_2026_jul25-sep13_SWAZ_boundary/risk_2026_jul25-sep13_SWAZ_boundary_summary.json \
  --map-png outputs/risk_2026_jul25-sep13_SWAZ_boundary/risk_2026_jul25-sep13_SWAZ_boundary.png \
  --output outputs/risk_2026_jul25-sep13_SWAZ_boundary/bulletin_2026_jul25-sep13_SWAZ.md \
  --region "South West Agricultural Zone"
```

### Soil-context grouping (review input only)

With the local SWAZ review bundle present (see the [backlog](docs/backlog.md) for its approval limits), group the run by soil context and render one self-contained HTML page:

```bash
D=outputs/risk_2026_jul25-sep13_SWAZ_boundary
uv run python -m scripts.grouped_soil_context --run-netcdf $D/risk_2026_jul25-sep13_SWAZ_boundary.nc
uv run python -m scripts.render_grouped_summary \
  --grouped-json $D/*_grouped_coverage_split.json $D/*_grouped_awc_terciles.json \
  --output $D/grouped_summary.html \
  --title "SWAZ drought risk, 25 July to 13 September 2026, by soil context" \
  --scope-note "Review input for Karen Holmes and Dennis van Gool under the 2026-08-31 waiver. Not for distribution or operational use." \
  --risk-png $D/risk_2026_jul25-sep13_SWAZ_boundary.png --diagnostics-png $D/stress_diagnostics.png \
  --boundary-gpkg data/south_west_agricultural_boundary.gpkg
```

Grouping never changes per-cell risk. Flags for both scripts: [CLI reference](docs/cli-reference.md).

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
| `src/soil_moisture_trio/grouped_summary.py` | Grouping-agnostic summaries of a finished run, with reconciliation and persisted grouping rasters |
| `src/soil_moisture_trio/slga/` | Separate static-soil retrieval, harmonisation, artifact I/O and checkpoints |
| `scripts/` | Bulletin renderer, soil-context grouping driver, grouped-summary HTML renderer, moisture diagnostic, bounded SLGA pilot and explicit builder |
| `tests/` | Deterministic regression, failure-path and orchestration tests |

Use the [CLI reference](docs/cli-reference.md) for all flags and build commands, [architecture](docs/architecture.md) for data flow, and [technical report](docs/technical_report.md) for risk methodology. Soil requirements belong to the [evidence review](docs/slga-evidence-review.md) and [builder contract](docs/slga-builder-contract.md). Historical evidence stays in [CHANGELOG](CHANGELOG.md) and `sessions/`.
