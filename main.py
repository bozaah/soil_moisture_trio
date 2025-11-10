from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.visualize import create_interactive_map

# Example Usage
if __name__ == "__main__":
    # Init & prep
    config = ClassifierConfig(moisture_threshold=0.2)  # Tweak via Pydantic
    pipeline = DryWetClassifierPipeline(config)
    pipeline.prepare_data('netcdf')  # Or 'netcdf', path='your_file.nc'
    
    # Train & eval
    pipeline.train()
    metrics = pipeline.evaluate()
    
    # Predict
    pred_map = pipeline.predict_grid()
    
    # Visualize
    create_interactive_map(
        classification_grid=pred_map,
        lats=pipeline.data_grids['lats'],
        lons=pipeline.data_grids['lons'],
        data_grids=pipeline.data_grids,
        output_path="classification_map.html"
    )
    
    # For export: e.g., xr.Dataset({'dry_wet': (['lat', 'lon'], pred_map)}).to_netcdf('output.nc')
