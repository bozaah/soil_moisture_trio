import os
from typing import Any, Dict, Optional

import numpy as np
import xarray as xr
import rioxarray as rio
from catboost import CatBoostClassifier, Pool

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.risk import assess_risk_levels

# Main Pipeline Class
class DryWetClassifierPipeline:
    def __init__(self, config: Optional[ClassifierConfig] = None):
        self.config = config or ClassifierConfig()
        self.model: Optional[CatBoostClassifier] = None
        print(f"Pipeline initialized with config: {self.config.model_dump()}")
    
    def _load_real_netcdf(self, file_path: str, var_name: str) -> np.ndarray:
        """Load a single variable from a real NetCDF file (e.g., via xarray)."""
        print(f"Loading {var_name} from {file_path}...")
        if file_path.startswith('s3://') or file_path.startswith('https://s3'):
            # Set environment variables for GDAL and AWS S3 access
            os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
            os.environ['AWS_NO_SIGN_REQUEST'] = 'YES'
            os.environ['GDAL_MAX_RAW_BLOCK_CACHE_SIZE'] = '200000000'
            os.environ['GDAL_SWATH_SIZE'] = '200000000'
            os.environ['VSI_CURL_CACHE_SIZE'] = '200000000'
            os.environ['GDAL_SKIP'] = 'netCDF'
            os.environ['AWS_NO_SIGN_REQUEST'] = 'YES' # Ensure this is set for public S3 access
            os.environ['AWS_REQUEST_PAYER'] = 'requester' # For requester pays buckets
            
            with rio.open_rasterio(file_path, chunks=(1,1024,1024)) as ds:
                # For now, we'll just take the first time step.
                # We will need to handle time alignment later.
                data = ds.isel(band=0).values
        elif file_path.startswith('http://') or file_path.startswith('https://'):
            # Check if it's an OPeNDAP URL (e.g., NCI THREDDS)
            if 'thredds.nci.org.au/thredds/dodsC' in file_path:
                with xr.open_dataset(file_path) as ds:
                    data = ds[var_name].isel(time=0).values
            else:
                # Use rio.open_rasterio for generic HTTP/HTTPS NetCDF files
                with rio.open_rasterio(file_path, chunks=(1,1024,1024)) as ds:
                    # For now, we'll just take the first time step.
                    # We will need to handle time alignment later.
                    data = ds.isel(band=0).values
        else:
            # Fallback for local files or other protocols
            with xr.open_dataset(file_path) as ds:
                data = ds[var_name].isel(time=0).values
        return data

    def _load_all_real_data(self) -> Dict[str, np.ndarray]:
        """Load all required variables from their respective NetCDF sources."""
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

        # For now, we only load soil moisture. We'll add the others later.
        soil_moisture_data = self._load_real_netcdf(
            data_sources['soil_moisture']['url'],
            data_sources['soil_moisture']['var_name']
        )

        temperature_data = self._load_real_netcdf(
            data_sources['temperature']['url'],
            data_sources['temperature']['var_name']
        )

        vpd_data = self._load_real_netcdf(
            data_sources['vpd']['url'],
            data_sources['vpd']['var_name']
        )

        # We need to get lats and lons as well. We can get them from the soil moisture dataset.
        with xr.open_dataset(data_sources['soil_moisture']['url']) as ds:
            lats = ds['latitude'].values
            lons = ds['longitude'].values

        # For now, we will use synthetic data for the other variables.
        # This will be replaced as we integrate the other data sources.
        grid_size_lat = len(lats)
        grid_size_lon = len(lons)
        # temperature = np.random.uniform(15, 35, (grid_size_lat, grid_size_lon)) # This is now loaded
        ndvi = np.random.uniform(-0.1, 1.0, (grid_size_lat, grid_size_lon)) # Reintroduce synthetic NDVI
        ndwi = np.random.uniform(-0.5, 0.5, (grid_size_lat, grid_size_lon))
        fire_index = np.random.uniform(0, 10, (grid_size_lat, grid_size_lon)) # Reintroduce synthetic Fire Index

        return {
            'soil_moisture': soil_moisture_data,
            'temperature': temperature_data,
            'ndvi': ndvi,
            'ndwi': ndwi,
            'fire_index': fire_index,
            'vpd': vpd_data,
            'lats': lats,
            'lons': lons
        }

    def prepare_data(self) -> None:
        """Prep X/y from the configured real-world data sources."""
        data = self._load_all_real_data()
        
        # Flatten to samples
        X = np.column_stack([
            data['soil_moisture'].flatten(),
            data['temperature'].flatten(),
            data['ndvi'].flatten(), # Placeholder until real NDVI integration
            data['vpd'].flatten()
        ])

        # Handle NaN values
        if np.isnan(X).any():
            print("Warning: NaN values found in input data. Replacing with mean.")
            col_mean = np.nanmean(X, axis=0)
            inds = np.where(np.isnan(X))
            X[inds] = np.take(col_mean, inds[1])
        
        # Labels: Dry if low moisture OR (low NDVI + high fire) OR (low NDWI + high temp)
        # Updated classification logic
        y = np.where(
            (X[:, 0] < self.config.moisture_threshold) &
            ((X[:, 1] > self.config.temp_threshold) | (X[:, 3] > self.config.vpd_threshold)),
            0, 1
        ).astype(np.float32)
        
        # Split
        split = int(0.8 * len(X))
        self.X_train, self.X_test = X[:split], X[split:]
        self.y_train, self.y_test = y[:split], y[split:]
        self.data_grids = data  # Store for grid prediction
        
        print(f"Data prepared. Labels: {np.bincount(y.astype(int))} (dry, wet)")
    
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
        
        X_grid = np.column_stack([
            self.data_grids['soil_moisture'].flatten(),
            self.data_grids['temperature'].flatten(),
            self.data_grids['ndvi'].flatten(), # Placeholder until real NDVI integration
            self.data_grids['vpd'].flatten()
        ])
        
        pred_probs = self.model.predict_proba(X_grid)[:, 1].reshape(
            self.data_grids['soil_moisture'].shape
        )
        pred_class = (pred_probs > 0.5).astype(int)
        
        dry_count = np.sum(pred_class == 0)
        wet_count = np.sum(pred_class == 1)
        print(f"Grid classified. Dry cells: {dry_count}, Wet cells: {wet_count}")
        return pred_class  # Binary map for export/visualization

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
