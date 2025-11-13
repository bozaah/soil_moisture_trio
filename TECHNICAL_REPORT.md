## Soil Moisture Trio — Technical Report

Date: 2025-11-12

This report summarizes the data sources, thresholds and heuristics, model design (CatBoost), and outputs produced by the Soil Moisture Trio pipeline. It is intended to be a concise, technical reference for reviewers and engineers integrating or validating the system.

---

## 1) Data sources

- AWRAL soil moisture (`sm_pct`)
  - Source: NCI THREDDS OPeNDAP/NetCDF (example URL pattern used by the pipeline):
    `https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/values/day/sm_pct_{YEAR}.nc`
  - Variable name: `sm_pct`.
  - Notes: some deployments of `sm_pct` are encoded as percents (0–100) and some as fractions (0–1). The pipeline detects units heuristically (see §2) and uses volumetric fraction (0–1) internally.

- SILO variables (via `weather_tools` COG loader or NetCDF fallback)
  - Max temperature (tmax / `max_temp`) — used as a heat stress proxy.
  - Vapour pressure deficit (VPD / `vp_deficit`) — used as an atmospheric dryness stressor. Units: hPa.
  - Sources: SILO on AWS S3 (NetCDF) or COG tiles via the `weather_tools` loader for bounding-box subsetting.

- Other variables
  - NDVI, NDWI, and Fire Index are currently synthetic/placeholders in the repo and not supplied from real feeds yet.

