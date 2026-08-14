from pathlib import Path

import numpy as np
from rasterio import Affine
from rasterio.crs import CRS

from src.soil_moisture_trio.slga.builder import build_tiled_artifact_data
from src.soil_moisture_trio.slga.catalogue import load_source_catalogue
from src.soil_moisture_trio.slga.cog import RasterWindowData

CATALOGUE = load_source_catalogue(Path("manifests/slga_awc_des_sources_v1.json"))


class FakeCogReader:
    def __init__(self):
        self.catalogue = CATALOGUE
        self.window_cache_bytes = 0
        self.window_cache_hits = 0
        self.window_cache_misses = 0
        self.cog_window_fetches = 0

    def read_pixel_window(self, product_id, window):
        layer = CATALOGUE.layers[product_id]
        shape = (int(window.height), int(window.width))
        rows, cols = np.indices(shape)
        variation = (rows + cols) * 1e-4
        if layer.property_code == "AWC":
            base = {"05": 8.0, "EV": 10.0, "95": 12.0}[layer.component]
        else:
            base = {"10": 0.4, "EV": 0.5, "90": 0.6}[layer.component]
        values = np.full(shape, base, dtype=np.float64) + variation
        transform = Affine(*CATALOGUE.profile.transform) * Affine.translation(
            window.col_off, window.row_off
        )
        return RasterWindowData(
            layer=layer,
            values=values,
            transform=transform,
            crs=CRS.from_epsg(4326),
            window=window,
            retrieved_at="2026-08-12T08:00:00+00:00",
        )


def test_tiled_builder_reads_integrates_and_returns_artifact_contract_data():
    result = build_tiled_artifact_data(
        CATALOGUE,
        FakeCogReader(),
        np.array([-32.0, -32.05]),
        np.array([116.0, 116.05]),
        target_tile_shape=(1, 1),
    )

    data = result.artifact_data
    assert data.full_cell_area_m2.shape == (2, 2)
    assert set(data.storage_mm) == {
        "ev",
        "awc05_des_ev",
        "awc95_des_ev",
        "awc_ev_des10",
        "awc_ev_des90",
        "mixed_lower_awc05_des10",
        "mixed_upper_awc95_des90",
    }
    assert np.all(np.isfinite(data.storage_mm["ev"]))
    assert np.all(data.storage_mm["mixed_lower_awc05_des10"] <= data.storage_mm["ev"])
    assert np.all(data.storage_mm["ev"] <= data.storage_mm["mixed_upper_awc95_des90"])
    assert np.all(data.mixed_uncertainty_width_mm >= 0)
    assert result.source_window_reads == 4 * 18
    assert len(result.source_retrieval_timestamps_utc) == 18
