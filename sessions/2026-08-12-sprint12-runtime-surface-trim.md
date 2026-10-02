# Session — 2026-08-12: Sprint 12 runtime surface trim

## Goal

Complete cleanup Phase 2 by removing two unsupported surfaces: the raw soil-moisture compatibility path and the optional Folium HTML renderer. Preserve the SILO NetCDF fallback.

## Decisions

- AWRA-L `sm_pct` percentile ranks are mandatory. The raw-values product is scientifically non-equivalent and must not be substituted.
- Operational outputs are NetCDF, JSON, PNG risk/diagnostic figures, and Markdown bulletin.
- Interactive Folium HTML is not a supported product.
- The SILO weather-tools COG loader retains its annual NetCDF fallback because both paths provide the same atmospheric variables and units.

## Changes

- Removed `allow_legacy_sm` from `ClassifierConfig`, `run_pipeline()`, argparse, tests, and active documentation.
- Removed the legacy AWRAL URL, normalization method, and fallback branch from `pipeline.py`.
- Retained a clear `RuntimeError` when the required decile product cannot be loaded.
- Removed `visualize.py`, its regression test, Folium CLI arguments, and Folium from dependencies.
- Regenerated `uv.lock`, removing Folium, Branca, and xyzservices.
- Removed the now-unused `RISK_SUMMARY_ORDER` constant.
- Updated the remote moisture diagnostic to inspect the required decile product and fail when values are outside the expected 0–1 scale.
- Updated README, AGENTS, architecture, data-source, CLI, risk-model, threshold, technical-report, backlog, and changelog content.

## Verification

- `uv sync --frozen --group dev` succeeded.
- `uv run pytest -q` resulted in `14 passed`.
- `uv run ruff check` resulted in `All checks passed!`.
- `git diff --check` succeeded.
- `main.py --help` contains neither `--allow-legacy-sm`, `--visualize`, nor `--output-path`.
- `main.py --help` still exposes `--use-silo-cog-loader` and `--no-silo-cog-loader`.
- Active code and reference docs contain no retired fallback URL or Folium implementation references; the backlog retains a short historical note explaining B7's retirement.

## Conditions and limitations

- No live remote run was performed; the supported decile loading path and risk computation were not changed.
- If NCI THREDDS or the required annual decile dataset is unavailable, the pipeline now stops rather than changing scientific semantics.
- Historical changelog and session notes from earlier sprints still describe the removed features as part of repository history.
