import os
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from typing import List, Dict, Any, Optional
import xarray as xr
import rioxarray as rio
import fsspec

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.model import SoilData, DryWetClassifier

# Main Pipeline Class
class DryWetClassifierPipeline:
    def __init__(self, config: Optional[ClassifierConfig] = None):
        self.config = config or ClassifierConfig()
        self.model: Optional[DryWetClassifier] = None
        self.criterion = nn.BCELoss()
        self.optimizer: Optional[optim.Optimizer] = None
        
        # Determine device
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")
        print(f"Using device: {self.device}")
        
        print(f"Pipeline initialized with config: {self.config.model_dump()}")
    
    def _generate_synthetic_data(self) -> Dict[str, np.ndarray]:
        """Generate synthetic grids (replace with real NetCDF load)."""
        grid_size = 20
        np.random.seed(42)
        lats = np.linspace(-10, 10, grid_size)
        lons = np.linspace(-20, 20, grid_size)
        lon, lat = np.meshgrid(lons, lats)
        
        soil_moisture = np.random.uniform(0, 0.5, (grid_size, grid_size))
        temperature = np.random.uniform(15, 35, (grid_size, grid_size))  # Vegetation index
        ndvi = np.random.uniform(-0.1, 1.0, (grid_size, grid_size))  # Vegetation index
        ndwi = np.random.uniform(-0.5, 0.5, (grid_size, grid_size))  # Water index
        fire_index = np.random.uniform(0, 10, (grid_size, grid_size))  # Fire risk
        
        print("Synthetic data generated. Shapes:", (grid_size, grid_size) * 5)
        return {
            'soil_moisture': soil_moisture,
            'temperature': temperature,
            'ndvi': ndvi,
            'ndwi': ndwi,
            'fire_index': fire_index,
            'lats': lats,
            'lons': lons
        }
    
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

    def prepare_data(self, data_source: str = 'synthetic', file_path: Optional[str] = None) -> None:
        """Prep X/y from data source."""
        if data_source == 'synthetic':
            data = self._generate_synthetic_data()
        elif data_source == 'netcdf':
            data = self._load_all_real_data()
        else:
            raise ValueError("Use 'synthetic' or 'netcdf'.")
        
        # Flatten to samples
        X = np.column_stack([
            data['soil_moisture'].flatten(),
            data['temperature'].flatten(),
            data['ndvi'].flatten(), # Synthetic
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
        """Initialize model & optimizer."""
        self.model = DryWetClassifier(input_size=4) # Updated input size
        self.model.to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.config.lr)
    
    def train(self) -> None:
        """Train the model."""
        if not self.model:
            self.build_model()
        
        train_ds = SoilData(self.X_train, self.y_train)
        train_loader = DataLoader(train_ds, batch_size=self.config.batch_size, shuffle=True)
        
        self.model.train()
        for epoch in range(self.config.epochs):
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                self.optimizer.zero_grad()
                out = self.model(X_batch)
                loss = self.criterion(out, y_batch)
                loss.backward()
                self.optimizer.step()
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{self.config.epochs}, Loss: {loss.item():.4f}")
    
    def evaluate(self) -> Dict[str, float]:
        """Evaluate on test set."""
        if not self.model:
            raise ValueError("Train first!")
        
        test_ds = SoilData(self.X_test, self.y_test)
        test_loader = DataLoader(test_ds, batch_size=self.config.batch_size, shuffle=False)
        
        self.model.eval()
        with torch.no_grad():
            test_pred = self.model(torch.tensor(self.X_test, dtype=torch.float32).to(self.device))
            test_loss = self.criterion(test_pred, torch.tensor(self.y_test, dtype=torch.float32).unsqueeze(1).to(self.device))
            accuracy = ((test_pred > 0.5).float() == torch.tensor(self.y_test, dtype=torch.float32).unsqueeze(1).to(self.device)).float().mean()
        
        print(f"Test Loss: {test_loss.item():.4f}, Accuracy: {accuracy.item():.4f}")
        return {'loss': test_loss.item(), 'accuracy': accuracy.item()}
    
    def predict_grid(self) -> np.ndarray:
        """Classify full grid."""
        if not self.model:
            raise ValueError("Train first!")
        
        X_grid = np.column_stack([
            self.data_grids['soil_moisture'].flatten(),
            self.data_grids['temperature'].flatten(),
            self.data_grids['ndvi'].flatten(), # Synthetic
            self.data_grids['vpd'].flatten()
        ])
        
        with torch.no_grad():
            pred_probs = self.model(torch.tensor(X_grid, dtype=torch.float32).to(self.device)).cpu().numpy().reshape(
                self.data_grids['soil_moisture'].shape
            )
            pred_class = (pred_probs > 0.5).astype(int)
        
        dry_count = np.sum(pred_class == 0)
        wet_count = np.sum(pred_class == 1)
        print(f"Grid classified. Dry cells: {dry_count}, Wet cells: {wet_count}")
        return pred_class  # Binary map for export/visualization