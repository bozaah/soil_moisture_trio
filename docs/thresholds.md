# Thresholds & Classification Logic

## Label Generation (Rule-Based)

Applied in `classify_grid()`:

```
Dry (0): sm_pct_decile < moisture_threshold
         AND (temperature > temp_threshold OR vpd > vpd_threshold)
Wet (1): all other valid cells
```

`sm_pct_decile` is an AWRAL **percentile rank** (0–1) calibrated against the full 1911–2026 historical record. A rank of 0.10 means soil moisture is at or below the 10th percentile for that location and season.

## Current Thresholds (`ClassifierConfig` defaults)

### Classification thresholds

| Parameter | Default | Unit | Role |
|---|---|---|---|
| `moisture_threshold` | 0.30 | percentile rank | Binary dry/wet boundary; also sets dryness=0 in stress index |
| `temp_threshold` | 30.0 | °C | Heat stress trigger for binary classification |
| `vpd_threshold` | 20.0 | hPa | Atmospheric dryness trigger for binary classification |

### Risk level thresholds

| Percentile rank | Category | Config field |
|---|---|---|
| ≤ 0.10 | **Critical** | `severe_moisture_threshold` |
| 0.10–0.20 | **Alert** | `alert_moisture_threshold` |
| 0.20–0.30 | **Watch** | implied by `moisture_threshold` |
| ≥ 0.30 | **Low** | `moisture_threshold` |

| Parameter | Default | Unit | Role |
|---|---|---|---|
| `severe_moisture_threshold` | 0.10 | percentile rank | Critical/Alert boundary |
| `alert_moisture_threshold` | 0.20 | percentile rank | Alert/Watch boundary |
| `critical_temp_threshold` | 40.0 | °C | Stress index normaliser |
| `critical_vpd_threshold` | 32.0 | hPa | Stress index normaliser |
| `alert_temp_threshold` | 32.0 | °C | Reserved in config |
| `alert_vpd_threshold` | 24.0 | hPa | Reserved in config |

## Stress Index Formula

Used in `risk.py` `_compute_risk_map()`:

```
dryness   = clip((moisture_threshold - sm_pct_decile) / moisture_threshold, 0, 1)
temp_fac  = clip(temperature / critical_temp_threshold, 0, 1)
vpd_fac   = clip(vpd / critical_vpd_threshold, 0, 1)

stress_index = 0.6 * dryness + 0.25 * vpd_fac + 0.15 * temp_fac
```

`stress_index` maps to risk categories: Critical ≥ 0.85, Alert ≥ 0.60, Watch ≥ 0.35, Low < 0.35.

With the decile input, `dryness = 0` for cells at or above the 30th percentile; cells at the 10th percentile have `dryness ≈ 0.67`.

## Calibration Baseline — Jan–Mar 2026 WA

From `data/awral_decile_sm_pct_WA_monthly.nc` (1911–2026, WA subset):

| Category | Threshold | Cells | % of valid |
|---|---|---|---|
| Critical | < 0.10 | 1,011 | 1.1% |
| Alert | 0.10–0.20 | 6,243 | 6.8% |
| Watch | 0.20–0.30 | 11,318 | 12.3% |
| Low | ≥ 0.30 | 73,619 | 79.9% |

Historical Jan–Feb–Mar mean rank: 0.500 (confirms decile is centred on median as expected).

**Compare to old raw sm_pct results (Jan–Mar 2026):** Critical 47.1%, Alert 29.5%, Watch 9.4%, Low 14.1%. The decile product eliminates the over-classification artefact.

## Resolution — B1 and B3 (closed)

**B1 (moisture_threshold too high):** Resolved by switching to AWRAL percentile rank product. The decile is spatially and seasonally normalised by construction — `moisture_threshold=0.30` corresponds to the actual 30th percentile for each location/season, not a fixed raw value.

**B3 (calibration helper):** Resolved — the decile product *is* the calibration. No separate calibration step needed; thresholds map directly to percentile ranks with stable climatological meaning.

See `docs/data-sources.md` for the updated AWRAL URL and `docs/backlog.md` where B1/B3 are marked closed.
