from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np
from rasterio import Affine

from src.soil_moisture_trio.slga.harmonise import (
    HarmonisationError,
    HarmonisedValues,
    coordinate_edges,
    harmonise_fractional_overlap,
)


@dataclass(frozen=True)
class SourceWindow:
    row_start: int
    row_stop: int
    col_start: int
    col_stop: int

    @property
    def shape(self) -> tuple[int, int]:
        return (self.row_stop - self.row_start, self.col_stop - self.col_start)


@dataclass(frozen=True)
class TileMetrics:
    tile_index: int
    target_row_start: int
    target_row_stop: int
    target_col_start: int
    target_col_stop: int
    source_window: SourceWindow
    elapsed_seconds: float


SourceWindowReader = Callable[[SourceWindow], Mapping[str, np.ndarray]]
TileMetricsCallback = Callable[[TileMetrics], None]


def harmonise_fractional_overlap_tiled(
    source_window_reader: SourceWindowReader,
    variable_names: Sequence[str],
    source_shape: tuple[int, int],
    source_transform: Affine,
    source_crs: str,
    target_latitude: np.ndarray,
    target_longitude: np.ndarray,
    *,
    target_tile_shape: tuple[int, int],
    tile_order: str = "row-major",
    tile_metrics_callback: TileMetricsCallback | None = None,
) -> HarmonisedValues:
    """Harmonise bounded source windows while assigning every target cell once."""
    names = tuple(variable_names)
    if (
        not names
        or len(names) != len(set(names))
        or not all(isinstance(name, str) and name for name in names)
    ):
        raise HarmonisationError("Tiled variable names must be non-empty and unique.")
    if len(source_shape) != 2 or any(
        not isinstance(size, int) or isinstance(size, bool) or size <= 0
        for size in source_shape
    ):
        raise HarmonisationError(
            "Tiled source shape must contain two positive integers."
        )
    if len(target_tile_shape) != 2 or any(
        not isinstance(size, int) or isinstance(size, bool) or size <= 0
        for size in target_tile_shape
    ):
        raise HarmonisationError(
            "Target tile shape must contain two positive integers."
        )
    if tile_order not in {"row-major", "reverse"}:
        raise HarmonisationError("Tile order must be 'row-major' or 'reverse'.")
    if tile_metrics_callback is not None and not callable(tile_metrics_callback):
        raise HarmonisationError("Tile metrics callback must be callable.")

    latitude = np.asarray(target_latitude, dtype=np.float64)
    longitude = np.asarray(target_longitude, dtype=np.float64)
    latitude_edges = coordinate_edges(latitude, "latitude")
    longitude_edges = coordinate_edges(longitude, "longitude")
    tile_slices = _target_tile_slices(latitude.size, longitude.size, target_tile_shape)
    if tile_order == "reverse":
        tile_slices.reverse()

    target_shape = (latitude.size, longitude.size)
    means = {name: np.full(target_shape, np.nan, dtype=np.float64) for name in names}
    dispersion = {
        name: np.full(target_shape, np.nan, dtype=np.float64) for name in names
    }
    valid_area = {name: np.zeros(target_shape, dtype=np.float64) for name in names}
    coverage = {name: np.zeros(target_shape, dtype=np.float64) for name in names}
    full_area = np.zeros(target_shape, dtype=np.float64)
    assigned = np.zeros(target_shape, dtype=bool)

    for tile_index, (latitude_slice, longitude_slice) in enumerate(tile_slices):
        tile_started = time.perf_counter()
        if np.any(assigned[latitude_slice, longitude_slice]):
            raise HarmonisationError(
                "A target cell was assigned to more than one tile."
            )
        window = _source_window_for_target_tile(
            source_shape,
            source_transform,
            latitude_edges,
            longitude_edges,
            latitude_slice,
            longitude_slice,
        )
        window_values = source_window_reader(window)
        if set(window_values) != set(names):
            raise HarmonisationError(
                "Source-window reader variables do not match the tiled contract."
            )
        if any(np.asarray(window_values[name]).shape != window.shape for name in names):
            raise HarmonisationError(
                "Source-window reader returned an array with the wrong shape."
            )
        window_transform = source_transform * Affine.translation(
            window.col_start, window.row_start
        )
        tile_result = harmonise_fractional_overlap(
            window_values,
            window_transform,
            source_crs,
            latitude[latitude_slice],
            longitude[longitude_slice],
            source_grid_transform=source_transform,
            source_window_row_offset=window.row_start,
            source_window_col_offset=window.col_start,
            target_latitude_edges=latitude_edges[
                latitude_slice.start : latitude_slice.stop + 1
            ],
            target_longitude_edges=longitude_edges[
                longitude_slice.start : longitude_slice.stop + 1
            ],
        )
        for name in names:
            means[name][latitude_slice, longitude_slice] = tile_result.means[name]
            dispersion[name][latitude_slice, longitude_slice] = (
                tile_result.mapped_prediction_sd[name]
            )
            valid_area[name][latitude_slice, longitude_slice] = (
                tile_result.valid_source_area_m2[name]
            )
            coverage[name][latitude_slice, longitude_slice] = (
                tile_result.source_coverage_fraction[name]
            )
        full_area[latitude_slice, longitude_slice] = tile_result.full_cell_area_m2
        assigned[latitude_slice, longitude_slice] = True
        tile_elapsed = time.perf_counter() - tile_started
        if not math.isfinite(tile_elapsed) or tile_elapsed < 0:
            raise HarmonisationError(
                "Tile elapsed time must be finite and non-negative."
            )
        if tile_metrics_callback is not None:
            tile_metrics_callback(
                TileMetrics(
                    tile_index=tile_index,
                    target_row_start=latitude_slice.start,
                    target_row_stop=latitude_slice.stop,
                    target_col_start=longitude_slice.start,
                    target_col_stop=longitude_slice.stop,
                    source_window=window,
                    elapsed_seconds=tile_elapsed,
                )
            )

    if not np.all(assigned):
        raise HarmonisationError("Tiled harmonisation left an unassigned target cell.")
    return HarmonisedValues(
        means=means,
        mapped_prediction_sd=dispersion,
        valid_source_area_m2=valid_area,
        source_coverage_fraction=coverage,
        full_cell_area_m2=full_area,
        latitude=latitude,
        longitude=longitude,
    )


