# Architecture — Soil Moisture Trio

## Pipeline Flow

```text
main.py
  -> build one validated ClassifierConfig from CLI flags
  -> run_pipeline(config, output options)
  -> DryWetClassifierPipeline.prepare_data()
       -> optionally derive bbox from --boundary-gpkg (+0.1° buffer)
       -> load AWRAL sm_pct decile product from NCI THREDDS
       -> require every requested daily timestamp and percentile units/bounds
       -> retrieve SILO max_temp + vp_deficit daily files via weather_tools
          -> verify filenames, read each day without suppressing failures
          -> OR use explicitly selected SILO NetCDF, verifying its own coordinates
       -> orient coordinates ascending and verify/regrid against the AWRA-L grid
       -> clip to requested bounds
       -> average complete per-cell daily windows, preserving missing-day exclusions
       -> build valid mask from finite soil moisture / temperature / VPD means
       -> if boundary_gpkg is set, mask out cells outside the polygon
  -> DryWetClassifierPipeline.assess_risk()
       -> compute continuous stress index
       -> assign Low / Watch / Alert / Critical categories
  -> write NetCDF + summary JSON
  -> optionally render risk and diagnostics PNGs
```

## Module Responsibilities

| File | Responsibility |
|---|---|
| `main.py` | argparse CLI and end-to-end orchestration |
| `src/soil_moisture_trio/config.py` | `ClassifierConfig` with all runtime parameters |
| `src/soil_moisture_trio/pipeline.py` | Data loading, spatial alignment, valid-mask construction, risk assessment entrypoint |
| `src/soil_moisture_trio/data_sources.py` | `WeatherToolsSiloLoader` wrapper, bbox-scoped cache directories, regridding |
| `src/soil_moisture_trio/risk.py` | Stress index calculation, `RiskLevel`, NetCDF/JSON persistence |
| `src/soil_moisture_trio/plot.py` | Risk PNG and diagnostics PNG generation |
| `src/soil_moisture_trio/slga/` | Phase 5 static-soil catalogue, COG access, integration, harmonisation, tiling, and reviewed v1-candidate artifact I/O; not called by the operational risk pipeline |
| `scripts/render_bulletin.py` | Markdown bulletin rendering from summary JSON |
| `src/soil_moisture_trio/slga/checkpoint.py` | Credential-free immutable stripe checkpoints and exact stripe assembly for resumable SWAZ builds |
| `scripts/slga_tiled_pilot.py` | Development-only bounded authenticated SLGA pilot with retry/cache/tile/RSS diagnostics; does not write or approve a production artifact |
| `scripts/slga_build_swaz_artifact.py` | Explicit clean-commit-only SWAZ builder: 10-row resumable stripes, 10×10 tiles, 256 MiB cache, reviewed immutable bundle publication |

## Phase 5 Static-Soil Path — Prototype Only

The SLGA work is deliberately separated from `main.py` and the operational risk flow:

```text
explicit pinned AWRA-L v7 grid file
  + tracked 18-source SLGA AWC/DES manifest
  -> strict canonical-grid and source-profile validation
  -> authenticated bounded full-resolution COG windows
  -> native-grid DES-capped AWC storage integration
  -> bounded EPSG:3577 fractional-overlap harmonisation
  -> SoilArtifactData
  -> atomic checksum-bound 10-row stripe checkpoints
  -> exact full-SWAZ stripe assembly
  -> immutable staged v1-candidate NetCDF + sidecar + build-report bundle

future operational soil context:
approved immutable artifact
  -> credential-free checksum/schema-verifying loader
  -> exact contiguous AWRA-L coordinate subset
  -> separate soil-summary mask and grouped summaries
```

Normal drought runs never retrieve, rebuild or load SLGA data. The builder targets the SWAZ rectangle, not full WA. Artifact requirements and measured pilot limits belong to the [builder contract](slga-builder-contract.md). Current completion/approval status belongs to the [backlog](backlog.md).

