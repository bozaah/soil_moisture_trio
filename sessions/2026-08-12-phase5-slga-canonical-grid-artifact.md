# Session — 2026-08-12: canonical AWRA-L grid, artifact I/O, and tiled invariance

## Goal

Resolve the immediate B25b reproducibility blockers without building the full-WA soil artifact or changing any drought-risk behavior:

1. pin an authoritative AWRA-L coordinate source and independent checksum;
2. implement strict local canonical-grid validation;
3. implement/test the provisional deterministic NetCDF writer and credential-free exact-subset runtime loader;
4. implement a bounded tiling seam and prove tile-boundary invariance against the correctness-first overlap engine.

## Assumptions and validity conditions

- A canonical source must be the Bureau-produced operational AWRA-L v7 lineage used by this project, not merely another file with matching 0.05° coordinates.
- A stable remote URL is not itself immutable. The accepted build input is an explicit local byte copy matching a tracked filename, size, and independently computed SHA-256.
- The source coordinates are interpreted as AWRA-L model-grid cell centres. The source supplies no coordinate-bounds variables; target edges continue to be derived from adjacent-centre midpoints and exterior half spacing.
- Synthetic writer/loader and tiling tests establish software behavior, not full-WA source completeness, performance, scientific fitness, or artifact approval.
- No soil bands, coverage threshold, DES uncertainty category, or risk-model parameter was selected.

## Canonical-source decision

Selected:

```text
provider: Bureau of Meteorology
host: NCI THREDDS
product lineage: historical/v1/AWRALv7/processed/deciles/day
file: sm_pct_2025.nc
size: 312193677 bytes
SHA-256: 353af96c7826111a54e189120ed6e1dcb6f9d2a1a0d6966c286aae4f4429095b
HTTP last-modified observed: 2026-07-02T13:09:10Z
```

The complete 2025 operational file was downloaded once from the NCI FileServer and hashed independently. Local inspection established:

- dimensions `time=365`, `latitude=681`, `longitude=841`;
- source variable `sm_pct(time, latitude, longitude)`, float32;
- float64 latitude centres descending from −10 to −44;
- float64 longitude centres ascending from 112 to 154;
- nominal 0.05° spacing with expected binary float variation;
- Bureau/AWRA-L global identity attributes.

`manifests/awral_v7_grid_source_v1.json` pins the file identity, URLs, product/version lineage, schema, global/coordinate attributes, orientation/endpoints, and normalised little-endian float64 coordinate hashes. `slga.grid` requires an explicit matching local file and performs no network access or coordinate regeneration.

Zenodo record 10689080 corroborates the 681×841 coordinates but was rejected as canonical provenance because it is a third-party republication and its record metadata does not identify AWRA-L v7.

## Artifact implementation

Added `slga.artifact` with:

- the seven ordered storage cases from `slga.integration`;
- the provisional compressed/chunked v1 NetCDF schema in `docs/slga-builder-contract.md`;
- exact canonical-coordinate subset validation before writing;
- complete embedded canonical-grid and SLGA source-manifest JSON/provenance;
- explicit scientific limitations and no risk variables;
- temporary write in the destination directory, close-then-schema validation, post-close size/SHA-256, and atomic promotion;
- deterministic sorted/indented/newline-terminated sidecar JSON;
- cleanup if writing or sidecar promotion fails;
- a credential-free runtime loader that verifies filename, version, size, SHA-256, schema, tracked grid/source manifest identities, cross-file metadata, and exact contiguous coordinates before loading a subset into memory.

No production artifact or `data/processed/slga_awral/` directory was created.

## Tiling implementation and proof

Added `slga.tiling` as a bounded orchestration seam:

- target cells are partitioned into disjoint tiles and assigned exactly once;
- each tile derives a clamped source window plus a one-native-pixel halo;
- source arrays are supplied by a callback, allowing the eventual builder to retrieve/integrate only bounded windows;
- global source row/column offsets are passed into `slga.harmonise`, so source polygon vertices and target-edge segmentation use the same global transform regardless of tile boundaries;
- source candidates remain accumulated in stable global row-major order within every target cell;
- no-overlap tiles use a bounded 1×1 border window and return zero coverage/NaN mapped values.

Tests compare tiled output with the untiled engine across 1×1, asymmetric, full-window, forward, and reverse tile orders. Coordinates, full-cell area, means, mapped dispersion, valid area, and coverage are exactly equal, including variable-specific nodata. Complete valid-source area reconciles to full target-cell area. A source pixel may legitimately contribute different fractional intersections to adjacent target cells; it is not duplicated within a target-cell accumulation.

