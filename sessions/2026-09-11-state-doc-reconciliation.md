# 2026-09-11 — State verification and documentation reconciliation

Rodrigo requested a repo-state and documentation check, then approved corrections in this repo and `personal-assistant`. Scope: documentation only. No code changes, artifact build, Git writes or release approval.

## Verified state

Before edits, `dev` was clean at `03d42c9` (31 August), equal to locally recorded `origin/dev`, 20 commits ahead of `main`. Live remote and PR status were not checked.

`uv run --frozen pytest -q`: 91 passed, 1 skipped in 4.90s. The skipped test requires `RUN_SLGA_LIVE_TESTS=1` and `TERN_API_KEY`. `uv run --frozen ruff check`: all checks passed. These are implementation checks, not fresh source-service access or independent validation of drought impacts.

The operational classifier produces NetCDF, JSON, PNG and Markdown bulletins. It does not call SLGA. Static-soil retrieval, harmonisation, immutable artifact I/O and resumable builder machinery exist, but no SWAZ artifact or checkpoints exist locally. B14a/B25c grouped summaries remain unimplemented. Retained results comprise March SWAZ drought bundles and small SLGA engineering pilots. No presentation deck was found.

`data/` and `outputs/` are ignored by Git. Off-machine backup was not verified. A local-link check across 39 tracked Markdown files found five missing references, all in the historical March audit pointing to removed diagnostic/Folium files. Historical audit references remain unchanged.

## Corrections

Active docs now link the [08-31 waiver](2026-08-31-swaz-review-build-waiver.md). The general approval gate remains, with one named exception for review input to Karen Holmes and Dennis van Gool. Distribution, promotion and operational use still require approval. The builder records actual clean HEAD, not the older commit quoted in the waiver's historical command context.

B3 now describes percentile ranks as input normalisation and composite stress thresholds as the classification rule. Build/restart machinery is implemented, not pending design. Exact soil bands, reference domain and coverage rules remain unresolved despite Karen's support for the rationale.

The companion project/state records now use SWAZ-only soil scope and separate grouped summaries rather than full-WA soil construction or changes to `risk.py`. Removed current-state claims for Folium, raw-product compatibility, unresolved B8 and independent scientific/presentation readiness. Historical progress entries remain as recorded with an explicit correction notice.

## Next action

Recheck pinned inputs, credentials and the clean-worktree requirement before Rodrigo runs the review build. These documentation edits require Rodrigo's commit first. Arrange the Karen + Dennis review, then settle product/bands/coverage before implementing grouped summaries. Talk scope remains Rodrigo's decision.
