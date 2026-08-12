from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import numpy as np
from pyproj import CRS, Transformer
from rasterio import Affine
from shapely import box
from shapely.geometry import Polygon
from shapely.ops import transform as transform_geometry
from shapely.strtree import STRtree

AWRA_SPACING_DEGREES = 0.05
COORDINATE_ABS_TOLERANCE = 1e-10
TARGET_EDGE_SEGMENT_DEGREES = 0.005
OVERLAP_AREA_TOLERANCE_M2 = 1e-6
COVERAGE_TOLERANCE = 1e-12
SOURCE_CRS = CRS.from_epsg(4326)
AREA_CRS = CRS.from_epsg(3577)


class HarmonisationError(ValueError):
    """Raised when grids or overlap results violate the harmonisation contract."""


@dataclass(frozen=True)
class HarmonisedValues:
    means: Mapping[str, np.ndarray]
    mapped_prediction_sd: Mapping[str, np.ndarray]
    valid_source_area_m2: Mapping[str, np.ndarray]
    source_coverage_fraction: Mapping[str, np.ndarray]
    full_cell_area_m2: np.ndarray
    latitude: np.ndarray
    longitude: np.ndarray


def coordinate_edges(coordinates: np.ndarray, axis_name: str) -> np.ndarray:
    values = np.asarray(coordinates, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise HarmonisationError(
            f"{axis_name} must be a one-dimensional array of at least two centres."
        )
    if not np.all(np.isfinite(values)):
        raise HarmonisationError(f"{axis_name} contains a non-finite coordinate.")
    differences = np.diff(values)
    if not (np.all(differences > 0) or np.all(differences < 0)):
        raise HarmonisationError(f"{axis_name} must be strictly monotonic and unique.")
    absolute_differences = np.abs(differences)
    spacing = float(np.median(absolute_differences))
    if not math.isclose(
        spacing,
        AWRA_SPACING_DEGREES,
        rel_tol=0.0,
        abs_tol=COORDINATE_ABS_TOLERANCE,
    ) or not np.allclose(
        absolute_differences,
        spacing,
        rtol=0.0,
        atol=COORDINATE_ABS_TOLERANCE,
    ):
        raise HarmonisationError(
            f"{axis_name} must use regular {AWRA_SPACING_DEGREES} degree AWRA-L spacing."
        )

    edges = np.empty(values.size + 1, dtype=np.float64)
    edges[1:-1] = (values[:-1] + values[1:]) / 2.0
    edges[0] = values[0] - differences[0] / 2.0
    edges[-1] = values[-1] + differences[-1] / 2.0
    return edges


def harmonise_fractional_overlap(
    values: Mapping[str, np.ndarray],
    source_transform: Affine,
    source_crs: CRS | str,
    target_latitude: np.ndarray,
    target_longitude: np.ndarray,
) -> HarmonisedValues:
    """Area-weight continuous native-grid values onto a tiny AWRA-L target window."""
    if not values:
        raise HarmonisationError("At least one source value array is required.")
    source_crs_value = CRS.from_user_input(source_crs)
    if source_crs_value != SOURCE_CRS:
        raise HarmonisationError("The B25b source grid must use EPSG:4326.")
    if not isinstance(source_transform, Affine) or not all(
        math.isfinite(value) for value in tuple(source_transform)[:6]
    ):
        raise HarmonisationError("source_transform must be a finite affine transform.")
    if source_transform.b != 0 or source_transform.d != 0:
        raise HarmonisationError("Rotated or sheared source grids are unsupported.")
    if source_transform.a <= 0 or source_transform.e >= 0:
        raise HarmonisationError(
            "Source grid must be north-up with positive x and negative y spacing."
        )
    if (
        max(abs(source_transform.a), abs(source_transform.e))
        > TARGET_EDGE_SEGMENT_DEGREES
    ):
        raise HarmonisationError(
            "Source spacing exceeds the pinned B25b geometry limit."
        )

    arrays = {
        name: np.asarray(array, dtype=np.float64) for name, array in values.items()
    }
    first_shape = next(iter(arrays.values())).shape
    if len(first_shape) != 2 or any(
        array.shape != first_shape for array in arrays.values()
    ):
        raise HarmonisationError(
            "All source arrays must share one two-dimensional grid."
        )
    if any(np.any(np.isinf(array)) for array in arrays.values()):
        raise HarmonisationError(
            "Source arrays may contain NaN nodata but not infinite values."
        )

    latitude = np.asarray(target_latitude, dtype=np.float64)
    longitude = np.asarray(target_longitude, dtype=np.float64)
    latitude_edges = coordinate_edges(latitude, "latitude")
    longitude_edges = coordinate_edges(longitude, "longitude")

    transformer = Transformer.from_crs(SOURCE_CRS, AREA_CRS, always_xy=True)
    source_polygons = _source_pixel_polygons(first_shape, source_transform, transformer)
    tree = STRtree(source_polygons)

    target_shape = (latitude.size, longitude.size)
    full_area = np.zeros(target_shape, dtype=np.float64)
    means = {name: np.full(target_shape, np.nan, dtype=np.float64) for name in arrays}
    dispersion = {
        name: np.full(target_shape, np.nan, dtype=np.float64) for name in arrays
    }
    valid_area = {name: np.zeros(target_shape, dtype=np.float64) for name in arrays}
    coverage = {name: np.zeros(target_shape, dtype=np.float64) for name in arrays}
    source_width = first_shape[1]

    for lat_index in range(latitude.size):
        south = min(latitude_edges[lat_index], latitude_edges[lat_index + 1])
        north = max(latitude_edges[lat_index], latitude_edges[lat_index + 1])
        for lon_index in range(longitude.size):
            west = min(longitude_edges[lon_index], longitude_edges[lon_index + 1])
            east = max(longitude_edges[lon_index], longitude_edges[lon_index + 1])
            target_geographic = _target_geographic_polygon(
                west, south, east, north, source_transform
            )
            target = transform_geometry(transformer.transform, target_geographic)
            target_area = float(target.area)
            if (
                not target.is_valid
                or not math.isfinite(target_area)
                or target_area <= 0
            ):
                raise HarmonisationError(
                    "Target-cell transformation produced invalid area."
                )
            full_area[lat_index, lon_index] = target_area

            candidates = sorted(int(index) for index in tree.query(target))
            overlaps: list[tuple[int, float]] = []
            for source_index in candidates:
                overlap_area = float(
                    source_polygons[source_index].intersection(target).area
                )
                if (
                    not math.isfinite(overlap_area)
                    or overlap_area < -OVERLAP_AREA_TOLERANCE_M2
                ):
                    raise HarmonisationError(
                        "Source/target intersection produced invalid area."
                    )
                if overlap_area > OVERLAP_AREA_TOLERANCE_M2:
                    overlaps.append((source_index, overlap_area))

            for name, array in arrays.items():
                weighted_values: list[tuple[float, float]] = []
                area_sum = 0.0
                weighted_sum = 0.0
                for source_index, overlap_area in overlaps:
                    row, col = divmod(source_index, source_width)
                    value = float(array[row, col])
                    if math.isnan(value):
                        continue
                    area_sum += overlap_area
                    weighted_sum += overlap_area * value
                    weighted_values.append((value, overlap_area))

                valid_area[name][lat_index, lon_index] = area_sum
                fraction = area_sum / target_area
                fraction = _normalise_coverage(fraction, name, lat_index, lon_index)
                coverage[name][lat_index, lon_index] = fraction
                if area_sum == 0:
                    continue
                mean = weighted_sum / area_sum
                distinct_values = {value for value, _area in weighted_values}
                if len(distinct_values) == 1:
                    variance = 0.0
                else:
                    variance = (
                        sum(
                            area * (value - mean) ** 2
                            for value, area in weighted_values
                        )
                        / area_sum
                    )
                if variance < 0 and variance >= -1e-15:
                    variance = 0.0
                if variance < 0 or not math.isfinite(variance):
                    raise HarmonisationError("Mapped prediction variance is invalid.")
                means[name][lat_index, lon_index] = mean
                dispersion[name][lat_index, lon_index] = math.sqrt(variance)

    return HarmonisedValues(
        means=means,
        mapped_prediction_sd=dispersion,
        valid_source_area_m2=valid_area,
        source_coverage_fraction=coverage,
        full_cell_area_m2=full_area,
        latitude=latitude,
        longitude=longitude,
    )


def require_exact_coordinate_subset(
    canonical: np.ndarray,
    requested: np.ndarray,
    axis_name: str,
) -> slice:
    """Return the contiguous exact subset slice or fail without tolerant matching."""
    full = np.asarray(canonical, dtype=np.float64)
    subset = np.asarray(requested, dtype=np.float64)
    if full.ndim != 1 or subset.ndim != 1 or subset.size == 0:
        raise HarmonisationError(
            f"{axis_name} coordinates must be non-empty one-dimensional arrays."
        )
    matches = np.flatnonzero(full == subset[0])
    for start in matches:
        stop = int(start + subset.size)
        if stop <= full.size and np.array_equal(full[start:stop], subset):
            return slice(int(start), stop)
    raise HarmonisationError(
        f"Requested {axis_name} coordinates are not an exact contiguous canonical subset."
    )


def _source_pixel_polygons(
    shape: tuple[int, int],
    transform: Affine,
    transformer: Transformer,
) -> list[Polygon]:
    height, width = shape
    polygons: list[Polygon] = []
    for row in range(height):
        for col in range(width):
            west, north = transform * (col, row)
            east, south = transform * (col + 1, row + 1)
            geographic = box(west, south, east, north)
            polygon = transform_geometry(transformer.transform, geographic)
            area = float(polygon.area)
            if not polygon.is_valid or not math.isfinite(area) or area <= 0:
                raise HarmonisationError(
                    "Source-pixel transformation produced invalid area."
                )
            polygons.append(polygon)
    return polygons


def _target_geographic_polygon(
    west: float,
    south: float,
    east: float,
    north: float,
    source_transform: Affine,
) -> Polygon:
    x_breaks = _source_grid_breaks(west, east, source_transform.c, source_transform.a)
    y_breaks = _source_grid_breaks(
        south, north, source_transform.f, abs(source_transform.e)
    )
    coordinates = (
        [(x, y_breaks[0]) for x in x_breaks]
        + [(x_breaks[-1], y) for y in y_breaks[1:]]
        + [(x, y_breaks[-1]) for x in reversed(x_breaks[:-1])]
        + [(x_breaks[0], y) for y in reversed(y_breaks[1:-1])]
    )
    return Polygon(coordinates)


def _source_grid_breaks(
    low: float,
    high: float,
    origin: float,
    spacing: float,
) -> list[float]:
    def snap(value: float) -> float:
        index = round((value - origin) / spacing)
        candidate = origin + index * spacing
        if math.isclose(
            value, candidate, rel_tol=0.0, abs_tol=COORDINATE_ABS_TOLERANCE
        ):
            return candidate
        return value

    lower = snap(low)
    upper = snap(high)
    first_index = math.ceil((lower - origin) / spacing)
    last_index = math.floor((upper - origin) / spacing)
    interior = [
        origin + index * spacing
        for index in range(first_index, last_index + 1)
        if lower < origin + index * spacing < upper
    ]
    return [lower, *interior, upper]


def _normalise_coverage(
    fraction: float,
    variable: str,
    lat_index: int,
    lon_index: int,
) -> float:
    if not math.isfinite(fraction):
        raise HarmonisationError("Coverage fraction is non-finite.")
    if fraction < -COVERAGE_TOLERANCE or fraction > 1.0 + COVERAGE_TOLERANCE:
        raise HarmonisationError(
            f"Coverage outside [0, 1] for {variable} at ({lat_index}, {lon_index}): {fraction}."
        )
    if abs(fraction) <= COVERAGE_TOLERANCE:
        return 0.0
    if abs(fraction - 1.0) <= COVERAGE_TOLERANCE:
        return 1.0
    return fraction
