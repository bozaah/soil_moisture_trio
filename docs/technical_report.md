# Soil Moisture Trio — Technical Report

**Version:** Sprint 11 | **Date:** 2026-08-12
**Status:** Operational — decile-calibrated, composite stress index risk classification

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

## 2. Soil Moisture Percentile Rank — Interpretation Reference

The table below shows how `sm_pct` percentile rank values map to drought severity classes for interpretation and communication purposes.

> **Note:** The pipeline's actual risk assignment uses the **composite stress index** described in Section 3, not these percentile bands directly. The table below is an interpretation aid for the decile product itself.

| Percentile rank | Severity class | Interpretation |
|---|---|---|
| ≤ 0.10 | **Critical** | Soil moisture is at or below the 10th percentile — conditions as dry or drier than 90% of historical observations for this location and season. Consistent with severe drought. |
| 0.10 – 0.20 | **Alert** | 10th to 20th percentile. Significant drying episode; below what is typical for the season. Likely to affect pasture recovery, crop viability, and stock water. |
| 0.20 – 0.30 | **Watch** | 20th to 30th percentile. Drier than roughly two-thirds of historical years. Warrants monitoring, particularly if conditions persist. |
| > 0.30 | **Low** | Above the 30th percentile. Within or above the historically normal range. No immediate drought concern. |

### 2.1 Why These Boundaries?

