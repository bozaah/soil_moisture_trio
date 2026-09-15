# Session — 2026-03-25: Persistent SILO Cache + Bulletin Template (Sprint 7)

## Goal

Two deliverables:

1. Make the SILO GeoTIFF cache persistent by default (`~/.cache/soil_moisture_trio/silo`) so operational re-runs do not re-download tiles.
2. Add a reproducible Markdown bulletin template (Jinja2) + CLI renderer for policy communications.

Plus: correct a documentation/code discrepancy found during review.

---

## Discrepancy Found — Section 2 vs Actual Code

During review, the following was identified:

**Section 2 of `docs/technical_report.md`** stated that "the pipeline assigns each grid cell to one of four drought risk categories based on its soil moisture percentile rank" and listed thresholds (≤0.10 Critical, 0.10–0.20 Alert, etc.).

**`risk.py` does not use those thresholds** to assign risk levels. The actual classification path is:

1. Compute `dryness_factor = clip((0.50 - sm_pct) / 0.50, 0, 1)` — continuous
2. Compute `temp_factor = clip(temp / 40.0, 0, 1)` — continuous
3. Compute `vpd_factor = clip(vpd / 32.0, 0, 1)` — continuous
4. `stress_index = 0.60 * dryness + 0.25 * vpd + 0.15 * temp`
5. Assign risk level from stress index: ≥0.85 → Critical, 0.60–0.85 → Alert, 0.35–0.60 → Watch, <0.35 → Low

The following `ClassifierConfig` fields are **defined but never referenced by `risk.py`**:

| Field | Value | Status |
|---|---|---|
| `severe_moisture_threshold` | 0.10 | Legacy — unused by risk.py |
| `alert_moisture_threshold` | 0.20 | Legacy — unused by risk.py |
| `watch_margin` | 0.10 | Legacy — unused by risk.py |
| `temp_threshold` | 30.0 | Legacy — unused by risk.py |
| `vpd_threshold` | 20.0 | Legacy — unused by risk.py |
| `alert_temp_threshold` | 32.0 | Legacy — unused by risk.py |
| `alert_vpd_threshold` | 24.0 | Legacy — unused by risk.py |

These are vestiges of the pre-Sprint-6 rule-based classifier. They are retained in config (may be useful for future stepped-threshold or ML work) but documented as legacy in the technical report.

**Decision**: Reframe Section 2 as an interpretive reference for the soil moisture component; Section 3 (composite stress index) is the authoritative classification methodology.

---

## Step 1 — Persistent SILO cache

**Change**: `src/soil_moisture_trio/config.py`

```python
# Before
silo_cache_dir: Optional[Path] = Field(None, ...)

# After
silo_cache_dir: Path = Field(
    default_factory=lambda: Path.home() / ".cache" / "soil_moisture_trio" / "silo",
    ...
)
```

Prior behaviour: `cache_dir=None` → `save_to_disk=False` in `WeatherToolsSiloLoader` → tiles downloaded but not persisted by the pipeline. weather_tools may have maintained its own internal temp cache, but this was not portable or guaranteed to survive across OS reboots.

New behaviour: cache dir created automatically at `~/.cache/soil_moisture_trio/silo`; tiles saved and LRU-evicted to `silo_cache_max_size_mb` (default 200 MB). Override with `--silo-cache-dir PATH`.

Migration: Prior runs with `save_to_disk=False` left no managed cache files. Any weather_tools internal temp tiles at `/var/folders/.../T/weather_tools_cache/` were searched; if found, they were moved to the new location.

---

## Step 2 — Bulletin template

New files:

- `templates/bulletin_template.j2` — Jinja2 Markdown template
- `scripts/render_bulletin.py` — CLI renderer

Usage:

```bash
uv run python scripts/render_bulletin.py \
  --summary-json outputs/risk_2026_jan-mar_WA_summary.json \
  --map-png outputs/risk_2026_jan-mar_WA.png \
  --output outputs/bulletin_2026_jan-mar_WA.md
```

---

## Step 3 — Outputs regenerated

Jan–Mar 2026 WA outputs regenerated with calibrated pipeline:

- `outputs/risk_2026_jan-mar_WA_summary.json` — overwritten
- `outputs/risk_2026_jan-mar_WA.png` — overwritten
- `outputs/stress_diagnostics.png` — overwritten

Pre-regeneration JSON (legacy, pre-decile-fix): Critical 47.1%, Alert 29.5%, Watch 9.4%, Low 14.1%.
Post-regeneration (calibrated): see fresh `outputs/risk_2026_jan-mar_WA_summary.json`.

---

## Step 4 — Threshold recalibration: moisture_threshold 0.30 → 0.50

**Problem:** With `moisture_threshold = 0.30`, the dryness factor was zero for all cells above the 30th percentile and underweighted cells in the 10th–30th percentile range. In autumn/spring when VPD and temperature are moderate, Critical and Alert were near-zero even when soil moisture was substantially below normal. March 2026 SWAZ with old setting: Critical 0.0%, Alert 8.6%.

**Decision:** Change `moisture_threshold` from 0.30 to 0.50 (climatological median as reference). The dryness factor now measures departure below the median, consistent with BoM anomaly framing. This is Option B from the threshold analysis. Option C (seasonal thresholds) added to backlog as B23.

**Validation — March 1–23 2026, SWAZ (lat -35 to -27, lon 114 to 123):**

| | Old (0.30) | New (0.50) | Target |
|---|---|---|---|
| Critical | 0.0% | 1.7% | < 10% ✓ |
| Alert | 8.6% | 15.6% | < 20–25% ✓ |
| Watch | 35.0% | 43.3% | — |
| Low | 56.4% | 39.4% | — |

The Watch increase reflects that cells between the 30th and 50th percentile now contribute partial dryness, which is appropriate for below-median soil moisture in combination with end-of-summer atmospheric stress.

**New bug noted:** B22 — SILO cache key does not include bounding box, causing shape mismatch crashes when mixing bbox runs in one cache dir. Workaround documented in backlog.

---

## Changes Summary

| File | Change |
|---|---|
| `src/soil_moisture_trio/config.py` | `silo_cache_dir` default → persistent `~/.cache/soil_moisture_trio/silo`; `moisture_threshold` 0.30 → 0.50 |
| `docs/data-sources.md` | SILO cache section updated with new default path |
| `docs/backlog.md` | B21 resolved (cache); B22 added (cache-bbox bug); B23 added (seasonal thresholds, future) |
| `docs/technical_report.md` | Section 2 reframed as interpretive reference; Section 3 expanded with scientific rationale; §3.5 new subsection on moisture_threshold=0.50 rationale and calibration note |
| `templates/bulletin_template.j2` | New — Jinja2 bulletin template |
| `scripts/render_bulletin.py` | New — CLI bulletin renderer |
