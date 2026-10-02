# Session 02 — 2026-03-18: Remove CatBoost

## Decision

Removed CatBoost classifier. Replaced with `classify_grid()` — a deterministic threshold rule.

## Why

The CatBoost implementation was scientifically invalid on three counts:

1. **Tautology** — training labels were derived from the same three features (`soil_moisture`, `temperature`, `vpd`) fed to the model. It was learning to reproduce a rule from its own output.
2. **Random NDVI** — `ndvi = np.random.uniform(...)` was a placeholder feature generating noise each run.
3. **Classification never used** — `risk.py` only read `classification_grid >= 0` as a valid-cell mask. The actual dry/wet value was never consumed downstream.

## What changed

| File | Change |
|---|---|
| `pipeline.py` | Removed `build_model`, `train`, `evaluate`, `predict_grid`; added `classify_grid()`; removed `ndvi`/`ndwi`/`fire_index` from data grids; `prepare_data()` now only builds `valid_mask_grid` |
| `config.py` | Removed `ndvi_threshold`, `lr`, `epochs`, `batch_size`, `catboost_*` fields |
| `main.py` | Removed CatBoost CLI flags and train/evaluate block |
| `pyproject.toml` | Removed `catboost`; added `scipy` (direct dep, was catboost transitive) and `pytest` to dev group |
| `tests/test_pipeline.py` | Replaced ML tests with `test_classify_grid_*`; updated mock data |
| `docs/cli-reference.md` | Removed Model Tuning section |
| `docs/backlog.md` | Closed B2/B4/B6/B11/B13; added B20 for future ML |

## Future ML path (B20)

Preconditions before reintroducing an ML classifier:
- Independent labelled dataset (historical expert labels or remote-sensing ground truth — not self-generated from thresholds)
- Real NDVI source (MODIS MOD13A3 or Sentinel-2 composite)
- Spatial cross-validation (block CV, not sequential split)
- `classify_grid()` kept as the interface — ML would slot in behind it without changing the rest of the pipeline

## Test result

`11 passed` — `tests/test_pipeline.py` + `tests/test_data_sources.py`
