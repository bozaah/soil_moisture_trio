from __future__ import annotations

import numpy as np
import pytest
from rasterio import Affine

import src.soil_moisture_trio.slga.tiling as tiling_module
from src.soil_moisture_trio.slga.harmonise import (
    HarmonisationError,
    harmonise_fractional_overlap,
)
from src.soil_moisture_trio.slga.tiling import (
    SourceWindow,
    harmonise_fractional_overlap_tiled,
)

SOURCE_TRANSFORM = Affine(0.005, 0.0, 114.973, 0.0, -0.005, -29.973)
SOURCE_SHAPE = (44, 44)
TARGET_LATITUDE = np.array([-30.0, -30.05, -30.10, -30.15])
TARGET_LONGITUDE = np.array([115.0, 115.05, 115.10, 115.15])


def _source_values() -> dict[str, np.ndarray]:
    rows, cols = np.indices(SOURCE_SHAPE)
    complete = rows.astype(np.float64) * 100.0 + cols
    partial = complete / 10.0
    partial[8:16, 9:19] = np.nan
    return {"complete": complete, "partial": partial}


def _reader(values, observed_windows):
    def read(window: SourceWindow):
        observed_windows.append(window)
        return {
            name: array[
                window.row_start : window.row_stop,
                window.col_start : window.col_stop,
            ]
            for name, array in values.items()
        }

    return read


def _assert_results_equal(expected, actual):
    np.testing.assert_array_equal(actual.latitude, expected.latitude)
    np.testing.assert_array_equal(actual.longitude, expected.longitude)
    np.testing.assert_array_equal(actual.full_cell_area_m2, expected.full_cell_area_m2)
    for name in expected.means:
        np.testing.assert_array_equal(actual.means[name], expected.means[name])
        np.testing.assert_array_equal(
            actual.mapped_prediction_sd[name], expected.mapped_prediction_sd[name]
        )
        np.testing.assert_array_equal(
            actual.valid_source_area_m2[name], expected.valid_source_area_m2[name]
        )
        np.testing.assert_array_equal(
            actual.source_coverage_fraction[name],
            expected.source_coverage_fraction[name],
        )


def test_tiled_results_are_invariant_to_tile_shape_and_processing_order():
    values = _source_values()
    expected = harmonise_fractional_overlap(
        values,
        SOURCE_TRANSFORM,
        "EPSG:4326",
        TARGET_LATITUDE,
        TARGET_LONGITUDE,
    )

    for tile_shape, order in (
        ((1, 1), "row-major"),
        ((2, 3), "row-major"),
        ((3, 2), "reverse"),
        ((4, 4), "reverse"),
    ):
        windows = []
        actual = harmonise_fractional_overlap_tiled(
            _reader(values, windows),
            tuple(values),
            SOURCE_SHAPE,
            SOURCE_TRANSFORM,
            "EPSG:4326",
            TARGET_LATITUDE,
            TARGET_LONGITUDE,
            target_tile_shape=tile_shape,
            tile_order=order,
        )
        _assert_results_equal(expected, actual)
        assert max(window.shape[0] for window in windows) <= tile_shape[0] * 11 + 3
        assert max(window.shape[1] for window in windows) <= tile_shape[1] * 11 + 3


def test_per_tile_elapsed_metrics_are_stable_with_a_mocked_clock(monkeypatch):
    values = _source_values()
    observed_metrics = []
    clock = iter([1.0, 1.25, 2.0, 2.5, 3.0, 3.75, 4.0, 5.0])
    monkeypatch.setattr(tiling_module.time, "perf_counter", lambda: next(clock))

    harmonise_fractional_overlap_tiled(
        _reader(values, []),
        tuple(values),
        SOURCE_SHAPE,
        SOURCE_TRANSFORM,
        "EPSG:4326",
        TARGET_LATITUDE[:2],
        TARGET_LONGITUDE[:2],
        target_tile_shape=(1, 1),
        tile_metrics_callback=observed_metrics.append,
    )

    assert [metric.tile_index for metric in observed_metrics] == [0, 1, 2, 3]
    assert [metric.elapsed_seconds for metric in observed_metrics] == [
        0.25,
        0.5,
        0.75,
        1.0,
    ]
    assert [
        (
            metric.target_row_start,
            metric.target_row_stop,
            metric.target_col_start,
            metric.target_col_stop,
        )
        for metric in observed_metrics
    ] == [(0, 1, 0, 1), (0, 1, 1, 2), (1, 2, 0, 1), (1, 2, 1, 2)]


def test_complete_source_area_reconciles_without_cross_tile_double_counting():
    values = _source_values()
    windows = []
    result = harmonise_fractional_overlap_tiled(
        _reader(values, windows),
        tuple(values),
        SOURCE_SHAPE,
        SOURCE_TRANSFORM,
        "EPSG:4326",
        TARGET_LATITUDE,
        TARGET_LONGITUDE,
        target_tile_shape=(1, 2),
    )

    np.testing.assert_array_equal(
        result.source_coverage_fraction["complete"], np.ones((4, 4))
    )
    np.testing.assert_allclose(
        result.valid_source_area_m2["complete"],
        result.full_cell_area_m2,
        rtol=0.0,
        atol=1e-6,
    )
    assert sum(window.shape[0] * window.shape[1] for window in windows) < np.prod(
        SOURCE_SHAPE
    ) * len(windows)


def test_tile_outside_source_uses_bounded_window_and_returns_zero_coverage():
    values = _source_values()
    windows = []
    latitude = np.array([-31.0, -31.05])
    longitude = np.array([116.0, 116.05])
    result = harmonise_fractional_overlap_tiled(
        _reader(values, windows),
        tuple(values),
        SOURCE_SHAPE,
        SOURCE_TRANSFORM,
        "EPSG:4326",
        latitude,
        longitude,
        target_tile_shape=(1, 1),
    )

    assert all(window.shape == (1, 1) for window in windows)
    np.testing.assert_array_equal(
        result.source_coverage_fraction["complete"], np.zeros((2, 2))
    )
    assert np.all(np.isnan(result.means["complete"]))


def test_reader_shape_variables_and_window_offsets_are_validated():
    values = _source_values()

    with pytest.raises(HarmonisationError, match="variables do not match"):
        harmonise_fractional_overlap_tiled(
            lambda window: {"wrong": np.zeros(window.shape)},
            tuple(values),
            SOURCE_SHAPE,
            SOURCE_TRANSFORM,
            "EPSG:4326",
            TARGET_LATITUDE[:2],
            TARGET_LONGITUDE[:2],
            target_tile_shape=(1, 1),
        )

    with pytest.raises(HarmonisationError, match="wrong shape"):
        harmonise_fractional_overlap_tiled(
            lambda _window: {name: np.zeros((1, 1)) for name in values},
            tuple(values),
            SOURCE_SHAPE,
            SOURCE_TRANSFORM,
            "EPSG:4326",
            TARGET_LATITUDE[:2],
            TARGET_LONGITUDE[:2],
            target_tile_shape=(2, 2),
        )

    with pytest.raises(HarmonisationError, match="do not align"):
        harmonise_fractional_overlap(
            values,
            SOURCE_TRANSFORM,
            "EPSG:4326",
            TARGET_LATITUDE,
            TARGET_LONGITUDE,
            source_grid_transform=SOURCE_TRANSFORM,
            source_window_row_offset=1,
        )
