import os
from datetime import date
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import rioxarray as rio
from catboost import CatBoostClassifier, Pool
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.data_sources import WeatherToolsSiloLoader, WeatherToolsResult
from src.soil_moisture_trio.risk import assess_risk_levels

# Main Pipeline Class
class DryWetClassifierPipeline:
    def __init__(self, config: Optional[ClassifierConfig] = None):
        self.config = config or ClassifierConfig()
        self.model: Optional[CatBoostClassifier] = None
        self.valid_mask_grid: Optional[np.ndarray] = None
        self.valid_mask_flat: Optional[np.ndarray] = None
        self.time_metadata: Optional[Dict[str, str]] = None
        self._silo_loader: Optional[WeatherToolsSiloLoader] = None
        print(f"Pipeline initialized with config: {self.config.model_dump()}")

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
                temp_arr = temp_arr[::-1, ...]
            if lon_desc:
                temp_arr = temp_arr[:, ::-1, ...]
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
            aligned[key] = aligned[key][np.ix_(lat_mask, lon_mask)]
        
        return aligned, lat_array[lat_indices], lon_array[lon_indices]
    
    def _determine_time_window(self, time_values: np.ndarray) -> tuple[slice, Dict[str, str]]:
        if time_values.size == 0:
            return slice(None), {}
        pd_times = pd.to_datetime(time_values)
        start_target = pd.Timestamp(self.config.start_date) if self.config.start_date else pd_times[0]
        end_target = pd.Timestamp(self.config.end_date) if self.config.end_date else (pd.Timestamp(self.config.start_date) if self.config.start_date else pd_times[-1])
        if end_target < start_target:
            end_target = start_target
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
        print(f"Loading {var_name} from {file_path}...")

        if file_path.startswith('s3://') or file_path.startswith('https://s3'):
            os.environ['AWS_NO_SIGN_REQUEST'] = 'YES'
            os.environ['AWS_REQUEST_PAYER'] = 'requester'
            os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
            os.environ['GDAL_MAX_RAW_BLOCK_CACHE_SIZE'] = '200000000'
            os.environ['GDAL_SWATH_SIZE'] = '200000000'
            os.environ['VSI_CURL_CACHE_SIZE'] = '200000000'
            os.environ['GDAL_SKIP'] = 'netCDF'

        if 'thredds.nci.org.au' in file_path:
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
                band_slice = slice(band_values[start_idx], band_values[stop_idx - 1])
                data_array = data_array.sel(band=band_slice).mean(dim='band')
            else:
                data_array = data_array.isel(band=0)
        data = data_array.values
        return data, time_meta

    def _load_all_real_data(self) -> Dict[str, np.ndarray]:
        """Load required grids via either NetCDF or the weather_tools SILO loader."""
        data_sources = {
            'soil_moisture': {
                'url': f'https://thredds.nci.org.au/thredds/dodsC/iu04/australian-water-outlook/historical/v1/AWRALv7/processed/values/day/sm_{self.config.year}.nc',
                'var_name': 'sm'
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

        soil_moisture_data, soil_meta = self._load_real_netcdf(
            data_sources['soil_moisture']['url'],
            data_sources['soil_moisture']['var_name']
        )

        with xr.open_dataset(data_sources['soil_moisture']['url']) as ds:
            lats = ds['latitude'].values
            lons = ds['longitude'].values

        time_metas = [soil_meta]
        data: Dict[str, np.ndarray] = {}
        clipped_lats: np.ndarray
        clipped_lons: np.ndarray

        if self.config.use_silo_cog_loader:
            aligned_soil, clipped_lats, clipped_lons = self._align_lat_lon(
                {'soil_moisture': soil_moisture_data},
                lats,
                lons,
            )
            data.update(aligned_soil)
            try:
                silo_result = self._load_silo_via_weather_tools(clipped_lats, clipped_lons)
                data.update(self._map_silo_variables(silo_result.data))
                time_metas.append(silo_result.time_metadata)
            except Exception as exc:
                print(f"weather_tools COG loader failed ({exc}). Falling back to SILO NetCDF files.")
                data, clipped_lats, clipped_lons, fallback_metas = self._load_silo_via_netcdf_and_align(
                    soil_moisture_data,
                    lats,
                    lons,
                    data_sources,
                )
                time_metas.extend(fallback_metas)
        else:
            data, clipped_lats, clipped_lons, fallback_metas = self._load_silo_via_netcdf_and_align(
                soil_moisture_data,
                lats,
                lons,
                data_sources,
            )
            time_metas.extend(fallback_metas)

        self.time_metadata = self._combine_time_metadata(time_metas)

        if data.get('temperature') is None or data.get('vpd') is None:
            raise ValueError(
                "SILO data did not provide both temperature and VPD grids. "
                "Ensure 'max_temp' and 'vp_deficit' are included in silo_variables."
            )

        grid_shape = data['soil_moisture'].shape
        ndvi = np.random.uniform(-0.1, 1.0, grid_shape)
        ndwi = np.random.uniform(-0.5, 0.5, grid_shape)
        fire_index = np.random.uniform(0, 10, grid_shape)

        return {
            'soil_moisture': data['soil_moisture'],
            'temperature': data.get('temperature'),
            'ndvi': ndvi,
            'ndwi': ndwi,
            'fire_index': fire_index,
            'vpd': data.get('vpd'),
            **{k: v for k, v in data.items() if k not in {'soil_moisture', 'temperature', 'vpd'}},
            'lats': clipped_lats,
            'lons': clipped_lons,
            'time_metadata': self.time_metadata,
        }

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
            end = start
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
        """Prep X/y from the configured real-world data sources."""
        data = self._load_all_real_data()
        
        # Flatten to samples
        soil = data['soil_moisture']
        temp = data['temperature']
        ndvi = data['ndvi']
        vpd = data['vpd']
        valid_mask_grid = (
            np.isfinite(soil) &
            np.isfinite(temp) &
            np.isfinite(ndvi) &
            np.isfinite(vpd)
        )
        valid_flat = valid_mask_grid.flatten()
        if not valid_flat.any():
            raise ValueError("No valid grid cells available after masking NaN values.")
        
        X = np.column_stack([
            soil.flatten(),
            temp.flatten(),
            ndvi.flatten(),  # Placeholder until real NDVI integration
            vpd.flatten()
        ])

        y_full = np.where(
            (soil.flatten() < self.config.moisture_threshold) &
            ((temp.flatten() > self.config.temp_threshold) | (vpd.flatten() > self.config.vpd_threshold)),
            0, 1
        ).astype(np.float32)

        X = X[valid_flat]
        y = y_full[valid_flat]

        split = int(0.8 * len(X))
        self.X_train, self.X_test = X[:split], X[split:]
        self.y_train, self.y_test = y[:split], y[split:]
        self.data_grids = data  # Store for grid prediction
        self.valid_mask_grid = valid_mask_grid
        self.valid_mask_flat = valid_flat
        
        counts = np.bincount(y.astype(int), minlength=2)
        print(f"Data prepared. Labels: {counts} (dry, wet)")
    
    def build_model(self) -> None:
        """Initialize CatBoost model."""
        self.model = CatBoostClassifier(
            iterations=self.config.catboost_iterations or self.config.epochs,
            depth=self.config.catboost_depth,
            learning_rate=self.config.catboost_learning_rate or self.config.lr,
            loss_function="Logloss",
            eval_metric="Logloss",
            verbose=False,
        )
    
    def train(self) -> None:
        """Train the CatBoost classifier."""
        if not self.model:
            self.build_model()
        
        train_pool = Pool(self.X_train, label=self.y_train)
        eval_pool = Pool(self.X_test, label=self.y_test)
        self.model.fit(train_pool, eval_set=eval_pool, verbose=False)
    
    def evaluate(self) -> Dict[str, float]:
        """Evaluate on test set."""
        if not self.model:
            raise ValueError("Train first!")
        
        test_probs = self.model.predict_proba(self.X_test)[:, 1]
        epsilon = 1e-9
        test_loss = -np.mean(
            self.y_test * np.log(test_probs + epsilon) +
            (1 - self.y_test) * np.log(1 - test_probs + epsilon)
        )
        accuracy = np.mean((test_probs > 0.5) == self.y_test)
        
        print(f"Test Loss: {test_loss:.4f}, Accuracy: {accuracy:.4f}")
        return {'loss': float(test_loss), 'accuracy': float(accuracy)}
    
    def predict_grid(self) -> np.ndarray:
        """Classify full grid."""
        if not self.model:
            raise ValueError("Train first!")
        if self.valid_mask_grid is None or self.valid_mask_flat is None:
            raise ValueError("Prepare data before predicting the grid.")
        
        features = np.column_stack([
            self.data_grids['soil_moisture'].flatten(),
            self.data_grids['temperature'].flatten(),
            self.data_grids['ndvi'].flatten(),  # Placeholder until real NDVI integration
            self.data_grids['vpd'].flatten()
        ])
        
        valid_flat = self.valid_mask_flat
        pred_probs_flat = np.full(features.shape[0], np.nan, dtype=np.float32)
        pred_probs_flat[valid_flat] = self.model.predict_proba(features[valid_flat])[:, 1]
        
        grid_shape = self.data_grids['soil_moisture'].shape
        pred_class = np.full(grid_shape, -1, dtype=np.int8)
        valid_classes = (pred_probs_flat[valid_flat] > 0.5).astype(np.int8)
        pred_class_flat = pred_class.flatten()
        pred_class_flat[valid_flat] = valid_classes
        pred_class = pred_class_flat.reshape(grid_shape)
        
        dry_count = int(np.sum(pred_class == 0))
        wet_count = int(np.sum(pred_class == 1))
        invalid_count = int(np.sum(pred_class < 0))
        print(f"Grid classified. Dry: {dry_count}, Wet: {wet_count}, No data: {invalid_count}")
        return pred_class  # -1 denotes invalid/ocean cells

    def assess_risk(self, classification_grid: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Generate the risk layer and summary statistics.

        Args:
            classification_grid: Optional cached prediction. If None, predict_grid() is invoked.

        Returns:
            Dict containing the risk_map and summary counts/percentages.
        """
        if not hasattr(self, "data_grids"):
            raise ValueError("Prepare data before assessing risk.")
        if classification_grid is None:
            classification_grid = self.predict_grid()

        risk_map, summary = assess_risk_levels(self.data_grids, classification_grid, self.config)
        return {"risk_map": risk_map, "summary": summary}
