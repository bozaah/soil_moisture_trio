from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import xarray as xr

from src.soil_moisture_trio.slga.harmonise import (
    AWRA_SPACING_DEGREES,
    COORDINATE_ABS_TOLERANCE,
    HarmonisationError,
    coordinate_edges,
)

GRID_CONTRACT_SCHEMA_VERSION = 1
DEFAULT_GRID_CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "manifests" / "awral_v7_grid_source_v1.json"
)


class CanonicalGridError(ValueError):
    """Raised when the canonical AWRA-L input violates its pinned contract."""


@dataclass(frozen=True)
class CanonicalGrid:
    latitude: np.ndarray
    longitude: np.ndarray
    contract_id: str
    contract_sha256: str
    source_filename: str
    source_size_bytes: int
    source_sha256: str
    source_url: str
    model_version: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_grid_contract(path: Path = DEFAULT_GRID_CONTRACT_PATH) -> Mapping[str, Any]:
    contract_path = Path(path)
    try:
        raw = contract_path.read_bytes()
        contract = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalGridError(
            f"Cannot read canonical-grid contract {contract_path}."
        ) from exc
    if not isinstance(contract, dict):
        raise CanonicalGridError("Canonical-grid contract must be a JSON object.")
    if contract.get("grid_contract_schema_version") != GRID_CONTRACT_SCHEMA_VERSION:
        raise CanonicalGridError("Unsupported canonical-grid contract schema version.")
    if not isinstance(contract.get("grid_contract_id"), str):
        raise CanonicalGridError("Canonical-grid contract ID is missing or malformed.")
    _mapping(contract, "source")
    _mapping(contract, "coordinate_contract")
    return contract


