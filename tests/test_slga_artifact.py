from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.soil_moisture_trio.slga import artifact as artifact_module
from src.soil_moisture_trio.slga.artifact import (
    ARTIFACT_CONTRACT_VERSION,
    ARTIFACT_VERSION,
    STORAGE_CASES,
    ArtifactBuildMetadata,
    SoilArtifactData,
    SoilArtifactError,
    load_soil_artifact,
    write_soil_artifact,
)
from src.soil_moisture_trio.slga.grid import CanonicalGrid, sha256_file

LATITUDE = np.array([-30.0, -30.05, -30.10], dtype=np.float64)
LONGITUDE = np.array([115.0, 115.05, 115.10], dtype=np.float64)


def _write_contracts(tmp_path: Path) -> tuple[Path, Path, CanonicalGrid]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    grid_contract_path = tmp_path / "grid.json"
    grid_contract = {
        "grid_contract_schema_version": 1,
        "grid_contract_id": "synthetic_grid_v1",
        "source": {},
        "coordinate_contract": {},
    }
    grid_contract_path.write_text(
        json.dumps(grid_contract, sort_keys=True), encoding="utf-8"
    )
    source_manifest_path = tmp_path / "sources.json"
    source_manifest = {
        "manifest_schema_version": 1,
        "manifest_id": "synthetic_sources_v1",
        "layers": [
            {"product_id": "AWC_TEST"},
            {"product_id": "DES_TEST"},
        ],
    }
    source_manifest_path.write_text(
        json.dumps(source_manifest, sort_keys=True), encoding="utf-8"
    )
    grid = CanonicalGrid(
        latitude=LATITUDE,
        longitude=LONGITUDE,
        contract_id="synthetic_grid_v1",
        contract_sha256=sha256_file(grid_contract_path),
        source_filename="synthetic_awral.nc",
        source_size_bytes=1234,
        source_sha256="a" * 64,
        source_url="https://example.test/synthetic_awral.nc",
        model_version="AWRA-L v7 synthetic",
    )
    return source_manifest_path, grid_contract_path, grid


def _data() -> SoilArtifactData:
    base = np.arange(9, dtype=np.float64).reshape(3, 3) + 50.0
    storage = {case: base + float(index) for index, case in enumerate(STORAGE_CASES)}
    dispersion = {
        case: np.full((3, 3), index) for index, case in enumerate(STORAGE_CASES)
    }
    valid_area = {case: np.full((3, 3), 80.0) for case in STORAGE_CASES}
    coverage = {case: np.full((3, 3), 0.8) for case in STORAGE_CASES}
    return SoilArtifactData(
        latitude=LATITUDE,
        longitude=LONGITUDE,
        storage_mm=storage,
        mapped_prediction_sd_mm=dispersion,
        valid_source_area_m2=valid_area,
        source_coverage_fraction=coverage,
        full_cell_area_m2=np.full((3, 3), 100.0),
        mixed_uncertainty_width_mm=np.full((3, 3), 20.0),
    )


def _metadata(grid: CanonicalGrid) -> ArtifactBuildMetadata:
    return ArtifactBuildMetadata(
        canonical_grid=grid,
        creation_timestamp_utc="2026-08-12T08:00:00Z",
        builder_version="0.1.0-test",
        builder_commit="abc123",
        source_retrieval_timestamps_utc={
            "AWC_TEST": "2026-08-12T07:00:00+00:00",
            "DES_TEST": "2026-08-12T07:01:00+00:00",
        },
    )


