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
    ReaderMetrics,
    assert_common_window_grid,
)
from src.soil_moisture_trio.slga.integration import (
    STORAGE_CASE_COMPONENTS,
    integrate_source_windows,
)
from src.soil_moisture_trio.slga.tiling import (
    SourceWindow,
    TileMetrics,
    harmonise_fractional_overlap_tiled,
)

MIXED_WIDTH_VARIABLE = "mixed_uncertainty_width_mm"
DES_COMPONENTS = ("EV", "10", "90")
DES_VALUE_VARIABLES = {
    component: f"depth_of_soil_{component.lower()}_m" for component in DES_COMPONENTS
}
DES_SHALLOW_VARIABLES = {
    component: f"depth_of_soil_{component.lower()}_shallower_than_1m"
    for component in DES_COMPONENTS
}
BUILDER_VARIABLES = (
    *STORAGE_CASE_COMPONENTS,
    MIXED_WIDTH_VARIABLE,
    *DES_VALUE_VARIABLES.values(),
    *DES_SHALLOW_VARIABLES.values(),
)
READER_COUNTER_FIELDS = (
    "cache_hits",
    "cache_misses",
    "cache_evictions",
    "cog_access_attempts",
    "cog_access_successes",
    "cog_retryable_failures",
    "cog_terminal_failures",
    "cog_exhausted_failures",
    "cog_window_fetch_attempts",
    "cog_window_fetches",
    "stac_request_attempts",
    "stac_request_successes",
    "stac_retryable_failures",
    "stac_terminal_failures",
    "stac_exhausted_failures",
    "stac_validation_failures",
)


@dataclass(frozen=True)
class TiledBuildResult:
    artifact_data: SoilArtifactData
    source_retrieval_timestamps_utc: Mapping[str, str]
    source_window_reads: int
    source_cache_bytes: int
    source_cache_peak_bytes: int
    source_cache_hits: int
    source_cache_misses: int
    source_cache_evictions: int
    cog_window_fetches: int
    reader_metrics_before: ReaderMetrics
    reader_metrics_after: ReaderMetrics
    reader_counter_delta: Mapping[str, int]
    tile_metrics: tuple[TileMetrics, ...]


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
        des_values = {
            DES_VALUE_VARIABLES[component]: integrated.des_metres[component]
            for component in DES_COMPONENTS
        }
        des_shallow = {
            DES_SHALLOW_VARIABLES[component]: np.where(
                np.isfinite(integrated.des_metres[component]),
                integrated.des_metres[component] < 1.0,
                np.nan,
            )
            for component in DES_COMPONENTS
        }
        return {
            **integrated.storage_mm,
            MIXED_WIDTH_VARIABLE: integrated.mixed_uncertainty_width_mm,
            **des_values,
            **des_shallow,
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
    metrics_before = cog_reader.metrics
    integrated_reader = IntegratedSourceWindowReader(catalogue, cog_reader)
    profile = catalogue.profile
    tile_metrics: list[TileMetrics] = []
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
        tile_metrics_callback=tile_metrics.append,
    )
    metrics_after = cog_reader.metrics
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
        mixed_uncertainty_width_mapped_prediction_sd_mm=(
            harmonised.mapped_prediction_sd[MIXED_WIDTH_VARIABLE]
        ),
        mixed_uncertainty_width_valid_source_area_m2=(
            harmonised.valid_source_area_m2[MIXED_WIDTH_VARIABLE]
        ),
        mixed_uncertainty_width_source_coverage_fraction=(
            harmonised.source_coverage_fraction[MIXED_WIDTH_VARIABLE]
        ),
        depth_of_soil_m={
            component: harmonised.means[DES_VALUE_VARIABLES[component]]
            for component in DES_COMPONENTS
        },
        depth_of_soil_mapped_prediction_sd_m={
            component: harmonised.mapped_prediction_sd[DES_VALUE_VARIABLES[component]]
            for component in DES_COMPONENTS
        },
        depth_of_soil_valid_source_area_m2={
            component: harmonised.valid_source_area_m2[DES_VALUE_VARIABLES[component]]
            for component in DES_COMPONENTS
        },
        depth_of_soil_source_coverage_fraction={
            component: harmonised.source_coverage_fraction[
                DES_VALUE_VARIABLES[component]
            ]
            for component in DES_COMPONENTS
        },
        depth_of_soil_shallower_than_1m_fraction={
            component: harmonised.means[DES_SHALLOW_VARIABLES[component]]
            for component in DES_COMPONENTS
        },
    )
    return TiledBuildResult(
        artifact_data=artifact_data,
        source_retrieval_timestamps_utc=dict(
            integrated_reader.retrieval_timestamps_utc
        ),
        source_window_reads=integrated_reader.source_window_reads,
        source_cache_bytes=metrics_after.cache_current_bytes,
        source_cache_peak_bytes=metrics_after.cache_peak_bytes,
        source_cache_hits=metrics_after.cache_hits,
        source_cache_misses=metrics_after.cache_misses,
        source_cache_evictions=metrics_after.cache_evictions,
        cog_window_fetches=metrics_after.cog_window_fetches,
        reader_metrics_before=metrics_before,
        reader_metrics_after=metrics_after,
        reader_counter_delta={
            field: getattr(metrics_after, field) - getattr(metrics_before, field)
            for field in READER_COUNTER_FIELDS
        },
        tile_metrics=tuple(tile_metrics),
    )
