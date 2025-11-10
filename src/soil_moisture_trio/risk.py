import json
from enum import IntEnum
from pathlib import Path
from typing import Dict, Tuple, Union

import numpy as np
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig


class RiskLevel(IntEnum):
    LOW = 0
    WATCH = 1
    ELEVATED = 2
    CRITICAL = 3


RISK_LABELS = {
    RiskLevel.LOW: "Wet / Low Risk",
    RiskLevel.WATCH: "Watch (approaching dry thresholds)",
    RiskLevel.ELEVATED: "Elevated Dry Risk",
    RiskLevel.CRITICAL: "Critical Dry Risk",
}

RISK_COLORS = {
    RiskLevel.LOW: "#2b83ba",
    RiskLevel.WATCH: "#abdda4",
    RiskLevel.ELEVATED: "#fdae61",
    RiskLevel.CRITICAL: "#d7191c",
}


def _validate_shapes(data_grids: Dict[str, np.ndarray], classification_grid: np.ndarray) -> None:
    """Ensure all required grids share the same shape."""
    required = ['soil_moisture', 'temperature', 'vpd']
    base_shape = classification_grid.shape
    for key in required:
        if data_grids[key].shape != base_shape:
            raise ValueError(f"{key} grid shape {data_grids[key].shape} does not match classification grid {base_shape}.")


def _compute_risk_map(
    data_grids: Dict[str, np.ndarray],
    classification_grid: np.ndarray,
    config: ClassifierConfig
) -> np.ndarray:
    soil_moisture = data_grids['soil_moisture']
    temperature = data_grids['temperature']
    vpd = data_grids['vpd']

    risk_map = np.full(soil_moisture.shape, -1, dtype=np.int8)
    valid_mask = classification_grid >= 0
    if not valid_mask.any():
        return risk_map
    risk_map[valid_mask] = RiskLevel.LOW

    dry_mask = valid_mask & (classification_grid == 0)
    critical_mask = (
        valid_mask &
        (soil_moisture <= config.severe_moisture_threshold) &
        ((temperature >= config.critical_temp_threshold) | (vpd >= config.critical_vpd_threshold))
    )
    elevated_mask = dry_mask & ~critical_mask
    watch_mask = (
        (~dry_mask) & valid_mask &
        (
            (soil_moisture <= config.moisture_threshold + config.watch_margin) |
            (temperature >= config.temp_threshold) |
            (vpd >= config.vpd_threshold)
        )
    )

    risk_map[watch_mask] = RiskLevel.WATCH
    risk_map[elevated_mask] = RiskLevel.ELEVATED
    risk_map[critical_mask] = RiskLevel.CRITICAL

    return risk_map


def assess_risk_levels(
    data_grids: Dict[str, np.ndarray],
    classification_grid: np.ndarray,
    config: ClassifierConfig
) -> Tuple[np.ndarray, Dict[str, Dict[str, float]]]:
    """
    Derive a categorical risk layer from the classifier output and raw grids.

    Returns:
        risk_map: np.ndarray of RiskLevel values per cell.
        summary: Dict keyed by risk level name with counts & percentages.
    """
    _validate_shapes(data_grids, classification_grid)
    risk_map = _compute_risk_map(data_grids, classification_grid, config)

    total = risk_map.size
    valid_mask = risk_map >= 0
    total_valid = int(np.sum(valid_mask))
    invalid_count = total - total_valid
    summary: Dict[str, Dict[str, float]] = {}
    for level in RiskLevel:
        count = int(np.sum(risk_map == level))
        summary[level.name.lower()] = {
            "count": count,
            "percentage": (count / total_valid) if total_valid else 0.0,
            "label": RISK_LABELS[level],
        }

    summary["invalid"] = {
        "count": invalid_count,
        "percentage": (invalid_count / total) if total else 0.0,
        "label": "No Data",
    }
    summary["valid_cells"] = {
        "count": total_valid,
        "percentage": (total_valid / total) if total else 0.0,
        "label": "Valid grid cells",
    }
    summary["total_cells"] = {"count": total, "percentage": 1.0, "label": "Total grid cells"}
    return risk_map, summary


def save_risk_outputs(
    risk_map: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    summary: Dict[str, Dict[str, float]],
    base_path: Union[str, Path] = "risk_layer",
) -> Dict[str, Path]:
    """
    Persist the risk map to NetCDF and the summary to JSON.

    Args:
        risk_map: 2D array of RiskLevel values.
        lats/lons: 1D coordinate arrays aligned with risk_map.
        summary: Dict produced by assess_risk_levels.
        base_path: Prefix for output files; '.nc' and '_summary.json' will be appended if missing.

    Returns:
        dict with keys 'netcdf' and 'summary' pointing to the written file paths.
    """
    base_path = Path(base_path).expanduser()
    if base_path.suffix:
        nc_path = base_path
        summary_path = base_path.with_name(base_path.stem + "_summary.json")
    else:
        nc_path = base_path.with_suffix(".nc")
        summary_path = base_path.with_name(base_path.stem + "_summary.json")

    nc_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    ds = xr.Dataset(
        {
            "risk_level": (("lat", "lon"), risk_map.astype(np.int8)),
        },
        coords={"lat": lats, "lon": lons},
    )
    ds.attrs["risk_summary_json"] = json.dumps(summary)
    ds.to_netcdf(nc_path)

    with summary_path.open("w", encoding="utf-8") as fp:
        json.dump(summary, fp, indent=2)

    return {"netcdf": nc_path, "summary": summary_path}


__all__ = ["RiskLevel", "RISK_LABELS", "RISK_COLORS", "assess_risk_levels", "save_risk_outputs"]
