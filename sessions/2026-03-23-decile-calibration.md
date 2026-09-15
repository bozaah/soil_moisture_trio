# Session — 2026-03-23: Decile Calibration Sprint

## Goal

Switch pipeline from raw `sm_pct` (values/day) to AWRAL percentile rank decile product (deciles/day). Resolves B1 (moisture_threshold over-classification) and B3 (calibration helper).

## Step 0 — OPeNDAP probe

URL: `https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/deciles/day/sm_pct_2024.nc`

```
Dimensions: (time: 366, latitude: 681, longitude: 841)
Variable: sm_pct — units: relative, dtype: float32
Coordinates: time, latitude (-10 → -44), longitude (112 → 154)
```

Variable name confirmed as `sm_pct` (not `s0_pct_` or `sd_pct_` as catalog warned). Units are `relative` = percentile rank 0–1.

## Step 1 — WA monthly calibration download

URL: `.../deciles/month/sm_pct.nc` (full Australia, 3 GB, 1382 months 1911–2026)

Strategy: OPeNDAP decade-chunked download (full pull fails with Authorization failure; 1-year chunk = 5.6s, 10-year chunk = 31s).

```
Output: data/awral_decile_sm_pct_WA_monthly.nc
Shape: (1382, 441, 341)  — lat -35 to -13, lon 112 to 129
Time: 1911-01-31 to 2026-02-28
Download time: 5.3 min (12 decade chunks)
```

## Step 2 — Exploratory calibration (Jan–Mar 2026 WA)

| Category | Threshold | Cells | % valid |
|---|---|---|---|
| Critical | < 0.10 | 1,011 | 1.1% |
| Alert | 0.10–0.20 | 6,243 | 6.8% |
| Watch | 0.20–0.30 | 11,318 | 12.3% |
| Low | ≥ 0.30 | 73,619 | 79.9% |

Historical Jan–Feb–Mar mean rank: 0.500 ✓ (uniform 0-1 by construction)

Thresholds are spatially sensible. Compare to old approach (Jan–Mar 2026): Critical 47.1%, Alert 29.5% — the raw product over-classified because 75%+ of WA cells have `sm_pct < 0.25` fraction regardless of historical context.

Plot saved to `outputs/decile_calibration_jan-mar-2026.png`.

## Step 3 — Code changes

| File | Change |
|---|---|
| `pipeline.py` | URL `values/day` → `deciles/day`; updated load messages |
| `config.py` | `moisture_threshold` 0.25 → 0.30; `alert_moisture_threshold` 0.18 → 0.20; `watch_margin` 0.08 → 0.10; field descriptions updated |
| `main.py` | Removed hardcoded `moisture_threshold=0.2` override |
| `docs/thresholds.md` | Rewritten for decile product; B1/B3 resolved |
| `docs/data-sources.md` | AWRAL section updated with decile URLs and product table |
| `docs/backlog.md` | B1 and B3 marked resolved |

## classify_grid refactor

`classify_grid()` was producing a binary dry/wet grid that was only used by `_compute_risk_map()` as a valid-cell mask (`classification_grid >= 0`). The 0/1 dry/wet values themselves were never consumed downstream.

Changes:

- `risk.py`: `_compute_risk_map()` and `assess_risk_levels()` now accept `valid_mask` (boolean array) directly
- `pipeline.py`: `assess_risk()` uses `self.valid_mask_grid` directly; no longer calls `classify_grid()`
- `main.py`: removed `pred_map = pipeline.classify_grid()` call
- `classify_grid()` retained as a standalone diagnostic utility

## Tests

11 unit tests pass (`pytest tests/ --ignore=tests/test_moisture_ranges.py`). Updated `test_assess_risk_levels_categorizes_cells` and `test_assess_risk_levels_handles_invalid_cells` to pass boolean `valid_mask` instead of integer `classification`. B12 (test_moisture_ranges.py breaks pytest collection) is pre-existing and not touched this sprint.

## New threshold mapping

```
≤ 0.10  → Critical  (config.severe_moisture_threshold)
0.10–0.20 → Alert   (config.alert_moisture_threshold)
0.20–0.30 → Watch   (implied by moisture_threshold)
≥ 0.30  → Low       (config.moisture_threshold)
```
