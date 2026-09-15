"""Group a finished SWAZ risk run by SLGA soil context from the review bundle.

Review input only, under the 2026-08-31 waiver. Produces, beside the run's
outputs, a grouped-summary JSON and grouping raster per grouping:

- ``coverage_split``: cells at or above a coverage fraction versus below it. A
  framework exercise showing how much of the risk domain a coverage rule
  would exclude. Not a soil band.
- ``awc_terciles``: AWC storage capacity split at terciles of the risk-valid
  domain. Illustrative bands, cut by this script, not the B25a bands that
  Karen Holmes and Dennis van Gool are yet to settle.

The descriptive text below is authored here, travels with the JSON, and is
printed verbatim by ``scripts/render_grouped_summary.py``. Change the
grouping and the text together.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List

import numpy as np
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.grouped_summary import GroupedSummary, save_grouped_summary, summarise_by_group
from src.soil_moisture_trio.slga.artifact import load_soil_context

LOGGER = logging.getLogger(__name__)
DEFAULT_BUNDLE = Path("data/processed/slga_awral/slga_awc_des_awral_swaz_0p05deg_v1")


def _read_run(run_nc: Path) -> Dict[str, np.ndarray]:
    with xr.open_dataset(run_nc) as ds:
        out = {
            "lats": ds.lat.values.copy(),
            "lons": ds.lon.values.copy(),
            "risk_map": ds.risk_level.values.copy(),
            "stress_index": ds["stress_index"].values.copy() if "stress_index" in ds else None,
            "model_metadata": json.loads(ds.attrs["risk_model_json"]) if "risk_model_json" in ds.attrs else {},
        }
    return out


def _config_from_run(model_metadata: Dict) -> ClassifierConfig:
    fields = {k: v for k, v in model_metadata.items() if k in ClassifierConfig.model_fields}
    return ClassifierConfig(**fields)


def coverage_split(run: Dict, coverage: np.ndarray, threshold: float, config: ClassifierConfig) -> tuple[GroupedSummary, Dict]:
    valid = run["risk_map"] >= 0
    gids = np.where(coverage >= threshold, 1, 0).astype(np.int8)
    gvalid = np.isfinite(coverage)
    summary = summarise_by_group(
        run["risk_map"], run["stress_index"], valid, gids, gvalid, config,
        grouping_name="coverage_split",
        group_labels={1: f"Soil data coverage at or above {threshold:g}", 0: f"Soil data coverage below {threshold:g}"},
        title=f"Soil-data coverage: at or above {threshold:g} versus below",
        description=(
            "Each grid cell in the soil artifact carries a coverage fraction: the share of the cell's area for which "
            "the SLGA source rasters had valid data. This grouping splits the risk domain at a coverage of "
            f"{threshold:g} to show how many cells a minimum-coverage rule at that level would keep and exclude, and "
            "whether the excluded cells differ in drought risk from the rest. It is a check on the coverage rule, not a soil classification."
        ),
        notes=[
            "The minimum acceptable coverage is an open review question (B25a). The value used here is a working choice, not an approved rule.",
            "Cells below the threshold sit on the coastal fringe of the zone. Any difference in their risk mix reflects location as much as data quality.",
        ],
    )
    return summary, {"lats": run["lats"], "lons": run["lons"], "group_ids": gids, "group_valid_mask": gvalid, "risk_valid_mask": valid}


def awc_terciles(run: Dict, awc: np.ndarray, coverage: np.ndarray, threshold: float, config: ClassifierConfig) -> tuple[GroupedSummary, Dict]:
    valid = run["risk_map"] >= 0
    usable = np.isfinite(awc) & (coverage >= threshold)
    q1, q2 = np.quantile(awc[valid & usable], [1 / 3, 2 / 3])
    gids = np.full(awc.shape, -1, dtype=np.int8)
    gids[np.isfinite(awc)] = np.digitize(awc[np.isfinite(awc)], [q1, q2])
    labels = {0: f"Lower AWC (below {q1:.0f} mm)", 1: f"Middle AWC ({q1:.0f} to {q2:.0f} mm)", 2: f"Higher AWC ({q2:.0f} mm and above)"}
    summary = summarise_by_group(
        run["risk_map"], run["stress_index"], valid, gids, usable, config,
        grouping_name="awc_terciles",
        group_labels=labels,
        title="Available water capacity of the soil profile, in three equal-count bands",
        description=(
            "Available water capacity (AWC) is the amount of water, in millimetres, that the soil profile can hold for plant use, "
            "taken here from the SLGA-derived review artifact. The risk-valid cells are split into three groups of equal size at the "
            f"tercile values of AWC ({q1:.0f} mm and {q2:.0f} mm). For each group the table and bar show how the drought-risk "
            "categories and the stress index are distributed. The per-cell risk itself is unchanged: this only regroups it."
        ),
        notes=[
            "The three bands are cut at terciles for illustration. They are not the soil bands for the product, which await the Karen Holmes and Dennis van Gool review (B25a).",
            "AWC is not evenly spread across the zone. A difference between bands may reflect where those soils sit (and the rainfall they received) rather than how the soil holds water. This has not been separated.",
            f"Cells with soil-data coverage below {threshold:g} are reported as uncovered rather than assigned to a band.",
        ],
    )
    return summary, {"lats": run["lats"], "lons": run["lons"], "group_ids": gids, "group_valid_mask": usable, "risk_valid_mask": valid}


def run_groupings(run_nc: Path, bundle: Path, coverage_threshold: float = 0.5) -> List[Dict[str, Path]]:
    run = _read_run(run_nc)
    config = _config_from_run(run["model_metadata"])
    soil = load_soil_context(bundle, run["lats"], run["lons"])
    coverage = soil["source_coverage_fraction"].isel(storage_case=0).values
    awc = soil["awc_storage_capacity_mm"].isel(storage_case=0).values
    base = run_nc.with_suffix("")
    written = []
    for summary, grouping in (
        coverage_split(run, coverage, coverage_threshold, config),
        awc_terciles(run, awc, coverage, coverage_threshold, config),
    ):
        if not summary.reconciled:
            raise RuntimeError(f"{summary.grouping_name}: groups plus uncovered do not reconcile to the risk-valid domain")
        paths = save_grouped_summary(summary, base, grouping)
        LOGGER.info("%s: %s", summary.grouping_name, paths["json"])
        written.append(paths)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Group a finished SWAZ risk run by SLGA soil context (review input only).")
    parser.add_argument("--run-netcdf", required=True, type=Path, help="Risk run NetCDF written by main.py")
    parser.add_argument("--bundle", default=DEFAULT_BUNDLE, type=Path, help="SWAZ review bundle directory")
    parser.add_argument("--coverage-threshold", default=0.5, type=float, help="Working minimum soil-data coverage fraction")
    args = parser.parse_args()
    for paths in run_groupings(args.run_netcdf, args.bundle, args.coverage_threshold):
        print(paths["json"])


if __name__ == "__main__":
    main()