def _target_tile_slices(
    latitude_size: int,
    longitude_size: int,
    tile_shape: tuple[int, int],
) -> list[tuple[slice, slice]]:
    latitude_tile_size, longitude_tile_size = tile_shape
    return [
        (
            slice(
                latitude_start, min(latitude_start + latitude_tile_size, latitude_size)
            ),
            slice(
                longitude_start,
                min(longitude_start + longitude_tile_size, longitude_size),
            ),
        )
        for latitude_start in range(0, latitude_size, latitude_tile_size)
        for longitude_start in range(0, longitude_size, longitude_tile_size)
    ]


def _source_window_for_target_tile(
    source_shape: tuple[int, int],
    source_transform: Affine,
    latitude_edges: np.ndarray,
    longitude_edges: np.ndarray,
    latitude_slice: slice,
    longitude_slice: slice,
) -> SourceWindow:
    if (
        not isinstance(source_transform, Affine)
        or source_transform.a <= 0
        or source_transform.e >= 0
    ):
        raise HarmonisationError(
            "Tiled source transform must be north-up and unrotated."
        )
    if source_transform.b != 0 or source_transform.d != 0:
        raise HarmonisationError(
            "Tiled source transform must be north-up and unrotated."
        )

    west = min(
        longitude_edges[longitude_slice.start], longitude_edges[longitude_slice.stop]
    )
    east = max(
        longitude_edges[longitude_slice.start], longitude_edges[longitude_slice.stop]
    )
    south = min(
        latitude_edges[latitude_slice.start], latitude_edges[latitude_slice.stop]
    )
    north = max(
        latitude_edges[latitude_slice.start], latitude_edges[latitude_slice.stop]
    )
    inverse = ~source_transform
    west_pixel, north_pixel = inverse * (west, north)
    east_pixel, south_pixel = inverse * (east, south)
    row_start = math.floor(min(north_pixel, south_pixel)) - 1
    row_stop = math.ceil(max(north_pixel, south_pixel)) + 1
    col_start = math.floor(min(west_pixel, east_pixel)) - 1
    col_stop = math.ceil(max(west_pixel, east_pixel)) + 1
    height, width = source_shape
    row_start, row_stop = _clamp_or_nearest(row_start, row_stop, height)
    col_start, col_stop = _clamp_or_nearest(col_start, col_stop, width)
    return SourceWindow(row_start, row_stop, col_start, col_stop)


def _clamp_or_nearest(start: int, stop: int, size: int) -> tuple[int, int]:
    clamped_start = min(max(start, 0), size)
    clamped_stop = min(max(stop, 0), size)
    if clamped_start < clamped_stop:
        return clamped_start, clamped_stop
    nearest = min(max((start + stop) // 2, 0), size - 1)
    return nearest, nearest + 1
