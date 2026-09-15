from datetime import date

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline


def config(**overrides):
    return ClassifierConfig(**{
        "year": 2025, "start_date": "2025-01-01", "end_date": "2025-01-03",
        **overrides,
    })


def cube(variable="sm_pct", **overrides):
    dataset = xr.Dataset(
        {variable: (("time", "latitude", "longitude"), np.full((3, 2, 2), 0.5))},
        coords={
            "time": pd.date_range("2025-01-01", periods=3),
            "latitude": [-34.0, -35.0], "longitude": [115.0, 116.0],
        },
    )
    dataset[variable].attrs["units"] = "relative"
    return dataset.assign_coords(overrides)


@pytest.mark.parametrize("dates", [
    [], ["2025-01-01"], ["2025-01-01", "2025-01-03"],
    ["2025-01-01", "2025-01-01", "2025-01-03"],
    ["2025-01-03", "2025-01-02", "2025-01-01"],
    ["2025-01-01T12:00", "2025-01-02T12:00", "2025-01-03T12:00"],
    ["NaT", "2025-01-02", "2025-01-03"],
])
def test_daily_window_rejects_incomplete_duplicate_unordered_or_subdaily_dates(dates):
    pipeline = DryWetClassifierPipeline(config())
    with pytest.raises(ValueError):
        pipeline._determine_time_window(np.array(dates, dtype="datetime64[ns]"))


def test_daily_window_accepts_exact_subset_and_leap_day():
    pipeline = DryWetClassifierPipeline(config(year=2024, start_date="2024-02-28", end_date="2024-03-01"))
    selected, meta = pipeline._determine_time_window(pd.date_range("2024-01-01", "2024-12-31").values)
    assert selected.stop - selected.start == 3
    assert meta == {"time_start": "2024-02-28", "time_end": "2024-03-01"}


@pytest.mark.parametrize("metas", [
    [], [{}], [{"time_start": "2025-01-01"}],
    [{"time_start": "NaT", "time_end": "2025-01-03"}],
    [{"time_start": "2025-01-03", "time_end": "2025-01-01"}],
    [{"time_start": "2025-01-01", "time_end": "2025-01-03"},
     {"time_start": "2025-02-01", "time_end": "2025-02-03"}],
])
def test_time_metadata_must_match_not_union(metas):
    with pytest.raises(ValueError):
        DryWetClassifierPipeline._combine_time_metadata(metas)


def test_equivalent_iso_time_metadata_is_accepted():
    meta = {"time_start": "2025-01-01", "time_end": "2025-01-03"}
    assert DryWetClassifierPipeline._combine_time_metadata([
        meta, {key: value + "T00:00:00" for key, value in meta.items()},
    ]) == meta


@pytest.mark.parametrize("value", [-0.01, 1.01, 1.2, 50, np.inf, -np.inf])
def test_percentile_bounds_rejected_before_averaging(monkeypatch, value):
    ds = cube()
    ds.sm_pct.values[0, 0, 0] = value
    monkeypatch.setattr("src.soil_moisture_trio.pipeline.xr.open_dataset", lambda *a, **k: ds)
    with pytest.raises(ValueError, match=r"percentile values must lie in \[0, 1\]"):
        DryWetClassifierPipeline(config())._load_real_netcdf("synthetic.nc", "sm_pct")


@pytest.mark.parametrize("units", [None, "%", "percent", "mm", ""])
def test_percentile_units_are_required_not_guessed(monkeypatch, units):
    ds = cube()
    ds.sm_pct.attrs = {} if units is None else {"units": units}
    monkeypatch.setattr("src.soil_moisture_trio.pipeline.xr.open_dataset", lambda *a, **k: ds)
    with pytest.raises(ValueError, match="units 'relative'"):
        DryWetClassifierPipeline(config())._load_real_netcdf("synthetic.nc", "sm_pct")


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize("variable", ["sm_pct", "max_temp", "vp_deficit"])
def test_complete_netcdf_mean_preserves_previous_precision(monkeypatch, dtype, variable):
    ds = cube(variable)
    values = np.random.default_rng(17).uniform(0, 1, size=(3, 2, 2)).astype(dtype)
    ds[variable] = xr.DataArray(values, dims=("time", "latitude", "longitude"), attrs={"units": "relative"})
    expected = ds[variable].mean("time").values[::-1]
    if variable == "sm_pct":
        expected = expected.astype(float)
    monkeypatch.setattr("src.soil_moisture_trio.pipeline.xr.open_dataset", lambda *a, **k: ds)
    actual, *_ = DryWetClassifierPipeline(config())._load_real_netcdf("synthetic.nc", variable)
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == expected.dtype


