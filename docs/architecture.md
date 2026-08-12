# Architecture — Soil Moisture Trio

## Pipeline Flow

```text
main.py
  -> build ClassifierConfig from CLI flags
  -> DryWetClassifierPipeline.prepare_data()
       -> optionally derive bbox from --boundary-gpkg (+0.1° buffer)
       -> load AWRAL sm_pct decile product from NCI THREDDS
       -> load SILO max_temp + vp_deficit via weather_tools COG loader
          -> fall back to SILO annual NetCDF if COG loading fails or is disabled
       -> align all grids to ascending AWRAL lat/lon coordinates
       -> clip to requested bounds
       -> build valid mask from finite soil moisture / temperature / VPD cells
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
| `scripts/render_bulletin.py` | Markdown bulletin rendering from summary JSON |

## Data Contract

All analysis grids are 2D `(lat, lon)` arrays after time averaging and spatial alignment.

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

1. `soil_moisture`, `temperature`, and `vpd` are all finite.
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

Config validation requires weights to sum to 1, risk thresholds to be strictly ordered, date windows not to be inverted, and minimum spatial bounds to be less than maximum bounds.

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
- The weather-tools cache is scoped by a hash of the requested bounds under `silo_cache_dir`, which prevents cross-bbox reuse within the same cache root.
- SILO availability still lags by roughly 1 to 2 days, so operational runs should keep `--end-date` at most two days behind today.
