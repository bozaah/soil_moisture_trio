# Session — 2026-08-14: provisional artifact schema and promotion review

## Goal

Review the provisional B25b artifact variables, dtypes, chunks, DES uncertainty presentation, sidecar publication, version promotion, and rollback behavior after bounded SWAZ profiling. Do not build or promote an artifact.

## Assumptions and validity conditions

- The first artifact covers only the approved 156×186 SWAZ rectangle.
- Soil context remains interpretive and separate from risk calculation and masking.
- DES means mapped A- and B-horizon depth, not effective crop rooting depth.
- AWC 05/95 and DES 10/90 mixed scenarios are not a formal confidence interval.
- No minimum coverage threshold, uncertainty category, or soil band may be inferred during this engineering review.
- Artifact version `v1` must mean an approved immutable release, not merely an implemented prototype constant.

## Reviewed implementation

- `src/soil_moisture_trio/slga/artifact.py`
- `tests/test_slga_artifact.py`
- `docs/slga-builder-contract.md`, Sections 5, 8, 9, and 11
- `docs/slga-evidence-review.md`, Sections 9–13 and 17–18

## Findings

### 1. Core storage schema is reasonable

Retain the seven explicit storage cases:

- expected AWC + expected DES;
- AWC-only 05/95 effects with DES EV;
- DES-only 10/90 effects with AWC EV;
- mixed AWC05+DES10 and AWC95+DES90 scenarios.

This is more transparent than exposing only an expected value and one ambiguous width. The storage cases preserve the distinct AWC and DES effects and make the mixed-scenario limitation visible.

The existing representation is suitable for the small SWAZ artifact:

- float32 for mapped storage, mapped dispersion, coverage, and uncertainty widths;
- float64 for full and valid area;
- float64 exact coordinates;
- zlib level 4 with shuffle;
- `(1,64,64)` chunks for case variables and `(64,64)` for grid variables.

At 156×186 cells, these chunks produce a small number of chunks while preserving efficient case/subset reads. Build tile shape and NetCDF storage chunks do not need to match.

### 2. DES companion presentation is incomplete — release blocker

The evidence contract calls DES a required companion and says mapped shallow-soil area should be reportable. The current artifact stores only DES-influenced AWC storage scenarios. It does not persist directly mapped:

- DES EV/10/90 in metres;
- DES mapped-prediction dispersion;
- DES valid area and coverage;
- fraction of valid mapped soil shallower than 1 m.

Without those variables, downstream users cannot distinguish the mapped depth context from its indirect effect on storage or report the shallow-profile support promised by the scientific contract. Adding direct DES variables does not change risk outputs and is preferable before `v1` promotion.

### 3. Mixed-width support is discarded — release blocker

The builder harmonises `mixed_uncertainty_width_mm` as its own variable, correctly using the intersection where the native lower and upper scenarios are both available. `SoilArtifactData` then retains only the mapped mean and drops that variable’s:

- valid source area;
- source coverage fraction;
- mapped-prediction dispersion.

The storage cases may have different valid footprints; common nodata cannot be assumed by contract. A width without its own support is therefore not adequately auditable. Either:

1. retain the mixed width and persist its own valid area, coverage, and mapped dispersion; or
2. omit the standalone width and require downstream paired-scenario treatment with explicit support reconciliation.

Recommended: option 1, because the native intersection width is already computed and scientifically labelled as a proxy rather than a confidence interval.

### 4. Storage-case metadata needs explicit definitions

The artifact stores ordered case labels and a JSON list, but not a machine-readable mapping from each label to:

- AWC component;
- DES component;
- expected/component/mixed interpretation;
- statement that mixed cases are scenarios, not confidence bounds.

Persist the existing `STORAGE_CASE_COMPONENTS` definition plus interpretation labels as canonical JSON and add descriptive attributes to the `storage_case` coordinate.

### 5. Immutable promotion and rollback are unsafe — release blocker

`write_soil_artifact()` currently allows existing artifact and sidecar paths to be replaced. If artifact promotion succeeds and sidecar promotion then fails, cleanup removes the newly promoted artifact. If an older artifact existed at that path, it has already been replaced and is lost while the old sidecar may remain.

For an immutable approved artifact:

