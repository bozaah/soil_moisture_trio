# Session — 2026-08-12: Phase 5 backlog and SLGA architecture planning

## Goal

Clarify which open backlog items are central to the next scientific phase, assess the internal `SLGApy` package, and choose an SLGA integration direction before selecting products or writing implementation code.

## Assumptions

- Soil-property stratification is the immediate scientific direction and supports the SSA 2026 work.
- Phase 5 adds interpretation and grouped summaries around existing per-cell drought-risk outputs.
- Phase 5 must not change the stress formula, configured thresholds, categorical risk assignment, or existing risk valid mask.
- Exact SLGA properties, depths, uncertainty components, band definitions, and aggregation statistics require scientific review and remain undecided.
- Approved WA-specific digital soil maps may follow SLGA but are not part of the first implementation.

## Backlog triage decision

The former undifferentiated future backlog was reorganised as follows:

- **Now:** B25 soil-property stratification and B14a generic grouped summaries.
- **Next:** B23 seasonal calibration and B24 multi-region support.
- **Later:** B15 trend analysis and B16 persistent hotspots.
- **Conditional / parked:** B20 machine learning, pending independent labelled outcomes and spatial validation data.
- **Engineering optimisation:** B19 asynchronous loading, pending evidence from profiling.

B25 was split into scientific design, enabling implementation, an initial deliberately small product, and validation. B14a remains generic so the same aggregation machinery can later support soil groups, administrative regions, NRM regions, and catchments.

## `SLGApy` assessment

Repository checks established that `SLGApy` is not currently part of Soil Moisture Trio:

- it is absent from `pyproject.toml` and `uv.lock`;
- it is not installed in this project's virtual environment;
- neither `SLGApy` nor `slgapy` is importable here.

A sibling checkout exists at `../SLGApy`, tracking `DPIRD-FSI/SLGApy` at commit `30b087de6f2d69f198af29efee70260a5a1c8fbb`. Its deterministic test suite passed with `90 passed, 9 deselected`. The checkout contained unrelated local changes and was inspected only; it was not modified.

`SLGApy` is useful as a reference and exploratory tool for metadata discovery, authenticated COG access, spatial subsetting, and grid matching. However, direct adoption raised several concerns for this project:

- its general API and dependency surface are broader than required;
- product shorthand and documentation do not fully match current validation behaviour;
- metadata contains multiple versions, resolutions, depths, modelled values, and confidence-limit components, so generic labels such as “SLGA v2” are not reproducible enough;
- generic bilinear matching or COG overview reads do not by themselves define a scientifically defensible 90 m to AWRA-L aggregation;
- Soil Moisture Trio needs explicit control over coverage, nodata, provenance, uncertainty, and reconciliation with the existing risk domain.

## Architecture decision

Build the smallest practical project-owned SLGA module after the B25a scientific contract is approved. Do not add `SLGApy` as a production dependency at this stage and do not recreate a general-purpose SLGA client or CLI.

The local implementation should have three narrow responsibilities:

1. **Approved product catalogue**
   - Include only scientifically approved full product identifiers.
   - Record property, depth, units, component, version/current-version status, native resolution, stable source, citation, and licence.
   - Never silently select a newer product or resolve an ambiguous shorthand code.

2. **SLGA COG access adapter**
   - Read only the required spatial window for the analysis geometry.
   - Support TERN authentication through `TERN_API_KEY` without persisting credentials.
   - Preserve source nodata and validate the returned CRS, transform, shape, units, expected range, and metadata.
   - Follow project cache conventions if caching is introduced.
   - Return source values and provenance; do not define soil bands or alter drought risk.

3. **Explicit harmonisation and stratification layer**
   - Aggregate or align source SLGA predictions to the exact AWRA-L target grid using the property-specific method approved in B25a.
   - Do not assume bilinear sampling is scientifically equivalent to area aggregation.
   - Calculate and retain source coverage for each AWRA-L cell.
   - Apply approved continuous bands or derived groups only after harmonisation.

All new runtime choices must be represented through `ClassifierConfig`; scientific thresholds or product choices must not be hidden as implementation constants. A small static approved-product catalogue may hold immutable source metadata once the products are selected.

## Masking and output invariant

SLGA availability must not modify the existing drought classification mask.

Conceptually:

```text
risk_valid_mask   = existing finite-input and boundary mask
soil_summary_mask = risk_valid_mask AND acceptable SLGA coverage
```

Consequences:

- the original per-cell `risk_map` remains bit-for-bit unchanged;
- missing soil data does not convert valid risk cells to `-1`;
- soil-stratified summaries expose covered and uncovered portions of the risk domain;
- grouped totals reconcile against the unstratified summary using explicit denominators;
- material soil coverage gaps are reported rather than silently dropped.

## Testing strategy

- Unit tests mock all network access and use small deterministic rasters.
- Tests cover nodata, partial coverage, CRS/grid mismatch, non-overlap, invalid metadata, authentication failure, and aggregation edge cases.
- Regression tests prove that enabling soil summaries does not alter `risk_map`, `stress_index`, or the existing valid mask.
- One small authenticated live COG check may be added as an opt-in integration test gated by an environment variable and `TERN_API_KEY`.
- If Rasterio is imported directly by project code, declare it as a direct dependency and lock it with `uv`.

## Conditions and limitations

- This session selected an architecture, not SLGA products or scientific bands.
- Confidence intervals are available for many candidate products and must be considered during fitness-for-purpose assessment rather than automatically ignored.
- The project will own maintenance of authentication, COG access, nodata handling, source changes, and harmonisation behaviour; keeping the module deliberately narrow is the control on that cost.
- No source code, dependencies, risk parameters, or outputs were changed in this session.

## Next step

Ground B25a product selection in scientific purpose and leverage. For each candidate property, evaluate its causal relevance to drought response, depth compatibility with AWRA-L root-zone moisture, redundancy with other properties, uncertainty availability, spatial coverage, units, current product/version status, and whether the resulting strata are interpretable for decision support. Only then define the first approved product set and acceptance criteria.
