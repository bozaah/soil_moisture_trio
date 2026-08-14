from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import xarray as xr

from src.soil_moisture_trio.slga.grid import (
    DEFAULT_GRID_CONTRACT_PATH,
    CanonicalGrid,
    load_grid_contract,
    sha256_file,
)
from src.soil_moisture_trio.slga.harmonise import (
    HarmonisationError,
    coordinate_edges,
    require_exact_coordinate_subset,
)
from src.soil_moisture_trio.slga.integration import STORAGE_CASE_COMPONENTS

ARTIFACT_CONTRACT_VERSION = "b25b-slga-awral-prototype-v1"
ARTIFACT_VERSION = "v1"
STORAGE_CASES = tuple(STORAGE_CASE_COMPONENTS)
DEFAULT_SOURCE_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "manifests" / "slga_awc_des_sources_v1.json"
)
REQUIRED_DATA_VARIABLES = {
    "awc_storage_capacity_mm",
    "mapped_prediction_sd_mm",
    "valid_source_area_m2",
    "source_coverage_fraction",
    "full_cell_area_m2",
    "mixed_uncertainty_width_mm",
}
SCIENTIFIC_LIMITATIONS = (
    "Static modelled SLGA storage-capacity context, not current soil water, observed "
    "field PAWC, effective crop rooting depth, distance from wilting, or independent "
    "validation of AWRA-L. Mixed lower/upper cases are not a confidence interval."
)


class SoilArtifactError(ValueError):
    """Raised when a soil artifact or its sidecar violates the v1 contract."""


@dataclass(frozen=True)
class SoilArtifactData:
    latitude: np.ndarray
    longitude: np.ndarray
    storage_mm: Mapping[str, np.ndarray]
    mapped_prediction_sd_mm: Mapping[str, np.ndarray]
    valid_source_area_m2: Mapping[str, np.ndarray]
    source_coverage_fraction: Mapping[str, np.ndarray]
    full_cell_area_m2: np.ndarray
    mixed_uncertainty_width_mm: np.ndarray


@dataclass(frozen=True)
class ArtifactBuildMetadata:
    canonical_grid: CanonicalGrid
    creation_timestamp_utc: str
    builder_version: str
    builder_commit: str
    source_retrieval_timestamps_utc: Mapping[str, str]


