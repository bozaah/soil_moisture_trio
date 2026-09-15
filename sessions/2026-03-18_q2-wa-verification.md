# Session 03 — 2026-03-18: Q2 2025 WA verification run

## Purpose

Verify the post-CatBoost pipeline produces correct, reproducible outputs for WA.

## Runs

### Run 1 — Q2 2025, Australia-wide (mistake)

Command omitted `--min-lat / --max-lat / --min-lon / --max-lon`. Pipeline defaulted to full Australia bounds (-45 to -8 lat, 110 to 155 lon). Result: 572,721 cells, 0% invalid, 100% Alert or Critical — correct technically but not the intended target and took ~8 minutes.

### Run 2 — Q2 2025, WA bounds (correct)

```bash
uv run python main.py \
  --year 2025 \
  --start-date 2025-04-01 \
  --end-date 2025-06-30 \
  --risk-output-prefix outputs/risk_2025_Q2_WA \
  --risk-plot-path outputs/risk_2025_Q2_WA.png \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --min-lat -35 --max-lat -13 \
  --min-lon 112 --max-lon 129
```

**Results:**

| Risk Level | Cells | % |
|---|---|---|
| Critical | 17,870 | 19.38% |
| Alert | 51,155 | 55.49% |
| Watch | 14,152 | 15.35% |
| Low | 9,014 | 9.78% |
| Invalid (ocean) | 58,190 | 38.70% |
| Valid cells | 92,191 | 61.30% |
| Total cells | 150,381 | 100% |

## Regression checks passed

| Check | Oct 2025 WA | Q2 2025 WA | Status |
|---|---|---|---|
| Total cells | 150,381 | 150,381 | ✅ |
| Invalid (ocean) | 58,190 (38.70%) | 58,190 (38.70%) | ✅ |
| Valid cells | 92,191 | 92,191 | ✅ |
| All 4 risk levels present | Yes | Yes | ✅ |

Grid clipping, ocean mask, and output format are all intact post-CatBoost removal.

## Cache behaviour

Run 2 downloaded 0 new files — all 182 SILO GeoTIFFs (91 × max_temp + 91 × vp_deficit) were already cached from Run 1.

## Known warnings (pre-existing, not regressions)

- `Warning: 58,090 extreme VPD values detected; masking for diagnostics.` — logged in B8. VPD values appear unrealistically large for Q2 (winter). Unit or scale issue in the SILO vp_deficit product for this period.

## Outputs

- `outputs/risk_2025_Q2_WA.nc`
- `outputs/risk_2025_Q2_WA_summary.json`
- `outputs/risk_2025_Q2_WA.png`
- `outputs/stress_diagnostics.png`

## Lesson

**Always pass WA bounds explicitly.** The default config covers all of Australia. Omitting bounds is slow (~8 min) and produces an uninformative all-stressed result. Standard WA bounds: `--min-lat -35 --max-lat -13 --min-lon 112 --max-lon 129`.
