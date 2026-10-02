# Session — 2026-08-14: resumable explicit SWAZ artifact command

## Goal

Implement the explicit reviewed SWAZ artifact command and approved failure/restart policy without executing the 29,016-cell build.

## User decisions

- Recovery: resume checksum- and contract-valid 10-row stripes.
- Publication: repo-local ignored immutable review bundle under `data/processed/slga_awral/`.
- HTTP evidence: audited reader/fetch/cache/retry/runtime/memory counters are sufficient; actual transferred bytes remain explicitly unavailable.
- Source object evidence: pinned publisher STAC multihashes plus strict live identity/profile checks are sufficient; do not download and independently hash all 18 full COGs.

## Build contract

The command is:

```bash
uv run python -m scripts.slga_build_swaz_artifact \
  --awral-grid-input data/source_inputs/sm_pct_2025.nc \
  --max-runtime-seconds 21600
```

Hard-scoped settings:

```text
artifact footprint: 156×186 SWAZ canonical cells
stripe rows:         10 (16 stripes; final stripe 6 rows)
target tile:         10×10
reader cache:        256 MiB
logical reads:       304 tiles × 18 sources = 5,472 before exact-window reuse
default work limit:  6 hours, checked between completed stripes
```

The command requires a clean Git worktree and records the exact 40-character Git commit plus installed project version. This prevents a resumed build from silently mixing code revisions.

## Checkpoint implementation

Added `src/soil_moisture_trio/slga/checkpoint.py`:

- each stripe is written to a new staging directory as compressed NumPy arrays plus a deterministic JSON manifest;
- data SHA-256 and byte size are recorded and verified;
- identity binds artifact contract/version, builder commit/version, canonical grid ID/hash/source hash, source manifest ID/hash, complete SWAZ coordinate hashes, stripe size, target tile, and cache budget;
- provenance retains source retrieval timestamps, reader counter deltas/snapshot, source logical reads, tile metrics, stripe rows, and elapsed time;
- no credential or authorization value is serialized;
- staging is renamed to a fail-if-present immutable stripe directory only after validation;
- resume re-verifies identity, checksum, exact expected coordinates, and array schema;
- assembly requires contiguous stripe indexes, identical longitudes, and exact reconciliation to the full canonical latitude axis.

Unexpected checkpoint-root entries fail rather than being deleted or ignored. A process crash may leave a staging directory; this is surfaced as unexpected state for explicit inspection.

## Build command behavior

Added `scripts/slga_build_swaz_artifact.py`:

1. rejects an existing final bundle;
2. requires a clean readable Git worktree;
3. byte-validates the explicit pinned local AWRA-L input;
4. derives only the tracked approved SWAZ footprint;
5. verifies/resumes each existing stripe or builds and atomically checkpoints a missing stripe;
6. stops between stripes after the approved work limit, retaining completed checkpoints;
7. combines only exact complete stripe coverage;
8. publishes NetCDF, sidecar, and `build_report.json` as one immutable staged bundle;
9. records the build report’s size/SHA-256 in the sidecar and verifies it on runtime load;
10. removes completed checkpoints only after bundle verification unless `--keep-checkpoints` is supplied.

The build report records per-stripe provenance, aggregate reader counters, process peak RSS, exact build identity/settings, source-hash policy, and `http_transfer_bytes: null` with the approved explanation.

## Failure behavior

- Missing key or source failure: current stripe fails; earlier immutable stripe checkpoints remain.
- Runtime limit: checked before starting another stripe; the completed current stripe remains.
- Contract/code/settings drift: resume fails before mixing data.
- Corrupt/missing checkpoint bytes: resume fails with checksum/schema evidence.
- Existing bundle: build fails before authenticated work.
- Bundle staging/promotion failure: staging is cleaned; prior immutable bundles are untouched; completed checkpoints remain until successful publication.
- Successful publication: checkpoint cleanup occurs last.

## Tests

Added deterministic tests for:

- checkpoint write/load and exact two-stripe assembly;
- identity, coordinate, byte-size/checksum drift;
- failed checkpoint promotion cleanup;
- clean versus dirty Git worktree enforcement;
- between-stripe runtime-stop messaging;
- unexpected checkpoint entries;
- checksummed additional build-report files in immutable bundles.

## Verification

```text
uv lock --check             -> succeeds
uv run pytest -q            -> 91 passed, 1 skipped
uv run ruff check .         -> All checks passed
focused ruff format --check -> 17 files already formatted
git diff --check            -> passes
changed Markdown links      -> resolve
```

The repository-wide formatting baseline remains unchanged; only focused modified Python files were checked.

## Scope preserved

The production command was **not run**. No SWAZ artifact exists or is approved. No full-WA static artifact will be built in this phase. Risk calculations, thresholds, masks, summaries, and invalid-cell behavior remain unchanged.

## Remaining release gates

- external soil-science review of direct DES terminology, shallow-profile fraction, mixed scenarios, and fitness for SWAZ use;
- internal distribution location/review authority and explicit permission to execute the review build;
- post-build independent bundle/schema/checksum/coverage review before operational integration;
- minimum soil coverage, soil bands, uncertainty categories, and B14a/B25c grouped summaries remain later science decisions.
