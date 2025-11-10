import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.risk import RiskLevel, assess_risk_levels, save_risk_outputs


def _mock_real_data(with_nan: bool = False) -> dict:
    soil = np.array(
        [[0.10, 0.40, 0.35],
         [0.20, 0.18, 0.50],
         [0.12, 0.22, 0.60]],
        dtype=np.float32
    )
    if with_nan:
        soil[0, 0] = np.nan
    temperature = np.array(
        [[36.0, 30.0, 25.0],
         [32.0, 28.0, 22.0],
         [34.0, 27.0, 24.0]],
        dtype=np.float32
    )
    vpd = np.array(
        [[35.0, 18.0, 12.0],
         [22.0, 15.0, 10.0],
         [28.0, 19.0, 11.0]],
        dtype=np.float32
    )
    ndvi = np.clip(1 - soil, 0, 1)
    ndwi = np.zeros_like(soil)
    fire_index = np.zeros_like(soil)
    lats = np.linspace(-35, -33, soil.shape[0])
    lons = np.linspace(115, 117, soil.shape[1])
    if with_nan:
        temperature[0, 0] = np.nan
    return {
        'soil_moisture': soil,
        'temperature': temperature,
        'ndvi': ndvi,
        'ndwi': ndwi,
        'fire_index': fire_index,
        'vpd': vpd,
        'lats': lats,
        'lons': lons,
    }


def test_pipeline_real_data_flow(monkeypatch):
    """End-to-end sanity check using mocked real data."""
    config = ClassifierConfig(epochs=2, batch_size=8, lr=0.01)
    pipeline = DryWetClassifierPipeline(config)
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data())
    pipeline.prepare_data()
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


def test_prepare_data_populates_expected_grids(monkeypatch):
    pipeline = DryWetClassifierPipeline(ClassifierConfig(epochs=1, batch_size=4))
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data())
    pipeline.prepare_data()

    required_keys = {'soil_moisture', 'temperature', 'ndvi', 'vpd', 'lats', 'lons'}
    assert required_keys.issubset(pipeline.data_grids.keys())
    assert pipeline.X_train.shape[0] == int(0.8 * pipeline.data_grids['soil_moisture'].size)
    assert pipeline.X_test.shape[0] == pipeline.data_grids['soil_moisture'].size - pipeline.X_train.shape[0]


def test_prepare_data_replaces_nan(monkeypatch):
    pipeline = DryWetClassifierPipeline(ClassifierConfig(epochs=1, batch_size=4))
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data(with_nan=True))
    pipeline.prepare_data()

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


def test_pipeline_assess_risk_returns_summary(monkeypatch):
    config = ClassifierConfig(epochs=1, batch_size=8)
    pipeline = DryWetClassifierPipeline(config)
    monkeypatch.setattr(pipeline, "_load_all_real_data", lambda: _mock_real_data())
    pipeline.prepare_data()
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

    base = tmp_path / "nested" / "risk_layer"
    files = save_risk_outputs(risk_map, lats, lons, summary, base)

    assert files['netcdf'].exists()
    assert files['summary'].exists()

    ds = xr.load_dataset(files['netcdf'])
    np.testing.assert_array_equal(ds['risk_level'].values, risk_map)
    assert json.loads(ds.attrs['risk_summary_json']) == summary

    with files['summary'].open() as fp:
        saved_summary = json.load(fp)
    assert saved_summary == summary
