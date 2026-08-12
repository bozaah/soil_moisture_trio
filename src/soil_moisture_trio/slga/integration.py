from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from src.soil_moisture_trio.slga.cog import RasterWindowData, assert_common_window_grid

DEPTH_CODES = ("000_005", "005_015", "015_030", "030_060", "060_100")
LAYER_TOPS_MM = np.array([0.0, 50.0, 150.0, 300.0, 600.0], dtype=np.float64)
LAYER_BOTTOMS_MM = np.array([50.0, 150.0, 300.0, 600.0, 1000.0], dtype=np.float64)
ORDERING_ABS_TOLERANCE = 1e-9

STORAGE_CASE_COMPONENTS: dict[str, tuple[str, str]] = {
    "ev": ("EV", "EV"),
    "awc05_des_ev": ("05", "EV"),
    "awc95_des_ev": ("95", "EV"),
    "awc_ev_des10": ("EV", "10"),
    "awc_ev_des90": ("EV", "90"),
    "mixed_lower_awc05_des10": ("05", "10"),
    "mixed_upper_awc95_des90": ("95", "90"),
}


class IntegrationError(ValueError):
    """Raised when native-grid source arrays violate the integration contract."""


@dataclass(frozen=True)
class StorageIntegration:
    storage_mm: Mapping[str, np.ndarray]
    represented_depth_mm: Mapping[str, np.ndarray]
    mixed_uncertainty_width_mm: np.ndarray


def integrate_source_windows(
    windows: Mapping[str, RasterWindowData],
) -> StorageIntegration:
    """Validate and organise the exact 18 approved windows before integration."""
    assert_common_window_grid(windows)
    awc: dict[str, dict[str, np.ndarray]] = {
        component: {} for component in ("EV", "05", "95")
    }
    des: dict[str, np.ndarray] = {}
    observed: set[tuple[str, str, str]] = set()
    for product_id, window in windows.items():
        if product_id != window.layer.product_id:
            raise IntegrationError(
                f"Window key does not match layer identity: {product_id}."
            )
        key = (
            window.layer.property_code,
            window.layer.depth_code,
            window.layer.component,
        )
        if key in observed:
            raise IntegrationError(f"Duplicate source window component: {key}.")
        observed.add(key)
        if window.layer.property_code == "AWC":
            awc[window.layer.component][window.layer.depth_code] = window.values
        elif window.layer.property_code == "DES":
            des[window.layer.component] = window.values
        else:
            raise IntegrationError(
                f"Unsupported source property: {window.layer.property_code}."
            )
    return integrate_storage(awc, des)


def integrate_storage(
    awc_percent: Mapping[str, Mapping[str, np.ndarray]],
    des_metres: Mapping[str, np.ndarray],
) -> StorageIntegration:
    """Calculate the seven DES-capped storage cases on one common native grid."""
    awc = _validate_awc_inputs(awc_percent)
    des = _validate_des_inputs(
        des_metres, next(iter(awc.values()))[DEPTH_CODES[0]].shape
    )
    _validate_component_order(awc, des)

    represented_depth = {
        component: np.minimum(values * 1000.0, 1000.0)
        for component, values in des.items()
    }
    storage = {
        case: _integrate_one_case(awc[awc_component], des[des_component])
        for case, (awc_component, des_component) in STORAGE_CASE_COMPONENTS.items()
    }
    _validate_derived_order(storage)
    mixed_width = (
        storage["mixed_upper_awc95_des90"] - storage["mixed_lower_awc05_des10"]
    )
    both_finite = np.isfinite(storage["mixed_upper_awc95_des90"]) & np.isfinite(
        storage["mixed_lower_awc05_des10"]
    )
    mixed_width[~both_finite] = np.nan
    if np.any(mixed_width[both_finite] < -ORDERING_ABS_TOLERANCE):
        raise IntegrationError("Mixed uncertainty width is negative.")
    mixed_width[both_finite & (mixed_width < 0)] = 0.0

    return StorageIntegration(
        storage_mm=storage,
        represented_depth_mm=represented_depth,
        mixed_uncertainty_width_mm=mixed_width,
    )


