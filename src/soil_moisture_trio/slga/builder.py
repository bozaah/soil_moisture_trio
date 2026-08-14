from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
from rasterio import Affine
from rasterio.windows import Window

from src.soil_moisture_trio.slga.artifact import SoilArtifactData
from src.soil_moisture_trio.slga.catalogue import SourceCatalogue
from src.soil_moisture_trio.slga.cog import (
    AuthenticatedCogReader,
    RasterWindowData,
    assert_common_window_grid,
)
from src.soil_moisture_trio.slga.integration import (
    STORAGE_CASE_COMPONENTS,
    integrate_source_windows,
)
from src.soil_moisture_trio.slga.tiling import (
    SourceWindow,
    harmonise_fractional_overlap_tiled,
)

MIXED_WIDTH_VARIABLE = "mixed_uncertainty_width_mm"
BUILDER_VARIABLES = (*STORAGE_CASE_COMPONENTS, MIXED_WIDTH_VARIABLE)


@dataclass(frozen=True)
class TiledBuildResult:
    artifact_data: SoilArtifactData
    source_retrieval_timestamps_utc: Mapping[str, str]
    source_window_reads: int
    source_cache_bytes: int
    source_cache_hits: int
    source_cache_misses: int
    cog_window_fetches: int


class IntegratedSourceWindowReader:
    """Retrieve the exact 18-layer window and integrate it before harmonisation."""

    def __init__(
        self,
        catalogue: SourceCatalogue,
        cog_reader: AuthenticatedCogReader,
    ) -> None:
        if cog_reader.catalogue is not catalogue:
            raise ValueError(
                "COG reader must use the supplied source catalogue instance."
            )
        self.catalogue = catalogue
        self.cog_reader = cog_reader
        self.retrieval_timestamps_utc: dict[str, str] = {}
        self.source_window_reads = 0

    def __call__(self, window: SourceWindow) -> Mapping[str, np.ndarray]:
        raster_window = Window(
            col_off=window.col_start,
            row_off=window.row_start,
            width=window.col_stop - window.col_start,
            height=window.row_stop - window.row_start,
        )
        source_windows: dict[str, RasterWindowData] = {}
        for product_id in self.catalogue.layers:
            result = self.cog_reader.read_pixel_window(product_id, raster_window)
            source_windows[product_id] = result
            self.retrieval_timestamps_utc.setdefault(product_id, result.retrieved_at)
            self.source_window_reads += 1
        assert_common_window_grid(source_windows)
        integrated = integrate_source_windows(source_windows)
        return {
            **integrated.storage_mm,
            MIXED_WIDTH_VARIABLE: integrated.mixed_uncertainty_width_mm,
        }


def build_tiled_artifact_data(
    catalogue: SourceCatalogue,
    cog_reader: AuthenticatedCogReader,
    target_latitude: np.ndarray,
    target_longitude: np.ndarray,
    *,
    target_tile_shape: tuple[int, int],
    tile_order: str = "row-major",
) -> TiledBuildResult:
    """Run bounded retrieve/integrate/harmonise orchestration without writing."""
    integrated_reader = IntegratedSourceWindowReader(catalogue, cog_reader)
    profile = catalogue.profile
    harmonised = harmonise_fractional_overlap_tiled(
        integrated_reader,
        BUILDER_VARIABLES,
        (profile.height, profile.width),
        Affine(*profile.transform),
        profile.crs,
        target_latitude,
        target_longitude,
        target_tile_shape=target_tile_shape,
        tile_order=tile_order,
    )
    artifact_data = SoilArtifactData(
        latitude=harmonised.latitude,
        longitude=harmonised.longitude,
        storage_mm={case: harmonised.means[case] for case in STORAGE_CASE_COMPONENTS},
        mapped_prediction_sd_mm={
            case: harmonised.mapped_prediction_sd[case]
            for case in STORAGE_CASE_COMPONENTS
        },
        valid_source_area_m2={
            case: harmonised.valid_source_area_m2[case]
            for case in STORAGE_CASE_COMPONENTS
        },
        source_coverage_fraction={
            case: harmonised.source_coverage_fraction[case]
            for case in STORAGE_CASE_COMPONENTS
        },
        full_cell_area_m2=harmonised.full_cell_area_m2,
        mixed_uncertainty_width_mm=harmonised.means[MIXED_WIDTH_VARIABLE],
    )
    return TiledBuildResult(
        artifact_data=artifact_data,
        source_retrieval_timestamps_utc=dict(
            integrated_reader.retrieval_timestamps_utc
        ),
        source_window_reads=integrated_reader.source_window_reads,
        source_cache_bytes=cog_reader.window_cache_bytes,
        source_cache_hits=cog_reader.window_cache_hits,
        source_cache_misses=cog_reader.window_cache_misses,
        cog_window_fetches=cog_reader.cog_window_fetches,
    )
