# Risk Model

## Overview

The risk layer translates CatBoost predictions + raw grids into a categorical risk map and a continuous stress index. It lives in `src/soil_moisture_trio/risk.py`.

The CatBoost classification (dry/wet) feeds into `assess_risk()` but the **risk categorisation itself** uses a physics-based stress index — not just the binary prediction. The classifier output is used to determine the valid-cell mask.

## Stress Index Formula

```python
dryness    = clip((moisture_threshold - soil_moisture) / moisture_threshold, 0, 1)
temp_factor = clip(temperature / critical_temp_threshold, 0, 1)
vpd_factor  = clip(vpd / critical_vpd_threshold, 0, 1)

stress_index = 0.6 * dryness + 0.25 * vpd_factor + 0.15 * temp_factor
```

- Range: 0–1 (0 = no stress, 1 = maximum stress)
- `moisture_threshold` and `critical_*_threshold` come from `ClassifierConfig`
- **Weights (0.6/0.25/0.15) are hardcoded** in `risk.py:85` — not currently exposed via config

### Normaliser choices

- Dryness: linear deficit from threshold to zero (zero moisture = fully dry)
- Temperature: fraction of `critical_temp_threshold` (default 40°C)
- VPD: fraction of `critical_vpd_threshold` (default 32 hPa)

## Risk Categories (`RiskLevel` IntEnum)

| Level | Value | Label | stress_index | Colour |
|---|---|---|---|---|
| LOW | 0 | Low | < 0.35 | Blue `#2b83ba` |
| WATCH | 1 | Watch | 0.35–0.60 | Green `#c7e9b4` |
| ALERT | 2 | Alert | 0.60–0.85 | Orange `#fdae61` |
| CRITICAL | 3 | High | ≥ 0.85 | Red `#d7191c` |

Invalid cells (ocean, NaN): encoded as `-1` in `risk_map`.

## Outputs

### `assess_risk_levels()` returns
- `risk_map` — int8 ndarray `(lat, lon)`, RiskLevel values
- `summary` — dict with per-level counts, percentages, labels
- `stress_index` — float ndarray `(lat, lon)`, 0–1

### `save_risk_outputs()` writes
- `{prefix}.nc` — NetCDF with `risk_level` variable + lat/lon + time attrs
- `{prefix}_summary.json` — JSON with summary + time_metadata

### `save_risk_plot()` writes
- Two-panel PNG: categorical risk map (left) + continuous stress index (right)

### `plot_dryness_diagnostics()` writes
- Histogram of stress_index distribution
- Scatter: soil moisture (x) vs VPD (y), coloured by stress_index

## Known Issues / Improvements

- Stress weights (0.6/0.25/0.15) should be exposed via `ClassifierConfig` for tuning
- Dryness normaliser is sensitive to `moisture_threshold` — if threshold is wrong (see `docs/thresholds.md`), stress index will be distorted for most cells
- `_compute_risk_map` return type annotation is incorrect (says `np.ndarray`, returns 2-tuple)