def test_netcdf_complete_cell_mean_unchanged_and_missing_day_invalid(monkeypatch):
    ds = cube()
    ds.sm_pct.values[:, 0, 0] = [0.0, 0.5, 1.0]
    ds.sm_pct.values[0, 1, 1] = np.nan
    monkeypatch.setattr("src.soil_moisture_trio.pipeline.xr.open_dataset", lambda *a, **k: ds)
    values, meta, lats, lons = DryWetClassifierPipeline(config())._load_real_netcdf("synthetic.nc", "sm_pct")
    assert values[1, 0] == 0.5
    assert np.isnan(values[0, 1])
    np.testing.assert_array_equal(lats, [-35, -34])
    np.testing.assert_array_equal(lons, [115, 116])
    assert meta == {"time_start": "2025-01-01", "time_end": "2025-01-03"}


@pytest.mark.parametrize("coord, values", [
    ("latitude", [-34, -34]), ("longitude", [115, np.nan]),
])
def test_netcdf_rejects_invalid_spatial_coordinates(monkeypatch, coord, values):
    ds = cube(**{coord: values})
    monkeypatch.setattr("src.soil_moisture_trio.pipeline.xr.open_dataset", lambda *a, **k: ds)
    with pytest.raises(ValueError, match="coordinates"):
        DryWetClassifierPipeline(config())._load_real_netcdf("synthetic.nc", "sm_pct")


def test_netcdf_requires_daily_cube_not_first_raster_band(monkeypatch):
    ds = xr.Dataset({"sm_pct": (("latitude", "longitude"), np.ones((2, 2)))})
    monkeypatch.setattr("src.soil_moisture_trio.pipeline.xr.open_dataset", lambda *a, **k: ds)
    with pytest.raises(ValueError, match="dimensions"):
        DryWetClassifierPipeline(config())._load_real_netcdf("synthetic.nc", "sm_pct")


@pytest.mark.parametrize("shift", [0.0, 0.001])
@pytest.mark.parametrize("short_names", [False, True])
def test_explicit_netcdf_checks_own_coordinates(monkeypatch, shift, short_names):
    def opened(path):
        variable = "max_temp" if "max_temp" in path else "vp_deficit" if "vp_deficit" in path else "sm_pct"
        ds = cube(variable)
        if variable != "sm_pct":
            ds = ds.assign_coords(longitude=ds.longitude + shift)
            ds[variable].values[:] = 25 if variable == "max_temp" else 15
            if short_names:
                ds = ds.rename({"latitude": "lat", "longitude": "lon"})
        return ds
    monkeypatch.setattr("src.soil_moisture_trio.pipeline.xr.open_dataset", opened)
    pipeline = DryWetClassifierPipeline(config(use_silo_cog_loader=False))
    if shift:
        with pytest.raises(ValueError, match="coordinates do not match"):
            pipeline.prepare_data()
    else:
        pipeline.prepare_data()
        assert pipeline.valid_mask_grid.all()
        assert pipeline.assess_risk()["summary"]["valid_cells"]["count"] == 4


def test_cog_failure_does_not_switch_to_netcdf(monkeypatch):
    calls = []
    def opened(path):
        calls.append(path)
        return cube()
    monkeypatch.setattr("src.soil_moisture_trio.pipeline.xr.open_dataset", opened)
    def fail(**kwargs):
        raise ValueError("missing SILO day")
    from types import SimpleNamespace
    pipeline = DryWetClassifierPipeline(config())
    monkeypatch.setattr(pipeline, "_get_silo_loader", lambda: SimpleNamespace(load=fail))
    with pytest.raises(ValueError, match="missing SILO day"):
        pipeline.prepare_data()
    assert len(calls) == 1
    assert "sm_pct_2025" in calls[0]


def test_config_date_window_defaults_are_shared():
    assert ClassifierConfig(year=2024).date_range() == (date(2024, 1, 1), date(2024, 12, 31))
    assert ClassifierConfig(year=2025, start_date="2025-01-02").date_range() == (date(2025, 1, 2), date(2025, 1, 2))
    assert ClassifierConfig(year=2025, end_date="2025-01-03").date_range() == (date(2025, 1, 1), date(2025, 1, 3))
