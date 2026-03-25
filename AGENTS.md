# Soil Moisture Trio — Agent Context

Rule-based drought risk monitoring pipeline. Classifies Australian grid cells into Low / Watch / Alert / Critical using AWRA-L `sm_pct` percentile rank (NCI THREDDS), SILO maximum temperature, and SILO VPD. Outputs: NetCDF risk map, summary JSON, PNG figures, Markdown bulletin, optional Folium HTML.

## Tech Stack

Python · xarray · rioxarray · pydantic · jinja2 · folium · scipy · `uv`

## Key Files

| File | Role |
| --- | --- |
| `main.py` | argparse CLI entrypoint |
| `src/.../config.py` | `ClassifierConfig` — Pydantic, all tunable params |
| `src/.../pipeline.py` | `DryWetClassifierPipeline` — loading, valid-mask, risk assessment |
| `src/.../data_sources.py` | `WeatherToolsSiloLoader` — SILO COG/NetCDF + persistent bbox-keyed cache |
| `src/.../risk.py` | Composite stress index, `RiskLevel` enum, NetCDF/JSON output |
| `src/.../plot.py` | PNG outputs (risk map + diagnostics) |
| `src/.../visualize.py` | Folium HTML map |
| `templates/bulletin_template.j2` | Jinja2 Markdown bulletin template |
| `scripts/render_bulletin.py` | CLI: `--summary-json`, `--map-png`, `--output` |
| `tests/` | pytest suite — mock `_load_all_real_data` for speed |

## Docs

- [technical_report.md](docs/technical_report.md) — full methodology: data sources, stress index formula, scientific rationale for all thresholds and weights
- [architecture.md](docs/architecture.md) — pipeline flow, data contract, spatial handling
- [data-sources.md](docs/data-sources.md) — AWRAL/SILO URLs, units, cache details
- [cli-reference.md](docs/cli-reference.md) — all CLI flags + example run
- [backlog.md](docs/backlog.md) — open issues, next steps

## Operational Notes

**SILO cache:** defaults to `~/.cache/soil_moisture_trio/silo` — persistent and created automatically. Different bounding box runs must use separate cache dirs (B22 — cache key does not include bbox):

```bash
--silo-cache-dir ~/.cache/soil_moisture_trio/silo_swaz
```

**Output subdirectory convention** — use `--output-dir` to keep all run files together:

```bash
--output-dir outputs/risk_2026_mar_SWAZ \
--risk-output-prefix risk_2026_mar_SWAZ \
--risk-plot-path risk_2026_mar_SWAZ.png
```

All outputs (`.nc`, `_summary.json`, risk PNG, `stress_diagnostics.png`) land in the specified dir. Bulletin should be rendered to the same dir so the PNG reference is a relative path that VSCode preview can resolve.

**SWAZ operational run** (Southwest Agricultural Zone, recommended for WA work):

```bash
--min-lat -35 --max-lat -27 --min-lon 114 --max-lon 123
```

**Full WA run** (includes northern rangelands):

```bash
--min-lat -35 --max-lat -13 --min-lon 112 --max-lon 129
```

**SILO data lag:** SILO tiles are typically available with a 1–2 day lag. Always set `--end-date` to at most 2 days before today or the pipeline will fail with shape-mismatch errors on missing future tiles.

## Session History

- [CHANGELOG.md](CHANGELOG.md) — per-sprint changes
- [sessions/2026-03-18-session-01.md](sessions/2026-03-18-session-01.md) — docs hygiene + code audit
- [sessions/2026-03-18_q2-wa-verification.md](sessions/2026-03-18_q2-wa-verification.md) — Q2 2025 WA run + regression checks
- [sessions/2026-03-18_2026-ytd-run.md](sessions/2026-03-18_2026-ytd-run.md) — Jan–Mar 2026 WA run; AWRAL unit change noted; cache location documented
- [sessions/2026-03-23-decile-calibration.md](sessions/2026-03-23-decile-calibration.md) — Sprint 6: switch to decile product; B1/B3 resolved; calibration baseline downloaded
- [sessions/2026-03-25-sprint7-persistent-cache-bulletin.md](sessions/2026-03-25-sprint7-persistent-cache-bulletin.md) — Sprint 7: persistent cache, bulletin template, moisture_threshold recalibration
- [sessions/2026-03-25-sprint8-plot-output-fixes.md](sessions/2026-03-25-sprint8-plot-output-fixes.md) — Sprint 8: bulletin PNG path fix, south y-axis buffer, SM histogram, --output-dir flag

## First Principles

Before writing any code:

1. State your assumptions explicitly.
2. Do not claim correctness you haven't verified.
3. Do not handle only the happy path — consider missing data, edge cases, and failure modes.
4. Ask: *under what conditions does this work?*

## Agent Directives

- Use `ClassifierConfig` for all new parameters. Never hardcode thresholds.
- Use `uv run ...` / `.venv` — do not create custom environments.
- Keep `tests/` updated; mock `_load_all_real_data` for unit tests; do not hit real network.
- NaN cells must be masked out (not imputed); preserve `-1` sentinel through all outputs.
- Prefer `logging` over `print` for any new code.
- Decision-support outputs must use risk thresholds from `ClassifierConfig`.
- Check `docs/backlog.md` for known issues before changing thresholds or model parameters.
- SILO end dates must be ≤ today − 2 days to avoid missing-tile shape errors (SILO data lag).
