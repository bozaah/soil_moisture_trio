# Thresholds & Classification Logic

## Label Generation (Rule-Based)

Applied in `prepare_data()` to produce training labels:

```
Dry (0): soil_moisture < moisture_threshold
         AND (temperature > temp_threshold OR vpd > vpd_threshold)
Wet (1): all other cells
```

## Current Thresholds (`ClassifierConfig` defaults)

| Parameter | Default | Unit | Role |
|---|---|---|---|
| `moisture_threshold` | 0.25 | fraction | Primary dry/wet boundary |
| `temp_threshold` | 30.0 | °C | Heat stress trigger |
| `vpd_threshold` | 20.0 | hPa | Atmospheric dryness trigger |
| `ndvi_threshold` | 0.3 | — | Reserved; not used in current classification |
| `severe_moisture_threshold` | 0.10 | fraction | Risk layer: critical dryness |
| `critical_temp_threshold` | 40.0 | °C | Risk layer: stress index normaliser |
| `critical_vpd_threshold` | 32.0 | hPa | Risk layer: stress index normaliser |
| `watch_margin` | 0.08 | fraction | Reserved in config |
| `alert_moisture_threshold` | 0.18 | fraction | Reserved in config |
| `alert_temp_threshold` | 32.0 | °C | Reserved in config |
| `alert_vpd_threshold` | 24.0 | hPa | Reserved in config |

**Note:** `main.py` hardcodes `moisture_threshold=0.2` overriding the default.

## Known Issue — Threshold Too High

Observed AWRAL `sm_pct` quantiles for a 2024 window (converted to fraction):

```
  0%        25%       50%       75%       100%
0.000027  0.011726  0.052861  0.180270  1.000000
```

With `moisture_threshold=0.25`: cells below 0.25 represent ~75%+ of valid cells → more than 75% labelled **dry**. CatBoost learns a near-all-dry world. This inflates dry-class recall and deflates wet-class metrics.

With `moisture_threshold=0.2`: cells below 0.2 represent ~70%+ of valid cells. Same problem.

## Recommended Strategy

### Short-term
Set `moisture_threshold` to the 25th–33rd percentile of the dataset you are analysing. For the 2024 window above, this is approximately 0.01–0.02. Pass via CLI: `--moisture-threshold 0.02` (flag not yet implemented — modify `ClassifierConfig` directly or add the flag).

### Medium-term (recommended)
Implement an automated calibration helper:
1. Load a multi-year baseline (e.g., 2010–2020)
2. Compute regional/seasonal percentiles (e.g., 10th, 25th, 50th)
3. Set `moisture_threshold = 25th pct`, `severe_moisture_threshold = 10th pct`
4. Persist recommended defaults to a config file

This is tracked in `docs/backlog.md` as item B3.

## Risk Layer Thresholds

Used in `risk.py` stress index formula — see `docs/risk-model.md`.
