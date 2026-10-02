import numpy as np
import pytest
from rasterio import Affine

from src.soil_moisture_trio.slga.harmonise import (
    HarmonisationError,
    coordinate_edges,
    harmonise_fractional_overlap,
    require_exact_coordinate_subset,
)

TARGET_LATS = np.array([-30.025, -30.075])
TARGET_LONS = np.array([115.025, 115.075])


def test_coordinate_edges_preserve_orientation_and_reject_bad_spacing():
    np.testing.assert_allclose(
        coordinate_edges(TARGET_LATS, "latitude"),
        [-30.0, -30.05, -30.10],
    )
    np.testing.assert_allclose(
        coordinate_edges(TARGET_LONS, "longitude"),
        [115.0, 115.05, 115.10],
    )

    with pytest.raises(HarmonisationError, match="regular"):
        coordinate_edges(np.array([115.0, 115.06]), "longitude")
    with pytest.raises(HarmonisationError, match="strictly monotonic"):
        coordinate_edges(np.array([115.0, 115.0]), "longitude")


def test_constant_full_coverage_maps_without_dispersion():
    transform = Affine(0.005, 0.0, 115.0, 0.0, -0.005, -30.0)
    source = np.full((20, 20), 12.5)

    result = harmonise_fractional_overlap(
        {"ev": source}, transform, "EPSG:4326", TARGET_LATS, TARGET_LONS
    )

    np.testing.assert_allclose(result.means["ev"], 12.5)
    np.testing.assert_allclose(result.mapped_prediction_sd["ev"], 0.0)
    np.testing.assert_allclose(
        result.source_coverage_fraction["ev"], 1.0, rtol=0, atol=1e-12
    )
    np.testing.assert_allclose(
        result.valid_source_area_m2["ev"], result.full_cell_area_m2, rtol=0, atol=1e-5
    )


def test_partial_coverage_and_non_overlap_are_visible():
    transform = Affine(0.005, 0.0, 115.0, 0.0, -0.005, -30.0)

    result = harmonise_fractional_overlap(
        {"ev": np.array([[10.0]])},
        transform,
        "EPSG:4326",
        TARGET_LATS,
        TARGET_LONS,
    )

    assert result.means["ev"][0, 0] == pytest.approx(10.0)
    assert 0.009 < result.source_coverage_fraction["ev"][0, 0] < 0.011
    assert result.valid_source_area_m2["ev"][0, 0] > 0
    assert np.isnan(result.means["ev"][0, 1])
    assert result.source_coverage_fraction["ev"][0, 1] == 0
    assert result.valid_source_area_m2["ev"][0, 1] == 0


def test_variable_specific_nodata_coverage_and_weighted_dispersion():
    transform = Affine(0.005, 0.0, 115.0, 0.0, -0.005, -30.0)
    variable = np.zeros((10, 10))
    variable[:, 5:] = 10.0
    partial = variable.copy()
    partial[:, 5:] = np.nan

    result = harmonise_fractional_overlap(
        {"complete": variable, "partial": partial},
        transform,
        "EPSG:4326",
        TARGET_LATS,
        TARGET_LONS,
    )

    assert result.means["complete"][0, 0] == pytest.approx(5.0, abs=1e-6)
    assert result.mapped_prediction_sd["complete"][0, 0] == pytest.approx(5.0, abs=1e-6)
    assert result.source_coverage_fraction["complete"][0, 0] == pytest.approx(1.0)
    assert result.source_coverage_fraction["partial"][0, 0] == pytest.approx(
        0.5, abs=1e-5
    )


def test_non_epsg4326_and_grid_shape_mismatch_fail():
    transform = Affine(0.005, 0.0, 115.0, 0.0, -0.005, -30.0)
    with pytest.raises(HarmonisationError, match="EPSG:4326"):
        harmonise_fractional_overlap(
            {"ev": np.ones((2, 2))}, transform, "EPSG:3577", TARGET_LATS, TARGET_LONS
        )
    with pytest.raises(HarmonisationError, match="share one"):
        harmonise_fractional_overlap(
            {"a": np.ones((2, 2)), "b": np.ones((3, 2))},
            transform,
            "EPSG:4326",
            TARGET_LATS,
            TARGET_LONS,
        )


def test_runtime_subset_requires_exact_contiguous_coordinates():
    canonical = np.array([112.0, 112.05, 112.10, 112.15])

    assert require_exact_coordinate_subset(
        canonical, np.array([112.05, 112.10]), "longitude"
    ) == slice(1, 3)
    with pytest.raises(HarmonisationError, match="exact contiguous"):
        require_exact_coordinate_subset(
            canonical, np.array([112.05 + 1e-12, 112.10]), "longitude"
        )
    with pytest.raises(HarmonisationError, match="exact contiguous"):
        require_exact_coordinate_subset(
            canonical, np.array([112.05, 112.15]), "longitude"
        )


def test_repeated_harmonisation_is_numerically_reproducible():
    transform = Affine(0.005, 0.0, 115.0, 0.0, -0.005, -30.0)
    values = {"ev": np.arange(16, dtype=float).reshape(4, 4)}

    first = harmonise_fractional_overlap(
        values, transform, "EPSG:4326", TARGET_LATS, TARGET_LONS
    )
    second = harmonise_fractional_overlap(
        values, transform, "EPSG:4326", TARGET_LATS, TARGET_LONS
    )

    np.testing.assert_array_equal(first.means["ev"], second.means["ev"])
    np.testing.assert_array_equal(
        first.mapped_prediction_sd["ev"], second.mapped_prediction_sd["ev"]
    )
    np.testing.assert_array_equal(
        first.valid_source_area_m2["ev"], second.valid_source_area_m2["ev"]
    )