Data-handling notes
- The loader will average over a selected time window (by `start_date`/`end_date` or default to the dataset's time slice) and return gridded arrays aligned to the user-specified bounding box.
- The pipeline retains a valid/no-data mask so outputs preserve `-1` for invalid/ocean cells.

---

## 2) Thresholds & heuristics

Canonical internal units
- The pipeline operates on soil moisture as volumetric fraction (0–1). To avoid silent unit errors, the loader performs a simple detection: if the loaded `sm_pct` grid has a maximum value > 1.1, it is treated as a percent product and divided by 100; otherwise it is assumed to already be a fraction. A concise informative message is emitted on load.

Observed sample (2024, single-window)
- Example quantiles observed for a 2024 window (flattened grid):

```
  0%      25%      50%      75%     100%
0.000027 0.011726 0.052861 0.180270 1.000000
```

Implication: many cells have very small volumetric fraction values; applying large absolute thresholds (e.g., 0.25) will classify most of the grid as dry. Use percentile-based thresholds or much smaller absolute thresholds appropriate to the product distribution.

Current configured thresholds (kept for compatibility)
- `moisture_threshold`: 0.25 (dry if soil moisture < this). NOTE: may be large for some `sm_pct` realizations; recommended adjustment below.
- `temp_threshold`: 30.0 (°C)
- `vpd_threshold`: 20.0 (hPa)
- `severe_moisture_threshold`: 0.10
- `critical_temp_threshold`: 40.0 (°C)
- `critical_vpd_threshold`: 32.0 (hPa)
- `alert_moisture_threshold`: 0.18

Recommended threshold strategy
- Short-term: validate the existing defaults on the dataset you are running. For the 2024 sample above, plausible short-term values would be in the range 0.01–0.03 (1–3% fraction) for `moisture_threshold`.
- Medium-term (recommended): compute thresholds from a multi-year climatology for the region/season. For example:
  - `moisture_threshold` = 25th percentile of the climatology
  - `severe_moisture_threshold` = 10th percentile
  - `alert_moisture_threshold` = 33rd percentile or `moisture_threshold + margin`

Autodetection and safe defaults
- The loader prints a short summary of the original maximum and whether a conversion occurred. This is a useful run-time sanity check before interpreting diagnostics.

---

## 3) CatBoost: why, what, and how

Why CatBoost
- CatBoost is a gradient-boosted decision-tree implementation that handles categorical variables (not used presently), provides robust default behaviour, and requires minimal preprocessing for tabular data. It is fast, deterministic when configured, and well-suited for small-to-medium tabular problems like grid-sample classification.

Input features
- The model is trained per-grid-cell on flattened samples with features:
  1. soil_moisture (fraction)
  2. temperature (max daily / averaged window)
  3. NDVI (placeholder synthetic values currently)
  4. VPD

Labels
- Rule-based label assignment at prepare-time:
  - Dry (0) if soil_moisture < moisture_threshold AND (temperature > temp_threshold OR vpd > vpd_threshold)
  - Wet (1) otherwise

Preprocessing
- NaNs are masked out of the valid cell set (cells with NaN in any of the critical inputs are excluded). The valid mask is stored so predictions preserve NoData cells.
- Features are flattened and stacked into an (N, 4) array. No further scaling is applied because tree ensembles are scale-invariant.

Training procedure
- Model: CatBoostClassifier
- Default hyperparameters (in `ClassifierConfig`):
  - iterations/epochs: 30 (overridable via `catboost_iterations`)
  - depth: 6
  - learning_rate: 0.01 (or `catboost_learning_rate` when provided)
- Train/validation split: an 80/20 split is used on the flattened samples (first 80% train, last 20% eval). This is a pragmatic default for quick runs; for more rigorous experiments use k-fold CV or hold-out by location/time.
- Metrics reported: log-loss and classification accuracy on the held-out set.

Why the rule-based labels?
- The pipeline’s labels are generated by a domain-informed rule to provide an explainable target for the model. This lets CatBoost learn residual structure beyond the binary rubric and produce probabilistic outputs that can be post-processed.

Model outputs
- The classifier produces per-sample probabilities for the positive class (wet). These are remapped back onto the full grid (invalid cells remain -1) and used for diagnostic or optional downstream tasks.

Reproducibility & performance
- For reproducibility, seed the CatBoost RNG and pin the environment where necessary. For performance, tune `iterations`, `depth`, and `learning_rate` for dataset size and desired latency.

---

## 4) Outputs

- Categorical risk map (NetCDF)
  - Produced by `save_risk_outputs()`; stored as a NetCDF with a `risk_level` 2D variable and latitude/longitude coordinates.
  - Risk levels use the `RiskLevel` IntEnum (LOW=0, WATCH=1, ALERT=2, CRITICAL=3). Invalid/no-data cells are encoded as `-1`.

- Summary JSON
  - A compact JSON summary containing counts and percentages per risk band plus time_metadata.

- PNG visual outputs
  - Two-panel PNG created by `save_risk_plot()`:
    - Left: categorical risk map
    - Right: continuous dryness/stress index (0–1)
  - Diagnostics PNG created by `plot_dryness_diagnostics()` (histogram + scatter):
    - Histogram of the continuous `stress_index` distribution.
    - Scatter: Soil Moisture (x) vs VPD (hPa) (y), colored by `stress_index`.

- Interactive Folium map (HTML)
  - Optional interactive output built by `visualize.create_interactive_map()`; consumes the risk map and summary and creates an HTML file for browser inspection.

Downstream/decision-support considerations
- The `stress_index` is a continuous composite (0–1) combining soil moisture deficit, temperature factor, and VPD factor. This is useful for thresholding, risk aggregation, and time-series analysis.
- For operational decision support, prefer percentile or climatology-derived thresholds over fixed absolute thresholds to avoid bias from sensor/unit differences.

---

## Data contract (short)

- Inputs:
  - `sm_pct` grid: 2D or 3D NetCDF with (time, lat, lon). After averaging over time the pipeline expects a 2D array with shape (lat, lon). Values: fraction 0–1 (loader will convert if it detects percent encoding).
  - `max_temp` grid: same shape, units °C.
  - `vp_deficit` grid: same shape, units hPa.

- Outputs:
  - `risk_map`: int8 array (lat, lon) with values -1, 0..3
  - `stress_index`: float array (lat, lon), range 0–1 (NaN for invalid cells)
  - JSON summary and NetCDF files, plus PNG/HTML visual artifacts

---

## Recommended next steps (engineering)

1. Add unit tests that assert loader conversion behaviour for edge cases.
2. Add an automated threshold-calibration routine (CLI helper) that computes percentiles for a selected multi-year baseline.
3. Replace print statements with `logging` at INFO level for production readiness and better CI clarity.
4. Add integration tests that mock remote reads and validate the full pipeline end-to-end for a small bounding box.

---

## Example run

Use the project `uv` toolchain to run a short window for testing:

```bash
uv run python main.py \
  --year 2025 \
  --start-date 2025-10-01 \
  --end-date 2025-10-15 \
  --risk-output-prefix outputs/risk_layer_2025oct_WA \
  --risk-plot-path outputs/risk_layer_2025oct_WA.png \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --silo-cache-dir /tmp/silo_cache \
  --silo-cache-max-mb 200 \
  --min-lat -35 \
  --max-lat -13 \
  --min-lon 112 \
  --max-lon 129
```

---

If you'd like, I can convert this to a PDF, add it to the repo root as `TECHNICAL_REPORT.md` (already created), or extend sections with equations and more explicit calibration code (e.g., the percentile helper). Any parts you want expanded or adjusted? 