def _write(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source_manifest, grid_contract, grid = _write_contracts(tmp_path)
    artifact = tmp_path / "soil_v1.nc"
    sidecar = tmp_path / "soil_v1.manifest.json"
    write_soil_artifact(
        artifact,
        sidecar,
        _data(),
        _metadata(grid),
        source_manifest_path=source_manifest,
        grid_contract_path=grid_contract,
    )
    return artifact, sidecar, source_manifest, grid_contract


def _load(
    artifact: Path,
    sidecar: Path,
    source_manifest: Path,
    grid_contract: Path,
    *,
    latitude: np.ndarray = LATITUDE,
    longitude: np.ndarray = LONGITUDE,
) -> xr.Dataset:
    return load_soil_artifact(
        artifact,
        sidecar,
        latitude,
        longitude,
        source_manifest_path=source_manifest,
        grid_contract_path=grid_contract,
    )


def test_writer_and_runtime_loader_round_trip_exact_subset(tmp_path, monkeypatch):
    monkeypatch.delenv("TERN_API_KEY", raising=False)
    artifact, sidecar, source_manifest, grid_contract = _write(tmp_path)

    subset = _load(
        artifact,
        sidecar,
        source_manifest,
        grid_contract,
        latitude=LATITUDE[1:3],
        longitude=LONGITUDE[0:2],
    )

    np.testing.assert_array_equal(subset.latitude, LATITUDE[1:3])
    np.testing.assert_array_equal(subset.longitude, LONGITUDE[0:2])
    assert tuple(str(value) for value in subset.storage_case.values) == STORAGE_CASES
    assert set(subset.data_vars) == {
        "awc_storage_capacity_mm",
        "mapped_prediction_sd_mm",
        "valid_source_area_m2",
        "source_coverage_fraction",
        "full_cell_area_m2",
        "mixed_uncertainty_width_mm",
    }
    assert not any("risk" in name for name in subset.variables)
    assert subset.awc_storage_capacity_mm.dtype == np.dtype("float32")
    assert subset.valid_source_area_m2.dtype == np.dtype("float64")

    document = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar.read_bytes().endswith(b"\n")
    assert document["artifact_contract_version"] == ARTIFACT_CONTRACT_VERSION
    assert document["artifact_version"] == ARTIFACT_VERSION
    assert document["artifact_size_bytes"] == artifact.stat().st_size
    assert document["artifact_sha256"] == sha256_file(artifact)

    with xr.open_dataset(artifact, decode_times=False, mask_and_scale=False) as dataset:
        assert dataset.awc_storage_capacity_mm.encoding["chunksizes"] == (1, 3, 3)
        assert dataset.full_cell_area_m2.encoding["chunksizes"] == (3, 3)
        assert dataset.awc_storage_capacity_mm.encoding["zlib"] is True
        assert dataset.latitude.encoding["zlib"] is False


def test_missing_corrupt_checksum_and_sidecar_version_fail(tmp_path):
    artifact, sidecar, source_manifest, grid_contract = _write(tmp_path)

    with pytest.raises(SoilArtifactError, match="artifact is missing"):
        _load(
            tmp_path / "missing.nc",
            sidecar,
            source_manifest,
            grid_contract,
        )

    original = artifact.read_bytes()
    artifact.write_bytes(original + b"corrupt")
    with pytest.raises(SoilArtifactError, match="size does not match"):
        _load(artifact, sidecar, source_manifest, grid_contract)

    artifact.write_bytes(original)
    document = json.loads(sidecar.read_text(encoding="utf-8"))
    document["artifact_sha256"] = "0" * 64
    sidecar.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(SoilArtifactError, match="SHA-256 does not match"):
        _load(artifact, sidecar, source_manifest, grid_contract)

    document["artifact_sha256"] = sha256_file(artifact)
    document["artifact_version"] = "v2"
    sidecar.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(SoilArtifactError, match="sidecar version mismatch"):
        _load(artifact, sidecar, source_manifest, grid_contract)


def test_schema_and_tracked_contract_drift_fail(tmp_path):
    artifact, sidecar, source_manifest, grid_contract = _write(tmp_path)

    with xr.open_dataset(artifact) as dataset:
        malformed = dataset.drop_vars("mixed_uncertainty_width_mm").load()
    malformed.to_netcdf(artifact)
    document = json.loads(sidecar.read_text(encoding="utf-8"))
    document["artifact_size_bytes"] = artifact.stat().st_size
    document["artifact_sha256"] = sha256_file(artifact)
    sidecar.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(SoilArtifactError, match="data-variable schema mismatch"):
        _load(artifact, sidecar, source_manifest, grid_contract)

    artifact, sidecar, source_manifest, grid_contract = _write(tmp_path / "second")
    source_manifest.write_text(
        '{"manifest_id":"changed","layers":[]}', encoding="utf-8"
    )
    with pytest.raises(SoilArtifactError, match="source-manifest identity mismatch"):
        _load(artifact, sidecar, source_manifest, grid_contract)

    artifact, sidecar, source_manifest, grid_contract = _write(tmp_path / "third")
    grid_contract.write_text(
        grid_contract.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(SoilArtifactError, match="canonical-grid SHA-256 mismatch"):
        _load(artifact, sidecar, source_manifest, grid_contract)


def test_requested_coordinates_must_be_exact_contiguous_and_ordered(tmp_path):
    artifact, sidecar, source_manifest, grid_contract = _write(tmp_path)

    with pytest.raises(SoilArtifactError, match="not an exact contiguous"):
        _load(
            artifact,
            sidecar,
            source_manifest,
            grid_contract,
            latitude=LATITUDE[[0, 2]],
        )
    with pytest.raises(SoilArtifactError, match="not an exact contiguous"):
        _load(
            artifact,
            sidecar,
            source_manifest,
            grid_contract,
            longitude=LONGITUDE[::-1],
        )
    off_grid = LONGITUDE.copy()
    off_grid[1] += 1e-12
    with pytest.raises(SoilArtifactError, match="not an exact contiguous"):
        _load(
            artifact,
            sidecar,
            source_manifest,
            grid_contract,
            longitude=off_grid,
        )


def test_non_utc_retrieval_timestamp_fails_before_writing(tmp_path):
    source_manifest, grid_contract, grid = _write_contracts(tmp_path)
    metadata = ArtifactBuildMetadata(
        canonical_grid=grid,
        creation_timestamp_utc="2026-08-12T08:00:00Z",
        builder_version="test",
        builder_commit="abc",
        source_retrieval_timestamps_utc={
            "AWC_TEST": "2026-08-12T08:00:00+01:00",
            "DES_TEST": "2026-08-12T07:01:00+00:00",
        },
    )

    with pytest.raises(SoilArtifactError, match="must be UTC"):
        write_soil_artifact(
            tmp_path / "soil.nc",
            tmp_path / "soil.json",
            _data(),
            metadata,
            source_manifest_path=source_manifest,
            grid_contract_path=grid_contract,
        )


def test_invalid_values_and_retrieval_identity_fail_before_writing(tmp_path):
    source_manifest, grid_contract, grid = _write_contracts(tmp_path)
    artifact = tmp_path / "soil.nc"
    sidecar = tmp_path / "soil.json"
    data = _data()
    data.source_coverage_fraction[STORAGE_CASES[0]][0, 0] = 1.1
    with pytest.raises(SoilArtifactError, match="coverage"):
        write_soil_artifact(
            artifact,
            sidecar,
            data,
            _metadata(grid),
            source_manifest_path=source_manifest,
            grid_contract_path=grid_contract,
        )
    assert not artifact.exists()
    assert not sidecar.exists()

    metadata = ArtifactBuildMetadata(
        canonical_grid=grid,
        creation_timestamp_utc="2026-08-12T08:00:00Z",
        builder_version="test",
        builder_commit="abc",
        source_retrieval_timestamps_utc={"AWC_TEST": "2026-08-12T07:00:00Z"},
    )
    with pytest.raises(SoilArtifactError, match="timestamps must match"):
        write_soil_artifact(
            artifact,
            sidecar,
            _data(),
            metadata,
            source_manifest_path=source_manifest,
            grid_contract_path=grid_contract,
        )


def test_interrupted_write_leaves_no_final_or_temporary_files(tmp_path, monkeypatch):
    source_manifest, grid_contract, grid = _write_contracts(tmp_path)
    artifact = tmp_path / "soil.nc"
    sidecar = tmp_path / "soil.json"

    def fail_write(*_args, **_kwargs):
        raise OSError("simulated interruption")

    monkeypatch.setattr(xr.Dataset, "to_netcdf", fail_write)
    with pytest.raises(OSError, match="simulated interruption"):
        write_soil_artifact(
            artifact,
            sidecar,
            _data(),
            _metadata(grid),
            source_manifest_path=source_manifest,
            grid_contract_path=grid_contract,
        )

    assert not artifact.exists()
    assert not sidecar.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_sidecar_promotion_failure_removes_promoted_artifact(tmp_path, monkeypatch):
    source_manifest, grid_contract, grid = _write_contracts(tmp_path)
    artifact = tmp_path / "soil.nc"
    sidecar = tmp_path / "soil.json"
    real_replace = artifact_module.os.replace
    calls = 0

    def fail_second_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated sidecar promotion failure")
        return real_replace(source, destination)

    monkeypatch.setattr(artifact_module.os, "replace", fail_second_replace)
    with pytest.raises(OSError, match="sidecar promotion failure"):
        write_soil_artifact(
            artifact,
            sidecar,
            _data(),
            _metadata(grid),
            source_manifest_path=source_manifest,
            grid_contract_path=grid_contract,
        )

    assert not artifact.exists()
    assert not sidecar.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_repeated_writes_are_numerically_reproducible(tmp_path):
    source_manifest, grid_contract, grid = _write_contracts(tmp_path)
    datasets = []
    for directory_name in ("first", "second"):
        directory = tmp_path / directory_name
        artifact = directory / "soil.nc"
        sidecar = directory / "soil.json"
        write_soil_artifact(
            artifact,
            sidecar,
            _data(),
            _metadata(grid),
            source_manifest_path=source_manifest,
            grid_contract_path=grid_contract,
        )
        datasets.append(_load(artifact, sidecar, source_manifest, grid_contract))

    xr.testing.assert_identical(datasets[0], datasets[1])
