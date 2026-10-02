import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

import main
from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline


def _mock_end_to_end_data() -> dict[str, object]:
    soil = np.array([[0.10, 0.40], [0.20, np.nan]], dtype=np.float32)
    temperature = np.array([[36.0, 30.0], [32.0, np.nan]], dtype=np.float32)
    vpd = np.array([[35.0, 18.0], [22.0, np.nan]], dtype=np.float32)
    return {
        "soil_moisture": soil,
        "temperature": temperature,
        "vpd": vpd,
        "lats": np.array([-35.0, -34.95]),
        "lons": np.array([115.0, 115.05]),
        "time_metadata": {
            "time_start": "2025-01-01T00:00:00",
            "time_end": "2025-01-07T00:00:00",
        },
    }


def test_run_pipeline_mocked_end_to_end_writes_outputs(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        DryWetClassifierPipeline,
        "_load_all_real_data",
        lambda self: _mock_end_to_end_data(),
    )

    main.run_pipeline(
        ClassifierConfig(
            year=2025, start_date="2025-01-01", end_date="2025-01-07",
            min_lat=-35.0, max_lat=-34.9, min_lon=115.0, max_lon=115.1,
        ),
        output_dir=str(tmp_path), risk_output_prefix="risk_test",
    )

    netcdf_path = tmp_path / "risk_test.nc"
    summary_path = tmp_path / "risk_test_summary.json"
    assert netcdf_path.exists()
    assert summary_path.exists()

    with xr.open_dataset(netcdf_path) as dataset:
        risk_map = dataset["risk_level"].values
        model_metadata = json.loads(dataset.attrs["risk_model_json"])
        assert risk_map.shape == (2, 2)
        assert risk_map[1, 1] == -1
        assert model_metadata["dryness_weight"] == 0.60
        assert model_metadata["critical_risk_threshold"] == 0.85

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["summary"]["valid_cells"]["count"] == 3
    assert payload["summary"]["invalid"]["count"] == 1
    assert payload["model_metadata"]["vpd_weight"] == 0.25
    assert payload["time_metadata"] == _mock_end_to_end_data()["time_metadata"]
    # Independent fixed reference for the documented default formula on these inputs.
    # Stress values are 0.865, 0.373125 and 0.651875 (last cell is invalid).
    np.testing.assert_array_equal(risk_map, [[3, 1], [2, -1]])


@pytest.mark.parametrize("flags, use_cog", [([], True), (["--no-silo-cog-loader"], False), (["--use-silo-cog-loader"], True)])
def test_cli_preserves_defaults_and_explicit_loader_choice(monkeypatch, flags, use_cog):
    calls = []
    monkeypatch.setattr(main, "run_pipeline", lambda config, **outputs: calls.append((config, outputs)))
    main.cli(flags)
    config, outputs = calls[0]
    assert config == ClassifierConfig(use_silo_cog_loader=use_cog)
    assert outputs == {"output_dir": None, "risk_output_prefix": None, "risk_plot_path": None}


def test_cli_maps_all_existing_flags_into_one_config(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "run_pipeline", lambda config, **outputs: calls.append((config, outputs)))
    main.cli([
        "--year", "2025", "--start-date", "2025-01-01", "--end-date", "2025-01-07",
        "--dryness-weight", "0.5", "--vpd-weight", "0.3", "--temperature-weight", "0.2",
        "--watch-risk-threshold", "0.2", "--alert-risk-threshold", "0.5", "--critical-risk-threshold", "0.8",
        "--silo-variable", "max_temp", "--silo-variable", "vp_deficit",
        "--silo-cache-dir", "/tmp/silo", "--silo-cache-max-mb", "150",
        "--silo-overview-level", "1", "--silo-buffer-deg", "0.1", "--no-silo-cog-loader",
        "--min-lat", "-35", "--max-lat", "-30", "--min-lon", "115", "--max-lon", "120",
        "--boundary-gpkg", "boundary.gpkg", "--output-dir", "out",
        "--risk-output-prefix", "risk", "--risk-plot-path", "risk.png",
    ])
    config, outputs = calls[0]
    assert config == ClassifierConfig(
        year=2025, start_date="2025-01-01", end_date="2025-01-07",
        dryness_weight=0.5, vpd_weight=0.3, temperature_weight=0.2,
        watch_risk_threshold=0.2, alert_risk_threshold=0.5, critical_risk_threshold=0.8,
        silo_cache_dir=Path("/tmp/silo"), silo_cache_max_size_mb=150,
        silo_overview_level=1, silo_buffer_degrees=0.1, use_silo_cog_loader=False,
        min_lat=-35, max_lat=-30, min_lon=115, max_lon=120, boundary_gpkg=Path("boundary.gpkg"),
    )
    assert outputs == {"output_dir": "out", "risk_output_prefix": "risk", "risk_plot_path": "risk.png"}


@pytest.mark.parametrize("flags", [
    ["--year", "2025", "--start-date", "2026-01-01"],
    ["--silo-variable", "max_temp", "--silo-variable", "vp"],
    ["--dryness-weight", "0.9"],
])
def test_cli_rejects_invalid_config_before_runner(monkeypatch, flags):
    calls = []
    monkeypatch.setattr(main, "run_pipeline", lambda *a, **k: calls.append(True))
    with pytest.raises(ValueError):
        main.cli(flags)
    assert not calls
