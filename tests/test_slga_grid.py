from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.soil_moisture_trio.slga.grid import (
    DEFAULT_GRID_CONTRACT_PATH,
    CanonicalGridError,
    load_canonical_grid,
    load_grid_contract,
    select_exact_coordinate_range,
    sha256_file,
)


def _write_source(
    path: Path,
    *,
    latitude: np.ndarray | None = None,
    longitude: np.ndarray | None = None,
    institution: str = "Bureau of Meteorology",
) -> None:
    latitude = (
        np.array([-10.0, -10.05, -10.10], dtype=np.float64)
        if latitude is None
        else np.asarray(latitude, dtype=np.float64)
    )
    longitude = (
        np.array([112.0, 112.05, 112.10], dtype=np.float64)
        if longitude is None
        else np.asarray(longitude, dtype=np.float64)
    )
    dataset = xr.Dataset(
        data_vars={
            "sm_pct": (
                ("time", "latitude", "longitude"),
                np.zeros((1, latitude.size, longitude.size), dtype=np.float32),
            )
        },
        coords={
            "time": np.array([0], dtype=np.int32),
            "latitude": latitude,
            "longitude": longitude,
        },
        attrs={
            "title": "Australian Landscape Water Balance AWRA-L Model",
            "summary": "Data produced by Bureau of Meteorology Australian Water Resources Assessment Landscape Model (AWRA-L)",
            "source": "AWRA-L",
            "institution": institution,
            "var_name": "sm_pct",
            "Conventions": "CF-1.6, ACDD-1.3",
        },
    )
    for name, units in (("latitude", "degrees_north"), ("longitude", "degrees_east")):
        dataset[name].attrs = {
            "name": name,
            "standard_name": name,
            "long_name": name,
            "units": units,
        }
    dataset.to_netcdf(path)


