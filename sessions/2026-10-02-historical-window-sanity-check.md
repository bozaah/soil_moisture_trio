# 2026-10-02 — Historical window sanity check, window A (March to May)

Rodrigo asked for runs over periods known to be problematic, suggesting 2019 before the break and 2026, which he described as very low in the Mid West. No code or configuration changed. Commit `9be38ea`, `dev` level with `origin/dev`.

## Design

Agreed before running:

- Compare years in the same calendar window, not windows across seasons. Soil moisture is a percentile rank by location and day of year, but temperature and VPD use fixed cut-offs (40 °C, 32 hPa), so autumn heat inflates stress in every year (B23). Comparing years in one window cancels most of that.
- Contrast year 2021, assumed a strong WA season. Not checked against BoM or DPIRD records.
- Two windows: A, 1 March to 31 May (pre-break), and B, 25 May to 31 July (break of season, where the 2019 Mid West problem was assumed to sit). Only A has been run.
- The summary JSON covers the whole SWAZ and dilutes a Mid West signal. A regional breakdown needs the polygon grouping input still open under B14a. For now the north is approximated by a latitude cut at 30.5°S, computed from the run NetCDF, not an official region boundary.

The check is whether known-bad years show more Watch/Alert than the contrast year. It is a sanity check, not independent skill.

## Runs

README defaults with dates and names changed, SWAZ boundary, sequential:

```bash
for y in 2019 2021 2026; do n=risk_${y}_mar-may_SWAZ_boundary
  uv run --frozen python main.py --year $y --start-date $y-03-01 --end-date $y-05-31 \
    --output-dir outputs/$n --risk-output-prefix $n --risk-plot-path $n.png \
    --boundary-gpkg data/south_west_agricultural_boundary.gpkg > outputs/logs/$n.log 2>&1
done
```

All exited 0, about 4 minutes each including the 2019 and 2021 downloads. Each run has 9,650 valid of 29,016 cells, the same as the 50-day July to September run.

| Mar–May | Low | Watch | Alert | Critical |
|---|---|---|---|---|
| 2019 SWAZ | 35.6% | 56.4% | 8.0% | 1 cell |
| 2019 north of 30.5°S (1,803 cells) | 0% | 60.1% | 39.8% | 0.1% |
| 2019 south (7,847 cells) | 43.8% | 55.5% | 0.6% | 0 |
| 2021 SWAZ | 99.9% | 0.1% | 0 | 0 |
| 2026 SWAZ | 99.6% | 0.4% | 0 | 0 |

Mean stress index in the north: 2019 0.57, 2021 0.25, 2026 0.28.

## Findings

- 2019 separates clearly from 2021, concentrated in the north. Consistent with a dry northern autumn, not yet checked against external records.
- March to May 2026 is as benign as 2021 under this model, north included. The Mid West dryness Rodrigo described is either later in the year or not captured. The July to September 2026 run (17.6% Alert) suggests later.
- Critical is almost absent. Averaging over 92 days pulls daily extremes toward the middle, so seasonal windows rarely reach Critical.

Outputs (gitignored): `outputs/risk_{2019,2021,2026}_mar-may_SWAZ_boundary/` with run NetCDF, summary JSON, risk PNG and `stress_diagnostics.png`. Logs in `outputs/logs/`.

## Next

1. Run window B (25 May to 31 July) for 2019, 2021 and 2026 with the same command pattern.
2. Check 2019 and 2021 as bad/good years and the timing of 2026 Mid West dryness against BoM rainfall deciles or DPIRD season reports.
3. If a regional split is needed beyond the latitude cut, it depends on B14a's polygon-to-raster grouping input.
