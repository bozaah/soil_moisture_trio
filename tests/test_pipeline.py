import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.plot import save_risk_plot
from src.soil_moisture_trio.risk import RISK_LABELS, RiskLevel, assess_risk_levels, save_risk_outputs


def _mock_real_data(with_nan: bool = False) -> dict:
    soil = np.array(
        [[0.10, 0.40, np.nan],
         [0.20, 0.18, 0.50],
         [0.12, 0.22, 0.60]],
        dtype=np.float32,
    )
    temperature = np.array(
        [[36.0, 30.0, np.nan],
         [32.0, 28.0, 22.0],
         [34.0, 27.0, 24.0]],
        dtype=np.float32,
    )
    vpd = np.array(
        [[35.0, 18.0, np.nan],
         [22.0, 15.0, 10.0],
         [28.0, 19.0, 11.0]],
        dtype=np.float32,
    )
    if with_nan:
        soil[0, 0] = np.nan
        temperature[0, 0] = np.nan
        vpd[0, 0] = np.nan
    lats = np.linspace(-35, -33, soil.shape[0])
    lons = np.linspace(115, 117, soil.shape[1])
    return {
        'soil_moisture': soil,
        'temperature': temperature,
        'vpd': vpd,
        'lats': lats,
        'lons': lons,
        'time_metadata': {'time_start': '2025-01-01T00:00:00', 'time_end': '2025-01-01T00:00:00'},
    }


def test_map_silo_variables_aliases_known_keys():
    pipeline = DryWetClassifierPipeline(ClassifierConfig())
    arrays = {
        'max_temp': np.full((2, 2), 1.0, dtype=np.float32),
        'vp_deficit': np.full((2, 2), 2.0, dtype=np.float32),
    }
    mapped = pipeline._map_silo_variables(arrays)
    assert 'temperature' in mapped
    assert 'vpd' in mapped
    np.testing.assert_allclose(mapped['temperature'], arrays['max_temp'])
    np.testing.assert_allclose(mapped['vpd'], arrays['vp_deficit'])


def test_prepare_data_populates_expected_grids(monkeypatch):
    pipeline = DryWetClassifierPipeline(ClassifierConfig())
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data())
    pipeline.prepare_data()

    required_keys = {'soil_moisture', 'temperature', 'vpd', 'lats', 'lons'}
    assert required_keys.issubset(pipeline.data_grids.keys())
    assert 'time_metadata' in pipeline.data_grids
    assert pipeline.valid_mask_grid is not None
    assert pipeline.valid_mask_grid.shape == pipeline.data_grids['soil_moisture'].shape


def test_prepare_data_excludes_nan_cells(monkeypatch):
    """NaN cells must be excluded from valid_mask_grid."""
    pipeline = DryWetClassifierPipeline(ClassifierConfig())
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data(with_nan=True))
    pipeline.prepare_data()

    # NaN cells should be False in valid_mask_grid
    soil = pipeline.data_grids['soil_moisture']
    assert not pipeline.valid_mask_grid[np.isnan(soil)].any()


def test_classify_grid_shape_and_values(monkeypatch):
    """classify_grid must return correct shape with only -1, 0, 1 values."""
    pipeline = DryWetClassifierPipeline(ClassifierConfig())
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data())
    pipeline.prepare_data()
    grid = pipeline.classify_grid()

    assert grid.shape == pipeline.data_grids['soil_moisture'].shape
    assert np.isin(grid, [-1, 0, 1]).all()
    # NaN input cells must be -1
    nan_mask = ~pipeline.valid_mask_grid
    assert (grid[nan_mask] == -1).all()


def test_classify_grid_dry_rule(monkeypatch):
    """Cells meeting dry rule must be 0; others must be 1 (when valid)."""
    config = ClassifierConfig(moisture_threshold=0.25, temp_threshold=30.0, vpd_threshold=20.0)
    pipeline = DryWetClassifierPipeline(config)
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data())
    pipeline.prepare_data()
    grid = pipeline.classify_grid()

    soil = pipeline.data_grids['soil_moisture']
    temp = pipeline.data_grids['temperature']
    vpd = pipeline.data_grids['vpd']
    valid = pipeline.valid_mask_grid

    expected_dry = valid & (soil < 0.25) & ((temp > 30.0) | (vpd > 20.0))
    assert (grid[expected_dry] == 0).all()
    assert (grid[valid & ~expected_dry] == 1).all()


def test_pipeline_assess_risk_returns_summary(monkeypatch):
    pipeline = DryWetClassifierPipeline(ClassifierConfig())
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data())
    pipeline.prepare_data()

    output = pipeline.assess_risk()
    assert 'risk_map' in output
    assert 'summary' in output
    assert 'stress_index' in output
    assert output['risk_map'].shape == pipeline.data_grids['soil_moisture'].shape
    assert 'total_cells' in output['summary']
    assert 'invalid' in output['summary']


def test_assess_risk_levels_categorizes_cells():
    config = ClassifierConfig(
        moisture_threshold=0.25,
        temp_threshold=30.0,
        vpd_threshold=20.0,
        critical_temp_threshold=35.0,
        critical_vpd_threshold=30.0,
    )
    soil = np.array([[0.10, 0.22], [0.31, 0.26]])
    temp = np.array([[36.0, 34.0], [28.0, 29.0]])
    vpd = np.array([[35.0, 15.0], [10.0, 25.0]])
    valid_mask = np.array([[True, True], [True, True]])

    risk_map, summary, stress_index = assess_risk_levels(
        {'soil_moisture': soil, 'temperature': temp, 'vpd': vpd},
        valid_mask,
        config,
    )

    expected = np.full(stress_index.shape, -1, dtype=np.int8)
    expected[valid_mask] = RiskLevel.LOW
    expected[valid_mask & (stress_index >= 0.85)] = RiskLevel.CRITICAL
    expected[valid_mask & ~(stress_index >= 0.85) & (stress_index >= 0.6)] = RiskLevel.ALERT
    expected[valid_mask & ~(stress_index >= 0.6) & (stress_index >= 0.35)] = RiskLevel.WATCH

    np.testing.assert_array_equal(risk_map, expected)

    for level in RiskLevel:
        assert summary[level.name.lower()]['count'] == int(np.sum(risk_map == level))
        assert summary[level.name.lower()]['label'] == RISK_LABELS[level]
    assert summary['total_cells']['count'] == risk_map.size
    assert "elevated" not in summary