def write_soil_artifact(
    artifact_path: Path,
    sidecar_path: Path,
    data: SoilArtifactData,
    metadata: ArtifactBuildMetadata,
    *,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
    grid_contract_path: Path = DEFAULT_GRID_CONTRACT_PATH,
) -> Mapping[str, Any]:
    """Atomically write and close-validate the provisional v1 artifact and sidecar."""
    artifact = Path(artifact_path)
    sidecar = Path(sidecar_path)
    if artifact.resolve() == sidecar.resolve():
        raise SoilArtifactError("Artifact and sidecar paths must differ.")
    if artifact.suffix != ".nc" or sidecar.suffix != ".json":
        raise SoilArtifactError("Artifact must be .nc and sidecar must be .json.")

    source_manifest_file = Path(source_manifest_path)
    grid_contract_file = Path(grid_contract_path)
    source_manifest, source_manifest_bytes = _load_json_object(source_manifest_file)
    grid_contract, grid_contract_bytes = _load_json_object(grid_contract_file)
    source_manifest_id = _required_string(source_manifest, "manifest_id")
    grid_contract_id = _required_string(grid_contract, "grid_contract_id")
    if grid_contract_id != metadata.canonical_grid.contract_id:
        raise SoilArtifactError("Canonical-grid contract identity mismatch.")
    grid_contract_sha256 = _sha256_bytes(grid_contract_bytes)
    if grid_contract_sha256 != metadata.canonical_grid.contract_sha256:
        raise SoilArtifactError("Canonical-grid contract SHA-256 mismatch.")

    retrieval_timestamps = dict(metadata.source_retrieval_timestamps_utc)
    layer_ids = _source_layer_ids(source_manifest)
    if set(retrieval_timestamps) != set(layer_ids):
        raise SoilArtifactError(
            "Source retrieval timestamps must match the source manifest layer IDs."
        )
    _validate_utc_timestamp(metadata.creation_timestamp_utc, "creation timestamp")
    for product_id, timestamp in retrieval_timestamps.items():
        _validate_utc_timestamp(timestamp, f"retrieval timestamp for {product_id}")

    dataset = _build_dataset(
        data,
        metadata,
        source_manifest,
        source_manifest_id,
        _sha256_bytes(source_manifest_bytes),
        grid_contract,
        grid_contract_id,
        grid_contract_sha256,
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    artifact_temp = _temporary_path(artifact)
    sidecar_temp = _temporary_path(sidecar)
    artifact_promoted = False
    sidecar_promoted = False
    try:
        dataset.to_netcdf(artifact_temp, engine="netcdf4", encoding=_encoding(data))
        dataset.close()
        _validate_artifact_schema(artifact_temp)
        artifact_size = artifact_temp.stat().st_size
        artifact_sha256 = sha256_file(artifact_temp)
        sidecar_document = {
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
            "artifact_filename": artifact.name,
            "artifact_sha256": artifact_sha256,
            "artifact_size_bytes": artifact_size,
            "artifact_version": ARTIFACT_VERSION,
            "builder_commit": metadata.builder_commit,
            "builder_version": metadata.builder_version,
            "canonical_grid_contract_id": grid_contract_id,
            "canonical_grid_contract_sha256": grid_contract_sha256,
            "canonical_grid_source_filename": metadata.canonical_grid.source_filename,
            "canonical_grid_source_sha256": metadata.canonical_grid.source_sha256,
            "canonical_grid_source_size_bytes": metadata.canonical_grid.source_size_bytes,
            "creation_timestamp_utc": metadata.creation_timestamp_utc,
            "source_manifest_id": source_manifest_id,
            "source_manifest_sha256": _sha256_bytes(source_manifest_bytes),
            "source_retrieval_timestamps_utc": {
                key: retrieval_timestamps[key] for key in sorted(retrieval_timestamps)
            },
        }
        sidecar_temp.write_text(
            json.dumps(sidecar_document, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(artifact_temp, artifact)
        artifact_promoted = True
        os.replace(sidecar_temp, sidecar)
        sidecar_promoted = True
    except Exception:
        dataset.close()
        artifact_temp.unlink(missing_ok=True)
        sidecar_temp.unlink(missing_ok=True)
        if artifact_promoted:
            artifact.unlink(missing_ok=True)
        if sidecar_promoted:
            sidecar.unlink(missing_ok=True)
        raise
    return sidecar_document


def load_soil_artifact(
    artifact_path: Path,
    sidecar_path: Path,
    requested_latitude: np.ndarray,
    requested_longitude: np.ndarray,
    *,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
    grid_contract_path: Path = DEFAULT_GRID_CONTRACT_PATH,
) -> xr.Dataset:
    """Verify an approved artifact and return one exact contiguous in-memory subset."""
    artifact = Path(artifact_path)
    sidecar = Path(sidecar_path)
    if not artifact.is_file():
        raise SoilArtifactError(f"Approved soil artifact is missing: {artifact}.")
    if not sidecar.is_file():
        raise SoilArtifactError(
            f"Approved soil artifact sidecar is missing: {sidecar}."
        )
    sidecar_document, _sidecar_bytes = _load_json_object(sidecar)
    _validate_sidecar(
        sidecar_document,
        artifact,
        Path(source_manifest_path),
        Path(grid_contract_path),
    )
    _validate_artifact_schema(artifact)

    with xr.open_dataset(artifact, decode_times=False, mask_and_scale=True) as dataset:
        latitude = np.asarray(dataset.latitude.values, dtype=np.float64)
        longitude = np.asarray(dataset.longitude.values, dtype=np.float64)
        try:
            latitude_slice = require_exact_coordinate_subset(
                latitude, requested_latitude, "latitude"
            )
            longitude_slice = require_exact_coordinate_subset(
                longitude, requested_longitude, "longitude"
            )
        except HarmonisationError as exc:
            raise SoilArtifactError(str(exc)) from exc
        return dataset.isel(
            latitude=latitude_slice,
            longitude=longitude_slice,
        ).load()


def _build_dataset(
    data: SoilArtifactData,
    metadata: ArtifactBuildMetadata,
    source_manifest: Mapping[str, Any],
    source_manifest_id: str,
    source_manifest_sha256: str,
    grid_contract: Mapping[str, Any],
    grid_contract_id: str,
    grid_contract_sha256: str,
) -> xr.Dataset:
    latitude = np.asarray(data.latitude, dtype=np.float64)
    longitude = np.asarray(data.longitude, dtype=np.float64)
    coordinate_edges(latitude, "latitude")
    coordinate_edges(longitude, "longitude")
    try:
        require_exact_coordinate_subset(
            metadata.canonical_grid.latitude, latitude, "latitude"
        )
        require_exact_coordinate_subset(
            metadata.canonical_grid.longitude, longitude, "longitude"
        )
    except HarmonisationError as exc:
        raise SoilArtifactError(str(exc)) from exc

    shape = (latitude.size, longitude.size)
    storage = _stack_case_mapping(data.storage_mm, shape, "storage")
    dispersion = _stack_case_mapping(
        data.mapped_prediction_sd_mm, shape, "mapped prediction SD"
    )
    valid_area = _stack_case_mapping(
        data.valid_source_area_m2, shape, "valid source area"
    )
    coverage = _stack_case_mapping(
        data.source_coverage_fraction, shape, "source coverage"
    )
    full_area = _array(data.full_cell_area_m2, shape, "full cell area")
    mixed_width = _array(
        data.mixed_uncertainty_width_mm, shape, "mixed uncertainty width"
    )
    _validate_values(storage, dispersion, valid_area, coverage, full_area, mixed_width)

    dataset = xr.Dataset(
        data_vars={
            "awc_storage_capacity_mm": (
                ("storage_case", "latitude", "longitude"),
                storage.astype(np.float32),
            ),
            "mapped_prediction_sd_mm": (
                ("storage_case", "latitude", "longitude"),
                dispersion.astype(np.float32),
            ),
            "valid_source_area_m2": (
                ("storage_case", "latitude", "longitude"),
                valid_area.astype(np.float64),
            ),
            "source_coverage_fraction": (
                ("storage_case", "latitude", "longitude"),
                coverage.astype(np.float32),
            ),
            "full_cell_area_m2": (
                ("latitude", "longitude"),
                full_area.astype(np.float64),
            ),
            "mixed_uncertainty_width_mm": (
                ("latitude", "longitude"),
                mixed_width.astype(np.float32),
            ),
        },
        coords={
            "storage_case": np.asarray(STORAGE_CASES, dtype=object),
            "latitude": latitude,
            "longitude": longitude,
        },
        attrs={
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
            "artifact_version": ARTIFACT_VERSION,
            "builder_commit": metadata.builder_commit,
            "builder_version": metadata.builder_version,
            "canonical_grid_contract_id": grid_contract_id,
            "canonical_grid_contract_json": _canonical_json(grid_contract),
            "canonical_grid_contract_sha256": grid_contract_sha256,
            "canonical_grid_model_version": metadata.canonical_grid.model_version,
            "canonical_grid_source_filename": metadata.canonical_grid.source_filename,
            "canonical_grid_source_sha256": metadata.canonical_grid.source_sha256,
            "canonical_grid_source_size_bytes": metadata.canonical_grid.source_size_bytes,
            "canonical_grid_source_url": metadata.canonical_grid.source_url,
            "coordinate_semantics": "persisted source cell centres; edges are adjacent-centre midpoints with half-spacing exterior extrapolation",
            "created_utc": metadata.creation_timestamp_utc,
            "depth_integration_formula": "sum((AWC_percent / 100) * represented_layer_thickness_mm), with represented depth min(DES_m * 1000, 1000)",
            "geographic_crs": "EPSG:4326",
            "overlap_area_crs": "EPSG:3577",
            "scientific_limitations": SCIENTIFIC_LIMITATIONS,
            "source_retrieval_timestamps_json": _canonical_json(
                {
                    key: metadata.source_retrieval_timestamps_utc[key]
                    for key in sorted(metadata.source_retrieval_timestamps_utc)
                }
            ),
            "source_manifest_id": source_manifest_id,
            "source_manifest_json": _canonical_json(source_manifest),
            "source_manifest_sha256": source_manifest_sha256,
            "storage_cases_json": _canonical_json(list(STORAGE_CASES)),
        },
    )
    dataset.latitude.attrs = {
        "standard_name": "latitude",
        "long_name": "latitude",
        "units": "degrees_north",
    }
    dataset.longitude.attrs = {
        "standard_name": "longitude",
        "long_name": "longitude",
        "units": "degrees_east",
    }
    dataset.awc_storage_capacity_mm.attrs = {
        "long_name": "DES-capped modelled available water storage capacity",
        "units": "mm",
    }
    dataset.mapped_prediction_sd_mm.attrs = {
        "long_name": "area-weighted population standard deviation among mapped predictions",
        "units": "mm",
    }
    dataset.valid_source_area_m2.attrs = {"units": "m2"}
    dataset.source_coverage_fraction.attrs = {"units": "1"}
    dataset.full_cell_area_m2.attrs = {"units": "m2"}
    dataset.mixed_uncertainty_width_mm.attrs = {
        "long_name": "provisional mixed-quantile upper minus lower storage scenario width",
        "units": "mm",
    }
    return dataset


def _encoding(data: SoilArtifactData) -> dict[str, dict[str, Any]]:
    latitude_size = np.asarray(data.latitude).size
    longitude_size = np.asarray(data.longitude).size
    case_chunks = (1, min(64, latitude_size), min(64, longitude_size))
    grid_chunks = (min(64, latitude_size), min(64, longitude_size))
    compressed = {"zlib": True, "complevel": 4, "shuffle": True}
    return {
        "awc_storage_capacity_mm": {
            **compressed,
            "dtype": "float32",
            "_FillValue": np.float32(np.nan),
            "chunksizes": case_chunks,
        },
        "mapped_prediction_sd_mm": {
            **compressed,
            "dtype": "float32",
            "_FillValue": np.float32(np.nan),
            "chunksizes": case_chunks,
        },
        "valid_source_area_m2": {
            **compressed,
            "dtype": "float64",
            "_FillValue": None,
            "chunksizes": case_chunks,
        },
        "source_coverage_fraction": {
            **compressed,
            "dtype": "float32",
            "_FillValue": np.float32(np.nan),
            "chunksizes": case_chunks,
        },
        "full_cell_area_m2": {
            **compressed,
            "dtype": "float64",
            "_FillValue": None,
            "chunksizes": grid_chunks,
        },
        "mixed_uncertainty_width_mm": {
            **compressed,
            "dtype": "float32",
            "_FillValue": np.float32(np.nan),
            "chunksizes": grid_chunks,
        },
        "latitude": {"dtype": "float64", "_FillValue": None},
        "longitude": {"dtype": "float64", "_FillValue": None},
    }


def _validate_artifact_schema(path: Path) -> None:
    try:
        with xr.open_dataset(path, decode_times=False, mask_and_scale=False) as dataset:
            if set(dataset.data_vars) != REQUIRED_DATA_VARIABLES:
                raise SoilArtifactError("Soil artifact data-variable schema mismatch.")
            if (
                dataset.attrs.get("artifact_contract_version")
                != ARTIFACT_CONTRACT_VERSION
            ):
                raise SoilArtifactError("Soil artifact contract version mismatch.")
            if dataset.attrs.get("artifact_version") != ARTIFACT_VERSION:
                raise SoilArtifactError("Soil artifact version mismatch.")
            if (
                tuple(str(value) for value in dataset.storage_case.values)
                != STORAGE_CASES
            ):
                raise SoilArtifactError("Soil artifact storage-case ordering mismatch.")
            expected_case_dimensions = ("storage_case", "latitude", "longitude")
            for name in (
                "awc_storage_capacity_mm",
                "mapped_prediction_sd_mm",
                "valid_source_area_m2",
                "source_coverage_fraction",
            ):
                if dataset[name].dims != expected_case_dimensions:
                    raise SoilArtifactError(
                        f"Soil artifact variable {name!r} dimensions mismatch."
                    )
            for name in ("full_cell_area_m2", "mixed_uncertainty_width_mm"):
                if dataset[name].dims != ("latitude", "longitude"):
                    raise SoilArtifactError(
                        f"Soil artifact variable {name!r} dimensions mismatch."
                    )
            expected_dtypes = {
                "awc_storage_capacity_mm": np.dtype("float32"),
                "mapped_prediction_sd_mm": np.dtype("float32"),
                "valid_source_area_m2": np.dtype("float64"),
                "source_coverage_fraction": np.dtype("float32"),
                "full_cell_area_m2": np.dtype("float64"),
                "mixed_uncertainty_width_mm": np.dtype("float32"),
                "latitude": np.dtype("float64"),
                "longitude": np.dtype("float64"),
            }
            for name, dtype in expected_dtypes.items():
                if dataset[name].dtype != dtype:
                    raise SoilArtifactError(
                        f"Soil artifact variable {name!r} dtype mismatch."
                    )
            coordinate_edges(np.asarray(dataset.latitude.values), "latitude")
            coordinate_edges(np.asarray(dataset.longitude.values), "longitude")
    except SoilArtifactError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise SoilArtifactError("Soil artifact is unreadable or malformed.") from exc


def _validate_sidecar(
    sidecar: Mapping[str, Any],
    artifact_path: Path,
    source_manifest_path: Path,
    grid_contract_path: Path,
) -> None:
    if sidecar.get("artifact_contract_version") != ARTIFACT_CONTRACT_VERSION:
        raise SoilArtifactError("Soil artifact sidecar contract version mismatch.")
    if sidecar.get("artifact_version") != ARTIFACT_VERSION:
        raise SoilArtifactError("Soil artifact sidecar version mismatch.")
    if sidecar.get("artifact_filename") != artifact_path.name:
        raise SoilArtifactError("Soil artifact filename does not match its sidecar.")
    if sidecar.get("artifact_size_bytes") != artifact_path.stat().st_size:
        raise SoilArtifactError("Soil artifact size does not match its sidecar.")
    if sidecar.get("artifact_sha256") != sha256_file(artifact_path):
        raise SoilArtifactError("Soil artifact SHA-256 does not match its sidecar.")

    source_manifest, source_bytes = _load_json_object(source_manifest_path)
    if sidecar.get("source_manifest_id") != source_manifest.get("manifest_id"):
        raise SoilArtifactError("Soil artifact source-manifest identity mismatch.")
    if sidecar.get("source_manifest_sha256") != _sha256_bytes(source_bytes):
        raise SoilArtifactError("Soil artifact source-manifest SHA-256 mismatch.")

    grid_contract = load_grid_contract(grid_contract_path)
    grid_bytes = grid_contract_path.read_bytes()
    if sidecar.get("canonical_grid_contract_id") != grid_contract.get(
        "grid_contract_id"
    ):
        raise SoilArtifactError("Soil artifact canonical-grid identity mismatch.")
    if sidecar.get("canonical_grid_contract_sha256") != _sha256_bytes(grid_bytes):
        raise SoilArtifactError("Soil artifact canonical-grid SHA-256 mismatch.")

    with xr.open_dataset(
        artifact_path, decode_times=False, mask_and_scale=False
    ) as dataset:
        matched_metadata = {
            "artifact_contract_version": "artifact_contract_version",
            "artifact_version": "artifact_version",
            "builder_commit": "builder_commit",
            "builder_version": "builder_version",
            "canonical_grid_contract_id": "canonical_grid_contract_id",
            "canonical_grid_contract_sha256": "canonical_grid_contract_sha256",
            "canonical_grid_source_filename": "canonical_grid_source_filename",
            "canonical_grid_source_sha256": "canonical_grid_source_sha256",
            "canonical_grid_source_size_bytes": "canonical_grid_source_size_bytes",
            "source_manifest_id": "source_manifest_id",
            "source_manifest_sha256": "source_manifest_sha256",
        }
        for sidecar_key, attribute_name in matched_metadata.items():
            if sidecar.get(sidecar_key) != dataset.attrs.get(attribute_name):
                raise SoilArtifactError(
                    f"Soil artifact metadata {attribute_name!r} does not match its sidecar."
                )
        if sidecar.get("creation_timestamp_utc") != dataset.attrs.get("created_utc"):
            raise SoilArtifactError(
                "Soil artifact creation timestamp does not match its sidecar."
            )
        if _canonical_json(sidecar.get("source_retrieval_timestamps_utc")) != (
            dataset.attrs.get("source_retrieval_timestamps_json")
        ):
            raise SoilArtifactError(
                "Soil artifact retrieval timestamps do not match its sidecar."
            )


def _stack_case_mapping(
    mapping: Mapping[str, np.ndarray], shape: tuple[int, int], label: str
) -> np.ndarray:
    if set(mapping) != set(STORAGE_CASES):
        raise SoilArtifactError(
            f"{label} cases must match the seven ordered storage cases."
        )
    return np.stack(
        [_array(mapping[case], shape, f"{label} {case}") for case in STORAGE_CASES]
    )


def _array(values: np.ndarray, shape: tuple[int, int], label: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != shape:
        raise SoilArtifactError(f"{label} shape does not match artifact coordinates.")
    return array


def _validate_values(
    storage: np.ndarray,
    dispersion: np.ndarray,
    valid_area: np.ndarray,
    coverage: np.ndarray,
    full_area: np.ndarray,
    mixed_width: np.ndarray,
) -> None:
    for label, values in (
        ("storage", storage),
        ("mapped prediction SD", dispersion),
        ("mixed uncertainty width", mixed_width),
    ):
        if np.any(np.isinf(values)) or np.any(values[np.isfinite(values)] < 0):
            raise SoilArtifactError(f"{label} contains an invalid value.")
    if not np.all(np.isfinite(valid_area)) or np.any(valid_area < 0):
        raise SoilArtifactError("Valid source area must be finite and non-negative.")
    if not np.all(np.isfinite(full_area)) or np.any(full_area <= 0):
        raise SoilArtifactError("Full cell area must be finite and positive.")
    if (
        not np.all(np.isfinite(coverage))
        or np.any(coverage < 0)
        or np.any(coverage > 1)
    ):
        raise SoilArtifactError("Source coverage must be finite and within [0, 1].")
    if np.any(valid_area > full_area[np.newaxis, :, :] * (1.0 + 1e-12)):
        raise SoilArtifactError("Valid source area exceeds full cell area.")


def _source_layer_ids(source_manifest: Mapping[str, Any]) -> tuple[str, ...]:
    layers = source_manifest.get("layers")
    if not isinstance(layers, list) or not layers:
        raise SoilArtifactError("Source manifest layers are missing or malformed.")
    product_ids: list[str] = []
    for layer in layers:
        if not isinstance(layer, dict):
            raise SoilArtifactError("Source manifest layer is malformed.")
        product_ids.append(_required_string(layer, "product_id"))
    if len(product_ids) != len(set(product_ids)):
        raise SoilArtifactError("Source manifest contains duplicate product IDs.")
    return tuple(product_ids)


def _load_json_object(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SoilArtifactError(f"Cannot read required JSON file {path}.") from exc
    if not isinstance(value, dict):
        raise SoilArtifactError(f"Required JSON file {path} must contain an object.")
    return value, raw


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise SoilArtifactError(f"Required field {key!r} is missing or malformed.")
    return value


def _validate_utc_timestamp(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise SoilArtifactError(f"{label} must be an ISO-8601 UTC timestamp.")
    normalised = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError as exc:
        raise SoilArtifactError(f"{label} is malformed.") from exc
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise SoilArtifactError(f"{label} must be UTC.")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)
