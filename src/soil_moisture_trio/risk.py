import json
from enum import IntEnum
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import numpy as np
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig


# ---------------------------------------------------------------------
# Risk Levels
# ---------------------------------------------------------------------
class RiskLevel(IntEnum):
    LOW = 0
    WATCH = 1
    ALERT = 2
    CRITICAL = 3


RISK_LABELS = {
    RiskLevel.LOW: "Low",
    RiskLevel.WATCH: "Watch",
    RiskLevel.ALERT: "Alert",
    RiskLevel.CRITICAL: "Critical",
}

RISK_COLORS = {
    RiskLevel.LOW: "#2b83ba",     # Blue - Wet/Low Risk
    RiskLevel.WATCH: "#c7e9b4",   # Green - Early drying
    RiskLevel.ALERT: "#fdae61",   # Orange - Moderate stress
    RiskLevel.CRITICAL: "#d7191c" # Red - Severe stress
}


# ---------------------------------------------------------------------
# Validation Helper
# ---------------------------------------------------------------------
def _validate_shapes(data_grids: Dict[str, np.ndarray], valid_mask: np.ndarray) -> None:
    """Ensure all required grids share the same shape as the valid mask."""
    required = ['soil_moisture', 'temperature', 'vpd']
    base_shape = valid_mask.shape
    for key in required:
        if data_grids[key].shape != base_shape:
            raise ValueError(f"{key} grid shape {data_grids[key].shape} does not match valid_mask shape {base_shape}.")


# ---------------------------------------------------------------------
# Main Risk Calculation (Physics-informed dryness index)
# ---------------------------------------------------------------------
def _compute_risk_map(
    data_grids: Dict[str, np.ndarray],
    valid_mask: np.ndarray,
    config: ClassifierConfig
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute risk map using a physically-based dryness–stress index that combines:
      - soil moisture deficit (percentile rank below moisture_threshold)
      - temperature stress
      - vapour pressure deficit stress

    The stress index (0–1) uses the validated weights and category thresholds
    from ClassifierConfig.

    Args:
        valid_mask: boolean array marking land/data cells to include (False = ocean/NaN).
    """
    soil_moisture = data_grids['soil_moisture']
    temperature = data_grids['temperature']
    vpd = data_grids['vpd']

    risk_map = np.full(soil_moisture.shape, -1, dtype=np.int8)
    if not valid_mask.any():
        # also return a stress_index filled with NaNs when no valid cells
        stress_index = np.full(soil_moisture.shape, np.nan, dtype=float)
        return risk_map, stress_index

    # --- Compute continuous stress components ---
    dryness = np.clip((config.moisture_threshold - soil_moisture) / config.moisture_threshold, 0, 1)
    temp_factor = np.clip(temperature / config.critical_temp_threshold, 0, 1)
    vpd_factor = np.clip(vpd / config.critical_vpd_threshold, 0, 1)

    # Weighted composite stress index (0–1)
    stress_index = (
        (config.dryness_weight * dryness)
        + (config.vpd_weight * vpd_factor)
        + (config.temperature_weight * temp_factor)
    )
    stress_index = np.asarray(stress_index, dtype=float)
    stress_index[~valid_mask] = np.nan

    # --- Assign categorical risk levels ---
    risk_map[valid_mask] = RiskLevel.LOW
    critical_mask = valid_mask & (stress_index >= config.critical_risk_threshold)
    alert_mask = valid_mask & ~critical_mask & (stress_index >= config.alert_risk_threshold)
    watch_mask = valid_mask & ~alert_mask & ~critical_mask & (stress_index >= config.watch_risk_threshold)

    risk_map[watch_mask] = RiskLevel.WATCH
    risk_map[alert_mask] = RiskLevel.ALERT
    risk_map[critical_mask] = RiskLevel.CRITICAL

    return risk_map, stress_index


# ---------------------------------------------------------------------
# Summary and Output
# ---------------------------------------------------------------------
def assess_risk_levels(
    data_grids: Dict[str, np.ndarray],
    valid_mask: np.ndarray,
    config: ClassifierConfig
) -> Tuple[np.ndarray, Dict[str, Dict[str, float]], np.ndarray]:
    """
    Derive a categorical risk layer from soil moisture, temperature, and VPD using
    a physically grounded dryness–stress model.

    Args:
        valid_mask: boolean array (lat, lon) — True for land/data cells, False for ocean/NaN.

    Returns:
        risk_map: np.ndarray of RiskLevel values per grid cell
        summary: Dict summarising cell counts and proportions per level
        stress_index: continuous weighted stress array (NaN for invalid cells). It is within 0–1 when inputs and normalisation references follow the documented data contract.
    """
    _validate_shapes(data_grids, valid_mask)
    risk_map, stress_index = _compute_risk_map(data_grids, valid_mask, config)

    total = risk_map.size
    result_valid = risk_map >= 0
    total_valid = int(np.sum(result_valid))
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

    return risk_map, summary, stress_index


# ---------------------------------------------------------------------
# NetCDF + JSON Persistence
# ---------------------------------------------------------------------
def save_risk_outputs(
    risk_map: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    summary: Dict[str, Dict[str, float]],
    base_path: Union[str, Path] = "risk_layer",
    time_metadata: Optional[Dict[str, str]] = None,
    model_metadata: Optional[Dict[str, float]] = None,
) -> Dict[str, Path]:
    """
    Persist the risk map to NetCDF and the summary to JSON.

    Args:
        risk_map: 2D array of RiskLevel values
        lats/lons: coordinate arrays
        summary: Dict from assess_risk_levels
        base_path: Output file prefix
        time_metadata: Optional metadata (start/end ISO datetimes)
        model_metadata: Optional stress-model weights and thresholds

    Returns:
        dict with keys 'netcdf' and 'summary' pointing to written files
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
        {"risk_level": (("lat", "lon"), risk_map.astype(np.int8))},
        coords={"lat": lats, "lon": lons},
    )
    ds.attrs["risk_summary_json"] = json.dumps(summary)
    if time_metadata:
        ds.attrs.update(time_metadata)
    if model_metadata:
        ds.attrs["risk_model_json"] = json.dumps(model_metadata)
    ds.to_netcdf(nc_path)

    with summary_path.open("w", encoding="utf-8") as fp:
        payload = {
            "summary": summary,
            "time_metadata": time_metadata or {},
            "model_metadata": model_metadata or {},
        }
        json.dump(payload, fp, indent=2)

    return {"netcdf": nc_path, "summary": summary_path}


__all__ = [
    "RiskLevel",
    "RISK_LABELS",
    "RISK_COLORS",
    "assess_risk_levels",
    "save_risk_outputs",
]