The 10th, 20th, and 30th percentiles are standard reference points in Australian drought monitoring (consistent with the Bureau of Meteorology's decile-based drought classification). Defining categories in percentile space means:

- A cell at the 10th percentile in January in the wheatbelt is experiencing the same *relative* severity of dryness as a cell at the 10th percentile in July in the Kimberley — even though their absolute soil water contents differ greatly.
- The proportion of the landscape in each category is stable over long climatological averages (by construction, ~10%, ~10%, ~10%, ~70% on average).
- Short-term departures from those proportions indicate genuine anomalies.

### 2.2 Calibration Validation

Switching from raw volumetric fraction to the percentile rank product eliminated a systematic over-classification bias. The table below shows soil-moisture-only classification of January–March 2026 WA cells under both approaches:

| Category | Raw sm_pct (old) | Decile rank (current) |
|---|---|---|
| Critical | 47.1% | 1.1% |
| Alert | 29.5% | 6.8% |
| Watch | 9.4% | 12.3% |
| Low | 14.1% | 79.9% |

With the raw product, almost half of WA was classified Critical in summer — not because conditions were genuinely extreme, but because the absolute threshold (0.25 volumetric fraction) sat above most of the observed distribution. The decile product produces results consistent with climatological expectation: based on soil moisture alone, Critical and Alert conditions affect a small fraction of the landscape except during genuine drought events.

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

- **`dryness_factor`** measures how far below the climatological median (0.50 percentile rank) the current soil moisture is, expressed as a proportion of that reference point. A cell at or above the 50th percentile has dryness_factor = 0 (no soil water stress contribution). A cell at the 20th percentile has dryness_factor = 0.60. A cell at the 5th percentile has dryness_factor = 0.90. A cell at the 0th percentile has dryness_factor = 1.0 (maximum). Using the median as the reference — rather than an absolute volumetric threshold — means the dryness_factor is measuring *departure from climatological normal*, consistent with how BoM frames precipitation and soil moisture anomalies. This also ensures the formula is seasonally symmetric: conditions drier than the historical median always contribute positively to stress, regardless of season.

- **`temp_factor`** normalises temperature against the critical heat threshold (40°C). At 40°C, temp_factor = 1.0; below that it scales linearly.

- **`vpd_factor`** normalises vapour pressure deficit against a critical VPD threshold (32 hPa = 3.2 kPa). High VPD accelerates plant water loss and intensifies moisture stress independently of soil water content.

**Weights:** Soil moisture deficit is the primary driver (60%), with atmospheric demand (VPD, 25%) and heat (15%) as amplifiers.

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

The valid cell mask is built once during data loading (`prepare_data()`): a cell is valid if and only if all three inputs — soil moisture, temperature, and VPD — contain finite values. When `--boundary-gpkg` is used, the valid mask is further restricted to cells whose centres fall inside the supplied polygon. Ocean and missing-data cells are excluded at this stage and carry a sentinel value of `-1` through all outputs. No imputation is performed.

### 3.5 Scientific Rationale for Thresholds and Weights

#### Dryness reference point — 0.50 (climatological median)

The `moisture_threshold` parameter sets the reference point at which `dryness_factor` becomes zero — i.e., the soil moisture percentile rank above which a cell contributes no soil water stress to the composite index. Using the climatological median (0.50) means:

- The dryness formula measures *departure below the median*, directly analogous to BoM's approach of expressing anomalies relative to the historical median.
- Cells at the 30th–50th percentile (below-normal but not severe) contribute moderate dryness, which is appropriate in combination with elevated atmospheric demand in the shoulder seasons (autumn/spring).
- In genuine drought conditions (sm_pct < 10th percentile), dryness_factor ≥ 0.80, ensuring these cells drive Alert or Critical classification when atmospheric stress is present.
- The maximum soil-moisture-alone stress contribution is 0.60 × 1.0 = 0.60, which places a cell with zero soil moisture at the Alert/Critical boundary — requiring at least some atmospheric stress to confirm Critical classification. This prevents cells at extreme-but-not-exceptional soil moisture from being classified Critical solely on dryness.

> **Calibration note (Sprint 7):** `moisture_threshold` was changed from 0.30 to 0.50. The earlier value (0.30) caused dryness_factor to be zero for all cells above the 30th percentile and to underweight the contribution of cells in the 10th–30th percentile range. The result was near-zero Critical and low Alert proportions in autumn/spring even when soil moisture was substantially below normal. The 0.50 value restores the intended sensitivity and produces climatologically plausible outputs across all seasons. March 2026 SWAZ validation: Critical 1.7%, Alert 15.6% (target: <10%, <20–25%).

#### Temperature threshold — 40°C

Heat denaturation of photosynthetic enzymes (Rubisco) accelerates above 38–40°C in C3 crops. Wheat pollen viability drops sharply above 35°C and grain fill is critically impaired above 38°C; 40°C is the broadly-cited catastrophic damage threshold used in BoM agroclimate guidance and DPIRD agronomy advisory. For rangeland livestock, metabolic heat load in cattle and sheep becomes severe above 35°C and life-threatening above 40°C. Using 40°C as the normalisation denominator means `temp_factor` reaches 1.0 only at the observed physiological damage ceiling, and scales proportionally below it.

#### VPD threshold — 32 hPa (3.2 kPa)

Stomatal closure in most broadacre crops begins around 1.5 kPa; virtually all WA crop species show significant yield penalties above 2.5 kPa. At 3.2 kPa (32 hPa), atmospheric demand exceeds the capacity of most crops to maintain favourable water balance even with moderate soil moisture, and no longer discriminates meaningfully between "severe" and "catastrophic" conditions. This value represents the upper tail of the WA growing-season VPD distribution and is consistent with the threshold above which BoM classifies atmospheric dryness as extreme for agricultural purposes. Using 32 hPa as the normalisation denominator ensures `vpd_factor` captures the full dynamic range of agronomically meaningful VPD without saturating at moderate values.

#### Weight rationale — 0.60 / 0.25 / 0.15

| Component | Weight | Rationale |
|---|---|---|
| Soil moisture deficit | 0.60 | Water availability is the primary limiting factor for plant growth in dryland WA systems. The AWRA-L percentile rank directly measures the probability of seeing drier conditions, making it the most robust signal in the composite. |
| VPD | 0.25 | Drives transpiration demand and accelerates soil water depletion. High VPD independently reduces water-use efficiency and can cause stress even with moderate soil moisture. Its contribution amplifies soil moisture stress rather than substituting for it. |
| Temperature | 0.15 | Direct heat damage occurs at extremes but co-varies strongly with VPD (hot days are typically dry). A lower weight mitigates double-counting of the atmospheric stress signal already partially captured by the VPD term. |

These weights are consistent with the agronomic literature and represent expert judgment. They have **not been formally optimised against observed yield or pasture-loss data** and should be treated as calibration parameters subject to revision when labelled outcome data become available (see B20 in `docs/backlog.md`).

#### Stress index thresholds — 0.35 / 0.60 / 0.85

The thresholds are set so that atmospheric stress alone (VPD + temperature, with no soil moisture deficit) cannot drive cells above the Watch category, ensuring soil water depletion is always a prerequisite for higher-severity classification:

| Threshold | What is required to reach it |
|---|---|
| Watch (≥ 0.35) | Soil moisture near-adequate (dryness ≈ 0) with near-maximum combined VPD and temperature (max atmospheric contribution = 0.25 + 0.15 = 0.40). Atmospheric stress alone can just breach Watch; soil moisture deficit pulls it higher. |
| Alert (≥ 0.60) | Requires soil moisture deficit. With dryness = 0 (sm_pct ≥ 0.50), maximum stress is 0.40 — Alert is unreachable by atmospheric stress alone. A cell at the ~15th percentile with high VPD and temperature reaches Alert. |
| Critical (≥ 0.85) | Cannot be reached without severe soil moisture deficit. Requires sm_pct ≤ approximately the 8th percentile with near-maximum VPD and temperature, or sm_pct near the 0th percentile with moderate atmospheric stress. This ensures Critical reflects genuine multi-factor extremes. |

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

### 4.4 Bulletin (Markdown)

A formatted Markdown bulletin for policy staff, rendered from the summary JSON via `scripts/render_bulletin.py` against `templates/bulletin_template.j2`. Includes key finding, risk table, map reference, methodology note, and caveats. See Section 5.2.

### 4.5 Interactive Map (optional)

A Folium HTML map with clickable cells showing risk level and coordinates, for field-scale exploration.

---

## 5. Operational Use

### 5.1 Standard WA Run

The default spatial domain covers all of Australia. For Western Australia operational runs, either use explicit WA bounds or, for named regions such as SWAZ, prefer `--boundary-gpkg` so the bbox is derived automatically and cells outside the polygon are masked.

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

The SILO cache directory defaults to `~/.cache/soil_moisture_trio/silo` and is created automatically on first run. Cached GeoTIFFs are stored beneath bbox-hashed subdirectories inside that cache root. Pass `--silo-cache-dir PATH` to override. Re-running the same period with a warm cache incurs zero downloads.

For live operational runs, keep `--end-date` no later than today minus two days because SILO publication usually lags by 1 to 2 days.

Estimated run time for a WA window: ~5–10 minutes on first run (cold cache); substantially faster on subsequent runs.

### 5.2 Rendering a Bulletin

After a pipeline run, generate a policy bulletin from the summary JSON:

```bash
uv run python scripts/render_bulletin.py \
  --summary-json outputs/risk_2026_jan-mar_WA_summary.json \
  --map-png outputs/risk_2026_jan-mar_WA.png \
  --output outputs/bulletin_2026_jan-mar_WA.md
```

---

## 6. Known Limitations and Future Work

| Item | Description | Priority |
|---|---|---|
| Stress index weights not configurable | The 0.60/0.25/0.15 weights are hardcoded in `risk.py`. Adjustment requires modifying source code. Exposure via `ClassifierConfig` tracked as B10. | Medium |
| Weights not empirically validated | Weights and thresholds are expert-judgment calibrations. Formal optimisation against yield/pasture-loss data is tracked as B20. | Future |
| No temporal trend analysis | Each run produces a snapshot. Multi-period trend comparison (drying trajectories, persistent hotspots) is not yet implemented. | Future |
| No spatial aggregation | Risk map is cell-level only. Aggregation to NRM regions, catchments, or farm units would support decision-support use. | Future |

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
| Bulletin | `.md` | Policy-ready Markdown bulletin |