def _integrate_one_case(
    awc_by_depth: Mapping[str, np.ndarray],
    des: np.ndarray,
) -> np.ndarray:
    represented_depth_mm = np.minimum(des * 1000.0, 1000.0)
    valid = np.isfinite(des)
    result = np.zeros(des.shape, dtype=np.float64)

    for index, depth_code in enumerate(DEPTH_CODES):
        thickness = np.clip(
            represented_depth_mm - LAYER_TOPS_MM[index],
            0.0,
            LAYER_BOTTOMS_MM[index] - LAYER_TOPS_MM[index],
        )
        values = awc_by_depth[depth_code]
        required = thickness > 0.0
        available = np.isfinite(values)
        valid &= ~required | available
        contribution_mask = required & available
        result[contribution_mask] += (
            values[contribution_mask] / 100.0 * thickness[contribution_mask]
        )

    result[~valid] = np.nan
    return result


def _validate_awc_inputs(
    awc_percent: Mapping[str, Mapping[str, np.ndarray]],
) -> dict[str, dict[str, np.ndarray]]:
    if set(awc_percent) != {"EV", "05", "95"}:
        raise IntegrationError("AWC components must be exactly EV, 05, and 95.")
    validated: dict[str, dict[str, np.ndarray]] = {}
    expected_shape: tuple[int, ...] | None = None
    for component in ("EV", "05", "95"):
        by_depth = awc_percent[component]
        if set(by_depth) != set(DEPTH_CODES):
            raise IntegrationError(
                f"AWC {component} depths must be exactly {list(DEPTH_CODES)}."
            )
        validated[component] = {}
        for depth_code in DEPTH_CODES:
            values = _validate_values(
                by_depth[depth_code], f"AWC {component} {depth_code}"
            )
            if expected_shape is None:
                expected_shape = values.shape
                if len(expected_shape) != 2:
                    raise IntegrationError("Native AWC arrays must be two-dimensional.")
            elif values.shape != expected_shape:
                raise IntegrationError("All native AWC arrays must share one shape.")
            validated[component][depth_code] = values
    return validated


def _validate_des_inputs(
    des_metres: Mapping[str, np.ndarray],
    expected_shape: tuple[int, ...],
) -> dict[str, np.ndarray]:
    if set(des_metres) != {"EV", "10", "90"}:
        raise IntegrationError("DES components must be exactly EV, 10, and 90.")
    validated: dict[str, np.ndarray] = {}
    for component in ("EV", "10", "90"):
        values = _validate_values(des_metres[component], f"DES {component}")
        if values.shape != expected_shape:
            raise IntegrationError(
                "All native DES and AWC arrays must share one shape."
            )
        validated[component] = values
    return validated


def _validate_values(values: np.ndarray, label: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if np.any(np.isinf(array)):
        raise IntegrationError(f"{label} contains an infinite value.")
    if np.any(array[np.isfinite(array)] < 0):
        raise IntegrationError(f"{label} contains a negative valid value.")
    return array


def _validate_component_order(
    awc: Mapping[str, Mapping[str, np.ndarray]],
    des: Mapping[str, np.ndarray],
) -> None:
    for depth_code in DEPTH_CODES:
        _require_ordered(
            awc["05"][depth_code],
            awc["EV"][depth_code],
            awc["95"][depth_code],
            f"AWC {depth_code}",
        )
    _require_ordered(des["10"], des["EV"], des["90"], "DES")


def _validate_derived_order(storage: Mapping[str, np.ndarray]) -> None:
    _require_ordered(
        storage["mixed_lower_awc05_des10"],
        storage["ev"],
        storage["mixed_upper_awc95_des90"],
        "derived mixed storage",
    )
    _require_ordered(
        storage["awc05_des_ev"],
        storage["ev"],
        storage["awc95_des_ev"],
        "derived AWC-only storage",
    )
    _require_ordered(
        storage["awc_ev_des10"],
        storage["ev"],
        storage["awc_ev_des90"],
        "derived DES-only storage",
    )


def _require_ordered(
    lower: np.ndarray,
    expected: np.ndarray,
    upper: np.ndarray,
    label: str,
) -> None:
    comparable = np.isfinite(lower) & np.isfinite(expected) & np.isfinite(upper)
    invalid = comparable & (
        (lower > expected + ORDERING_ABS_TOLERANCE)
        | (expected > upper + ORDERING_ABS_TOLERANCE)
    )
    if np.any(invalid):
        raise IntegrationError(f"{label} violates lower <= EV <= upper ordering.")
