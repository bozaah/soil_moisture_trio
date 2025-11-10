import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.risk import RiskLevel, assess_risk_levels, save_risk_outputs


def test_pipeline_synthetic_data():
    """End-to-end sanity check on the synthetic data flow."""
    config = ClassifierConfig(epochs=2, batch_size=8, lr=0.01)
    pipeline = DryWetClassifierPipeline(config)
    pipeline.prepare_data('synthetic')
    pipeline.train()
    metrics = pipeline.evaluate()

    assert 'loss' in metrics
    assert 'accuracy' in metrics
    assert 0.0 <= metrics['accuracy'] <= 1.0
    assert metrics['loss'] >= 0.0

    pred_map = pipeline.predict_grid()
    target_shape = pipeline.data_grids['soil_moisture'].shape
    assert pred_map.shape == target_shape
    assert np.isin(pred_map, [0, 1]).all()


def test_prepare_data_populates_expected_grids():
    pipeline = DryWetClassifierPipeline(ClassifierConfig(epochs=1, batch_size=4))
    pipeline.prepare_data('synthetic')

    required_keys = {'soil_moisture', 'temperature', 'ndvi', 'vpd', 'lats', 'lons'}
    assert required_keys.issubset(pipeline.data_grids.keys())
    assert pipeline.X_train.shape[0] == int(0.8 * pipeline.data_grids['soil_moisture'].size)
    assert pipeline.X_test.shape[0] == pipeline.data_grids['soil_moisture'].size - pipeline.X_train.shape[0]


def test_prepare_data_replaces_nan(monkeypatch):
    pipeline = DryWetClassifierPipeline(ClassifierConfig(epochs=1, batch_size=4))

    def _fake_data():
        grid_size = 6
        base = np.random.rand(grid_size, grid_size).astype(np.float32)
        base[0, 0] = np.nan  # Inject NaN
        return {
            'soil_moisture': base.copy(),
            'temperature': base.copy(),
            'ndvi': base.copy(),
            'ndwi': base.copy(),
            'fire_index': base.copy(),
            'vpd': base.copy(),
            'lats': np.linspace(-1, 1, grid_size),
            'lons': np.linspace(-1, 1, grid_size),
        }

    monkeypatch.setattr(pipeline, "_generate_synthetic_data", _fake_data)
    pipeline.prepare_data('synthetic')

    assert not np.isnan(pipeline.X_train).any()
    assert not np.isnan(pipeline.X_test).any()


def test_assess_risk_levels_categorizes_cells():
    config = ClassifierConfig(
        moisture_threshold=0.25,
        severe_moisture_threshold=0.15,
        temp_threshold=30.0,
        vpd_threshold=20.0,
        critical_temp_threshold=35.0,
        critical_vpd_threshold=30.0,
        watch_margin=0.02,
        epochs=1,
        batch_size=4,
    )
    soil = np.array([[0.10, 0.22], [0.31, 0.26]])
    temp = np.array([[36.0, 32.0], [28.0, 29.0]])
    vpd = np.array([[35.0, 15.0], [10.0, 25.0]])
    classification = np.array([[0, 0], [1, 1]])

    risk_map, summary = assess_risk_levels(
        {'soil_moisture': soil, 'temperature': temp, 'vpd': vpd},
        classification,
        config,
    )

    assert risk_map[0, 0] == RiskLevel.CRITICAL
    assert risk_map[0, 1] == RiskLevel.ELEVATED
    assert risk_map[1, 0] == RiskLevel.LOW
    assert risk_map[1, 1] == RiskLevel.WATCH
    assert summary['critical']['count'] == 1
    assert summary['elevated']['count'] == 1
    assert summary['watch']['count'] == 1
    assert summary['low']['count'] == 1
    assert summary['total_cells']['count'] == 4


def test_pipeline_assess_risk_returns_summary():
    config = ClassifierConfig(epochs=1, batch_size=8)
    pipeline = DryWetClassifierPipeline(config)
    pipeline.prepare_data('synthetic')
    pipeline.train()

    output = pipeline.assess_risk()
    assert 'risk_map' in output
    assert 'summary' in output
    assert output['risk_map'].shape == pipeline.data_grids['soil_moisture'].shape
    assert 'total_cells' in output['summary']


def test_save_risk_outputs_writes_files(tmp_path):
    risk_map = np.array([[RiskLevel.LOW, RiskLevel.WATCH], [RiskLevel.ELEVATED, RiskLevel.CRITICAL]], dtype=np.int8)
    lats = np.array([0.0, 1.0])
    lons = np.array([10.0, 11.0])
    summary = {
        'low': {'count': 1, 'percentage': 0.25, 'label': 'Low'},
        'watch': {'count': 1, 'percentage': 0.25, 'label': 'Watch'},
        'elevated': {'count': 1, 'percentage': 0.25, 'label': 'Elevated'},
        'critical': {'count': 1, 'percentage': 0.25, 'label': 'Critical'},
        'total_cells': {'count': 4, 'percentage': 1.0, 'label': 'Total'},
    }

    base = tmp_path / "risk_layer"
    files = save_risk_outputs(risk_map, lats, lons, summary, base)

    assert files['netcdf'].exists()
    assert files['summary'].exists()

    ds = xr.load_dataset(files['netcdf'])
    np.testing.assert_array_equal(ds['risk_level'].values, risk_map)
    assert json.loads(ds.attrs['risk_summary_json']) == summary

    with files['summary'].open() as fp:
        saved_summary = json.load(fp)
    assert saved_summary == summary
