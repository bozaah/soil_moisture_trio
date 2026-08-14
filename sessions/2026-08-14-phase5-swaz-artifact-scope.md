# Session — 2026-08-14: Phase 5 static artifact scope changed to SWAZ

## Decision

The first production static SLGA-to-AWRA-L artifact will cover the South West Agricultural Zone (SWAZ) operational rectangle only. A full-WA static artifact will not be built in this phase.

This supersedes the 12 August plan for a 441×341 full-WA artifact. Historical session notes and changelog entries remain unchanged as records of the earlier decision; this note and the 14 August changelog entry record the superseding scope.

## Assumptions and validity conditions

- SWAZ means the approved local `data/south_west_agricultural_boundary.gpkg` used by the documented operational workflow.
- The inspected boundary has five features in EPSG:28350 and SHA-256 `407ce1b536e1391e73677d04e995de8c913d49859c328b3f8904deb92b198b66`.
- Reprojected EPSG:4326 boundary bounds are west 114.10831281, south −35.13552459, east 123.24668541, and north −27.52350348.
- The artifact rectangle follows the pipeline’s existing +0.1° buffered-bbox convention. After the pipeline’s six-decimal rounding, the operational bbox is west 114.008313, south −35.235525, east 123.346685, and north −27.423503.
- Canonical coordinates come only from the already pinned, independently hashed Bureau/NCI AWRA-L v7 `sm_pct_2025.nc` input. Coordinates are selected exactly; they are not rounded, regenerated, or tolerance-matched.
- The SWAZ polygon remains a later runtime centre mask. It does not clip source overlap during static harmonisation and does not redefine full-cell area or source-coverage denominators.
- This scope is valid only while the approved operational boundary matches the pinned hash and bounds. A replacement boundary requires explicit review of the footprint contract.

## Approved artifact footprint

```text
latitude centres:  −27.45 through −35.20, descending (156)
longitude centres: 114.05 through 123.30, ascending (186)
target cells:      156 × 186 = 29,016
```

Provisional artifact path:

```text
data/processed/slga_awral/slga_awc_des_awral_swaz_0p05deg_v1.nc
```

No production artifact was built in this session.

## Updated contract and active documentation

- `manifests/awral_v7_grid_source_v1.json`
- `README.md`
- `AGENTS.md`
- `CHANGELOG.md`
- `docs/architecture.md`
- `docs/backlog.md`
- `docs/cli-reference.md`
- `docs/data-sources.md`
- `docs/slga-builder-contract.md`
- `docs/slga-evidence-review.md`
- `docs/technical_report.md`
- `data/README.md`
- `tests/test_slga_grid.py`

## Preserved boundaries

- No authenticated SLGA run or full-WA artifact build was performed.
- The risk formula, configured thresholds, `risk_valid_mask`, `risk_map`, `stress_index`, existing summaries, and `-1`/`NaN` invalid-cell behavior are unchanged.
- Minimum soil coverage, stratification bands/reference domain, DES uncertainty presentation, grouped-summary policy, distribution/version promotion, and external soil-science approval remain unresolved.
- B24 future rangelands/multi-region work is not fulfilled by the SWAZ-only artifact.

## Next work

Credential-safe profiling instrumentation was completed later in this session and is recorded in [`2026-08-14-phase5-slga-profiling-instrumentation.md`](2026-08-14-phase5-slga-profiling-instrumentation.md). The next live step is a user-approved representative SWAZ coastal/nodata pilot. Production profiling and estimates must target the 29,016-cell SWAZ artifact, not full WA. The SWAZ artifact build remains gated by measured transfer-attempt/retry/cache/memory/runtime evidence, final schema and DES-presentation review, and distribution/version approval.
