# Soil Moisture Trio — Technical Report

**Version:** Sprint 6 | **Date:** 2026-03-23
**Status:** Operational — decile-calibrated, rule-based risk classification

---

## Purpose

This report describes the data sources, scientific methodology, classification thresholds, and outputs of the Soil Moisture Trio pipeline. It is written for soil and climate scientists and DPIRD policy/decision-makers. Engineering implementation detail is included only where it is necessary to understand what the system is doing and why.

---

## 1. Data Sources

### 1.1 Soil Moisture — AWRAL Decile Product

The pipeline uses the Australian Water Resources Assessment Landscape model (**AWRA-L v7**) soil moisture percentile rank product, provided by the Bureau of Meteorology through NCI THREDDS.

- **What it measures:** Total rootzone soil moisture integrated over the 0–100 cm profile, expressed as a **percentile rank** (0–1) relative to the full historical record for that location and day-of-year.
- **Historical baseline:** 1911 to present (~115 years).
- **Spatial resolution:** 0.05° (~5 km) across Australia.
- **Temporal resolution:** Daily (operational runs); monthly (calibration baseline).
- **URL pattern (daily, operational):**
  `https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/deciles/day/sm_pct_{YEAR}.nc`
- **Variable name:** `sm_pct`
- **Units:** `relative` — confirmed as percentile rank 0–1 (OPeNDAP probe, 2026-03-23).

> **Why percentile rank rather than raw soil moisture?**
> Raw AWRA-L soil moisture values (volumetric fraction) vary enormously across the landscape — sandy coastal soils in the south-west have a very different absolute wetness range than clay-rich soils in the Pilbara or the Kimberley. A threshold like "soil moisture < 0.10 is dry" may correctly identify dry conditions in one soil type while misclassifying another. The percentile rank removes this spatial heterogeneity: a rank of 0.10 always means the soil is drier than 90% of the historical observations **at that specific location and time of year**. Thresholds applied to percentile ranks therefore have a consistent climatological meaning everywhere in the domain.

### 1.2 Temperature and Vapour Pressure Deficit — SILO

Heat stress and atmospheric dryness are sourced from the SILO climate dataset (Bureau of Meteorology / Queensland Department of Environment), accessed via the `weather_tools` COG loader (primary) or SILO NetCDF on AWS S3 (fallback).

| Variable | SILO name | Internal name | Units | Role |
|---|---|---|---|---|
| Daily maximum temperature | `max_temp` | `temperature` | °C | Heat stress |
| Vapour pressure deficit | `vp_deficit` | `vpd` | hPa | Atmospheric dryness |

Values are averaged over the selected time window and spatially aligned to the AWRA-L grid.

### 1.3 Calibration Baseline Dataset

A WA monthly decile subset covering the full historical record has been downloaded for calibration and diagnostic use:

- **File:** `data/awral_decile_sm_pct_WA_monthly.nc`
- **Coverage:** Western Australia (lat −35° to −13°, lon 112° to 129°)
- **Dimensions:** 1,382 months × 441 latitude × 341 longitude cells (~831 MB)
- **Period:** January 1911 – February 2026

---

## 2. Classification Thresholds and Scientific Rationale

### 2.1 Risk Categories

The pipeline assigns each grid cell to one of four drought risk categories based on its soil moisture percentile rank:

| Percentile rank | Category | Interpretation |
|---|---|---|
| ≤ 0.10 | **Critical** | Soil moisture is at or below the 10th percentile — conditions as dry or drier than 90% of historical observations for this location and season. Consistent with severe drought. |
| 0.10 – 0.20 | **Alert** | 10th to 20th percentile. Significant drying episode; below what is typical for the season. Likely to affect pasture recovery, crop viability, and stock water. |
| 0.20 – 0.30 | **Watch** | 20th to 30th percentile. Drier than roughly two-thirds of historical years. Warrants monitoring, particularly if conditions persist. |
| > 0.30 | **Low** | Above the 30th percentile. Within or above the historically normal range. No immediate drought concern. |

