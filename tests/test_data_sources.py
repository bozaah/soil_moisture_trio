from datetime import date

import numpy as np
import pytest
from affine import Affine

from src.soil_moisture_trio.data_sources import WeatherToolsSiloLoader


def test_weather_tools_loader_regrids_and_tracks_metadata(monkeypatch):
    stack = np.arange(8, dtype=np.float32).reshape(2, 2, 2)
    profile = {
        'transform': Affine(0.5, 0, 150.0, 0, -0.5, -34.0),
        'height': 2,
        'width': 2,
    }

    captured = {}

    def fake_download_geotiff(**kwargs):
        captured.update(kwargs)
        return {'max_temp': (stack, profile)}

    monkeypatch.setattr('src.soil_moisture_trio.data_sources.download_geotiff', fake_download_geotiff)

    loader = WeatherToolsSiloLoader(
        cache_dir=None,
        cache_max_size_mb=100,
        overview_level=None,
        buffer_degrees=0.0,
    )

    target_lats = np.array([-34.75, -34.25])
    target_lons = np.array([150.25, 150.75])
    result = loader.load(
        variables=['max_temp'],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2),
        bounds=(-35.0, -34.0, 150.0, 151.0),
        target_lats=target_lats,
        target_lons=target_lons,
    )

    assert 'max_temp' in result.data
    assert result.data['max_temp'].shape == (2, 2)
    assert np.isclose(result.data['max_temp'].mean(), stack.mean())
    assert result.time_metadata == {'time_start': '2024-01-01', 'time_end': '2024-01-02'}
    assert captured['geometry'].bounds == (150.0, -35.0, 151.0, -34.0)


def test_weather_tools_loader_uses_bbox_scoped_cache_dir(monkeypatch, tmp_path):
    stack = np.arange(4, dtype=np.float32).reshape(1, 2, 2)
    profile = {
        'transform': Affine(0.5, 0, 150.0, 0, -0.5, -34.0),
        'height': 2,
        'width': 2,
    }
    output_dirs = []

    def fake_download_geotiff(**kwargs):
        output_dirs.append(kwargs["output_dir"])
        return {'max_temp': (stack, profile)}

    monkeypatch.setattr('src.soil_moisture_trio.data_sources.download_geotiff', fake_download_geotiff)

    loader = WeatherToolsSiloLoader(
        cache_dir=tmp_path,
        cache_max_size_mb=100,
        overview_level=None,
        buffer_degrees=0.0,
    )
    target_lats = np.array([-34.75, -34.25])
    target_lons = np.array([150.25, 150.75])

    loader.load(
        variables=['max_temp'],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        bounds=(-35.0, -34.0, 150.0, 151.0),
        target_lats=target_lats,
        target_lons=target_lons,
    )
    loader.load(
        variables=['max_temp'],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        bounds=(-30.0, -29.0, 120.0, 121.0),
        target_lats=target_lats,
        target_lons=target_lons,
    )

    assert len(output_dirs) == 2
    assert output_dirs[0] != output_dirs[1]
    assert output_dirs[0].parent == tmp_path
    assert output_dirs[1].parent == tmp_path


@pytest.mark.parametrize(
    "bounds, message",
    [
        ((-34.0, -35.0, 150.0, 151.0), "min_lat must be less than max_lat"),
        ((-35.0, -34.0, 151.0, 150.0), "min_lon must be less than max_lon"),
    ],
)
def test_weather_tools_loader_rejects_inverted_bounds(bounds, message):
    loader = WeatherToolsSiloLoader(
        cache_dir=None,
        cache_max_size_mb=100,
        overview_level=None,
        buffer_degrees=0.0,
    )

    with pytest.raises(ValueError, match=message):
        loader.load(
            variables=["max_temp"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            bounds=bounds,
            target_lats=np.array([-34.75, -34.25]),
            target_lons=np.array([150.25, 150.75]),
        )


def test_weather_tools_loader_rejects_missing_variable_payload(monkeypatch):
    stack = np.arange(4, dtype=np.float32).reshape(1, 2, 2)
    profile = {
        'transform': Affine(0.5, 0, 150.0, 0, -0.5, -34.0),
        'height': 2,
        'width': 2,
    }

    def fake_download_geotiff(**kwargs):
        return {'max_temp': (stack, profile)}

    monkeypatch.setattr('src.soil_moisture_trio.data_sources.download_geotiff', fake_download_geotiff)

    loader = WeatherToolsSiloLoader(
        cache_dir=None,
        cache_max_size_mb=100,
        overview_level=None,
        buffer_degrees=0.0,
    )

    with pytest.raises(ValueError, match="missing requested SILO variables"):
        loader.load(
            variables=['max_temp', 'vp_deficit'],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            bounds=(-35.0, -34.0, 150.0, 151.0),
            target_lats=np.array([-34.75, -34.25]),
            target_lons=np.array([150.25, 150.75]),
        )


def test_weather_tools_loader_rejects_non_2d_reduced_stack(monkeypatch):
    profile = {
        'transform': Affine(0.5, 0, 150.0, 0, -0.5, -34.0),
        'height': 2,
        'width': 2,
    }

    def fake_download_geotiff(**kwargs):
        return {'max_temp': (np.ones((2,), dtype=np.float32), profile)}

    monkeypatch.setattr('src.soil_moisture_trio.data_sources.download_geotiff', fake_download_geotiff)

    loader = WeatherToolsSiloLoader(
        cache_dir=None,
        cache_max_size_mb=100,
        overview_level=None,
        buffer_degrees=0.0,
    )

    with pytest.raises(ValueError, match="reduce to 2D grid"):
        loader.load(
            variables=['max_temp'],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            bounds=(-35.0, -34.0, 150.0, 151.0),
            target_lats=np.array([-34.75, -34.25]),
            target_lons=np.array([150.25, 150.75]),
        )
