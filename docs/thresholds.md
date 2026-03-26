# Thresholds & Classification Logic

This document describes the thresholds that exist in the current codebase and how they are used.

## Two Distinct Decision Surfaces

The repository still exposes two threshold sets:

1. `classify_grid()` in [`pipeline.py`](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/pipeline.py) produces a binary dry/wet grid.
2. `assess_risk_levels()` in [`risk.py`](/Users/dpird-mac/Documents/DPIRD/Git/soil_moisture_trio/src/soil_moisture_trio/risk.py) produces the operational Low / Watch / Alert / Critical outputs.

The operational outputs written to NetCDF, JSON, PNG, and bulletin are driven by the stress-index path in `risk.py`.

## Binary Dry/Wet Rule (`classify_grid`)

`classify_grid()` is still present and uses the following rule:

```text
Dry (0): soil_moisture < moisture_threshold
         AND (temperature > temp_threshold OR vpd > vpd_threshold)
Wet (1): all other valid cells
NoData (-1): invalid cells
```

Current defaults from `ClassifierConfig`:

| Parameter | Default | Unit | Used by |
|---|---|---|---|
| `moisture_threshold` | 0.50 | percentile rank | `classify_grid()` and `risk.py` dryness calculation |
| `temp_threshold` | 30.0 | °C | `classify_grid()` only |
| `vpd_threshold` | 20.0 | hPa | `classify_grid()` only |

`soil_moisture` is expected to be the AWRAL decile percentile-rank product on a `0–1` scale. A value of `0.10` means the cell is at or below the 10th percentile for that location and season.

## Operational Risk Model (`risk.py`)

The risk map is derived from a continuous stress index:

```text
dryness   = clip((moisture_threshold - soil_moisture) / moisture_threshold, 0, 1)
temp_fac  = clip(temperature / critical_temp_threshold, 0, 1)
vpd_fac   = clip(vpd / critical_vpd_threshold, 0, 1)

stress_index = 0.60 * dryness + 0.25 * vpd_fac + 0.15 * temp_fac
```

Current defaults:

| Parameter | Default | Unit | Role |
|---|---|---|---|
| `moisture_threshold` | 0.50 | percentile rank | Dryness reference point; cells at or above the median contribute zero dryness |
| `critical_temp_threshold` | 40.0 | °C | Temperature normalisation ceiling |
| `critical_vpd_threshold` | 32.0 | hPa | VPD normalisation ceiling |

### Risk Bands

| Stress index | Category |
|---|---|
| `< 0.35` | Low |
| `0.35–<0.60` | Watch |
| `0.60–<0.85` | Alert |
| `>= 0.85` | Critical |

Invalid cells remain `-1` in `risk_map` and `NaN` in `stress_index`.

## Why `moisture_threshold = 0.50`

Sprint 7 changed the dryness reference from `0.30` to `0.50`.

Current interpretation:

- cells at or above the climatological median contribute no soil-moisture stress
- cells in the `0.30–0.50` range now contribute moderate dryness, which improves sensitivity in shoulder seasons
- a cell at the 20th percentile has `dryness = 0.60`
- a cell at the 10th percentile has `dryness = 0.80`

This is a deliberate shift away from the older `0.30` setting, which zeroed out dryness for too many below-normal cells.

## Soil-Moisture Interpretation Bands

These percentile bands remain useful for interpretation, but they are not the direct mechanism used to assign the operational risk map:

| Percentile rank | Interpretation |
|---|---|
| `<= 0.10` | Severe dryness relative to local climatology |
| `0.10–0.20` | Strongly below normal |
| `0.20–0.30` | Moderately below normal |
| `> 0.30` | Within or above the historical normal range |

Those bands explain the decile product. The pipeline's actual risk assignment uses the composite stress index above.

## Current Gaps

- The stress-index weights `0.60 / 0.25 / 0.15` are hardcoded in `risk.py`; they are not yet configurable through `ClassifierConfig`.
- `classify_grid()` still uses `temp_threshold` and `vpd_threshold`, but the main operational products are produced by `assess_risk()`.
- Legacy raw-values soil moisture can still be used with `--allow-legacy-sm`, but those outputs are compatibility-only and should not be interpreted the same way as decile-based runs.
