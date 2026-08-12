# Risk Model

## Overview

The operational risk layer is computed directly from soil moisture, temperature, and VPD in [`risk.py`](../src/soil_moisture_trio/risk.py). There is no ML model in the current production path.

`DryWetClassifierPipeline.assess_risk()` passes the prepared grids and valid mask into `assess_risk_levels()`, which returns:

- `risk_map`
- `summary`
- `stress_index`

## Stress Index Formula

```python
dryness = clip((moisture_threshold - soil_moisture) / moisture_threshold, 0, 1)
temp_factor = clip(temperature / critical_temp_threshold, 0, 1)
vpd_factor = clip(vpd / critical_vpd_threshold, 0, 1)

stress_index = 0.6 * dryness + 0.25 * vpd_factor + 0.15 * temp_factor
```

Defaults come from `ClassifierConfig`:

- `moisture_threshold = 0.50`
- `critical_temp_threshold = 40.0`
- `critical_vpd_threshold = 32.0`

The weights are currently hardcoded.

## Risk Categories

| Level | Value | Label | Stress index |
|---|---|---|---|
| `LOW` | 0 | Low | `< 0.35` |
| `WATCH` | 1 | Watch | `0.35–<0.60` |
| `ALERT` | 2 | Alert | `0.60–<0.85` |
| `CRITICAL` | 3 | Critical | `>= 0.85` |

Invalid cells are encoded as `-1`.

## Valid Mask Behavior

The risk model only evaluates cells marked valid by `prepare_data()`. A cell is excluded when:

- soil moisture is missing
- temperature is missing
- VPD is missing
- the cell falls outside the optional boundary polygon

Excluded cells remain `-1` in the categorical map and `NaN` in the continuous stress layer.

## Outputs

`save_risk_outputs()` writes:

- `{prefix}.nc`
- `{prefix}_summary.json`

`save_risk_plot()` writes a two-panel PNG:

- categorical risk map
- continuous stress-index panel

`plot_dryness_diagnostics()` writes:

- soil-moisture histogram
- soil-moisture vs VPD scatter coloured by stress index

## Known Limitations

- Stress weights are not yet configurable through `ClassifierConfig`.
- The continuous stress thresholds are fixed year-round; seasonal calibration remains backlog work.
- Legacy soil-moisture fallback mode is available, but the risk interpretation is calibrated for the decile product, not the raw-values product.