The invariant for later integration is:

```text
risk_valid_mask   = existing finite-input and boundary mask
soil_summary_mask = risk_valid_mask AND approved soil-coverage rule
```

Missing soil data must not alter `risk_map`, `stress_index`, the risk valid mask, or existing risk summaries. See [`slga-builder-contract.md`](slga-builder-contract.md) for the complete provisional contract.

## Data Contract

All operational risk-analysis grids are 2D `(lat, lon)` arrays after time averaging and spatial alignment.

| Variable | Source | Units | Notes |
|---|---|---|---|
| `soil_moisture` | AWRAL `sm_pct` decile product | percentile rank 0–1 | Required input; the pipeline fails if the percentile-rank product is unavailable |
| `temperature` | SILO `max_temp` | °C | Time-averaged over selected window |
| `vpd` | SILO `vp_deficit` | hPa | Time-averaged over selected window |
| `lats` | AWRAL coordinates | degrees north | Returned ascending |
| `lons` | AWRAL coordinates | degrees east | Returned ascending |
| `time_metadata` | Combined across loaders | ISO datetime strings | `time_start` / `time_end` |

## Valid-Cell Rules

`prepare_data()` marks a cell valid only when:

1. `soil_moisture`, `temperature`, and `vpd` have finite means over every requested day. A missing/nonfinite daily value makes that cell's mean NaN.
2. The cell falls inside the optional boundary polygon when `--boundary-gpkg` is used.

Invalid cells are never imputed. They propagate as:

- `False` in `valid_mask_grid`
- `-1` in `risk_map`
- `NaN` in `stress_index`
- excluded from risk percentages

## Risk Assessment

`assess_risk()` delegates to [`src/soil_moisture_trio/risk.py`](../src/soil_moisture_trio/risk.py), which computes:

```text
dryness   = clip((moisture_threshold - soil_moisture) / moisture_threshold, 0, 1)
temp_fac  = clip(temperature / critical_temp_threshold, 0, 1)
vpd_fac   = clip(vpd / critical_vpd_threshold, 0, 1)

stress_index = dryness_weight * dryness
             + vpd_weight * vpd_fac
             + temperature_weight * temp_fac

Default weights: 0.60 / 0.25 / 0.15
```

Risk bands use validated `ClassifierConfig` thresholds. Defaults are:

| Stress index | Risk level |
|---|---|
| `< 0.35` | Low |
| `0.35–<0.60` | Watch |
| `0.60–<0.85` | Alert |
| `>= 0.85` | Critical |

Config validation requires weights to sum to 1, ordered risk thresholds, an ordered date window within the retrieval year, exactly the two supported SILO variables, and ordered spatial bounds. Input validation before averaging follows [data sources](data-sources.md).

## Output Contract

| Artifact | Format | Notes |
|---|---|---|
| `{prefix}.nc` | NetCDF | `risk_level` with lat/lon coords; summary, model parameters, and time metadata in attributes |
| `{prefix}_summary.json` | JSON | Per-category statistics, time metadata, and the run's model parameters |
| `risk PNG` | PNG | Two-panel categorical map + continuous stress index |
| `stress_diagnostics.png` | PNG | Soil-moisture histogram and soil-moisture vs VPD scatter |
| bulletin `.md` | Markdown | Rendered separately via `scripts/render_bulletin.py` |

## Operational Notes

- `--output-dir` is the recommended run layout. When set, `--risk-output-prefix` and `--risk-plot-path` are interpreted as basenames inside that directory.
- `--boundary-gpkg` is the preferred way to run named regions such as SWAZ. It derives the bbox automatically and applies a polygon mask after loading.
- The weather-tools cache identity includes bounds, buffer and overview under `silo_cache_dir`. COG failures propagate without automatic NetCDF fallback.
- SILO availability still lags by roughly 1 to 2 days, so operational runs should keep `--end-date` at most two days behind today.
