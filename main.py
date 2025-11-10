import argparse

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.risk import save_risk_outputs


def run_pipeline(
    visualize: bool = False,
    output_path: str = "classification_map.html",
    risk_output_prefix: str | None = None,
) -> None:
    """Execute the end-to-end training/eval flow with optional visualization."""
    # Init & prep
    config = ClassifierConfig(moisture_threshold=0.2)  # Tweak via Pydantic
    pipeline = DryWetClassifierPipeline(config)
    pipeline.prepare_data()
    
    # Train & eval
    pipeline.train()
    metrics = pipeline.evaluate()
    print(f"Metrics: {metrics}")
    
    # Predict & derive risk insights
    pred_map = pipeline.predict_grid()
    risk_report = pipeline.assess_risk(pred_map)
    risk_map = risk_report["risk_map"]
    risk_summary = risk_report["summary"]
    print("Risk summary (counts):")
    for level, stats in risk_summary.items():
        print(f"  {level}: {stats['count']} cells ({stats['percentage']:.2%})")

    if risk_output_prefix:
        files = save_risk_outputs(
            risk_map=risk_map,
            lats=pipeline.data_grids['lats'],
            lons=pipeline.data_grids['lons'],
            summary=risk_summary,
            base_path=risk_output_prefix,
        )
        print(f"Risk layer saved to {files['netcdf']} and summary to {files['summary']}")

    if visualize:
        from src.soil_moisture_trio.visualize import create_interactive_map
        create_interactive_map(
            risk_map=risk_map,
            lats=pipeline.data_grids['lats'],
            lons=pipeline.data_grids['lons'],
            risk_summary=risk_summary,
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
    parser.add_argument(
        "--risk-output-prefix",
        default=None,
        help="If provided, writes risk_map NetCDF + JSON summary using this prefix (e.g. 'risk_layer')."
    )
    args = parser.parse_args()
    run_pipeline(
        visualize=args.visualize,
        output_path=args.output_path,
        risk_output_prefix=args.risk_output_prefix,
    )
