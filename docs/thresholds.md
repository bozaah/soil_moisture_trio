# Thresholds and Risk Classification

The operational Low / Watch / Alert / Critical product is assigned by one decision surface: the composite stress index in [`risk.py`](../src/soil_moisture_trio/risk.py).

## Stress Components

```text
dryness   = clip((moisture_threshold - soil_moisture) / moisture_threshold, 0, 1)
temp_fac  = clip(temperature / critical_temp_threshold, 0, 1)
vpd_fac   = clip(vpd / critical_vpd_threshold, 0, 1)

stress_index = 0.60 * dryness + 0.25 * vpd_fac + 0.15 * temp_fac
```

Current normalisation defaults:

| Parameter | Default | Unit | Role |
|---|---:|---|---|
| `moisture_threshold` | 0.50 | percentile rank | Dryness reference; cells at or above the median contribute zero dryness |
| `critical_temp_threshold` | 40.0 | °C | Temperature normalisation ceiling |
| `critical_vpd_threshold` | 32.0 | hPa | VPD normalisation ceiling |

The weights remain hardcoded pending B10.

## Risk Bands

| Stress index | Category |
|---|---|
| `< 0.35` | Low |
| `0.35–<0.60` | Watch |
| `0.60–<0.85` | Alert |
| `>= 0.85` | Critical |

Invalid cells remain `-1` in `risk_map`. They are excluded from risk percentages.

## Why `moisture_threshold = 0.50`

Sprint 7 changed the dryness reference from `0.30` to `0.50`:

- cells at or above the climatological median contribute no soil-moisture stress
- cells in the `0.30–0.50` range contribute moderate dryness
- a cell at the 20th percentile has `dryness = 0.60`
- a cell at the 10th percentile has `dryness = 0.80`

This improves shoulder-season sensitivity compared with zeroing dryness above the 30th percentile.

## Soil-Moisture Interpretation Bands

These percentile bands help interpret the AWRA-L input but do not directly assign the operational risk category:

| Percentile rank | Interpretation |
|---|---|
| `<= 0.10` | Severe dryness relative to local climatology |
| `0.10–0.20` | Strongly below normal |
| `0.20–0.30` | Moderately below normal |
| `> 0.30` | Within or above the historical normal range |

## Current Gaps

- Stress weights are not yet exposed through `ClassifierConfig`.
- Risk-band thresholds are fixed in `risk.py` rather than configured.
- Seasonal calibration remains backlog work.
- Legacy raw-values soil moisture is compatibility-only and is not scientifically equivalent to percentile-rank operation.
