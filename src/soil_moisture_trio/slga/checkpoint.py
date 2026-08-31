from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from src.soil_moisture_trio.slga.artifact import (
    DES_COMPONENTS,
    STORAGE_CASES,
    SoilArtifactData,
    SoilArtifactError,
)

CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_DATA_FILENAME = "stripe_data.npz"
CHECKPOINT_MANIFEST_FILENAME = "stripe_manifest.json"

_MAPPING_FIELDS = {
    "storage": ("storage_mm", STORAGE_CASES),
    "storage_sd": ("mapped_prediction_sd_mm", STORAGE_CASES),
    "storage_valid_area": ("valid_source_area_m2", STORAGE_CASES),
    "storage_coverage": ("source_coverage_fraction", STORAGE_CASES),
    "des": ("depth_of_soil_m", DES_COMPONENTS),
    "des_sd": ("depth_of_soil_mapped_prediction_sd_m", DES_COMPONENTS),
    "des_valid_area": ("depth_of_soil_valid_source_area_m2", DES_COMPONENTS),
    "des_coverage": ("depth_of_soil_source_coverage_fraction", DES_COMPONENTS),
    "des_shallow": ("depth_of_soil_shallower_than_1m_fraction", DES_COMPONENTS),
}
_ARRAY_FIELDS = {
    "full_cell_area": "full_cell_area_m2",
    "mixed_width": "mixed_uncertainty_width_mm",
    "mixed_width_sd": "mixed_uncertainty_width_mapped_prediction_sd_mm",
    "mixed_width_valid_area": "mixed_uncertainty_width_valid_source_area_m2",
    "mixed_width_coverage": "mixed_uncertainty_width_source_coverage_fraction",
}


class StripeCheckpointError(SoilArtifactError):
    """Raised when a resumable build stripe is missing, corrupt, or incompatible."""


@dataclass(frozen=True)
class LoadedStripeCheckpoint:
    stripe_index: int
    data: SoilArtifactData
    identity: Mapping[str, Any]
    provenance: Mapping[str, Any]


def stripe_checkpoint_path(root: Path, stripe_index: int) -> Path:
    if (
        not isinstance(stripe_index, int)
        or isinstance(stripe_index, bool)
        or stripe_index < 0
    ):
        raise StripeCheckpointError("Stripe index must be a non-negative integer.")
    return Path(root) / f"stripe_{stripe_index:04d}"