These thresholds are set in `ClassifierConfig`:

- `moisture_threshold = 0.30` (Watch/Low boundary)
- `alert_moisture_threshold = 0.20` (Alert/Watch boundary)
- `severe_moisture_threshold = 0.10` (Critical/Alert boundary)

### 2.2 Why These Boundaries?

The 10th, 20th, and 30th percentiles are standard reference points in Australian drought monitoring (consistent with the Bureau of Meteorology's decile-based drought classification). Defining categories in percentile space means:

- A cell classified as Critical in January in the wheatbelt is experiencing the same *relative* severity of dryness as a Critical cell in July in the Kimberley — even though their absolute soil water contents differ greatly.
- The proportion of the landscape in each category is stable over long climatological averages (by construction, ~10%, ~10%, ~10%, ~70% on average).
- Short-term departures from those proportions indicate genuine anomalies.

### 2.3 Before and After Calibration

Switching from raw volumetric fraction to the percentile rank product eliminated a systematic over-classification bias. The table below shows the January–March 2026 WA results under both approaches:

| Category | Raw sm_pct (old) | Decile rank (current) |
|---|---|---|
| Critical | 47.1% | 1.1% |
| Alert | 29.5% | 6.8% |
| Watch | 9.4% | 12.3% |
| Low | 14.1% | 79.9% |

With the raw product, almost half of WA was classified Critical in summer — not because conditions were genuinely extreme, but because the absolute threshold (0.25 volumetric fraction) sat above most of the observed distribution. The decile product produces results consistent with climatological expectation: Critical and Alert conditions affect a small fraction of the landscape except during genuine drought events.

As a sanity check: the historical mean percentile rank across all Jan–Mar months (1911–2026) is exactly **0.500** — confirming the decile product is correctly centred on its long-run median.

---

## 3. Stress Index and Risk Map

### 3.1 Why a Stress Index?

Drought impact is rarely driven by soil moisture alone. A cell with low soil moisture but moderate temperature and low atmospheric demand may recover quickly; the same soil moisture under extreme heat and high VPD represents a much more severe agricultural and ecological stress. The pipeline therefore combines soil moisture, temperature, and VPD into a single composite **stress index** (0–1) before assigning risk levels.

### 3.2 Formula

```
dryness_factor   = clip((moisture_threshold − sm_pct_rank) / moisture_threshold, 0, 1)
temp_factor      = clip(temperature / critical_temp_threshold, 0, 1)
vpd_factor       = clip(vpd / critical_vpd_threshold, 0, 1)

stress_index = 0.60 × dryness_factor
             + 0.25 × vpd_factor
             + 0.15 × temp_factor
```

**What each component means:**

- **`dryness_factor`** measures how far below the Watch/Low threshold (0.30 percentile rank) the current soil moisture is, expressed as a proportion of that threshold. A cell at the 30th percentile has dryness_factor = 0 (no soil water stress). A cell at the 10th percentile has dryness_factor ≈ 0.67. A cell at or below the 0th percentile has dryness_factor = 1.0 (maximum). Crucially, because `sm_pct_rank` is already a percentile rank, the dryness_factor is measuring *probabilistic* deficit — how anomalous the current soil moisture is relative to the historical distribution at that location — rather than a raw physical water volume. This is a more meaningful input to a stress calculation than volumetric fraction because it captures the climatological context.

- **`temp_factor`** normalises temperature against the critical heat threshold (40°C). At 40°C, temp_factor = 1.0; below that it scales linearly. It represents the fraction of maximum heat stress being experienced.

- **`vpd_factor`** normalises vapour pressure deficit against a critical VPD threshold (32 hPa). High VPD accelerates plant water loss and intensifies moisture stress independently of soil water content.

**Weights:** Soil moisture deficit is the primary driver (60%), with atmospheric demand (VPD, 25%) and heat (15%) as amplifiers. This weighting reflects agronomic evidence that soil water depletion is the proximate cause of crop and pasture stress, while heat and VPD determine the rate of loss and the plant's ability to cope.

### 3.3 Risk Level Assignment

Cells are assigned to risk levels based on their stress index value:

| Stress index | Risk level |
|---|---|
| ≥ 0.85 | **Critical** |
| 0.60 – 0.85 | **Alert** |
| 0.35 – 0.60 | **Watch** |
| < 0.35 | **Low** |

Cells with no data (ocean, areas outside domain, or missing inputs) are assigned `-1` and excluded from all calculations and summaries.

### 3.4 Valid Cell Masking

The valid cell mask is built once during data loading (`prepare_data()`): a cell is valid if and only if all three inputs — soil moisture, temperature, and VPD — contain finite values. Ocean and missing-data cells are excluded at this stage and carry a sentinel value of `-1` through all outputs. No imputation is performed.

---

## 4. Outputs

### 4.1 Risk Map (NetCDF)

A 2D grid at AWRA-L resolution (0.05°) with each cell assigned an integer risk level (−1 = no data, 0 = Low, 1 = Watch, 2 = Alert, 3 = Critical). Latitude/longitude coordinates are retained. File includes a JSON-encoded summary in the global attributes and the time window metadata.

### 4.2 Summary JSON

Counts and proportions of cells in each risk category, plus time window metadata. Intended for tabular reporting and integration with decision-support dashboards.

### 4.3 PNG Outputs

Two figures are produced:

- **Risk map figure:** Side-by-side categorical risk map (colour-coded by level) and continuous stress index map (0–1 gradient). The stress index panel shows the intensity of conditions within each category.
- **Diagnostic figure:** Histogram of the stress index distribution and a soil moisture vs VPD scatter plot coloured by stress index, for quality-checking the run.

### 4.4 Interactive Map (optional)

A Folium HTML map with clickable cells showing risk level and coordinates, for field-scale exploration.

---

## 5. Spatial Domain and Operational Use

The default spatial domain covers all of Australia. For Western Australia operational runs, the following bounds are recommended to avoid unnecessary processing of the eastern states:

```bash
uv run python main.py \
  --year 2026 \
  --start-date 2026-01-01 \
  --end-date 2026-03-15 \
  --risk-output-prefix outputs/risk_2026_jan-mar_WA \
  --risk-plot-path outputs/risk_2026_jan-mar_WA.png \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --min-lat -35 --max-lat -13 \
  --min-lon 112 --max-lon 129
```

Estimated run time for a WA window: ~5–10 minutes depending on SILO cache state (cached runs are substantially faster).

---

## 6. Known Limitations and Future Work

| Item | Description | Priority |
|---|---|---|
| Stress index weights hardcoded | The 0.60/0.25/0.15 weights are not yet exposed as configurable parameters. Adjustment requires modifying `risk.py`. | Medium |
| No temporal trend analysis | Each run produces a snapshot. Multi-period trend comparison (drying trajectories, persistent hotspots) is not yet implemented. | Future |
| No spatial aggregation | Risk map is cell-level only. Aggregation to NRM regions, catchments, or farm units would support decision-support use. | Future |
| Logging | Pipeline uses `print()` for status messages. Replacing with structured `logging` would improve production readiness. | Low |

---

## 7. Data Contract (Summary)

| Input | Source | Units | Notes |
|---|---|---|---|
| `sm_pct` | AWRA-L v7 decile, NCI THREDDS | percentile rank 0–1 | Daily per year; averaged over selected window |
| `max_temp` | SILO | °C | Daily; averaged over window |
| `vp_deficit` | SILO | hPa | Daily; averaged over window |

| Output | Format | Description |
|---|---|---|
| `risk_map` | int8 array (lat, lon) | −1 = no data; 0 = Low; 1 = Watch; 2 = Alert; 3 = Critical |
| `stress_index` | float array (lat, lon) | Continuous 0–1; NaN for invalid cells |
| NetCDF | `.nc` | Risk map with coordinates and metadata |
| JSON | `.json` | Cell counts, percentages, time window |
| PNG | `.png` | Risk map + stress index + diagnostics |