This proves numerical partition invariance for the in-memory synthetic reader. It does not yet prove acceptable full-WA memory/runtime or prevent repeated HTTP transfer of overlapping COG internal blocks. Production tile size, the 18-source retrieve/integrate callback, and COG-block cache/reuse remain gates.

## Tests and failure coverage

New deterministic tests cover:

- missing, renamed, corrupt, checksum-mismatched, schema-drifted, reordered, and off-grid canonical inputs;
- exact source orientation and coordinate hashes;
- artifact missing/corrupt/checksum/schema/version/source-manifest/grid-contract mismatch;
- malformed values, incomplete source retrieval provenance, non-UTC timestamps, and compatibility with the live reader's ISO-8601 `+00:00` UTC timestamps;
- exact contiguous runtime subsets and reordered/off-grid rejection;
- credential-free runtime loading;
- interrupted NetCDF writes and failed sidecar promotion cleanup;
- repeated numerical output;
- bounded windows, no overlap, reader-contract failures, target assignment, tile-size invariance, and tile-order invariance.

## Verification

```text
uv lock --check       -> succeeds
uv run pytest -q      -> 77 passed, 1 skipped
uv run ruff check .   -> All checks passed!
ruff format --check   -> 19 files already formatted
git diff --check      -> passes
```

A path-level diff check confirms no changes to `main.py`, `config.py`, `pipeline.py`, `risk.py`, `data_sources.py`, bulletin templates, or rendering scripts. Existing risk calculations, thresholds, masks, summaries, and outputs remain unchanged.

## User decisions and authenticated tiled pilot

The user approved these continuation decisions:

- full-WA artifact footprint: inclusive exact AWRA-L centres latitude −13 through −35 in source-descending order and longitude 112 through 129 in source-ascending order;
- footprint shape: 441×341 = 150,381 cells, now tracked in `manifests/awral_v7_grid_source_v1.json`;
- retain the implemented artifact schema unchanged and provisional for the pilot;
- proceed with a bounded multi-tile SWAZ pilot, not a full-WA build.

Implemented `slga.builder` and `scripts/slga_tiled_pilot.py`:

- each target tile requests all 18 exact common-grid pixel windows;
- COG reads are expanded/aligned to internal blocks and retained in a bounded in-memory LRU cache;
- each native window is validated, integrated to seven storage cases, then harmonised;
- the script requires the independently verified local canonical input, enforces exact source-coordinate endpoints and a maximum target-cell safety limit, and writes diagnostic JSON only;
- optional opposite-order verification reruns from the cache and requires exact equality for all artifact arrays.

Authenticated pilot footprint:

```text
latitude:  -31.95, -32.00, -32.05
longitude: 116.00, 116.05, 116.10
target cells: 9
tile shape: 1×2 (six disjoint target tiles)
logical source-window reads: 108 (6 tiles × 18 layers)
instrumented row-major elapsed: 58.36 s (observed fresh-run range 44.66–71.02 s)
COG window fetches: 72
cache hits/misses: 36/72
opposite reverse-order verification: 1.40 s, exactly equal, 108 cache hits and 0 COG fetches
peak RSS reported by Python resource on macOS: 281,542,656 bytes
retained source cache: 84,934,656 bytes
```

All seven storage cases were finite in all nine cells. EV storage ranged 83.1613–122.2142 mm (mean 98.4392 mm). Variable coverage was 0.986110–1.0 (mean 0.997700). No minimum coverage threshold was applied or inferred. Output: `outputs/slga_b25b_tiled_pilot_3x3_verified.json` (ignored by Git).

The first direct-script invocation failed before network access because `scripts/` was the Python import root; the reproducible invocation is `uv run python -m scripts.slga_tiled_pilot ...`.

## Remaining work

B25b remains open. Before a production full-WA build:

1. review/approve the pinned canonical-grid source contract and approved operational-bbox footprint;
2. review/approve final v1 variables, names, dtypes, chunks, and DES uncertainty presentation after pilot inspection;
3. profile larger tiles/stripes and refine block-level cache reuse using measured HTTP transfer and retry counts, not logical read counts alone;
4. run a larger representative authenticated pilot including nodata/coast and measure memory, transfer, retries, and seam behavior;
5. decide artifact distribution, sidecar publication, version promotion, and rollback;
6. only then run and independently review the full-WA production build.

Soil bands, minimum acceptable coverage, polygon/coastal summary denominators, uncertainty thresholds, and external soil-science approval remain deliberately unresolved.
