from datetime import date
from pathlib import Path

import numpy as np
import pytest
from affine import Affine

from src.soil_moisture_trio.data_sources import WeatherToolsSiloLoader

PROFILE = {
    "transform": Affine(0.5, 0, 150, 0, -0.5, -34),
    "height": 2, "width": 2, "crs": "EPSG:4326",
}
ARGS = {
    "variables": ["max_temp"], "start_date": date(2024, 1, 1), "end_date": date(2024, 1, 2),
    "bounds": (-35.0, -34.0, 150.0, 151.0),
    "target_lats": np.array([-34.75, -34.25]), "target_lons": np.array([150.25, 150.75]),
}


def loader(cache_dir=None, **options):
    return WeatherToolsSiloLoader(cache_dir, 100, options.get("overview"), options.get("buffer", 0.0))


def mock_download(monkeypatch, names=None):
    calls = []
    def download(**kwargs):
        calls.append(kwargs)
        return {"max_temp": [Path(name) for name in (names if names is not None else [
            "20240101.max_temp.tif", "20240102.max_temp.tif",
        ])]}
    monkeypatch.setattr("src.soil_moisture_trio.data_sources.download_geotiff", download)
    monkeypatch.setattr("src.soil_moisture_trio.data_sources.read_cog", lambda path: (np.ones((2, 2)), PROFILE))
    return calls


def test_loader_reads_real_local_rasters_through_pinned_weather_tools(monkeypatch, tmp_path):
    import rasterio
    paths = []
    for day in (1, 2):
        path = tmp_path / f"2024010{day}.max_temp.tif"
        data = np.full((2, 2), day, dtype=np.float32)
        if day == 1:
            data[0, 0] = -9999
        with rasterio.open(path, "w", **{
            **PROFILE, "driver": "GTiff", "count": 1, "dtype": "float32", "nodata": -9999,
        }) as raster:
            raster.write(data, 1)
        paths.append(path)
    monkeypatch.setattr("src.soil_moisture_trio.data_sources.download_geotiff", lambda **kwargs: {"max_temp": paths})
    result = loader().load(**ARGS)
    assert np.isnan(result.data["max_temp"][1, 0])
    np.testing.assert_array_equal(result.data["max_temp"][0], [1.5, 1.5])
    assert result.data["max_temp"][1, 1] == 1.5


def test_loader_reads_explicit_days_and_regrids_complete_mean(monkeypatch):
    calls = mock_download(monkeypatch)
    stack = np.arange(8, dtype=np.float32).reshape(2, 2, 2)
    def read(path):
        index = 0 if Path(path).name.startswith("20240101") else 1
        return stack[index], PROFILE
    monkeypatch.setattr("src.soil_moisture_trio.data_sources.read_cog", read)
    result = loader().load(**ARGS)
    np.testing.assert_array_equal(result.data["max_temp"], stack.mean(axis=0)[::-1])
    assert result.time_metadata == {"time_start": "2024-01-01", "time_end": "2024-01-02"}
    assert calls[0]["read_files"] is False
    assert calls[0]["geometry"].bounds == (150, -35, 151, -34)


@pytest.mark.parametrize("names", [
    [], ["20240101.max_temp.tif"],
    ["20240101.max_temp.tif", "20240101.max_temp.tif"],
    ["20240102.max_temp.tif", "20240101.max_temp.tif"],
    ["20240101.max_temp.tif", "20240103.max_temp.tif"],
    ["20240101.vp.tif", "20240102.vp.tif"],
])
def test_missing_duplicate_reordered_or_wrong_daily_files_fail(monkeypatch, names):
    mock_download(monkeypatch, names)
    with pytest.raises(ValueError, match="daily file list"):
        loader().load(**ARGS)


def test_unreadable_day_is_not_silently_omitted(monkeypatch):
    mock_download(monkeypatch)
    def read(path):
        if "20240102" in path:
            raise OSError("broken raster")
        return np.ones((2, 2)), PROFILE
    monkeypatch.setattr("src.soil_moisture_trio.data_sources.read_cog", read)
    with pytest.raises(ValueError, match="required SILO day 20240102.*broken raster"):
        loader().load(**ARGS)


@pytest.mark.parametrize("key, value", [
    ("transform", Affine(0.5, 0, 151, 0, -0.5, -34)),
    ("crs", "EPSG:3577"), ("width", 3),
])
def test_daily_grid_changes_fail(monkeypatch, key, value):
    mock_download(monkeypatch)
    def read(path):
        profile = dict(PROFILE)
        if "20240102" in path:
            profile[key] = value
        return np.ones((2, 2)), profile
    monkeypatch.setattr("src.soil_moisture_trio.data_sources.read_cog", read)
    with pytest.raises(ValueError, match="daily grid changed"):
        loader().load(**ARGS)


def test_bad_daily_shape_fails(monkeypatch):
    mock_download(monkeypatch)
    monkeypatch.setattr("src.soil_moisture_trio.data_sources.read_cog", lambda path: (np.ones((3, 2)), PROFILE))
    with pytest.raises(ValueError, match="daily grid shape mismatch"):
        loader().load(**ARGS)


def test_masked_or_nonfinite_day_invalidates_cell(monkeypatch):
    mock_download(monkeypatch)
    def read(path):
        data = np.ma.array([[1.0, 2.0], [3.0, 4.0]], mask=False)
        if "20240101" in path:
            data.mask[0, 0] = True
            data[0, 1] = np.inf
        return data, PROFILE
    monkeypatch.setattr("src.soil_moisture_trio.data_sources.read_cog", read)
    result = loader().load(**ARGS)
    assert np.isnan(result.data["max_temp"][1]).all()
    np.testing.assert_array_equal(result.data["max_temp"][0], [3, 4])


@pytest.mark.parametrize("variables", [[], ["vp"], ["daily_rain"], ["max_temp", "max_temp"]])
def test_variables_restricted(variables):
    with pytest.raises(ValueError, match="Only max_temp and vp_deficit"):
        loader().load(**{**ARGS, "variables": variables})


def test_missing_variable_payload_fails(monkeypatch):
    mock_download(monkeypatch)
    with pytest.raises(ValueError, match="exactly the requested"):
        loader().load(**{**ARGS, "variables": ["max_temp", "vp_deficit"]})


@pytest.mark.parametrize("bounds", [(-34, -35, 150, 151), (-35, -34, 151, 150)])
def test_inverted_bounds_fail(bounds):
    with pytest.raises(ValueError, match="must be less than"):
        loader().load(**{**ARGS, "bounds": bounds})


def test_inverted_dates_fail():
    with pytest.raises(ValueError, match="end_date"):
        loader().load(**{**ARGS, "end_date": date(2023, 1, 1)})


def test_cache_identity_includes_bounds_buffer_and_overview(monkeypatch, tmp_path):
    calls = mock_download(monkeypatch)
    loader(tmp_path).load(**ARGS)
    loader(tmp_path).load(**ARGS)
    loader(tmp_path, buffer=0.1).load(**ARGS)
    loader(tmp_path, overview=1).load(**ARGS)
    loader(tmp_path).load(**{**ARGS, "bounds": (-35.00001, -34, 150, 151)})
    paths = [call["output_dir"] for call in calls]
    assert paths[0] == paths[1]
    assert len(set(paths)) == 4
    assert all(path.parent == tmp_path for path in paths)
