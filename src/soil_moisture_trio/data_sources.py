from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import numpy.ma as ma
import xarray as xr
from shapely.geometry import Polygon, box
from weather_tools.silo_geotiff import download_geotiff

logger = logging.getLogger(__name__)


@dataclass
class WeatherToolsResult:
    data: Dict[str, np.ndarray]
    lats: np.ndarray
    lons: np.ndarray
    time_metadata: Dict[str, str]


class WeatherToolsSiloLoader:
    """Thin wrapper around weather_tools' GeoTIFF helper with cache management."""

    def __init__(
        self,
        cache_dir: Optional[Path],
        cache_max_size_mb: int,
        overview_level: Optional[int],
        buffer_degrees: float,
    ) -> None:
        self.cache_dir = Path(cache_dir).expanduser() if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_max_bytes = cache_max_size_mb * 1024 * 1024
        self.overview_level = overview_level
        self.buffer_degrees = buffer_degrees

    def load(
        self,
        *,
        variables: Sequence[str],
        start_date: date,
        end_date: date,
        bounds: Tuple[float, float, float, float],
        target_lats: np.ndarray,
        target_lons: np.ndarray,
    ) -> WeatherToolsResult:
        if not variables:
            raise ValueError("At least one SILO variable must be provided.")

        min_lat, max_lat, min_lon, max_lon = bounds
        geometry = self._build_geometry(min_lat, max_lat, min_lon, max_lon)

        payload = download_geotiff(
            variables=list(variables),
            start_date=start_date,
            end_date=end_date,
            geometry=geometry,
            output_dir=self.cache_dir if self.cache_dir else None,
            save_to_disk=self.cache_dir is not None,
            read_files=True,
            overview_level=self.overview_level,
        )
        if not payload:
            raise ValueError("weather_tools returned no data for the requested SILO variables.")

        arrays: Dict[str, np.ndarray] = {}
        for variable, (stack, profile) in payload.items():
            reduced = self._reduce_stack(stack)
            lat_values, lon_values = self._coords_from_profile(profile)
            regridded = self._regrid_to_target(reduced, lat_values, lon_values, target_lats, target_lons)
            arrays[variable] = regridded.astype(np.float32)

        if self.cache_dir:
            self._enforce_cache_limit()

        meta = {'time_start': start_date.isoformat(), 'time_end': end_date.isoformat()}
        return WeatherToolsResult(data=arrays, lats=target_lats, lons=target_lons, time_metadata=meta)

    def _enforce_cache_limit(self) -> None:
        files = [p for p in self.cache_dir.rglob("*") if p.is_file()] if self.cache_dir else []
        total = sum(p.stat().st_size for p in files)
        if total <= self.cache_max_bytes:
            return
        files.sort(key=lambda p: p.stat().st_mtime)
        while total > self.cache_max_bytes and files:
            victim = files.pop(0)
            size = victim.stat().st_size
            try:
                victim.unlink()
            except FileNotFoundError:
                pass
            total -= size

    def _build_geometry(self, min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> Polygon:
        buffer = self.buffer_degrees
        geom = box(
            min_lon - buffer,
            min_lat - buffer,
            max_lon + buffer,
            max_lat + buffer,
        )
        return geom

    @staticmethod
    def _reduce_stack(stack: np.ndarray) -> np.ndarray:
        if ma.isMaskedArray(stack):
            data = stack.filled(np.nan).astype(np.float32)
        else:
            data = np.asarray(stack, dtype=np.float32)
        if data.ndim == 3:
            with np.errstate(invalid='ignore'):
                data = np.nanmean(data, axis=0)
        return data

    @staticmethod
    def _coords_from_profile(profile: dict) -> Tuple[np.ndarray, np.ndarray]:
        transform = profile['transform']
        height = profile['height']
        width = profile['width']
        cols = np.arange(width)
        rows = np.arange(height)
        lons = transform.c + (cols + 0.5) * transform.a
        lats = transform.f + (rows + 0.5) * transform.e
        return lats, lons

    @staticmethod
    def _regrid_to_target(
        data: np.ndarray,
        source_lats: np.ndarray,
        source_lons: np.ndarray,
        target_lats: np.ndarray,
        target_lons: np.ndarray,
    ) -> np.ndarray:
        data, source_lats, source_lons = WeatherToolsSiloLoader._orient_to_ascending(
            data, source_lats, source_lons
        )
        da = xr.DataArray(data, coords={'lat': source_lats, 'lon': source_lons}, dims=('lat', 'lon'))
        reindexed = da.interp(lat=target_lats, lon=target_lons, method='nearest')
        return reindexed.values

    @staticmethod
    def _orient_to_ascending(
        data: np.ndarray,
        lats: np.ndarray,
        lons: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        oriented = data
        lat_values = lats
        lon_values = lons
        if lat_values[0] > lat_values[-1]:
            oriented = oriented[::-1, ...]
            lat_values = lat_values[::-1]
        if lon_values[0] > lon_values[-1]:
            oriented = oriented[:, ::-1, ...]
            lon_values = lon_values[::-1]
        return oriented, lat_values, lon_values
