## Soil Moisture Trio

This project trains a CatBoost classifier to label Australian grid cells as **dry** or **wet** based on soil moisture, SILO temperature, NDVI (placeholder), and VPD. The CLI in `main.py` orchestrates data prep, training/testing, risk scoring, and optional Folium/PNG exports.

Key changes and operational notes (recent):

- The pipeline now requires the AWRAL `sm_pct` product for soil moisture. The loader is defensive about units: it will autodetect whether `sm_pct` is expressed as percent (0–100) or already as a fraction (0–1) and only convert (divide by 100) when the data clearly appears to be percent. A short INFO message is printed at load time describing which branch was taken. Internally the pipeline works with volumetric fraction (0–1).
- The legacy `sm` product fallback has been removed to avoid unit confusion. If `sm_pct` cannot be found the pipeline will raise a clear error (see `pipeline._load_all_real_data`).
- `assess_risk_levels()` now returns a continuous per-cell "dryness / stress" index in addition to the categorical risk map and summary — callers (and `pipeline.assess_risk`) now expose this `stress_index` for plotting and diagnostics.
- Plotting and diagnostics were hardened: diagnostic scatter/hist panels now flatten/mask NaNs and extreme outliers, and a lat/lon alignment bug (incorrect indexing for arrays with leading dims) was fixed so the diagnostic axes show realistic values.

Weather data sourcing

- Soil moisture: AWRAL `sm_pct` NetCDF on NCI (required). The pipeline converts this percent product into a volumetric fraction internally.
- SILO variables (max temperature, VPD, etc.) default to the `weather_tools` GeoTIFF/COG loader so we only download the requested bounding box. Use `--no-silo-cog-loader` to revert to the older NetCDF-based loader when needed.

Configure key loader/pipeline behaviour via `ClassifierConfig` and the `main.py` CLI flags:

- `--silo-variable` (repeatable) selects which SILO variables/presets to request (e.g., `max_temp`, `vp_deficit`).
- `--silo-cache-dir`, `--silo-cache-max-mb`, `--silo-overview-level`, and `--silo-buffer-deg` control COG subsetting and caching behaviour.
- Spatial focus: `--min-lat/--max-lat/--min-lon/--max-lon`.

Running the pipeline (example):

```bash
.venv/bin/python main.py \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --year 2024 \
  --start-date 2024-01-01 \
  --end-date 2024-03-31
```

Example using `uv` (project toolchain) with a WA bounding box and 2025-Oct window:

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


Thresholds and calibration guidance

The internal canonical soil moisture unit used by the pipeline is volumetric fraction (0–1). Note that some deployments of the AWRAL product provide `sm_pct` already as a fraction (0–1); others provide true percents (0–100). The loader now auto-detects and adapts. Recent diagnostics on 2024 data showed the grid contains much smaller values than older expectations (so an absolute cutoff like 0.25 would mark most cells dry).

Recommendations:

- Short-term (fast check): keep the existing hardcoded thresholds for compatibility, but when running on a new dataset try a lower `moisture_threshold` (for example 0.01–0.03 = 1–3% volumetric fraction) and visually inspect the risk maps.
- Medium/long-term (recommended): compute thresholds from a reference climatology (e.g., set `moisture_threshold` to the 25th percentile of the multi-year baseline for your region/season; `severe_moisture_threshold` could be the 10th percentile). This is more robust than fixed numbers and will adapt to sensor/processing differences.
- The pipeline now prints a helpful message when it detects that `sm_pct` was converted; use that to verify whether your copy of the product needs a manual override.

Developer notes

- Tests mock `_load_all_real_data` for speed (so unit tests remain fast and deterministic).

See `Plan.md` for suggested follow-ups: threshold calibration, integration tests, and optional CLI compatibility flag.
