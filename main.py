import argparse

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.risk import save_risk_outputs


def run_pipeline(
    visualize: bool = False,
    output_path: str = "classification_map.html",
    risk_output_prefix: str | None = None,
    catboost_iterations: int | None = None,
    catboost_depth: int | None = None,
    catboost_learning_rate: float | None = None,
    risk_plot_path: str | None = None,
    year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    silo_variables: list[str] | None = None,
    silo_cache_dir: str | None = None,
    silo_cache_max_mb: int | None = None,
    use_silo_cog_loader: bool | None = None,
    silo_overview_level: int | None = None,
    silo_buffer_deg: float | None = None,
) -> None:
    """Execute the end-to-end training/eval flow with optional visualization."""
    # Init & prep
    config_kwargs = {"moisture_threshold": 0.2}
    if year is not None:
        config_kwargs["year"] = year
    if catboost_iterations is not None:
        config_kwargs["catboost_iterations"] = catboost_iterations
    if catboost_depth is not None:
        config_kwargs["catboost_depth"] = catboost_depth
    if catboost_learning_rate is not None:
        config_kwargs["catboost_learning_rate"] = catboost_learning_rate
    if start_date is not None:
        config_kwargs["start_date"] = start_date
    if end_date is not None:
        config_kwargs["end_date"] = end_date
    if silo_variables:
        config_kwargs["silo_variables"] = silo_variables
    if silo_cache_dir is not None:
        config_kwargs["silo_cache_dir"] = silo_cache_dir
    if silo_cache_max_mb is not None:
        config_kwargs["silo_cache_max_size_mb"] = silo_cache_max_mb
    if use_silo_cog_loader is not None:
        config_kwargs["use_silo_cog_loader"] = use_silo_cog_loader
    if silo_overview_level is not None:
        config_kwargs["silo_overview_level"] = silo_overview_level
    if silo_buffer_deg is not None:
        config_kwargs["silo_buffer_degrees"] = silo_buffer_deg
    config = ClassifierConfig(**config_kwargs)
    pipeline = DryWetClassifierPipeline(config)
    pipeline.prepare_data()
    if pipeline.time_metadata:
        print(
            f"Time window: {pipeline.time_metadata['time_start']} to {pipeline.time_metadata['time_end']}"
        )
    
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
    preferred_order = ["critical", "elevated", "watch", "low", "invalid", "valid_cells", "total_cells"]
    for key in preferred_order:
        if key in risk_summary:
            stats = risk_summary[key]
            print(f"  {key}: {stats['count']} cells ({stats['percentage']:.2%})")

    if risk_output_prefix:
        files = save_risk_outputs(
            risk_map=risk_map,
            lats=pipeline.data_grids['lats'],
            lons=pipeline.data_grids['lons'],
            summary=risk_summary,
            base_path=risk_output_prefix,
            time_metadata=pipeline.time_metadata,
        )
        print(f"Risk layer saved to {files['netcdf']} and summary to {files['summary']}")

    if risk_plot_path:
        from src.soil_moisture_trio.plot import save_risk_plot

        plot_path = save_risk_plot(
            risk_map=risk_map,
            lats=pipeline.data_grids['lats'],
            lons=pipeline.data_grids['lons'],
            output_path=risk_plot_path,
        )
        print(f"Risk PNG exported to {plot_path}")

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
    parser.add_argument(
        "--catboost-iterations",
        type=int,
        default=None,
        help="Override CatBoost iterations (defaults to config.epochs).",
    )
    parser.add_argument(
        "--catboost-depth",
        type=int,
        default=None,
        help="Override CatBoost tree depth (defaults to config value).",
    )
    parser.add_argument(
        "--catboost-learning-rate",
        type=float,
        default=None,
        help="Override CatBoost learning rate (defaults to config.lr).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Override the data year (defaults to config value, currently 2024).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD) for averaging the inputs.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD) for averaging the inputs.",
    )
    parser.add_argument(
        "--risk-plot-path",
        default=None,
        help="If provided, saves a PNG rendering of the risk layer to this path.",
    )
    parser.add_argument(
        "--silo-variable",
        dest="silo_variables",
        action="append",
        default=None,
        help="SILO variable or preset to request via weather_tools (repeat for multiple).",
    )
    parser.add_argument(
        "--silo-cache-dir",
        default=None,
        help="Optional directory to persist SILO GeoTIFF downloads (default uses temp cache).",
    )
    parser.add_argument(
        "--silo-cache-max-mb",
        type=int,
        default=None,
        help="Maximum cache size in MB before pruning persisted SILO files.",
    )
    parser.add_argument(
        "--silo-overview-level",
        type=int,
        default=None,
        help="Optional overview level passed to weather_tools for lower-resolution reads.",
    )
    parser.add_argument(
        "--silo-buffer-deg",
        type=float,
        default=None,
        help="Extra degrees to buffer around the bounding box when requesting SILO COG subsets.",
    )
    parser.add_argument(
        "--use-silo-cog-loader",
        dest="use_silo_cog_loader",
        action="store_true",
        help="Force the weather_tools COG loader on (default).",
    )
    parser.add_argument(
        "--no-silo-cog-loader",
        dest="use_silo_cog_loader",
        action="store_false",
        help="Disable the weather_tools COG loader and fall back to NetCDF.",
    )
    parser.set_defaults(use_silo_cog_loader=None)
    args = parser.parse_args()
    run_pipeline(
        visualize=args.visualize,
        output_path=args.output_path,
        risk_output_prefix=args.risk_output_prefix,
        catboost_iterations=args.catboost_iterations,
        catboost_depth=args.catboost_depth,
        catboost_learning_rate=args.catboost_learning_rate,
        risk_plot_path=args.risk_plot_path,
        year=args.year,
        start_date=args.start_date,
        end_date=args.end_date,
        silo_variables=args.silo_variables,
        silo_cache_dir=args.silo_cache_dir,
        silo_cache_max_mb=args.silo_cache_max_mb,
        use_silo_cog_loader=args.use_silo_cog_loader,
        silo_overview_level=args.silo_overview_level,
        silo_buffer_deg=args.silo_buffer_deg,
    )
