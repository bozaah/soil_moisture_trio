import json

import numpy as np
import xarray as xr

import main
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
        output_dir=str(tmp_path),
        risk_output_prefix="risk_test",
        year=2025,
        start_date="2025-01-01",
        end_date="2025-01-07",
        min_lat=-35.0,
        max_lat=-34.9,
        min_lon=115.0,
        max_lon=115.1,
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
