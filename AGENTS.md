# Soil Moisture Trio — Agent Context

Rule-based pipeline classifying Australian grid cells as dry or wet using AWRAL `sm_pct` (NCI THREDDS), SILO temperature, and SILO VPD. Outputs: categorical risk map (NetCDF), summary JSON, PNG, optional Folium HTML.

## Tech Stack

Python · xarray · rioxarray · pydantic · folium · scipy · `uv`

## Key Files

| File | Role |
| --- | --- |
| `main.py` | argparse CLI entrypoint |
| `src/.../config.py` | `ClassifierConfig` — Pydantic, all tunable params |
| `src/.../pipeline.py` | `DryWetClassifierPipeline` — loading, rule-based classify, prediction |
| `src/.../data_sources.py` | `WeatherToolsSiloLoader` — SILO COG/NetCDF + cache |
| `src/.../risk.py` | Physics-based stress index, `RiskLevel` enum, file output |
| `src/.../plot.py` | PNG outputs (risk map + diagnostics) |
| `src/.../visualize.py` | Folium HTML map |
| `tests/` | pytest suite — mock `_load_all_real_data` for speed |

## Docs

- [architecture.md](docs/architecture.md) — pipeline flow, data contract, spatial handling
- [data-sources.md](docs/data-sources.md) — AWRAL/SILO URLs, units, NDVI placeholder status
- [thresholds.md](docs/thresholds.md) — classification thresholds, known calibration issue
- [cli-reference.md](docs/cli-reference.md) — all CLI flags + example run
- [risk-model.md](docs/risk-model.md) — stress index formula, risk bands, outputs
- [backlog.md](docs/backlog.md) — open issues, next steps

## Operational Notes

**Always pass explicit bounds when running for WA** — the default config covers all of Australia (slow, ~8 min). Standard WA bounds:

```bash
--min-lat -35 --max-lat -13 --min-lon 112 --max-lon 129
```

## Session History

- [CHANGELOG.md](CHANGELOG.md) — per-sprint changes
- [sessions/2026-03-18-session-01.md](sessions/2026-03-18-session-01.md) — docs hygiene + code audit
- [sessions/2026-03-18-session-02.md](sessions/2026-03-18-session-02.md) — CatBoost removal decision
- [sessions/2026-03-18_q2-wa-verification.md](sessions/2026-03-18_q2-wa-verification.md) — Q2 2025 WA run + regression checks
- [sessions/2026-03-18_2026-ytd-run.md](sessions/2026-03-18_2026-ytd-run.md) — Jan–Mar 2026 WA run; AWRAL unit change noted; cache location documented

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
- Check `docs/backlog.md` for known issues before changing thresholds or ML features.
