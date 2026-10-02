# 2026-08-31 — SWAZ review-build gate waived (review-input only)

## Request

Build the SWAZ SLGA artifact to show Karen Holmes and Dennis van Gool, so they can assess SLGA AWC/DES
fitness for WA and redirect the project onto a WA-specific soil product if appropriate.

## The conflict

Two documents forbid running the build:

- `docs/cli-reference.md`: "The command is implemented but must not be run until external soil-science
  and distribution review explicitly approves the SWAZ review build."
- `docs/backlog.md` B25b: external soil-science review, distribution/review-authority approval, and
  explicit permission to execute the SWAZ review build — all incomplete.

The named reviewers are Karen Holmes and Dennis van Gool. The artifact is the input to their review.
**Held literally, the gate blocks the conversation it exists to inform.**

## Decision

**Rodrigo waived the gate on 2026-08-31 for a review-only build.** Recorded in the personal-assistant
repo at `operations/decisions/2026-08-31-slga-swaz-review-build-waiver.md`.

Scope of the waiver:

- The artifact is a **review input**. It is **not** approved for distribution, promotion, or
  operational use.
- `docs/cli-reference.md` and `docs/backlog.md` B25b are **not** amended — the gate still stands for
  every other purpose. This is a single named exception, not a rescinded rule.
- The distribution/release approvals in `docs/slga-evidence-review.md` §18 items 4 and 7 are untouched
  and still required before anything is promoted.

## Why this does not create the risk the gate guards

The gate exists to stop an unreviewed soil product being treated as operational. **No code path can do
that.** `main.py` exposes no SLGA flags; `pipeline.py`, `config.py` and `data_sources.py` contain no
SLGA references; and the grouped-summary layer (B14a/B25c) that would join soil strata to risk output
is unimplemented. The artifact cannot reach a drought output without new code being written first.

## Command

```bash
uv run python -m scripts.slga_build_swaz_artifact \
  --awral-grid-input data/source_inputs/sm_pct_2025.nc \
  --max-runtime-seconds 21600
```

Run by Rodrigo. Prerequisites verified 2026-08-31: `TERN_API_KEY` present; grid input SHA-256 matches
the pin in `manifests/awral_v7_grid_source_v1.json` (312,193,677 bytes, `353af96c…`); worktree clean so
`_require_clean_git_commit()` passes; `data/processed/slga_awral/` absent so the fail-if-present bundle
check will not trip.

Build stamped `builder_commit` on `dev` (`0713eba`), which is not on `main` — PR #1 open.

## Expected outcome

Either Karen and Dennis accept SLGA AWC/DES for WA use — then seek distribution approval properly and
the waiver lapses — or they redirect to a WA-regional PAWC product, which `docs/slga-evidence-review.md`
§18 already anticipates as a benchmark that would change the recommendation. In that case the manifest
is re-pinned and this artifact is retired.

## Manual gate

The artifact must be presented to Karen and Dennis as a review input, explicitly. It must not be
distributed or loaded into an operational run under this waiver.
