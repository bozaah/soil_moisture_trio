# Architecture — Soil Moisture Trio

## Pipeline Stages

```
prepare_data()
  └─ _load_all_real_data()
       ├─ AWRAL sm_pct (NCI THREDDS OPeNDAP)
       ├─ SILO temperature + VPD (weather_tools COG or NetCDF fallback)
       ├─ _align_lat_lon() → ascending sort + bounding-box clip
       └─ valid cell mask (NaN-free cells only)
build_model()   → CatBoostClassifier from ClassifierConfig
train()         → fit on valid flat cells (80% train)
evaluate()      → log-loss + accuracy on held-out 20%
predict_grid()  → classify full grid; invalid cells = -1
assess_risk()   → stress_index + categorical risk map
```

## Module Responsibilities

| File | Responsibility |
|---|---|
| `main.py` | argparse CLI, orchestrates pipeline stages |
| `config.py` | `ClassifierConfig` — Pydantic model, all tunable params |
| `pipeline.py` | `DryWetClassifierPipeline` — all data loading, ML, prediction |
| `data_sources.py` | `WeatherToolsSiloLoader` — SILO COG fetcher, cache management |
| `risk.py` | `assess_risk_levels()`, `save_risk_outputs()`, `RiskLevel` enum |
| `plot.py` | `save_risk_plot()`, `plot_dryness_diagnostics()` — PNG outputs |
| `visualize.py` | `create_interactive_map()` — Folium HTML output |

## Data Contract

### Inputs (after loading)

All arrays are 2D `(lat, lon)` after time averaging, ascending lat/lon, clipped to bounds.

| Variable | Source | Units | Notes |
|---|---|---|---|
| `soil_moisture` | AWRAL `sm_pct` | fraction 0–1 | Loader auto-detects percent vs fraction |
| `temperature` | SILO `max_temp` | °C | |
| `vpd` | SILO `vp_deficit` | hPa | |
| `ndvi` | synthetic | — | Placeholder; `np.random.uniform(-0.1, 1.0)` |
| `ndwi` | synthetic | — | Stored but unused in model/risk |
| `fire_index` | synthetic | — | Stored but unused in model/risk |

### Outputs

| Output | Format | Notes |
|---|---|---|
| `risk_map` | int8 ndarray (lat, lon) | RiskLevel values; -1 = NoData |
| `stress_index` | float ndarray (lat, lon) | 0–1; NaN for invalid cells |
| `risk_layer.nc` | NetCDF | `risk_level` variable + lat/lon coords |
| `*_summary.json` | JSON | counts/percentages per risk band |
| `*.png` | PNG | two-panel risk + stress index |
| `*.html` | HTML | Folium interactive map (optional) |

## Spatial Handling

1. AWRAL grid loaded from OPeNDAP; lats may be descending — flipped to ascending
2. Bounding box clip via `config.min/max_lat/lon`
3. SILO data regridded to AWRAL grid via nearest-neighbour (`xr.DataArray.interp`)
4. Valid cell mask: `isfinite(sm) & isfinite(temp) & isfinite(ndvi) & isfinite(vpd)`
5. Mask propagated through training → prediction → risk (invalid cells always -1)

## ML Design Notes

- Features: `[soil_moisture, temperature, ndvi, vpd]` — 4 columns per valid cell
- Labels: rule-based (see `docs/thresholds.md`)
- Split: sequential 80/20 on flattened cells (no spatial shuffle — geographic bias present)
- Tree ensembles are scale-invariant; no feature scaling applied
- See `docs/thresholds.md` for known issues with default label distribution
