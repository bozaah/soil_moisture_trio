from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import src.soil_moisture_trio.slga.checkpoint as checkpoint_module
from src.soil_moisture_trio.slga.artifact import (
    DES_COMPONENTS,
    STORAGE_CASES,
    SoilArtifactData,
)
from src.soil_moisture_trio.slga.checkpoint import (
    StripeCheckpointError,
    combine_stripe_checkpoints,
    load_stripe_checkpoint,
    stripe_checkpoint_path,
    write_stripe_checkpoint,
)

LATITUDE = np.array([-30.0, -30.05, -30.10, -30.15])
LONGITUDE = np.array([115.0, 115.05, 115.10])
IDENTITY = {
    "artifact_contract_version": "test-v1",
    "builder_commit": "a" * 40,
    "target_tile_shape": [10, 10],
}


def _full_data() -> SoilArtifactData:
    shape = (LATITUDE.size, LONGITUDE.size)
    base = np.arange(np.prod(shape), dtype=np.float64).reshape(shape)
    storage = {case: base + index for index, case in enumerate(STORAGE_CASES)}
    storage_sd = {case: base / 100 for case in STORAGE_CASES}
    storage_area = {case: np.full(shape, 80.0) for case in STORAGE_CASES}
    storage_coverage = {case: np.full(shape, 0.8) for case in STORAGE_CASES}
    des = {
        component: base / 10 + index for index, component in enumerate(DES_COMPONENTS)
    }
    des_sd = {component: base / 1000 for component in DES_COMPONENTS}
    des_area = {component: np.full(shape, 80.0) for component in DES_COMPONENTS}
    des_coverage = {component: np.full(shape, 0.8) for component in DES_COMPONENTS}
    des_shallow = {component: np.full(shape, 0.5) for component in DES_COMPONENTS}
    return SoilArtifactData(
        latitude=LATITUDE,
        longitude=LONGITUDE,
        storage_mm=storage,
        mapped_prediction_sd_mm=storage_sd,
        valid_source_area_m2=storage_area,
        source_coverage_fraction=storage_coverage,
        full_cell_area_m2=np.full(shape, 100.0),
        mixed_uncertainty_width_mm=base + 20,
        mixed_uncertainty_width_mapped_prediction_sd_mm=base / 100,
        mixed_uncertainty_width_valid_source_area_m2=np.full(shape, 80.0),
        mixed_uncertainty_width_source_coverage_fraction=np.full(shape, 0.8),
        depth_of_soil_m=des,
        depth_of_soil_mapped_prediction_sd_m=des_sd,
        depth_of_soil_valid_source_area_m2=des_area,
        depth_of_soil_source_coverage_fraction=des_coverage,
        depth_of_soil_shallower_than_1m_fraction=des_shallow,
    )


def _stripe(data: SoilArtifactData, row_slice: slice) -> SoilArtifactData:
    def sliced(mapping):
        return {key: values[row_slice].copy() for key, values in mapping.items()}

    return replace(
        data,
        latitude=data.latitude[row_slice].copy(),
        storage_mm=sliced(data.storage_mm),
        mapped_prediction_sd_mm=sliced(data.mapped_prediction_sd_mm),
        valid_source_area_m2=sliced(data.valid_source_area_m2),
        source_coverage_fraction=sliced(data.source_coverage_fraction),
        full_cell_area_m2=data.full_cell_area_m2[row_slice].copy(),
        mixed_uncertainty_width_mm=data.mixed_uncertainty_width_mm[row_slice].copy(),
        mixed_uncertainty_width_mapped_prediction_sd_mm=(
            data.mixed_uncertainty_width_mapped_prediction_sd_mm[row_slice].copy()
        ),
        mixed_uncertainty_width_valid_source_area_m2=(
            data.mixed_uncertainty_width_valid_source_area_m2[row_slice].copy()
        ),
        mixed_uncertainty_width_source_coverage_fraction=(
            data.mixed_uncertainty_width_source_coverage_fraction[row_slice].copy()
        ),
        depth_of_soil_m=sliced(data.depth_of_soil_m),
        depth_of_soil_mapped_prediction_sd_m=sliced(
            data.depth_of_soil_mapped_prediction_sd_m
        ),
        depth_of_soil_valid_source_area_m2=sliced(
            data.depth_of_soil_valid_source_area_m2
        ),
        depth_of_soil_source_coverage_fraction=sliced(
            data.depth_of_soil_source_coverage_fraction
        ),
        depth_of_soil_shallower_than_1m_fraction=sliced(
            data.depth_of_soil_shallower_than_1m_fraction
        ),
    )


