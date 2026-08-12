import logging
import os
from datetime import date
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import rioxarray as rio
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.data_sources import WeatherToolsSiloLoader, WeatherToolsResult
from src.soil_moisture_trio.risk import assess_risk_levels

LOGGER = logging.getLogger(__name__)


class DryWetClassifierPipeline:
    def __init__(self, config: Optional[ClassifierConfig] = None):
        config = config or ClassifierConfig()
        if config.boundary_gpkg is not None:
            config = self._derive_bounds_from_gpkg(config)
        self.config = config
        self.valid_mask_grid: Optional[np.ndarray] = None
        self.time_metadata: Optional[Dict[str, str]] = None
        self._silo_loader: Optional[WeatherToolsSiloLoader] = None
        LOGGER.info("Pipeline initialized with config: %s", self.config.model_dump())

    @staticmethod
    def _derive_bounds_from_gpkg(config: ClassifierConfig, buffer: float = 0.1) -> ClassifierConfig:
        """Return a new config with min/max lat/lon derived from the boundary file (+buffer)."""
        import geopandas as gpd
        gdf = gpd.read_file(config.boundary_gpkg).to_crs("EPSG:4326")
        minx, miny, maxx, maxy = gdf.total_bounds  # (min_lon, min_lat, max_lon, max_lat)
        LOGGER.info(
            "Boundary file bounds (EPSG:4326): lon %.4f-%.4f, lat %.4f-%.4f. Applying %.1f° buffer.",
            minx,
            maxx,
            miny,
            maxy,
            buffer,
        )
        return config.model_copy(update={
            "min_lat": round(miny - buffer, 6),
            "max_lat": round(maxy + buffer, 6),
            "min_lon": round(minx - buffer, 6),
            "max_lon": round(maxx + buffer, 6),
        })

    def _build_polygon_mask(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """Boolean mask — True for cells whose centre falls inside the boundary polygon."""
        import geopandas as gpd
        from shapely import contains_xy
        gdf = gpd.read_file(self.config.boundary_gpkg).to_crs("EPSG:4326")
        union_geom = gdf.union_all()
        lon2d, lat2d = np.meshgrid(lons, lats)
        return contains_xy(union_geom, lon2d.flatten(), lat2d.flatten()).reshape(lon2d.shape)

    def _get_silo_loader(self) -> WeatherToolsSiloLoader:
        if self._silo_loader is None:
            self._silo_loader = WeatherToolsSiloLoader(
                cache_dir=self.config.silo_cache_dir,
                cache_max_size_mb=self.config.silo_cache_max_size_mb,
                overview_level=self.config.silo_overview_level,
                buffer_degrees=self.config.silo_buffer_degrees,
            )
        return self._silo_loader

    def _align_lat_lon(
        self,
        data_arrays: Dict[str, np.ndarray],
        lats: np.ndarray,
        lons: np.ndarray,
    ) -> tuple[Dict[str, np.ndarray], np.ndarray, np.ndarray]:
        """Ensure latitude/longitude are ascending and clip to config bounds."""
        aligned = {}
        lat_array = np.array(lats)
        lon_array = np.array(lons)

        lat_desc = lat_array[0] > lat_array[-1]
        lon_desc = lon_array[0] > lon_array[-1]

        for key, arr in data_arrays.items():
            temp_arr = arr.copy()
            if lat_desc:
                temp_arr = np.flip(temp_arr, axis=-2)
            if lon_desc:
                temp_arr = np.flip(temp_arr, axis=-1)
            aligned[key] = temp_arr

        if lat_desc:
            lat_array = lat_array[::-1]
        if lon_desc:
            lon_array = lon_array[::-1]

        lat_mask = (lat_array >= self.config.min_lat) & (lat_array <= self.config.max_lat)
        lon_mask = (lon_array >= self.config.min_lon) & (lon_array <= self.config.max_lon)
        if not lat_mask.any() or not lon_mask.any():
            raise ValueError("Clipping bounds produced an empty grid. Adjust min/max lat/lon.")

        lat_indices = np.where(lat_mask)[0]
        lon_indices = np.where(lon_mask)[0]

        for key in aligned:
            arr = aligned[key]
            if arr.ndim == 2:
                aligned[key] = arr[np.ix_(lat_indices, lon_indices)]
            elif arr.ndim > 2:
                tmp = np.take(arr, lat_indices, axis=-2)
                tmp = np.take(tmp, lon_indices, axis=-1)
                aligned[key] = tmp

        return aligned, lat_array[lat_indices], lon_array[lon_indices]

    def _determine_time_window(self, time_values: np.ndarray) -> tuple[slice, Dict[str, str]]:
        if time_values.size == 0:
            return slice(None), {}
        pd_times = pd.to_datetime(time_values)
        start_target = pd.Timestamp(self.config.start_date) if self.config.start_date else pd_times[0]
        end_target = pd.Timestamp(self.config.end_date) if self.config.end_date else (pd.Timestamp(self.config.start_date) if self.config.start_date else pd_times[-1])
        if end_target < start_target:
            raise ValueError("end_date must be on or after start_date.")
        mask = (pd_times >= start_target) & (pd_times <= end_target)
        if not mask.any():
            raise ValueError(f"No data found between {start_target} and {end_target}.")
        indices = np.where(mask)[0]
        time_slice = slice(indices[0], indices[-1] + 1)
        metadata = {
            'time_start': pd_times[indices[0]].isoformat(),
            'time_end': pd_times[indices[-1]].isoformat(),
        }
        return time_slice, metadata

    def _load_real_netcdf(self, file_path: str, var_name: str) -> tuple[np.ndarray, Dict[str, str]]:
        """Load a single variable from NetCDF and average over the requested time window."""
        LOGGER.info("Loading %s from %s", var_name, file_path)

        is_remote_netcdf = (
            'thredds.nci.org.au' in file_path
            or file_path.startswith('https://s3')
            or file_path.startswith('s3://')
        )
        if is_remote_netcdf:
            if file_path.startswith('https://s3') or file_path.startswith('s3://'):
                os.environ['AWS_NO_SIGN_REQUEST'] = 'YES'
            with xr.open_dataset(file_path) as ds:
                data_array = ds[var_name]
                time_meta = {}
                if 'time' in data_array.dims:
                    time_slice, time_meta = self._determine_time_window(ds['time'].values)
                    data_array = data_array.isel(time=time_slice).mean(dim='time')
                data = data_array.values
            return data, time_meta

        with rio.open_rasterio(file_path, chunks={'band': 1, 'y': 512, 'x': 512}) as da:
            data_array = da.load()

        time_meta: Dict[str, str] = {}
        if 'band' in data_array.dims:
            band_values = data_array['band'].values
            try:
                with xr.open_dataset(file_path) as meta_ds:
                    if 'time' in meta_ds:
                        time_slice, time_meta = self._determine_time_window(meta_ds['time'].values)
                        start_idx, stop_idx = time_slice.start, time_slice.stop
                    else:
                        start_idx = stop_idx = None
            except Exception:
                start_idx = stop_idx = None

            if start_idx is not None and stop_idx is not None and len(band_values) >= stop_idx:
                data_array = data_array.isel(band=slice(start_idx, stop_idx)).mean(dim='band')
            else:
                data_array = data_array.isel(band=0)
        data = data_array.values
        return data, time_meta

    def _load_all_real_data(self) -> Dict[str, np.ndarray]:
        """Load required grids via either NetCDF or the weather_tools SILO loader."""
        data_sources = {
            'soil_moisture': {
                'pct_url': f'https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/deciles/day/sm_pct_{self.config.year}.nc',
                'pct_var': 'sm_pct',
            },
            'temperature': {
                'url': f'https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/max_temp/{self.config.year}.max_temp.nc',
                'var_name': 'max_temp'
            },
            'vpd': {
                'url': f'https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/vp_deficit/{self.config.year}.vp_deficit.nc',
                'var_name': 'vp_deficit'
            }
        }

        soil_moisture_data, soil_meta, lats, lons = self._load_soil_moisture_data(data_sources['soil_moisture'])

        time_metas = [soil_meta]
        data: Dict[str, np.ndarray] = {}
        clipped_lats: np.ndarray
        clipped_lons: np.ndarray

        if self.config.use_silo_cog_loader:
            aligned_soil, clipped_lats, clipped_lons = self._align_lat_lon(
                {'soil_moisture': soil_moisture_data}, lats, lons,
            )
            data.update(aligned_soil)
            try:
                silo_result = self._load_silo_via_weather_tools(clipped_lats, clipped_lons)
                data.update(self._map_silo_variables(silo_result.data))
                time_metas.append(silo_result.time_metadata)
            except Exception as exc:
                LOGGER.warning(
                    "weather_tools COG loader failed (%s). Falling back to SILO NetCDF files.",
                    exc,
                )
                data, clipped_lats, clipped_lons, fallback_metas = self._load_silo_via_netcdf_and_align(
                    soil_moisture_data, lats, lons, data_sources,
                )
                time_metas.extend(fallback_metas)
        else:
            data, clipped_lats, clipped_lons, fallback_metas = self._load_silo_via_netcdf_and_align(
                soil_moisture_data, lats, lons, data_sources,
            )
            time_metas.extend(fallback_metas)

        self.time_metadata = self._combine_time_metadata(time_metas)

        if data.get('temperature') is None or data.get('vpd') is None:
            raise ValueError(
                "SILO data did not provide both temperature and VPD grids. "
                "Ensure 'max_temp' and 'vp_deficit' are included in silo_variables."
            )

        return {
            'soil_moisture': data['soil_moisture'],
            'temperature': data['temperature'],
            'vpd': data['vpd'],
            'lats': clipped_lats,
            'lons': clipped_lons,
            'time_metadata': self.time_metadata,
        }

    def _load_soil_moisture_data(
        self,
        soil_source: Dict[str, str],
    ) -> tuple[np.ndarray, Dict[str, str], np.ndarray, np.ndarray]:
        pct_url = soil_source['pct_url']
        pct_var = soil_source['pct_var']
        try:
            soil_moisture_data, soil_meta = self._load_real_netcdf(pct_url, pct_var)
            soil_moisture_data = self._normalize_sm_pct_decile(soil_moisture_data)
            lats, lons = self._load_spatial_coords(pct_url)
            return soil_moisture_data, soil_meta, lats, lons
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load required soil moisture decile product '{pct_url}': {exc}. "
                "The pipeline requires the AWRAL 'sm_pct' percentile-rank product on a 0-1 scale."
            ) from exc

    @staticmethod
    def _load_spatial_coords(file_path: str) -> tuple[np.ndarray, np.ndarray]:
        with xr.open_dataset(file_path) as ds:
            return ds['latitude'].values, ds['longitude'].values

    @staticmethod
    def _safe_nanmax(values: np.ndarray) -> float:
        try:
            return float(np.nanmax(values))
        except Exception:
            return float('nan')

    def _normalize_sm_pct_decile(self, soil_moisture_data: np.ndarray) -> np.ndarray:
        soil_moisture_data = np.asarray(soil_moisture_data, dtype=float)
        original_max = self._safe_nanmax(soil_moisture_data)
        if np.isnan(original_max):
            LOGGER.warning("Loaded soil moisture decile product contains no finite values.")
        elif original_max > 1.1:
            soil_moisture_data = soil_moisture_data / 100.0
            LOGGER.warning(
                "sm_pct decile unexpectedly in percent scale (max=%.3f); converted to 0-1.",
                original_max,
            )
        else:
            LOGGER.info("sm_pct decile product confirmed 0-1 scale (max=%.3f).", original_max)
        return soil_moisture_data

    def _load_silo_via_weather_tools(
        self,
        target_lats: np.ndarray,
        target_lons: np.ndarray,
    ) -> WeatherToolsResult:
        start_date, end_date = self._resolve_silo_date_range()
        loader = self._get_silo_loader()
        bounds = (
            self.config.min_lat,
            self.config.max_lat,
            self.config.min_lon,
            self.config.max_lon,
        )
        return loader.load(
            variables=self.config.silo_variables,
            start_date=start_date,
            end_date=end_date,
            bounds=bounds,
            target_lats=target_lats,
            target_lons=target_lons,
        )

    def _load_silo_via_netcdf_and_align(
        self,
        soil_moisture: np.ndarray,
        lats: np.ndarray,
        lons: np.ndarray,
        data_sources: Dict[str, Dict[str, str]],
    ) -> tuple[Dict[str, np.ndarray], np.ndarray, np.ndarray, list[Dict[str, str]]]:
        silo_data, silo_metas = self._load_silo_via_netcdf(data_sources)
        merged = {'soil_moisture': soil_moisture, **silo_data}
        aligned, clipped_lats, clipped_lons = self._align_lat_lon(merged, lats, lons)
        return aligned, clipped_lats, clipped_lons, silo_metas

    def _load_silo_via_netcdf(
        self,
        data_sources: Dict[str, Dict[str, str]],
    ) -> tuple[Dict[str, np.ndarray], list[Dict[str, str]]]:
        temperature_data, temp_meta = self._load_real_netcdf(
            data_sources['temperature']['url'],
            data_sources['temperature']['var_name'],
        )
        vpd_data, vpd_meta = self._load_real_netcdf(
            data_sources['vpd']['url'],
            data_sources['vpd']['var_name'],
        )
        metas = [m for m in (temp_meta, vpd_meta) if m]
        return {'temperature': temperature_data, 'vpd': vpd_data}, metas

    def _map_silo_variables(self, silo_data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        mapped: Dict[str, np.ndarray] = {}
        for variable, array in silo_data.items():
            canonical = self._canonical_silo_key(variable)
            mapped[canonical] = array
            if canonical != variable:
                mapped[variable] = array
        return mapped

    @staticmethod
    def _canonical_silo_key(variable: str) -> str:
        mapping = {
            'max_temp': 'temperature',
            'vp_deficit': 'vpd',
            'vp': 'vpd',
        }
        return mapping.get(variable, variable)

    def _resolve_silo_date_range(self) -> tuple[date, date]:
        start = self.config.start_date or date(self.config.year, 1, 1)
        if self.config.end_date:
            end = self.config.end_date
        elif self.config.start_date:
            end = self.config.start_date
        else:
            end = date(self.config.year, 12, 31)
        if end < start:
            raise ValueError("end_date must be on or after start_date.")
        return start, end

    @staticmethod
    def _combine_time_metadata(metas: list[Dict[str, str]]) -> Optional[Dict[str, str]]:
        valid = [m for m in metas if m]
        if not valid:
            return None
        start_times = [m.get('time_start') for m in valid if m.get('time_start')]
        end_times = [m.get('time_end') for m in valid if m.get('time_end')]
        if start_times and end_times:
            return {
                'time_start': min(start_times),
                'time_end': max(end_times),
            }
        return valid[0]

    def prepare_data(self) -> None:
        """Load and validate grids. Builds valid_mask_grid from non-NaN cells."""
        data = self._load_all_real_data()
        soil = data['soil_moisture']
        temp = data['temperature']
        vpd = data['vpd']

        self.valid_mask_grid = np.isfinite(soil) & np.isfinite(temp) & np.isfinite(vpd)
        if self.config.boundary_gpkg is not None:
            poly_mask = self._build_polygon_mask(data["lats"], data["lons"])
            self.valid_mask_grid = self.valid_mask_grid & poly_mask
            LOGGER.info("Polygon mask applied. Cells inside boundary: %d of %d", int(poly_mask.sum()), poly_mask.size)
        if not self.valid_mask_grid.any():
            raise ValueError("No valid grid cells after masking NaN values.")

        self.data_grids = data
        valid_count = int(self.valid_mask_grid.sum())
        LOGGER.info("Data prepared. Valid cells: %d of %d", valid_count, soil.size)

    def assess_risk(self) -> Dict[str, Any]:
        """
        Generate the risk layer and summary statistics.

        Uses valid_mask_grid (built by prepare_data) to identify land/data cells.
        Risk levels are derived entirely from the stress index formula — see risk.py.

        Returns:
            Dict with keys: risk_map, summary, stress_index.
        """
        if not hasattr(self, 'data_grids') or self.valid_mask_grid is None:
            raise ValueError("Call prepare_data() before assess_risk().")

        risk_map, summary, stress_index = assess_risk_levels(self.data_grids, self.valid_mask_grid, self.config)
        return {"risk_map": risk_map, "summary": summary, "stress_index": stress_index}
