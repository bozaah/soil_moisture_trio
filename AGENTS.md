# Soil Moisture Trio: agent instructions

Python/xarray drought-risk classifier with a separate experimental SLGA static-soil builder. Use `uv` and the existing environment. Do not introduce a general data platform or change the risk formula while implementing soil summaries.

## Read by task

| Need | Source of truth |
|---|---|
| Setup and quick start | [README](README.md) |
| Current status and open work | [backlog](docs/backlog.md) |
| Commands and build prerequisites | [CLI reference](docs/cli-reference.md) |
| Runtime structure and outputs | [architecture](docs/architecture.md) |
| Input validity, sources and cache | [data sources](docs/data-sources.md) |
| Risk methodology | [technical report](docs/technical_report.md) |
| Soil science and approval limits | [evidence review](docs/slga-evidence-review.md) |
| Static artifact schema and build contract | [builder contract](docs/slga-builder-contract.md) |
| Past work | [changelog](CHANGELOG.md) and `sessions/` |

Keep commands in the CLI reference, scientific requirements in the contracts, open work in the backlog, and dated evidence in sessions. Do not append session indexes or pilot measurements here. Tests bound this file and the backlog to prevent renewed growth.

## Constraints

- State assumptions before changing code. Verify claims and test missing data and failure paths, not just successful runs.
- `ClassifierConfig` owns model parameters and the common date window. `run_pipeline(config, ...)` takes output paths separately.
- Require every requested day. Reject missing/duplicate dates, inconsistent years, unrecognised soil-moisture units and out-of-range percentiles. Never guess a percent conversion or substitute `vp` for `vp_deficit`.
- COG errors must propagate. NetCDF is an explicit alternative and must verify its coordinates against AWRA-L. Keep live end dates at least two days behind today for SILO publication lag.
- A cell missing any requested day/input remains invalid. Preserve `-1` risk and `NaN` stress sentinels. Soil coverage must never change risk validity.
- Phase 5's static artifact is SWAZ-only. Rodrigo's [08-31 waiver](sessions/2026-08-31-swaz-review-build-waiver.md) permits review input for Karen Holmes and Dennis van Gool, not distribution, promotion or operational use.
- Keep a single clean commit throughout build/resume. Checkpoints bind to the whole commit, including documentation. The first build is Rodrigo's to run.
- Default tests must not access source services. Mock network I/O. Authenticated SLGA tests are opt-in.
- Tests establish implementation behaviour, not independent drought-impact skill. Do not claim scientific fitness or talk readiness from a green suite.
- Use logging, not prints. Local `data/` and `outputs/` are ignored and need backup outside Git.

## Git safety

Git access is read-only for the assistant. Never modify the working tree through Git, the index, commits, refs, branches, tags, stashes, remotes or repository configuration.

Do not run `git add`, `commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `restore`, `checkout`, `switch`, `cherry-pick`, `revert`, `stash`, `clean`, `mv`, `rm`, `tag` or mutating `config` operations. Read-only status, diff, log, show, blame, grep, rev-parse and ls-files are allowed. Report suggested Git writes for Rodrigo to run, never execute them. Restore test scaffolding from file copies, never from Git.
