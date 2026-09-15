# Backlog

Last reviewed: 2026-09-15

This file owns current status and open work. Requirements live in the linked contracts. Completed work and measurements live in [CHANGELOG](../CHANGELOG.md) and `sessions/`, not here.

## Current state

The operational classifier and the separate SLGA builder are implemented. The SWAZ review artifact was built 2026-09-14 under the 08-31 waiver (local, gitignored, not backed up) and covers 100% of the March risk-valid cells. `load_soil_context()` returns it in a run's coordinate order, `summarise_by_group()` aggregates a run by any grouping raster, and `scripts/grouped_soil_context.py` plus `scripts/render_grouped_summary.py` produce a review page with illustrative AWC terciles. Nothing operational calls any of it. No approved soil bands and no soil-stratified result exist; the illustrative tercile grouping is confounded with the zone's rainfall gradient. The accepted SSA2026 abstract promises soil stratification, so talk scope remains a decision for Rodrigo. Details: [session record](../sessions/2026-09-14-swaz-artifact-build-and-context-loader.md).

The 09-11 tightening pass enforces complete daily inputs, explicit percentile units/bounds and matching NetCDF coordinates. COG failures no longer trigger automatic fallback. Builder orchestration tests cover interrupted work, resume, verified publication and cleanup. The risk formula and artifact schema are unchanged. Verification details belong to the [session record](../sessions/2026-09-11-input-builder-tightening.md).

## Now: Phase 5 soil-property stratification

The dependency order is review-input build (done) → Karen + Dennis review → product/bands/coverage decisions → grouped summaries and validation. B14a's grouping-agnostic framework and its reconciliation tests landed 2026-09-15 without the review.

| Item | Remaining work | Contract |
|---|---|---|
| **B25a: product and scientific choices** | Review WA fitness, terminology, DES capping and mixed-quantile uncertainty with Karen Holmes and Dennis van Gool. Confirm or replace SLGA AWC/DES. Specify exact bands, fixed reference domain and minimum coverage. Karen's support for the rationale does not supply these values | [Evidence review](slga-evidence-review.md), especially §§5, 17–18 |
| **B25b: SWAZ review artifact** | Built 2026-09-14 (`63b0e8d9…4b266`, builder commit `42096ae`, 1 h 37 min, peak RSS 1.07 GB). Remaining: back up the bundle outside Git, send it with the evidence review to Karen and Dennis | [Builder contract](slga-builder-contract.md), [command](cli-reference.md#phase-5-slga-development-utilities) |
| **B14a: grouped-summary layer** | Framework built 2026-09-15 (`grouped_summary.py`): any integer grouping raster plus a validity mask, `uncovered` row, named denominators, reconciliation flag, separate JSON output. Remaining: polygon-to-raster grouping input, and wiring a soil grouping once B25a settles bands and coverage | [Architecture](architecture.md#phase-5-static-soil-path--prototype-only) |
| **B25c: first stratified product** | Use the reviewed artifact and approved bands/reference domain to summarise AWC+DES soil-capacity context. Persist the grouping definition. Do not attempt a comprehensive soil taxonomy | [Evidence review](slga-evidence-review.md) |
| **B25d: scientific/output checks** | Done 2026-09-15 for the framework: inputs unmodified, reconciliation asserted, shape/dtype/mask mismatches rejected, real-run test. Remaining for B25c: provenance (bundle SHA, builder commit) and scientific limits carried into the grouped JSON and page, and the spatial-confounding check | [Builder contract](slga-builder-contract.md), [evidence review](slga-evidence-review.md) |

**Build permission:** the general external review/distribution gate remains. Rodrigo's [2026-08-31 exception](../sessions/2026-08-31-swaz-review-build-waiver.md) permits a SWAZ build solely as input to Karen and Dennis's review. It does not authorise distribution, promotion or operational use. Full-WA static soil construction is out of scope.

The build uses the reviewed v1 candidate schema, 10×10 tiles, a 256 MiB cache and checksum-bound 10-row checkpoints. Keep the same clean commit through resume, including documentation. Those settings reflect bounded Albany measurements, not a whole-SWAZ performance guarantee. Do not add external HTTP-byte telemetry or full-object COG downloads without revisiting the existing decisions.

## Next

- **B23: seasonal stress calibration.** Assess bias from systematically higher summer VPD/temperature using historical SILO and the WA percentile baseline. Any change requires scientifically reviewed, configuration-driven thresholds. Keep classification unchanged during Phase 5.
- **B24: rangelands/multi-region support.** A future full-WA download/cache could serve multiple approved boundaries. The SWAZ-only soil artifact does not fulfil this item. Keep the current per-boundary workflow until there is a funded need.

## Later or conditional

- **B15: trends.** Establish stable metadata, comparable periods and retained outputs before comparing years/seasons.
- **B16: persistent hotspots.** Define persistence and missing-period rules after B15, then compare consecutive windows.
- **B20: ML.** Parked until independent labelled impacts exist. Require real predictors, spatial validation and comparison with the deterministic baseline, not labels generated by this classifier.
- **B19: async loading.** Only after profiling shows a material bottleneck. Not part of the Phase 5 scientific deliverable.

Completed B1/B3/B5/B7–B12/B17–B18/B21–B22 history remains in the changelog and dated sessions. Do not carry resolved items as live tasks.