def write_stripe_checkpoint(
    root: Path,
    stripe_index: int,
    data: SoilArtifactData,
    *,
    identity: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> LoadedStripeCheckpoint:
    """Write one credential-free stripe as a new atomic immutable directory."""
    checkpoint_root = Path(root)
    destination = stripe_checkpoint_path(checkpoint_root, stripe_index)
    if destination.exists():
        raise StripeCheckpointError("Immutable stripe checkpoint already exists.")
    identity_document = _json_mapping(identity, "checkpoint identity")
    provenance_document = _json_mapping(provenance, "checkpoint provenance")
    arrays = _serialise_data(data)

    checkpoint_root.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            suffix=".staging",
            dir=checkpoint_root,
        )
    )
    try:
        data_path = staging / CHECKPOINT_DATA_FILENAME
        with data_path.open("wb") as stream:
            np.savez_compressed(stream, **arrays)
        manifest = {
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "data_filename": CHECKPOINT_DATA_FILENAME,
            "data_sha256": _sha256_file(data_path),
            "data_size_bytes": data_path.stat().st_size,
            "identity": identity_document,
            "provenance": provenance_document,
            "stripe_index": stripe_index,
        }
        (staging / CHECKPOINT_MANIFEST_FILENAME).write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            raise StripeCheckpointError("Immutable stripe checkpoint already exists.")
        os.rename(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return load_stripe_checkpoint(
        destination,
        expected_index=stripe_index,
        expected_identity=identity_document,
        expected_latitude=np.asarray(data.latitude, dtype=np.float64),
        expected_longitude=np.asarray(data.longitude, dtype=np.float64),
    )


def load_stripe_checkpoint(
    path: Path,
    *,
    expected_index: int,
    expected_identity: Mapping[str, Any],
    expected_latitude: np.ndarray,
    expected_longitude: np.ndarray,
) -> LoadedStripeCheckpoint:
    """Checksum and contract-verify one completed stripe without credentials."""
    checkpoint = Path(path)
    manifest_path = checkpoint / CHECKPOINT_MANIFEST_FILENAME
    data_path = checkpoint / CHECKPOINT_DATA_FILENAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StripeCheckpointError(
            "Stripe checkpoint manifest is unreadable."
        ) from exc
    if not isinstance(manifest, dict):
        raise StripeCheckpointError("Stripe checkpoint manifest must be an object.")
    if manifest.get("checkpoint_schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise StripeCheckpointError("Stripe checkpoint schema version mismatch.")
    if manifest.get("stripe_index") != expected_index:
        raise StripeCheckpointError("Stripe checkpoint index mismatch.")
    expected_identity_document = _json_mapping(expected_identity, "expected identity")
    if _canonical_json(manifest.get("identity")) != _canonical_json(
        expected_identity_document
    ):
        raise StripeCheckpointError("Stripe checkpoint identity mismatch.")
    if manifest.get("data_filename") != CHECKPOINT_DATA_FILENAME:
        raise StripeCheckpointError("Stripe checkpoint data filename mismatch.")
    try:
        size = data_path.stat().st_size
    except OSError as exc:
        raise StripeCheckpointError("Stripe checkpoint data is missing.") from exc
    if manifest.get("data_size_bytes") != size:
        raise StripeCheckpointError("Stripe checkpoint data size mismatch.")
    if manifest.get("data_sha256") != _sha256_file(data_path):
        raise StripeCheckpointError("Stripe checkpoint data SHA-256 mismatch.")

    try:
        with np.load(data_path, allow_pickle=False) as archive:
            if set(archive.files) != _expected_array_keys():
                raise StripeCheckpointError("Stripe checkpoint array schema mismatch.")
            arrays = {name: np.asarray(archive[name]).copy() for name in archive.files}
    except StripeCheckpointError:
        raise
    except (OSError, ValueError) as exc:
        raise StripeCheckpointError("Stripe checkpoint arrays are unreadable.") from exc

    data = _deserialise_data(arrays)
    if not np.array_equal(
        np.asarray(data.latitude, dtype=np.float64),
        np.asarray(expected_latitude, dtype=np.float64),
    ) or not np.array_equal(
        np.asarray(data.longitude, dtype=np.float64),
        np.asarray(expected_longitude, dtype=np.float64),
    ):
        raise StripeCheckpointError("Stripe checkpoint coordinates mismatch.")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise StripeCheckpointError("Stripe checkpoint provenance is malformed.")
    return LoadedStripeCheckpoint(
        stripe_index=expected_index,
        data=data,
        identity=expected_identity_document,
        provenance=provenance,
    )


def combine_stripe_checkpoints(
    checkpoints: Sequence[LoadedStripeCheckpoint],
    *,
    expected_latitude: np.ndarray,
    expected_longitude: np.ndarray,
) -> SoilArtifactData:
    """Assemble ordered, disjoint stripe data into one exact artifact payload."""
    if not checkpoints:
        raise StripeCheckpointError("At least one stripe checkpoint is required.")
    ordered = sorted(checkpoints, key=lambda item: item.stripe_index)
    if [item.stripe_index for item in ordered] != list(range(len(ordered))):
        raise StripeCheckpointError(
            "Stripe checkpoint indexes must be contiguous from zero."
        )
    longitude = np.asarray(expected_longitude, dtype=np.float64)
    for item in ordered:
        if not np.array_equal(
            np.asarray(item.data.longitude, dtype=np.float64), longitude
        ):
            raise StripeCheckpointError("Stripe checkpoint longitudes do not match.")
    latitude = np.concatenate(
        [np.asarray(item.data.latitude, dtype=np.float64) for item in ordered]
    )
    if not np.array_equal(latitude, np.asarray(expected_latitude, dtype=np.float64)):
        raise StripeCheckpointError("Stripe checkpoint latitudes do not reconcile.")

    def combine_mapping(attribute: str, keys: Sequence[str]) -> dict[str, np.ndarray]:
        return {
            key: np.concatenate(
                [np.asarray(getattr(item.data, attribute)[key]) for item in ordered],
                axis=0,
            )
            for key in keys
        }

    def combine_array(attribute: str) -> np.ndarray:
        return np.concatenate(
            [np.asarray(getattr(item.data, attribute)) for item in ordered], axis=0
        )

    return SoilArtifactData(
        latitude=latitude,
        longitude=longitude,
        storage_mm=combine_mapping("storage_mm", STORAGE_CASES),
        mapped_prediction_sd_mm=combine_mapping(
            "mapped_prediction_sd_mm", STORAGE_CASES
        ),
        valid_source_area_m2=combine_mapping("valid_source_area_m2", STORAGE_CASES),
        source_coverage_fraction=combine_mapping(
            "source_coverage_fraction", STORAGE_CASES
        ),
        full_cell_area_m2=combine_array("full_cell_area_m2"),
        mixed_uncertainty_width_mm=combine_array("mixed_uncertainty_width_mm"),
        mixed_uncertainty_width_mapped_prediction_sd_mm=combine_array(
            "mixed_uncertainty_width_mapped_prediction_sd_mm"
        ),
        mixed_uncertainty_width_valid_source_area_m2=combine_array(
            "mixed_uncertainty_width_valid_source_area_m2"
        ),
        mixed_uncertainty_width_source_coverage_fraction=combine_array(
            "mixed_uncertainty_width_source_coverage_fraction"
        ),
        depth_of_soil_m=combine_mapping("depth_of_soil_m", DES_COMPONENTS),
        depth_of_soil_mapped_prediction_sd_m=combine_mapping(
            "depth_of_soil_mapped_prediction_sd_m", DES_COMPONENTS
        ),
        depth_of_soil_valid_source_area_m2=combine_mapping(
            "depth_of_soil_valid_source_area_m2", DES_COMPONENTS
        ),
        depth_of_soil_source_coverage_fraction=combine_mapping(
            "depth_of_soil_source_coverage_fraction", DES_COMPONENTS
        ),
        depth_of_soil_shallower_than_1m_fraction=combine_mapping(
            "depth_of_soil_shallower_than_1m_fraction", DES_COMPONENTS
        ),
    )


def _serialise_data(data: SoilArtifactData) -> dict[str, np.ndarray]:
    latitude = np.asarray(data.latitude, dtype=np.float64)
    longitude = np.asarray(data.longitude, dtype=np.float64)
    if (
        latitude.ndim != 1
        or longitude.ndim != 1
        or latitude.size < 2
        or longitude.size < 2
    ):
        raise StripeCheckpointError(
            "Stripe coordinates must be one-dimensional and non-trivial."
        )
    shape = (latitude.size, longitude.size)
    arrays: dict[str, np.ndarray] = {
        "latitude": latitude,
        "longitude": longitude,
    }
    for prefix, (attribute, keys) in _MAPPING_FIELDS.items():
        mapping = getattr(data, attribute)
        if set(mapping) != set(keys):
            raise StripeCheckpointError(f"Stripe mapping {attribute!r} is incomplete.")
        for key in keys:
            arrays[f"{prefix}__{key}"] = _stripe_array(mapping[key], shape, attribute)
    for key, attribute in _ARRAY_FIELDS.items():
        arrays[key] = _stripe_array(getattr(data, attribute), shape, attribute)
    return arrays


def _deserialise_data(arrays: Mapping[str, np.ndarray]) -> SoilArtifactData:
    def mapping(prefix: str, keys: Sequence[str]) -> dict[str, np.ndarray]:
        return {key: np.asarray(arrays[f"{prefix}__{key}"]).copy() for key in keys}

    return SoilArtifactData(
        latitude=np.asarray(arrays["latitude"], dtype=np.float64).copy(),
        longitude=np.asarray(arrays["longitude"], dtype=np.float64).copy(),
        storage_mm=mapping("storage", STORAGE_CASES),
        mapped_prediction_sd_mm=mapping("storage_sd", STORAGE_CASES),
        valid_source_area_m2=mapping("storage_valid_area", STORAGE_CASES),
        source_coverage_fraction=mapping("storage_coverage", STORAGE_CASES),
        full_cell_area_m2=np.asarray(arrays["full_cell_area"]).copy(),
        mixed_uncertainty_width_mm=np.asarray(arrays["mixed_width"]).copy(),
        mixed_uncertainty_width_mapped_prediction_sd_mm=np.asarray(
            arrays["mixed_width_sd"]
        ).copy(),
        mixed_uncertainty_width_valid_source_area_m2=np.asarray(
            arrays["mixed_width_valid_area"]
        ).copy(),
        mixed_uncertainty_width_source_coverage_fraction=np.asarray(
            arrays["mixed_width_coverage"]
        ).copy(),
        depth_of_soil_m=mapping("des", DES_COMPONENTS),
        depth_of_soil_mapped_prediction_sd_m=mapping("des_sd", DES_COMPONENTS),
        depth_of_soil_valid_source_area_m2=mapping("des_valid_area", DES_COMPONENTS),
        depth_of_soil_source_coverage_fraction=mapping("des_coverage", DES_COMPONENTS),
        depth_of_soil_shallower_than_1m_fraction=mapping("des_shallow", DES_COMPONENTS),
    )


def _stripe_array(values: np.ndarray, shape: tuple[int, int], label: str) -> np.ndarray:
    array = np.asarray(values)
    if array.shape != shape:
        raise StripeCheckpointError(f"Stripe array {label!r} has the wrong shape.")
    if array.dtype.kind != "f":
        raise StripeCheckpointError(f"Stripe array {label!r} must be floating point.")
    return array.copy()


def _expected_array_keys() -> set[str]:
    keys = {"latitude", "longitude", *_ARRAY_FIELDS}
    for prefix, (_attribute, components) in _MAPPING_FIELDS.items():
        keys.update(f"{prefix}__{component}" for component in components)
    return keys


def _json_mapping(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise StripeCheckpointError(f"{label} must be a mapping.")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise StripeCheckpointError(f"{label} must be JSON serialisable.") from exc
    if not isinstance(decoded, dict):
        raise StripeCheckpointError(f"{label} must be a JSON object.")
    return decoded


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
