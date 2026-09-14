import argparse
import logging
from pathlib import Path

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.risk import save_risk_outputs
from src.soil_moisture_trio.plot import save_risk_plot, plot_dryness_diagnostics

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    config: ClassifierConfig | None = None,
    *,
    output_dir: str | None = None,
    risk_output_prefix: str | None = None,
    risk_plot_path: str | None = None,
) -> None:
    """Run a validated model configuration. Output locations are separate options."""
    pipeline = DryWetClassifierPipeline(config)
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        if risk_output_prefix:
            risk_output_prefix = str(out / Path(risk_output_prefix).name)
        if risk_plot_path:
            risk_plot_path = str(out / Path(risk_plot_path).name)

    pipeline.prepare_data()
    if pipeline.time_metadata:
        LOGGER.info("Time window: %s to %s", pipeline.time_metadata["time_start"], pipeline.time_metadata["time_end"])
    report = pipeline.assess_risk()
    for key in ("critical", "alert", "watch", "low", "invalid", "valid_cells", "total_cells"):
        stats = report["summary"][key]
        LOGGER.info("%s: %s cells (%.2f%%)", key, stats["count"], stats["percentage"] * 100)

    if risk_output_prefix:
        files = save_risk_outputs(
            risk_map=report["risk_map"],
            lats=pipeline.data_grids["lats"], lons=pipeline.data_grids["lons"],
            summary=report["summary"], base_path=risk_output_prefix,
            time_metadata=pipeline.time_metadata,
            model_metadata=pipeline.config.risk_model_parameters(),
        )
        LOGGER.info("Risk layer saved to %s and summary to %s", files["netcdf"], files["summary"])

    if risk_plot_path:
        plot_path = save_risk_plot(
            risk_map=report["risk_map"], stress_index=report["stress_index"],
            lats=pipeline.data_grids["lats"], lons=pipeline.data_grids["lons"],
            output_path=risk_plot_path, time_metadata=pipeline.time_metadata,
            boundary_gpkg=pipeline.config.boundary_gpkg,
        )
        LOGGER.info("Risk PNG exported to %s", plot_path)
        diag_path = Path(risk_plot_path).with_name("stress_diagnostics.png")
        plot_dryness_diagnostics(
            soil_moisture=pipeline.data_grids["soil_moisture"],
            vpd=pipeline.data_grids["vpd"], stress_index=report["stress_index"],
            output_path=diag_path,
        )
        LOGGER.info("Diagnostic plots exported to %s", diag_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Soil Moisture Trio pipeline.")
    parser.add_argument("--output-dir", default=None, help="Directory for all run outputs. Output paths become basenames within it.")
    parser.add_argument("--risk-output-prefix", default=None, help="Prefix for NetCDF + JSON outputs.")
    parser.add_argument("--risk-plot-path", default=None, help="Path for risk PNG figure.")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--dryness-weight", type=float, default=None)
    parser.add_argument("--vpd-weight", type=float, default=None)
    parser.add_argument("--temperature-weight", type=float, default=None)
    parser.add_argument("--watch-risk-threshold", type=float, default=None)
    parser.add_argument("--alert-risk-threshold", type=float, default=None)
    parser.add_argument("--critical-risk-threshold", type=float, default=None)
    parser.add_argument("--silo-variable", dest="silo_variables", action="append", default=None)
    parser.add_argument("--silo-cache-dir", default=None)
    parser.add_argument("--silo-cache-max-mb", dest="silo_cache_max_size_mb", type=int, default=None)
    parser.add_argument("--silo-overview-level", type=int, default=None)
    parser.add_argument("--silo-buffer-deg", dest="silo_buffer_degrees", type=float, default=None)
    parser.add_argument("--use-silo-cog-loader", dest="use_silo_cog_loader", action="store_true")
    parser.add_argument("--no-silo-cog-loader", dest="use_silo_cog_loader", action="store_false", help="Explicit NetCDF path. COG errors never trigger automatic fallback.")
    parser.add_argument("--min-lat", type=float, default=None)
    parser.add_argument("--max-lat", type=float, default=None)
    parser.add_argument("--min-lon", type=float, default=None)
    parser.add_argument("--max-lon", type=float, default=None)
    parser.add_argument("--boundary-gpkg", default=None, help="Boundary GeoPackage: derives bbox and masks cells outside the polygon.")
    parser.set_defaults(use_silo_cog_loader=None)
    return parser.parse_args(argv)


def cli(argv: list[str] | None = None) -> None:
    options = vars(parse_args(argv))
    outputs = {name: options.pop(name) for name in ("output_dir", "risk_output_prefix", "risk_plot_path")}
    config = ClassifierConfig(**{key: value for key, value in options.items() if value is not None})
    run_pipeline(config, **outputs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cli()
