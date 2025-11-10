import argparse

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline


def run_pipeline(visualize: bool = False, output_path: str = "classification_map.html") -> None:
    """Execute the end-to-end training/eval flow with optional visualization."""
    # Init & prep
    config = ClassifierConfig(moisture_threshold=0.2)  # Tweak via Pydantic
    pipeline = DryWetClassifierPipeline(config)
    pipeline.prepare_data('netcdf')  # Or 'synthetic', path='your_file.nc'
    
    # Train & eval
    pipeline.train()
    metrics = pipeline.evaluate()
    print(f"Metrics: {metrics}")
    
    # Predict
    pred_map = pipeline.predict_grid()
    
    if visualize:
        from src.soil_moisture_trio.visualize import create_interactive_map
        create_interactive_map(
            classification_grid=pred_map,
            lats=pipeline.data_grids['lats'],
            lons=pipeline.data_grids['lons'],
            data_grids=pipeline.data_grids,
            output_path=output_path
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Soil Moisture Trio pipeline.")
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Generate the Folium map output after predictions."
    )
    parser.add_argument(
        "--output-path",
        default="classification_map.html",
        help="Path to save the visualization HTML when --visualize is set."
    )
    args = parser.parse_args()
    run_pipeline(visualize=args.visualize, output_path=args.output_path)
