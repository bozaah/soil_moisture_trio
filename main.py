import argparse
import logging
from pathlib import Path

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.risk import save_risk_outputs
from src.soil_moisture_trio.plot import save_risk_plot, plot_dryness_diagnostics

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    visualize: bool = False,
    output_path: str = "classification_map.html",
    output_dir: str | None = None,
    risk_output_prefix: str | None = None,
    risk_plot_path: str | None = None,
    boundary_gpkg: str | None = None,
    year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    silo_variables: list[str] | None = None,
    allow_legacy_sm: bool | None = None,
    silo_cache_dir: str | None = None,
    silo_cache_max_mb: int | None = None,
    use_silo_cog_loader: bool | None = None,
    silo_overview_level: int | None = None,
    silo_buffer_deg: float | None = None,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
) -> None:
    """Execute the end-to-end pipeline: load data, assess risk, and save outputs."""
    # ------------------------------------------------------------------
    # 1. Configuration
    # ------------------------------------------------------------------
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        if risk_output_prefix:
            risk_output_prefix = str(out / Path(risk_output_prefix).name)
        if risk_plot_path:
            risk_plot_path = str(out / Path(risk_plot_path).name)

    config_kwargs = {}
    if year is not None:
        config_kwargs["year"] = year
    if start_date is not None:
        config_kwargs["start_date"] = start_date
    if end_date is not None:
        config_kwargs["end_date"] = end_date
    if silo_variables:
        config_kwargs["silo_variables"] = silo_variables
    if allow_legacy_sm is not None:
        config_kwargs["allow_legacy_sm"] = allow_legacy_sm
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
    if min_lat is not None:
        config_kwargs["min_lat"] = min_lat
    if max_lat is not None:
        config_kwargs["max_lat"] = max_lat
    if min_lon is not None:
        config_kwargs["min_lon"] = min_lon
    if max_lon is not None:
        config_kwargs["max_lon"] = max_lon
    if boundary_gpkg is not None:
        config_kwargs["boundary_gpkg"] = boundary_gpkg

    config = ClassifierConfig(**config_kwargs)
    pipeline = DryWetClassifierPipeline(config)

    # ------------------------------------------------------------------
    # 2. Load and prepare data
    # ------------------------------------------------------------------
    pipeline.prepare_data()
    if pipeline.time_metadata:
        LOGGER.info(
            "Time window: %s to %s",
            pipeline.time_metadata["time_start"],
            pipeline.time_metadata["time_end"],
        )

    # ------------------------------------------------------------------
    # 3. Assess risk
    # ------------------------------------------------------------------
    risk_report = pipeline.assess_risk()
    risk_map = risk_report["risk_map"]
    risk_summary = risk_report["summary"]
    stress_index = risk_report["stress_index"]

    LOGGER.info("Risk summary (counts):")
    preferred_order = ["critical", "alert", "watch", "low", "invalid", "valid_cells", "total_cells"]
    for key in preferred_order:
        if key in risk_summary:
            stats = risk_summary[key]
            LOGGER.info("  %s: %s cells (%.2f%%)", key, stats["count"], stats["percentage"] * 100)

    # ------------------------------------------------------------------
    # 4. Save NetCDF and JSON summary
    # ------------------------------------------------------------------
    if risk_output_prefix:
        files = save_risk_outputs(
            risk_map=risk_map,
            lats=pipeline.data_grids["lats"],
            lons=pipeline.data_grids["lons"],
            summary=risk_summary,
            base_path=risk_output_prefix,
            time_metadata=pipeline.time_metadata,
        )
        LOGGER.info("Risk layer saved to %s and summary to %s", files["netcdf"], files["summary"])

    # ------------------------------------------------------------------
    # 5. Visualisation outputs
    # ------------------------------------------------------------------
    if risk_plot_path:
        LOGGER.info("Generating risk map with continuous dryness panel...")
        plot_path = save_risk_plot(
            risk_map=risk_map,
            stress_index=stress_index,
            lats=pipeline.data_grids["lats"],
            lons=pipeline.data_grids["lons"],
            output_path=risk_plot_path,
            time_metadata=pipeline.time_metadata,
            boundary_gpkg=boundary_gpkg,
        )
        LOGGER.info("Risk PNG exported to %s", plot_path)

        diag_path = Path(risk_plot_path).with_name("stress_diagnostics.png")
        plot_dryness_diagnostics(
            soil_moisture=pipeline.data_grids["soil_moisture"],
            vpd=pipeline.data_grids["vpd"],
            stress_index=stress_index,
            output_path=diag_path,
        )
        LOGGER.info("Diagnostic plots exported to %s", diag_path)

    if visualize:
        from src.soil_moisture_trio.visualize import create_interactive_map
        create_interactive_map(
            risk_map=risk_map,
            lats=pipeline.data_grids["lats"],
            lons=pipeline.data_grids["lons"],
            risk_summary=risk_summary,
            output_path=output_path,
        )


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run the Soil Moisture Trio pipeline.")
    parser.add_argument("--visualize", action="store_true", help="Generate the Folium map output.")
    parser.add_argument("--output-path", default="classification_map.html", help="HTML output path.")
    parser.add_argument("--output-dir", default=None, help="Directory for all run outputs. When set, --risk-output-prefix and --risk-plot-path are treated as basenames within this directory.")
    parser.add_argument("--risk-output-prefix", default=None, help="Prefix (or basename with --output-dir) for NetCDF + JSON outputs.")
    parser.add_argument("--risk-plot-path", default=None, help="Path (or basename with --output-dir) for risk PNG figure.")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--silo-variable", dest="silo_variables", action="append", default=None)
    parser.add_argument(
        "--allow-legacy-sm",
        action="store_true",
        help="Allow fallback to the legacy AWRAL raw-values soil-moisture product if the decile product cannot be loaded.",
    )
    parser.add_argument("--silo-cache-dir", default=None)
    parser.add_argument("--silo-cache-max-mb", type=int, default=None)
    parser.add_argument("--silo-overview-level", type=int, default=None)
    parser.add_argument("--silo-buffer-deg", type=float, default=None)
    parser.add_argument("--use-silo-cog-loader", dest="use_silo_cog_loader", action="store_true")
    parser.add_argument("--no-silo-cog-loader", dest="use_silo_cog_loader", action="store_false")
    parser.add_argument("--min-lat", type=float, default=None)
    parser.add_argument("--max-lat", type=float, default=None)
    parser.add_argument("--min-lon", type=float, default=None)
    parser.add_argument("--max-lon", type=float, default=None)
    parser.add_argument("--boundary-gpkg", default=None, help="Path to GeoPackage boundary file. Derives bbox automatically and masks cells outside the polygon.")
    parser.set_defaults(use_silo_cog_loader=None)
    args = parser.parse_args()

    run_pipeline(
        visualize=args.visualize,
        output_path=args.output_path,
        output_dir=args.output_dir,
        risk_output_prefix=args.risk_output_prefix,
        risk_plot_path=args.risk_plot_path,
        boundary_gpkg=args.boundary_gpkg,
        year=args.year,
        start_date=args.start_date,
        end_date=args.end_date,
        silo_variables=args.silo_variables,
        allow_legacy_sm=args.allow_legacy_sm,
        silo_cache_dir=args.silo_cache_dir,
        silo_cache_max_mb=args.silo_cache_max_mb,
        use_silo_cog_loader=args.use_silo_cog_loader,
        silo_overview_level=args.silo_overview_level,
        silo_buffer_deg=args.silo_buffer_deg,
        min_lat=args.min_lat,
        max_lat=args.max_lat,
        min_lon=args.min_lon,
        max_lon=args.max_lon,
    )