- final version paths must fail if already present;
- builds should write into a new versioned staging/bundle directory;
- validate the closed NetCDF and sidecar before publication;
- promote a complete bundle atomically where the filesystem permits, or publish to a new immutable directory and expose it only by an explicitly reviewed external pointer/catalogue step;
- rollback should select the prior immutable bundle, never overwrite it;
- tests must cover pre-existing destinations, interrupted bundle promotion, and preservation of the prior approved release.

The runtime loader already requires explicit artifact and sidecar paths, so a mutable “current” symlink/pointer is not required for Release 1.

### 6. Version status is premature

The code constants and provisional filename say `v1`, while documentation states the schema is unapproved. No production artifact exists, so this can still be corrected without migration. Recommended policy:

- use a release-candidate/provisional contract identifier during remaining implementation tests;
- reserve artifact version `v1` and the final SWAZ filename for the externally reviewed immutable release;
- include schema version, artifact version, builder commit, source/grid contract hashes, and creation/retrieval timestamps in both NetCDF and sidecar as currently designed.

### 7. Runtime validation can be strengthened

The checksum-verifying loader is sound for accidental corruption and tracked-contract drift. Before promotion, schema validation should also assert the approved variable attributes, storage-case definition metadata, encoding/chunk contract where required, and the exact persisted SWAZ footprint against the tracked coordinate contract. The writer currently prevents many malformed states, but explicit runtime checks make the release contract independently auditable.

## Recommended Release 1 schema direction

Keep:

- seven storage scenarios and their mapped dispersion/valid area/coverage;
- full-cell area;
- mixed uncertainty-width proxy, with its own support variables;
- existing dtypes, compression, and 64×64 chunking;
- exact canonical coordinates and complete embedded provenance.

Add before promotion:

- DES EV/10/90 mapped means in metres;
- DES EV/10/90 mapped dispersion, valid area, and coverage;
- valid-source-area fraction with DES <1 m (or equivalently shallow valid area plus DES valid area), explicitly based on the mapped DES prediction and not effective rooting depth;
- mixed-width mapped dispersion, valid area, and coverage;
- canonical machine-readable storage-case definitions and clearer coordinate/variable attributes.

Do not add:

- risk variables;
- coverage classifications or thresholds;
- soil bands;
- a formal confidence-interval label;
- crop-specific rooting or PAWC claims.

## Decisions still required

1. Approve adding direct DES and shallow-profile variables before `v1`, or accept a storage-only artifact with the documented loss of companion context.
2. Approve retaining mixed width with its own support variables, or remove standalone width from Release 1.
3. Approve immutable versioned bundle publication with fail-if-present behavior and rollback by selecting a prior bundle.
4. Decide internal distribution location, review authority, and who records release approval.
5. Obtain soil-science review of DES labels and scenario presentation before final promotion.

## User decisions and implementation follow-up

The user approved:

- direct DES EV/10/90 means, dispersion, valid area/coverage, and valid-DES-area shallow-than-1 m fractions;
- retaining mixed width with its own mapped dispersion, valid area, and coverage;
- immutable fail-if-present bundle publication and rollback by selecting a prior bundle;
- retaining the `v1` label during the remaining approval process rather than reserving it until external review.

Implemented after the review:

- `StorageIntegration` now returns validated raw DES components;
- the tiled builder harmonises direct DES and shallow indicators alongside storage cases and width;
- `SoilArtifactData` and the NetCDF schema retain all approved DES/width values and support;
- canonical storage-case definitions are embedded in global and coordinate metadata;
- low-level destinations fail if present;
- `write_soil_artifact_bundle()` validates a complete staging bundle and renames it to a new immutable directory;
- production artifact coordinates must match the tracked approved SWAZ footprint;
- deterministic tests cover schema round-trip, invalid DES/width values, immutable destinations, successful bundle loading, and failed-promotion cleanup.

The user’s `v1` decision supersedes the review recommendation to reserve that label. The artifact remains unapproved until external soil-science/distribution review and an explicit production build decision.

Verification after implementation:

```text
uv lock --check             -> succeeds
uv run pytest -q            -> 85 passed, 1 skipped
uv run ruff check .         -> All checks passed
focused ruff format --check -> 13 files already formatted
git diff --check            -> passes
changed Markdown links      -> resolve
```

## Scope preserved

No production artifact was built and no risk behavior was modified.