def test_checkpoint_round_trip_and_stripe_assembly(tmp_path):
    full = _full_data()
    checkpoints = []
    for index, row_slice in enumerate((slice(0, 2), slice(2, 4))):
        stripe = _stripe(full, row_slice)
        checkpoints.append(
            write_stripe_checkpoint(
                tmp_path,
                index,
                stripe,
                identity=IDENTITY,
                provenance={"source_window_reads": 18},
            )
        )

    combined = combine_stripe_checkpoints(
        checkpoints,
        expected_latitude=LATITUDE,
        expected_longitude=LONGITUDE,
    )

    np.testing.assert_array_equal(combined.latitude, full.latitude)
    np.testing.assert_array_equal(combined.storage_mm["ev"], full.storage_mm["ev"])
    np.testing.assert_array_equal(
        combined.depth_of_soil_m["90"], full.depth_of_soil_m["90"]
    )
    np.testing.assert_array_equal(
        combined.mixed_uncertainty_width_source_coverage_fraction,
        full.mixed_uncertainty_width_source_coverage_fraction,
    )


def test_checkpoint_rejects_identity_coordinate_and_checksum_drift(tmp_path):
    stripe = _stripe(_full_data(), slice(0, 2))
    write_stripe_checkpoint(
        tmp_path,
        0,
        stripe,
        identity=IDENTITY,
        provenance={"source_window_reads": 18},
    )
    path = stripe_checkpoint_path(tmp_path, 0)

    with pytest.raises(StripeCheckpointError, match="identity mismatch"):
        load_stripe_checkpoint(
            path,
            expected_index=0,
            expected_identity={**IDENTITY, "builder_commit": "b" * 40},
            expected_latitude=stripe.latitude,
            expected_longitude=stripe.longitude,
        )
    with pytest.raises(StripeCheckpointError, match="coordinates mismatch"):
        load_stripe_checkpoint(
            path,
            expected_index=0,
            expected_identity=IDENTITY,
            expected_latitude=stripe.latitude + 1e-12,
            expected_longitude=stripe.longitude,
        )

    data_path = path / checkpoint_module.CHECKPOINT_DATA_FILENAME
    data_path.write_bytes(data_path.read_bytes() + b"corrupt")
    with pytest.raises(StripeCheckpointError, match="data size mismatch"):
        load_stripe_checkpoint(
            path,
            expected_index=0,
            expected_identity=IDENTITY,
            expected_latitude=stripe.latitude,
            expected_longitude=stripe.longitude,
        )


def test_failed_checkpoint_promotion_cleans_staging(tmp_path, monkeypatch):
    stripe = _stripe(_full_data(), slice(0, 2))

    def fail_rename(*_args):
        raise OSError("simulated checkpoint promotion failure")

    monkeypatch.setattr(checkpoint_module.os, "rename", fail_rename)
    with pytest.raises(OSError, match="checkpoint promotion failure"):
        write_stripe_checkpoint(
            tmp_path,
            0,
            stripe,
            identity=IDENTITY,
            provenance={"source_window_reads": 18},
        )

    assert not stripe_checkpoint_path(tmp_path, 0).exists()
    assert not list(Path(tmp_path).glob(".*.staging"))
