import logging
import os
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.data_sources import WeatherToolsSiloLoader
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
        """Derive and validate the boundary's buffered bounds."""
        import geopandas as gpd
        gdf = gpd.read_file(config.boundary_gpkg).to_crs("EPSG:4326")
        minx, miny, maxx, maxy = gdf.total_bounds
        return ClassifierConfig.model_validate({
            **config.model_dump(),
            "min_lat": round(miny - buffer, 6),
            "max_lat": round(maxy + buffer, 6),
            "min_lon": round(minx - buffer, 6),
            "max_lon": round(maxx + buffer, 6),
        })

    def _build_polygon_mask(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """True for cells whose centre falls inside the boundary polygon."""
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

    def _determine_time_window(self, time_values: np.ndarray) -> tuple[slice, Dict[str, str]]:
        """Require every requested day exactly once, ordered, at daily resolution."""
        if time_values.ndim != 1 or not time_values.size:
            raise ValueError("Daily time coordinates must be a non-empty 1D array.")
        times = pd.DatetimeIndex(pd.to_datetime(time_values))
        if times.hasnans or not times.is_unique or not times.is_monotonic_increasing:
            raise ValueError("Daily time coordinates must be finite, unique and increasing.")
        if not times.equals(times.normalize()):
            raise ValueError("Expected daily midnight time coordinates.")
        start, end = self.config.date_range()
        expected = pd.date_range(start, end, freq="D")
        selected = times[(times >= pd.Timestamp(start)) & (times <= pd.Timestamp(end))]
        missing = expected.difference(selected)
        if not selected.equals(expected):
            raise ValueError(
                f"Incomplete daily window {start} to {end}: missing {len(missing)} days "
                f"({', '.join(missing.strftime('%Y-%m-%d')[:5])})."
            )
        first = int(times.get_loc(expected[0]))
        return slice(first, first + len(expected)), {
            "time_start": start.isoformat(), "time_end": end.isoformat(),
        }

    def _load_real_netcdf(
        self, file_path: str, var_name: str,
    ) -> tuple[np.ndarray, Dict[str, str], np.ndarray, np.ndarray]:
        """Read a daily cube with its own coordinates, then average a complete window."""
        LOGGER.info("Loading %s from %s", var_name, file_path)
        if file_path.startswith(("https://s3", "s3://")):
            os.environ["AWS_NO_SIGN_REQUEST"] = "YES"
        with xr.open_dataset(file_path) as ds:
            da = ds[var_name]
            if set(da.dims) == {"time", "lat", "lon"}:
                da = da.rename({"lat": "latitude", "lon": "longitude"})
            if set(da.dims) != {"time", "latitude", "longitude"}:
                raise ValueError(f"{var_name} must have time, latitude and longitude dimensions.")
            da = da.transpose("time", "latitude", "longitude")
            time_slice, time_meta = self._determine_time_window(da.time.values)
            da = da.isel(time=time_slice)
            for name, low, high in (
                ("latitude", self.config.min_lat, self.config.max_lat),
                ("longitude", self.config.min_lon, self.config.max_lon),
            ):
                coords = np.asarray(da[name].values)
                delta = np.diff(coords)
                if coords.ndim != 1 or not coords.size or not np.isfinite(coords).all():
                    raise ValueError(f"Invalid {name} coordinates for {var_name}.")
                if not ((delta > 0).all() or (delta < 0).all()):
                    raise ValueError(f"{name} coordinates must be strictly monotonic.")
                if coords.size > 1 and coords[0] > coords[-1]:
                    da = da.isel({name: slice(None, None, -1)})
                da = da.sel({name: slice(low, high)})
                if not da.sizes[name]:
                    raise ValueError(f"Clipping bounds produced an empty {name} grid.")
            values = np.array(da.values, copy=True)
            if not np.issubdtype(values.dtype, np.floating):
                values = values.astype(float)
            if var_name == "sm_pct":
                if da.attrs.get("units") != "relative":
                    raise ValueError("sm_pct requires the verified percentile product units 'relative'.")
                if np.isinf(values).any() or ((values < 0) | (values > 1)).any():
                    raise ValueError("sm_pct percentile values must lie in [0, 1], with NaN for missing data.")
            # Missing any requested day makes that cell invalid, not a shorter-window mean.
            values[~np.isfinite(values)] = np.nan
            averaged = np.mean(values, axis=0)
            if var_name == "sm_pct":
                averaged = np.asarray(averaged, dtype=float)
            return (
                averaged, time_meta,
                np.asarray(da.latitude.values), np.asarray(da.longitude.values),
            )

    def _load_all_real_data(self) -> Dict[str, Any]:
        soil_url = (
            "https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/"
            "historical/v1/AWRALv7/processed/deciles/day/"
            f"sm_pct_{self.config.year}.nc"
        )
        try:
            soil, soil_meta, lats, lons = self._load_real_netcdf(soil_url, "sm_pct")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load required soil moisture decile product '{soil_url}': {exc}. "
                "The pipeline requires the AWRAL 'sm_pct' percentile-rank product on a 0-1 scale."
            ) from exc

        data = {"soil_moisture": soil}
        metas = [soil_meta]
        mapping = {"max_temp": "temperature", "vp_deficit": "vpd"}
        if self.config.use_silo_cog_loader:
            start, end = self.config.date_range()
            result = self._get_silo_loader().load(
                variables=self.config.silo_variables,
                start_date=start, end_date=end,
                bounds=(self.config.min_lat, self.config.max_lat,
                        self.config.min_lon, self.config.max_lon),
                target_lats=lats, target_lons=lons,
            )
            # COG failures propagate. No automatic switch to a different data path.
            if not np.array_equal(result.lats, lats) or not np.array_equal(result.lons, lons):
                raise ValueError("SILO COG output coordinates do not match AWRA-L.")
            data.update({name: result.data[var] for var, name in mapping.items()})
            metas.append(result.time_metadata)
        else:
            for variable, name in mapping.items():
                url = (
                    "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/"
                    f"{variable}/{self.config.year}.{variable}.nc"
                )
                values, meta, silo_lats, silo_lons = self._load_real_netcdf(url, variable)
                if not np.array_equal(lats, silo_lats) or not np.array_equal(lons, silo_lons):
                    raise ValueError(f"SILO {variable} NetCDF coordinates do not match AWRA-L.")
                data[name] = values
                metas.append(meta)
        return {
            **data, "lats": lats, "lons": lons,
            "time_metadata": self._combine_time_metadata(metas),
        }

    @staticmethod
    def _combine_time_metadata(metas: list[Dict[str, str]]) -> Dict[str, str]:
        if not metas or any(set(m) != {"time_start", "time_end"} for m in metas):
            raise ValueError("Every input must provide a complete time window.")
        windows = [(pd.Timestamp(m["time_start"]), pd.Timestamp(m["time_end"])) for m in metas]
        if any(pd.isna(start) or pd.isna(end) or end < start for start, end in windows):
            raise ValueError("Invalid input time window.")
        if any(window != windows[0] for window in windows):
            raise ValueError("Input time windows do not match.")
        return dict(metas[0])

    def prepare_data(self) -> None:
        """Load grids and preserve missing-day/input and boundary exclusions."""
        data = self._load_all_real_data()
        soil, temp, vpd = (data[key] for key in ("soil_moisture", "temperature", "vpd"))
        shape = (len(data["lats"]), len(data["lons"]))
        if any(array.shape != shape for array in (soil, temp, vpd)):
            raise ValueError("Input grid shapes must match the latitude/longitude coordinates.")
        self.valid_mask_grid = np.isfinite(soil) & np.isfinite(temp) & np.isfinite(vpd)
        if self.config.boundary_gpkg is not None:
            self.valid_mask_grid &= self._build_polygon_mask(data["lats"], data["lons"])
        if not self.valid_mask_grid.any():
            raise ValueError("No valid grid cells after masking missing inputs and boundary.")
        self.time_metadata = data["time_metadata"]
        self.data_grids = data
        LOGGER.info("Data prepared. Valid cells: %d of %d", int(self.valid_mask_grid.sum()), soil.size)

    def assess_risk(self) -> Dict[str, Any]:
        """Classify the prepared grids using the unchanged composite stress index."""
        if not hasattr(self, 'data_grids') or self.valid_mask_grid is None:
            raise ValueError("Call prepare_data() before assess_risk().")
        risk_map, summary, stress_index = assess_risk_levels(self.data_grids, self.valid_mask_grid, self.config)
        return {"risk_map": risk_map, "summary": summary, "stress_index": stress_index}
