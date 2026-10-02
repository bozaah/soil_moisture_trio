# Session — 2026-03-25: Boundary GeoPackage Integration (Sprint 9)

## Goal

Use the DPIRD South West Agricultural Boundary (`data/south_west_agricultural_boundary.gpkg`) to:

1. Derive the download bounding box automatically (replacing hardcoded lat/lon CLI flags)
2. Mask grid cells outside the polygon so stats count only agricultural-zone cells

---

## Architecture Decision — Option B vs Option A

Two approaches were considered:

**Option B (implemented this sprint):** Derive download bbox from gpkg bounds + buffer; apply polygon mask after loading.

**Option A (backlog B24):** Download all WA once; cache at WA scale; clip/mask per region downstream. Better for a multi-region monitoring product (SWAZ + rangelands + pastoral), but requires fixing B22 (cache-bbox key) first. Option A is the right long-term architecture if rangelands outputs are needed alongside the agricultural zone.

**Decision:** Option B now. Option A when rangelands are in scope — it requires B22 fix and a redesign of the SILO cache layer.

---

## Boundary File

Path: `data/south_west_agricultural_boundary.gpkg`
CRS: EPSG:28350 (GDA94 MGA Zone 50)
Features: 5 MultiPolygon features (no meaningful attributes beyond geometry)
Bounds (EPSG:4326): lon 114.1083–123.2467, lat -35.1355–-27.5235

Key finding: the southern boundary reaches -35.14°, which was clipped by the previous hardcoded `-35` `--min-lat`. The 0.1° buffer brings the effective download extent to lat -35.24° — capturing all agricultural cells.

---

## Implementation

### `config.py`

Added:
```python
boundary_gpkg: Optional[Path] = Field(
    None,
    description="Path to a GeoPackage boundary file. When set, bbox is derived from its bounds (+0.1° buffer) and cells outside the polygon are masked."
)
```

### `pipeline.py`

Two new methods:

**`_derive_bounds_from_gpkg(config, buffer=0.1)`** — static method called at `__init__` if `boundary_gpkg` is set. Reads the file, projects to EPSG:4326, extracts `total_bounds`, adds buffer, returns `config.model_copy(update={...})`. This ensures all downstream methods (`_align_lat_lon`, `_load_silo_via_weather_tools`) use the correct bbox without any further changes.

**`_build_polygon_mask(lats, lons)`** — builds a boolean array the same shape as the grid. Uses `geopandas.union_all()` + `shapely.contains_xy()` (vectorised) to test whether each cell centre falls inside the union of all boundary features. Fast: the vectorised `contains_xy` handles the full ~29,000-cell grid in under a second.

Applied in `prepare_data()` after NaN masking:
```python
if self.config.boundary_gpkg is not None:
    poly_mask = self._build_polygon_mask(data["lats"], data["lons"])
    self.valid_mask_grid = self.valid_mask_grid & poly_mask
```

### `plot.py`

Added optional `boundary_gpkg` parameter to `save_risk_plot`. When set, overlays the boundary as a black polygon outline on both panels (categorical + continuous):
```python
if boundary_gpkg:
    gdf = gpd.read_file(boundary_gpkg).to_crs("EPSG:4326")
    for ax in axes:
        gdf.boundary.plot(ax=ax, color="black", linewidth=0.7, zorder=5)
```

### `main.py`

Added `--boundary-gpkg PATH` flag. When set:
- Passed to `ClassifierConfig` → pipeline derives bbox automatically
- Passed to `save_risk_plot` → boundary overlay on figures
- No need to specify `--min-lat / --max-lat / --min-lon / --max-lon` when using the boundary file

### New dependencies

Added to `pyproject.toml`:
- `geopandas>=1.0` — reads gpkg, CRS projection
- `matplotlib-scalebar>=0.9` — reserved for scale bar (Sprint 10)
- `pyogrio` — installed as geopandas dependency (fast GeoPackage I/O)

---

## New run command

```bash
uv run python main.py \
  --year 2026 \
  --start-date 2026-03-01 \
  --end-date 2026-03-23 \
  --output-dir outputs/risk_2026_mar_SWAZ_boundary \
  --risk-output-prefix risk_2026_mar_SWAZ_boundary \
  --risk-plot-path risk_2026_mar_SWAZ_boundary.png \
  --silo-variable max_temp \
  --silo-variable vp_deficit \
  --silo-cache-dir ~/.cache/soil_moisture_trio/silo_swaz \
  --boundary-gpkg data/south_west_agricultural_boundary.gpkg
```

---

## Verification — March 2026

| Run | Critical | Alert | Watch | Low | Valid cells |
|---|---|---|---|---|---|
| Bbox only (−35 to −27) | 405 (1.69%) | 3,745 (15.65%) | 10,351 (43.25%) | 9,432 (39.41%) | 23,933 |
| Boundary masked | 7 (0.07%) | 1,490 (15.48%) | 4,425 (45.97%) | 3,703 (38.47%) | 9,625 |

Key finding: the 405 "Critical" cells in the bbox-only run were almost entirely in the northern rangelands and non-agricultural areas outside the boundary polygon. Within the actual agricultural zone, only 7 cells meet the Critical threshold in March 2026. Alert proportion is stable (~15.5%), confirming it was already well-contained within the boundary.

The polygon correctly excludes: (a) ocean cells, (b) the Wheatbelt/rangeland fringe north of the agricultural zone, (c) isolated non-agricultural parcels.

11 unit tests pass.

---

## Backlog updates

- **B24 added** — Option A (full WA download + multi-region clip) for future rangelands support. Requires B22 fix first.

---

## Changes summary

| File | Change |
|---|---|
| `src/soil_moisture_trio/config.py` | `boundary_gpkg: Optional[Path]` field added |
| `src/soil_moisture_trio/pipeline.py` | `_derive_bounds_from_gpkg()` + `_build_polygon_mask()` + polygon masking in `prepare_data()` |
| `src/soil_moisture_trio/plot.py` | `boundary_gpkg` parameter in `save_risk_plot`; boundary overlay on both panels |
| `main.py` | `--boundary-gpkg` flag added, wired through config and plot |
| `docs/backlog.md` | B24 added |
| `pyproject.toml` | `geopandas`, `matplotlib-scalebar` added |
| `outputs/risk_2026_mar_SWAZ_boundary/` | New run outputs with boundary masking |