def _raw_coordinate_hash(values: np.ndarray) -> str:
    return hashlib.sha256(
        np.asarray(values, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _write_contract(path: Path, source_path: Path) -> dict:
    with xr.open_dataset(source_path, decode_times=False, mask_and_scale=False) as ds:
        latitude = np.asarray(ds.latitude.values, dtype=np.float64)
        longitude = np.asarray(ds.longitude.values, dtype=np.float64)
    contract = {
        "grid_contract_schema_version": 1,
        "grid_contract_id": "synthetic_awral_grid_v1",
        "source": {
            "filename": source_path.name,
            "size_bytes": source_path.stat().st_size,
            "sha256": sha256_file(source_path),
            "download_url": "https://example.test/source.nc",
            "model_version": "AWRA-L v7 synthetic test",
            "dimensions": {
                "time": 1,
                "latitude": int(latitude.size),
                "longitude": int(longitude.size),
            },
            "data_variable": {
                "name": "sm_pct",
                "dtype": "float32",
                "dimensions": ["time", "latitude", "longitude"],
            },
            "global_attributes": {
                "title": "Australian Landscape Water Balance AWRA-L Model",
                "summary": "Data produced by Bureau of Meteorology Australian Water Resources Assessment Landscape Model (AWRA-L)",
                "source": "AWRA-L",
                "institution": "Bureau of Meteorology",
                "var_name": "sm_pct",
                "Conventions": "CF-1.6, ACDD-1.3",
            },
        },
        "coordinate_contract": {
            "nominal_spacing_degrees": 0.05,
            "spacing_absolute_tolerance_degrees": 1e-10,
            "latitude": _coordinate_specification(
                latitude, "latitude", "degrees_north"
            ),
            "longitude": _coordinate_specification(
                longitude, "longitude", "degrees_east"
            ),
        },
    }
    path.write_text(json.dumps(contract), encoding="utf-8")
    return contract


def _coordinate_specification(values: np.ndarray, name: str, units: str) -> dict:
    return {
        "dimension": name,
        "dtype": "float64",
        "length": int(values.size),
        "first": float(values[0]),
        "last": float(values[-1]),
        "orientation": "ascending" if values[-1] > values[0] else "descending",
        "raw_float64_little_endian_sha256": _raw_coordinate_hash(values),
        "attributes": {
            "name": name,
            "standard_name": name,
            "long_name": name,
            "units": units,
        },
    }


def _rewrite_contract(path: Path, contract: dict) -> None:
    path.write_text(json.dumps(contract), encoding="utf-8")


def _refresh_source_identity(contract: dict, source_path: Path) -> None:
    contract["source"]["size_bytes"] = source_path.stat().st_size
    contract["source"]["sha256"] = sha256_file(source_path)


def test_tracked_grid_contract_pins_the_operational_awral_v7_source():
    contract = load_grid_contract(DEFAULT_GRID_CONTRACT_PATH)

    assert contract["grid_contract_id"] == "awral_v7_grid_source_v1"
    assert contract["source"]["model_version"] == "AWRA-L v7"
    assert contract["source"]["filename"] == "sm_pct_2025.nc"
    assert contract["source"]["size_bytes"] == 312_193_677
    assert contract["source"]["sha256"] == (
        "353af96c7826111a54e189120ed6e1dcb6f9d2a1a0d6966c286aae4f4429095b"
    )
    assert contract["coordinate_contract"]["latitude"]["length"] == 681
    assert contract["coordinate_contract"]["longitude"]["length"] == 841
    footprint = contract["coordinate_contract"]["approved_swaz_artifact_footprint"]
    assert footprint["latitude_first"] == -27.45
    assert footprint["latitude_last"] == -35.2
    assert footprint["latitude_length"] == 156
    assert footprint["longitude_first"] == 114.05
    assert footprint["longitude_last"] == 123.3
    assert footprint["longitude_length"] == 186
    assert footprint["cell_count"] == 29_016
    assert footprint["boundary_buffer_degrees"] == 0.1
    assert footprint["boundary_sha256"] == (
        "407ce1b536e1391e73677d04e995de8c913d49859c328b3f8904deb92b198b66"
    )


def test_exact_coordinate_range_preserves_source_values_and_orientation():
    latitude = np.array([-12.95, -13.0, -13.05, -13.10])
    longitude = np.array([111.95, 112.0, 112.05, 112.10])

    np.testing.assert_array_equal(
        select_exact_coordinate_range(latitude, -13.0, -13.10, "latitude"),
        [-13.0, -13.05, -13.10],
    )
    np.testing.assert_array_equal(
        select_exact_coordinate_range(longitude, 112.0, 112.10, "longitude"),
        [112.0, 112.05, 112.10],
    )
    with pytest.raises(CanonicalGridError, match="not exact canonical"):
        select_exact_coordinate_range(longitude, 112.0 + 1e-12, 112.10, "longitude")
    with pytest.raises(CanonicalGridError, match="canonical orientation"):
        select_exact_coordinate_range(longitude, 112.10, 112.0, "longitude")


def test_load_canonical_grid_verifies_source_and_preserves_orientation(tmp_path):
    source = tmp_path / "source.nc"
    contract_path = tmp_path / "contract.json"
    _write_source(source)
    _write_contract(contract_path, source)

    grid = load_canonical_grid(source, contract_path)

    np.testing.assert_array_equal(grid.latitude, [-10.0, -10.05, -10.10])
    np.testing.assert_array_equal(grid.longitude, [112.0, 112.05, 112.10])
    assert grid.contract_id == "synthetic_awral_grid_v1"
    assert grid.source_sha256 == sha256_file(source)
    assert grid.contract_sha256 == sha256_file(contract_path)
    assert grid.model_version == "AWRA-L v7 synthetic test"


def test_missing_wrong_named_corrupt_and_checksum_mismatch_inputs_fail(tmp_path):
    source = tmp_path / "source.nc"
    contract_path = tmp_path / "contract.json"
    _write_source(source)
    contract = _write_contract(contract_path, source)

    with pytest.raises(CanonicalGridError, match="missing or unreadable"):
        load_canonical_grid(tmp_path / "missing" / "source.nc", contract_path)

    renamed = tmp_path / "renamed.nc"
    renamed.write_bytes(source.read_bytes())
    with pytest.raises(CanonicalGridError, match="must be named"):
        load_canonical_grid(renamed, contract_path)

    source.write_bytes(source.read_bytes() + b"corrupt")
    with pytest.raises(CanonicalGridError, match="size mismatch"):
        load_canonical_grid(source, contract_path)

    _write_source(source)
    contract["source"]["size_bytes"] = source.stat().st_size
    contract["source"]["sha256"] = "0" * 64
    _rewrite_contract(contract_path, contract)
    with pytest.raises(CanonicalGridError, match="SHA-256 mismatch"):
        load_canonical_grid(source, contract_path)


def test_schema_and_coordinate_value_drift_fail_after_source_rehash(tmp_path):
    source = tmp_path / "source.nc"
    contract_path = tmp_path / "contract.json"
    _write_source(source)
    contract = _write_contract(contract_path, source)

    _write_source(source, institution="Not the pinned provider")
    _refresh_source_identity(contract, source)
    _rewrite_contract(contract_path, contract)
    with pytest.raises(CanonicalGridError, match="global attribute 'institution'"):
        load_canonical_grid(source, contract_path)

    longitude = np.array([112.0, 112.05 + 1e-12, 112.10])
    _write_source(source, longitude=longitude)
    _refresh_source_identity(contract, source)
    _rewrite_contract(contract_path, contract)
    with pytest.raises(CanonicalGridError, match="longitude value hash mismatch"):
        load_canonical_grid(source, contract_path)


def test_reordered_and_off_grid_coordinates_fail(tmp_path):
    source = tmp_path / "source.nc"
    contract_path = tmp_path / "contract.json"
    _write_source(source)
    contract = _write_contract(contract_path, source)

    reordered = np.array([112.0, 112.10, 112.05])
    _write_source(source, longitude=reordered)
    _refresh_source_identity(contract, source)
    contract["coordinate_contract"]["longitude"].update(
        {
            "last": float(reordered[-1]),
            "raw_float64_little_endian_sha256": _raw_coordinate_hash(reordered),
        }
    )
    _rewrite_contract(contract_path, contract)
    with pytest.raises(CanonicalGridError, match="orientation mismatch"):
        load_canonical_grid(source, contract_path)

    off_grid = np.array([112.0, 112.05, 112.11])
    _write_source(source, longitude=off_grid)
    _refresh_source_identity(contract, source)
    contract["coordinate_contract"]["longitude"].update(
        {
            "last": float(off_grid[-1]),
            "raw_float64_little_endian_sha256": _raw_coordinate_hash(off_grid),
        }
    )
    _rewrite_contract(contract_path, contract)
    with pytest.raises(CanonicalGridError, match="regular 0.05 degree"):
        load_canonical_grid(source, contract_path)


def test_malformed_contract_fails(tmp_path):
    path = tmp_path / "contract.json"
    path.write_text('{"grid_contract_schema_version": 2}', encoding="utf-8")
    with pytest.raises(CanonicalGridError, match="schema version"):
        load_grid_contract(path)