def select_exact_coordinate_range(
    coordinates: np.ndarray,
    first: float,
    last: float,
    axis_name: str,
) -> np.ndarray:
    """Select inclusive source-ordered endpoints without rounding or regeneration."""
    values = np.asarray(coordinates, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise CanonicalGridError(
            f"Canonical {axis_name} coordinates must be a finite one-dimensional array."
        )
    first_matches = np.flatnonzero(values == float(first))
    last_matches = np.flatnonzero(values == float(last))
    if first_matches.size != 1 or last_matches.size != 1:
        raise CanonicalGridError(
            f"Requested {axis_name} range endpoints are not exact canonical coordinates."
        )
    start = int(first_matches[0])
    stop = int(last_matches[0]) + 1
    if start >= stop:
        raise CanonicalGridError(
            f"Requested {axis_name} range does not follow canonical orientation."
        )
    selected = values[start:stop].copy()
    try:
        coordinate_edges(selected, axis_name)
    except HarmonisationError as exc:
        raise CanonicalGridError(str(exc)) from exc
    return selected


def load_canonical_grid(
    source_path: Path,
    contract_path: Path = DEFAULT_GRID_CONTRACT_PATH,
) -> CanonicalGrid:
    """Verify an explicit local AWRA-L NetCDF and return its exact coordinates."""
    source_file = Path(source_path)
    contract_file = Path(contract_path)
    contract = load_grid_contract(contract_file)
    source = _mapping(contract, "source")
    coordinate_contract = _mapping(contract, "coordinate_contract")

    expected_filename = _string(source, "filename")
    if source_file.name != expected_filename:
        raise CanonicalGridError(
            f"Canonical-grid input must be named {expected_filename!r}."
        )
    try:
        actual_size = source_file.stat().st_size
    except OSError as exc:
        raise CanonicalGridError(
            f"Canonical-grid input is missing or unreadable: {source_file}."
        ) from exc
    expected_size = _integer(source, "size_bytes")
    if actual_size != expected_size:
        raise CanonicalGridError(
            f"Canonical-grid input size mismatch: expected {expected_size}, got {actual_size}."
        )
    actual_sha256 = sha256_file(source_file)
    expected_sha256 = _sha256(source, "sha256")
    if actual_sha256 != expected_sha256:
        raise CanonicalGridError("Canonical-grid input SHA-256 mismatch.")

    _validate_spacing_contract(coordinate_contract)
    try:
        with xr.open_dataset(
            source_file,
            decode_times=False,
            mask_and_scale=False,
            cache=False,
        ) as dataset:
            _validate_dataset_schema(dataset, source)
            latitude = _validated_coordinate(dataset, coordinate_contract, "latitude")
            longitude = _validated_coordinate(dataset, coordinate_contract, "longitude")
    except CanonicalGridError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise CanonicalGridError(
            "Canonical-grid input is not a readable contract-compatible NetCDF."
        ) from exc

    return CanonicalGrid(
        latitude=latitude,
        longitude=longitude,
        contract_id=_string(contract, "grid_contract_id"),
        contract_sha256=sha256_file(contract_file),
        source_filename=expected_filename,
        source_size_bytes=actual_size,
        source_sha256=actual_sha256,
        source_url=_string(source, "download_url"),
        model_version=_string(source, "model_version"),
    )


def _validate_dataset_schema(dataset: xr.Dataset, source: Mapping[str, Any]) -> None:
    expected_dimensions = _mapping(source, "dimensions")
    for name, length in expected_dimensions.items():
        if not isinstance(name, str) or not isinstance(length, int):
            raise CanonicalGridError("Canonical-grid dimension contract is malformed.")
        if dataset.sizes.get(name) != length:
            raise CanonicalGridError(
                f"Canonical-grid dimension {name!r} does not match the contract."
            )

    expected_attributes = _mapping(source, "global_attributes")
    for name, value in expected_attributes.items():
        if dataset.attrs.get(name) != value:
            raise CanonicalGridError(
                f"Canonical-grid global attribute {name!r} does not match the contract."
            )

    variable_contract = _mapping(source, "data_variable")
    variable_name = _string(variable_contract, "name")
    if variable_name not in dataset.data_vars:
        raise CanonicalGridError(
            f"Canonical-grid source variable {variable_name!r} is missing."
        )
    variable = dataset[variable_name]
    expected_variable_dimensions = _string_sequence(variable_contract, "dimensions")
    if variable.dims != expected_variable_dimensions:
        raise CanonicalGridError("Canonical-grid source-variable dimensions mismatch.")
    expected_dtype = _dtype(variable_contract, "dtype")
    if variable.dtype != expected_dtype:
        raise CanonicalGridError("Canonical-grid source-variable dtype mismatch.")


def _validated_coordinate(
    dataset: xr.Dataset,
    coordinate_contract: Mapping[str, Any],
    axis_name: str,
) -> np.ndarray:
    specification = _mapping(coordinate_contract, axis_name)
    coordinate_name = axis_name
    if coordinate_name not in dataset.coords:
        raise CanonicalGridError(
            f"Canonical-grid coordinate {coordinate_name!r} is missing."
        )
    coordinate = dataset.coords[coordinate_name]
    dimension = _string(specification, "dimension")
    if coordinate.dims != (dimension,):
        raise CanonicalGridError(
            f"Canonical-grid {axis_name} coordinate dimensions mismatch."
        )
    expected_dtype = _dtype(specification, "dtype")
    if coordinate.dtype != expected_dtype:
        raise CanonicalGridError(f"Canonical-grid {axis_name} dtype mismatch.")

    expected_attributes = _mapping(specification, "attributes")
    for name, value in expected_attributes.items():
        if coordinate.attrs.get(name) != value:
            raise CanonicalGridError(
                f"Canonical-grid {axis_name} attribute {name!r} mismatch."
            )

    values = np.asarray(coordinate.values, dtype=np.float64)
    if values.size != _integer(specification, "length"):
        raise CanonicalGridError(f"Canonical-grid {axis_name} length mismatch.")
    if values[0] != _number(specification, "first") or values[-1] != _number(
        specification, "last"
    ):
        raise CanonicalGridError(f"Canonical-grid {axis_name} endpoints mismatch.")

    orientation = _string(specification, "orientation")
    differences = np.diff(values)
    if orientation == "ascending":
        orientation_valid = np.all(differences > 0)
    elif orientation == "descending":
        orientation_valid = np.all(differences < 0)
    else:
        raise CanonicalGridError(
            f"Canonical-grid {axis_name} orientation contract is malformed."
        )
    if not orientation_valid:
        raise CanonicalGridError(f"Canonical-grid {axis_name} orientation mismatch.")

    try:
        coordinate_edges(values, axis_name)
    except HarmonisationError as exc:
        raise CanonicalGridError(str(exc)) from exc

    raw_hash = hashlib.sha256(
        np.asarray(values, dtype="<f8").tobytes(order="C")
    ).hexdigest()
    if raw_hash != _sha256(specification, "raw_float64_little_endian_sha256"):
        raise CanonicalGridError(f"Canonical-grid {axis_name} value hash mismatch.")
    return values.copy()


def _validate_spacing_contract(contract: Mapping[str, Any]) -> None:
    spacing = _number(contract, "nominal_spacing_degrees")
    tolerance = _number(contract, "spacing_absolute_tolerance_degrees")
    if not math.isclose(spacing, AWRA_SPACING_DEGREES, rel_tol=0.0, abs_tol=0.0):
        raise CanonicalGridError("Canonical-grid nominal spacing contract mismatch.")
    if not math.isclose(tolerance, COORDINATE_ABS_TOLERANCE, rel_tol=0.0, abs_tol=0.0):
        raise CanonicalGridError("Canonical-grid spacing tolerance contract mismatch.")


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise CanonicalGridError(f"Canonical-grid contract field {key!r} is malformed.")
    return value


def _string(parent: Mapping[str, Any], key: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value:
        raise CanonicalGridError(f"Canonical-grid contract field {key!r} is malformed.")
    return value


def _integer(parent: Mapping[str, Any], key: str) -> int:
    value = parent.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CanonicalGridError(f"Canonical-grid contract field {key!r} is malformed.")
    return value


def _number(parent: Mapping[str, Any], key: str) -> float:
    value = parent.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise CanonicalGridError(f"Canonical-grid contract field {key!r} is malformed.")
    result = float(value)
    if not math.isfinite(result):
        raise CanonicalGridError(f"Canonical-grid contract field {key!r} is malformed.")
    return result


def _sha256(parent: Mapping[str, Any], key: str) -> str:
    value = _string(parent, key)
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise CanonicalGridError(f"Canonical-grid contract field {key!r} is malformed.")
    return value


def _dtype(parent: Mapping[str, Any], key: str) -> np.dtype[Any]:
    try:
        return np.dtype(_string(parent, key))
    except TypeError as exc:
        raise CanonicalGridError(
            f"Canonical-grid contract field {key!r} is malformed."
        ) from exc


def _string_sequence(parent: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = parent.get(key)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise CanonicalGridError(f"Canonical-grid contract field {key!r} is malformed.")
    return tuple(value)
