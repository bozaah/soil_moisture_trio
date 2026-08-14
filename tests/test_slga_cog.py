from pathlib import Path

import numpy as np
import pytest
from rasterio import Affine
from rasterio.crs import CRS
from rasterio.coords import BoundingBox
from rasterio.windows import Window

from src.soil_moisture_trio.slga.catalogue import load_source_catalogue
from src.soil_moisture_trio.slga.cog import (
    AuthenticatedCogReader,
    SourceAccessError,
    SourceValidationError,
    _block_aligned_window,
    _normalise_values,
    expanded_window_for_bounds,
    validate_bounds,
    validate_pixel_window,
    validate_cog_dataset,
)

CATALOGUE = load_source_catalogue(Path("manifests/slga_awc_des_sources_v1.json"))


class FakeDataset:
    def __init__(self, layer, *, description=None, crs="EPSG:4326"):
        profile = CATALOGUE.profile
        self.driver = profile.driver
        self.count = profile.band_count
        self.width = profile.width
        self.height = profile.height
        self.crs = CRS.from_string(crs)
        self.transform = Affine(*profile.transform)
        self.bounds = BoundingBox(*profile.bounds)
        self.dtypes = (layer.product.dtype,)
        self.nodata = layer.product.nodata
        self.block_shapes = [(512, 512)]
        self.descriptions = (description or layer.product_id,)
        self._tags = {"UNITS": layer.product.units, "AREA_OR_POINT": "Area"}

    def overviews(self, _band):
        return [2, 4]

    def tags(self):
        return self._tags


def test_missing_credentials_fail_before_network_access():
    reader = AuthenticatedCogReader(CATALOGUE, environment={})
    product_id = next(iter(CATALOGUE.layers))

    with pytest.raises(SourceAccessError, match="TERN_API_KEY is required"):
        reader.read_window(product_id, (116.0, -32.0, 116.005, -31.995))


@pytest.mark.parametrize(
    "bounds",
    [
        (1.0, 0.0, 1.0, 2.0),
        (1.0, 2.0, 3.0, 2.0),
        (1.0, 2.0, np.inf, 3.0),
    ],
)
def test_malformed_bounds_fail(bounds):
    with pytest.raises(ValueError):
        validate_bounds(bounds)


def test_window_is_expanded_one_pixel_and_non_overlap_fails():
    layer = next(iter(CATALOGUE.layers.values()))
    dataset = FakeDataset(layer)
    transform = dataset.transform
    west = transform.c + 100 * transform.a
    east = transform.c + 102 * transform.a
    north = transform.f + 200 * transform.e
    south = transform.f + 202 * transform.e

    window = expanded_window_for_bounds(dataset, (west, south, east, north))

    assert window.col_off == 99
    assert window.row_off == 199
    assert window.width == 4
    assert window.height == 4
    with pytest.raises(SourceValidationError, match="do not overlap"):
        expanded_window_for_bounds(dataset, (0.0, 0.0, 1.0, 1.0))


def test_exact_pixel_window_validation_and_block_alignment():
    requested = validate_pixel_window(Window(510, 511, 5, 3), CATALOGUE.profile)
    aligned = _block_aligned_window(
        requested,
        (512, 512),
        CATALOGUE.profile.height,
        CATALOGUE.profile.width,
    )

    assert aligned == Window(0, 0, 1024, 1024)
    with pytest.raises(ValueError, match="integral"):
        validate_pixel_window(Window(0.5, 0, 1, 1), CATALOGUE.profile)
    with pytest.raises(ValueError, match="exceeds"):
        validate_pixel_window(
            Window(CATALOGUE.profile.width - 1, 0, 2, 1), CATALOGUE.profile
        )


def test_bounded_window_cache_reuses_values_and_evicts_lru():
    reader = AuthenticatedCogReader(
        CATALOGUE,
        environment={"TERN_API_KEY": "test-only"},
        window_cache_max_bytes=32,
    )
    first = Window(0, 0, 2, 2)
    second = Window(2, 0, 2, 2)
    reader._cache_window("first", first, np.ones((2, 2)), "t1")
    assert reader._cached_window("first", first) is not None

    reader._cache_window("second", second, np.ones((2, 2)), "t2")

    assert reader._cached_window("first", first) is None
    assert reader._cached_window("second", second) is not None


def test_cog_validation_allows_only_stale_des_nat_description():
    layer = next(
        layer for layer in CATALOGUE.layers.values() if layer.property_code == "DES"
    )
    stale = layer.product_id.replace("_TRN_", "_NAT_")

    validate_cog_dataset(FakeDataset(layer, description=stale), CATALOGUE, layer)

    with pytest.raises(SourceValidationError, match="band-description mismatch"):
        validate_cog_dataset(
            FakeDataset(layer, description="unrelated"), CATALOGUE, layer
        )


def test_cog_validation_rejects_grid_mismatch():
    layer = next(iter(CATALOGUE.layers.values()))

    with pytest.raises(SourceValidationError, match="CRS mismatch"):
        validate_cog_dataset(FakeDataset(layer, crs="EPSG:3577"), CATALOGUE, layer)


def test_nodata_is_preserved_and_bad_valid_values_fail():
    awc_layer = next(
        layer for layer in CATALOGUE.layers.values() if layer.property_code == "AWC"
    )
    values = np.ma.array([[10, 65535]], mask=[[False, True]], dtype=np.uint16)
    normalised = _normalise_values(values, awc_layer)
    assert normalised[0, 0] == 10
    assert np.isnan(normalised[0, 1])

    des_layer = next(
        layer for layer in CATALOGUE.layers.values() if layer.property_code == "DES"
    )
    with pytest.raises(SourceValidationError, match="Negative valid value"):
        _normalise_values(np.ma.array([[-0.1]], mask=False), des_layer)
    with pytest.raises(SourceValidationError, match="Infinite valid value"):
        _normalise_values(np.ma.array([[np.inf]], mask=False), des_layer)