def test_assess_risk_levels_handles_invalid_cells():
    config = ClassifierConfig()
    soil = np.array([[0.1, 0.3], [0.2, 0.4]])
    temp = np.array([[36.0, 20.0], [28.0, 22.0]])
    vpd = np.array([[35.0, 10.0], [15.0, 12.0]])
    valid_mask = np.array([[True, False], [True, False]])

    risk_map, summary, stress_index = assess_risk_levels(
        {'soil_moisture': soil, 'temperature': temp, 'vpd': vpd},
        valid_mask,
        config,
    )

    assert summary['invalid']['count'] == 2
    assert summary['valid_cells']['count'] == 2
    assert risk_map[0, 1] == -1


def test_save_risk_outputs_writes_files(tmp_path):
    risk_map = np.array([[RiskLevel.LOW, -1], [RiskLevel.ALERT, RiskLevel.CRITICAL]], dtype=np.int8)
    lats = np.array([0.0, 1.0])
    lons = np.array([10.0, 11.0])
    summary = {
        'low': {'count': 1, 'percentage': 1 / 3, 'label': 'Low'},
        'watch': {'count': 0, 'percentage': 0.0, 'label': 'Watch'},
        'alert': {'count': 1, 'percentage': 1 / 3, 'label': 'Alert'},
        'critical': {'count': 1, 'percentage': 1 / 3, 'label': 'Critical'},
        'invalid': {'count': 1, 'percentage': 0.25, 'label': 'No Data'},
        'valid_cells': {'count': 3, 'percentage': 0.75, 'label': 'Valid grid cells'},
        'total_cells': {'count': 4, 'percentage': 1.0, 'label': 'Total grid cells'},
    }
    time_meta = {'time_start': '2025-01-01T00:00:00', 'time_end': '2025-01-07T00:00:00'}

    base = tmp_path / "nested" / "risk_layer"
    files = save_risk_outputs(risk_map, lats, lons, summary, base, time_metadata=time_meta)

    assert files['netcdf'].exists()
    assert files['summary'].exists()

    ds = xr.load_dataset(files['netcdf'])
    np.testing.assert_array_equal(ds['risk_level'].values, risk_map)
    assert json.loads(ds.attrs['risk_summary_json']) == summary
    for key, value in time_meta.items():
        assert ds.attrs[key] == value

    with files['summary'].open() as fp:
        payload = json.load(fp)
    assert payload['summary'] == summary
    assert payload['time_metadata'] == time_meta


def test_save_risk_plot_creates_png(tmp_path):
    risk_map = np.array([[RiskLevel.LOW, -1], [RiskLevel.WATCH, RiskLevel.ALERT]], dtype=np.int8)
    lats = np.array([0.0, 1.0])
    lons = np.array([10.0, 11.0])
    output = tmp_path / "plots" / "risk.png"

    path = save_risk_plot(risk_map=risk_map, lats=lats, lons=lons, output_path=output)
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 0


def test_load_soil_moisture_data_raises_when_decile_fails_without_opt_in(monkeypatch):
    pipeline = DryWetClassifierPipeline(ClassifierConfig(allow_legacy_sm=False))

    def fake_load_real_netcdf(file_path, var_name):
        raise OSError("decile unavailable")

    monkeypatch.setattr(pipeline, "_load_real_netcdf", fake_load_real_netcdf)

    with pytest.raises(RuntimeError, match="allow-legacy-sm"):
        pipeline._load_soil_moisture_data(
            {
                "pct_url": "decile-url",
                "pct_var": "sm_pct",
                "legacy_url": "legacy-url",
                "legacy_var": "sm_pct",
            }
        )


def test_load_soil_moisture_data_falls_back_to_legacy_when_opted_in(monkeypatch):
    pipeline = DryWetClassifierPipeline(ClassifierConfig(allow_legacy_sm=True))
    calls = []

    def fake_load_real_netcdf(file_path, var_name):
        calls.append((file_path, var_name))
        if file_path == "decile-url":
            raise OSError("decile unavailable")
        return np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32), {"time_start": "2025-01-01"}

    def fake_load_spatial_coords(file_path):
        assert file_path == "legacy-url"
        return np.array([-35.0, -34.0]), np.array([115.0, 116.0])

    monkeypatch.setattr(pipeline, "_load_real_netcdf", fake_load_real_netcdf)
    monkeypatch.setattr(pipeline, "_load_spatial_coords", fake_load_spatial_coords)

    soil, meta, lats, lons = pipeline._load_soil_moisture_data(
        {
            "pct_url": "decile-url",
            "pct_var": "sm_pct",
            "legacy_url": "legacy-url",
            "legacy_var": "sm_pct",
        }
    )

    assert calls == [("decile-url", "sm_pct"), ("legacy-url", "sm_pct")]
    np.testing.assert_allclose(soil, np.array([[0.1, 0.2], [0.3, 0.4]], dtype=float))
    assert meta == {"time_start": "2025-01-01"}
    np.testing.assert_allclose(lats, np.array([-35.0, -34.0]))
    np.testing.assert_allclose(lons, np.array([115.0, 116.0]))
