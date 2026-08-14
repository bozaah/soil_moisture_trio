#!/usr/bin/env python3
"""Build the reviewed immutable SWAZ SLGA artifact with resumable stripes."""

from __future__ import annotations

import argparse
import hashlib
import logging
import math
import resource
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from src.soil_moisture_trio.slga.artifact import (
    ARTIFACT_CONTRACT_VERSION,
    ARTIFACT_VERSION,
    DEFAULT_ARTIFACT_FILENAME,
    DEFAULT_SIDECAR_FILENAME,
    ArtifactBuildMetadata,
    write_soil_artifact_bundle,
)
from src.soil_moisture_trio.slga.builder import build_tiled_artifact_data
from src.soil_moisture_trio.slga.catalogue import load_source_catalogue
from src.soil_moisture_trio.slga.checkpoint import (
    combine_stripe_checkpoints,
    load_stripe_checkpoint,
    stripe_checkpoint_path,
    write_stripe_checkpoint,
)
from src.soil_moisture_trio.slga.cog import AuthenticatedCogReader
from src.soil_moisture_trio.slga.grid import (
    DEFAULT_GRID_CONTRACT_PATH,
    load_canonical_grid,
    load_grid_contract,
    select_exact_coordinate_range,
)

LOGGER = logging.getLogger(__name__)
SOURCE_MANIFEST_PATH = Path("manifests/slga_awc_des_sources_v1.json")
DEFAULT_BUNDLE_PATH = Path(
    "data/processed/slga_awral/slga_awc_des_awral_swaz_0p05deg_v1"
)
DEFAULT_CHECKPOINT_PATH = Path(
    "data/processed/slga_awral/.slga_awc_des_awral_swaz_0p05deg_v1.checkpoints"
)
BUILD_REPORT_FILENAME = "build_report.json"
TARGET_TILE_SHAPE = (10, 10)
STRIPE_ROWS = 10
CACHE_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_RUNTIME_SECONDS = 6 * 60 * 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--awral-grid-input", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_PATH)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_PATH)
    parser.add_argument(
        "--max-runtime-seconds",
        type=float,
        default=DEFAULT_MAX_RUNTIME_SECONDS,
        help="Stop after the current completed stripe once this build-work limit is reached.",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse only checksum- and contract-valid completed stripe checkpoints.",
    )
    parser.add_argument(
        "--keep-checkpoints",
        action="store_true",
        help="Retain verified stripe checkpoints after successful bundle publication.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not math.isfinite(args.max_runtime_seconds) or args.max_runtime_seconds <= 0:
        raise ValueError("--max-runtime-seconds must be finite and positive.")
    if args.bundle_dir.exists():
        raise FileExistsError(f"Immutable bundle already exists: {args.bundle_dir}")
    if args.checkpoint_dir.exists() and not args.resume:
        raise FileExistsError(
            f"Checkpoint directory exists but resume is disabled: {args.checkpoint_dir}"
        )

    builder_commit = _require_clean_git_commit()
    builder_version = version("soil-moisture-trio")
    grid = load_canonical_grid(args.awral_grid_input)
    grid_contract = load_grid_contract(DEFAULT_GRID_CONTRACT_PATH)
    footprint = _approved_footprint(grid_contract)
    latitude = select_exact_coordinate_range(
        grid.latitude,
        footprint["latitude_first"],
        footprint["latitude_last"],
        "latitude",
    )
    longitude = select_exact_coordinate_range(
        grid.longitude,
        footprint["longitude_first"],
        footprint["longitude_last"],
        "longitude",
    )
    if latitude.size * longitude.size != footprint["cell_count"]:
        raise ValueError("Approved SWAZ artifact footprint cell count mismatch.")

    catalogue = load_source_catalogue(SOURCE_MANIFEST_PATH)
    identity = _checkpoint_identity(
        grid,
        catalogue,
        latitude,
        longitude,
        builder_version,
        builder_commit,
    )
    stripe_ranges = [
        (start, min(start + STRIPE_ROWS, latitude.size))
        for start in range(0, latitude.size, STRIPE_ROWS)
    ]
    _reject_unknown_checkpoint_entries(args.checkpoint_dir, len(stripe_ranges))
    reader = AuthenticatedCogReader(catalogue, window_cache_max_bytes=CACHE_BYTES)
    checkpoints = []
    build_started = time.perf_counter()

    for stripe_index, (row_start, row_stop) in enumerate(stripe_ranges):
        stripe_latitude = latitude[row_start:row_stop]
        checkpoint_path = stripe_checkpoint_path(args.checkpoint_dir, stripe_index)
        if checkpoint_path.exists():
            checkpoint = load_stripe_checkpoint(
                checkpoint_path,
                expected_index=stripe_index,
                expected_identity=identity,
                expected_latitude=stripe_latitude,
                expected_longitude=longitude,
            )
            LOGGER.info(
                "Resumed verified stripe %d/%d (rows %d:%d).",
                stripe_index + 1,
                len(stripe_ranges),
                row_start,
                row_stop,
            )
        else:
            _require_runtime_remaining(
                build_started,
                args.max_runtime_seconds,
                stripe_index,
                len(stripe_ranges),
            )
            stripe_started = time.perf_counter()
            result = build_tiled_artifact_data(
                catalogue,
                reader,
                stripe_latitude,
                longitude,
                target_tile_shape=TARGET_TILE_SHAPE,
            )
            provenance = {
                "build_elapsed_seconds": time.perf_counter() - stripe_started,
                "reader_counter_delta": dict(result.reader_counter_delta),
                "reader_metrics_after": asdict(result.reader_metrics_after),
                "source_retrieval_timestamps_utc": dict(
                    sorted(result.source_retrieval_timestamps_utc.items())
                ),
                "source_window_reads": result.source_window_reads,
                "stripe_row_start": row_start,
                "stripe_row_stop": row_stop,
                "tile_metrics": [asdict(metric) for metric in result.tile_metrics],
            }
            checkpoint = write_stripe_checkpoint(
                args.checkpoint_dir,
                stripe_index,
                result.artifact_data,
                identity=identity,
                provenance=provenance,
            )
            LOGGER.info(
                "Completed and checkpointed stripe %d/%d in %.2f seconds.",
                stripe_index + 1,
                len(stripe_ranges),
                provenance["build_elapsed_seconds"],
            )
        checkpoints.append(checkpoint)
        if stripe_index < len(stripe_ranges) - 1:
            _require_runtime_remaining(
                build_started,
                args.max_runtime_seconds,
                stripe_index + 1,
                len(stripe_ranges),
            )

    artifact_data = combine_stripe_checkpoints(
        checkpoints,
        expected_latitude=latitude,
        expected_longitude=longitude,
    )
    retrieval_timestamps = _combined_retrieval_timestamps(checkpoints, catalogue.layers)
    creation_timestamp = datetime.now(timezone.utc).isoformat()
    report = _build_report(
        checkpoints,
        identity,
        latitude,
        longitude,
        args,
        build_started,
        creation_timestamp,
    )
    metadata = ArtifactBuildMetadata(
        canonical_grid=grid,
        creation_timestamp_utc=creation_timestamp,
        builder_version=builder_version,
        builder_commit=builder_commit,
        source_retrieval_timestamps_utc=retrieval_timestamps,
    )
    sidecar = write_soil_artifact_bundle(
        args.bundle_dir,
        artifact_data,
        metadata,
        artifact_filename=DEFAULT_ARTIFACT_FILENAME,
        sidecar_filename=DEFAULT_SIDECAR_FILENAME,
        additional_json_files={BUILD_REPORT_FILENAME: report},
        source_manifest_path=SOURCE_MANIFEST_PATH,
        grid_contract_path=DEFAULT_GRID_CONTRACT_PATH,
    )
    LOGGER.info(
        "Published immutable review bundle %s (artifact SHA-256 %s).",
        args.bundle_dir,
        sidecar["artifact_sha256"],
    )
    if not args.keep_checkpoints:
        _remove_completed_checkpoints(args.checkpoint_dir, len(stripe_ranges))
        LOGGER.info("Removed completed stripe checkpoints after verified publication.")


def _approved_footprint(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    coordinate_contract = contract.get("coordinate_contract")
    if not isinstance(coordinate_contract, dict):
        raise ValueError("Canonical-grid coordinate contract is malformed.")
    footprint = coordinate_contract.get("approved_swaz_artifact_footprint")
    required = {
        "latitude_first",
        "latitude_last",
        "latitude_length",
        "longitude_first",
        "longitude_last",
        "longitude_length",
        "cell_count",
    }
    if not isinstance(footprint, dict) or not required.issubset(footprint):
        raise ValueError("Approved SWAZ artifact footprint is malformed.")
    return footprint


def _checkpoint_identity(
    grid,
    catalogue,
    latitude: np.ndarray,
    longitude: np.ndarray,
    builder_version: str,
    builder_commit: str,
) -> dict[str, Any]:
    return {
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "builder_commit": builder_commit,
        "builder_version": builder_version,
        "cache_max_bytes": CACHE_BYTES,
        "canonical_grid_contract_id": grid.contract_id,
        "canonical_grid_contract_sha256": grid.contract_sha256,
        "canonical_grid_source_sha256": grid.source_sha256,
        "latitude_sha256": _coordinate_sha256(latitude),
        "longitude_sha256": _coordinate_sha256(longitude),
        "source_manifest_id": catalogue.manifest_id,
        "source_manifest_sha256": catalogue.sha256,
        "stripe_rows": STRIPE_ROWS,
        "target_tile_shape": list(TARGET_TILE_SHAPE),
    }


def _coordinate_sha256(values: np.ndarray) -> str:
    return hashlib.sha256(
        np.asarray(values, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _require_clean_git_commit() -> str:
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            check=True,
            capture_output=True,
            text=True,
            cwd=root,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Production build requires a readable Git worktree."
        ) from exc
    if status.strip():
        raise RuntimeError(
            "Production build requires a clean Git worktree so builder_commit identifies the exact code."
        )
    if len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        raise RuntimeError("Git HEAD is not a full lowercase SHA-1 commit ID.")
    return commit


def _reject_unknown_checkpoint_entries(root: Path, stripe_count: int) -> None:
    checkpoint_root = Path(root)
    if not checkpoint_root.exists():
        return
    allowed = {
        stripe_checkpoint_path(checkpoint_root, index).name
        for index in range(stripe_count)
    }
    unknown = {entry.name for entry in checkpoint_root.iterdir()} - allowed
    if unknown:
        raise RuntimeError(
            f"Checkpoint directory contains unexpected entries: {sorted(unknown)}"
        )


def _require_runtime_remaining(
    started: float,
    maximum_seconds: float,
    completed_stripes: int,
    total_stripes: int,
) -> None:
    elapsed = time.perf_counter() - started
    if elapsed >= maximum_seconds:
        raise TimeoutError(
            f"SWAZ build runtime limit reached after {completed_stripes}/{total_stripes} "
            "stripes; verified checkpoints are retained for resume."
        )


def _combined_retrieval_timestamps(
    checkpoints,
    expected_product_ids: Mapping[str, Any],
) -> dict[str, str]:
    combined: dict[str, str] = {}
    expected = set(expected_product_ids)
    for checkpoint in checkpoints:
        timestamps = checkpoint.provenance.get("source_retrieval_timestamps_utc")
        if not isinstance(timestamps, dict) or set(timestamps) != expected:
            raise RuntimeError(
                "Stripe retrieval timestamps do not match source identity."
            )
        for product_id, timestamp in timestamps.items():
            if not isinstance(timestamp, str) or not timestamp:
                raise RuntimeError("Stripe retrieval timestamp is malformed.")
            combined[product_id] = min(timestamp, combined.get(product_id, timestamp))
    return dict(sorted(combined.items()))


def _build_report(
    checkpoints,
    identity: Mapping[str, Any],
    latitude: np.ndarray,
    longitude: np.ndarray,
    args: argparse.Namespace,
    started: float,
    creation_timestamp: str,
) -> dict[str, Any]:
    counter_totals: dict[str, int] = {}
    stripe_reports = []
    for checkpoint in sorted(checkpoints, key=lambda item: item.stripe_index):
        provenance = dict(checkpoint.provenance)
        counters = provenance.get("reader_counter_delta", {})
        if not isinstance(counters, dict):
            raise RuntimeError("Stripe reader counters are malformed.")
        for name, value in counters.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise RuntimeError("Stripe reader counter is malformed.")
            counter_totals[name] = counter_totals.get(name, 0) + value
        stripe_reports.append(
            {
                "provenance": provenance,
                "stripe_index": checkpoint.stripe_index,
            }
        )
    return {
        "artifact_scope": "SWAZ buffered operational rectangle",
        "build_completed_utc": creation_timestamp,
        "build_identity": dict(identity),
        "build_work_elapsed_seconds": time.perf_counter() - started,
        "checkpoint_count": len(checkpoints),
        "checkpoint_policy": {
            "keep_after_success": bool(args.keep_checkpoints),
            "resume_enabled": bool(args.resume),
            "stripe_rows": STRIPE_ROWS,
        },
        "http_transfer_bytes": None,
        "http_transfer_bytes_status": (
            "unavailable by approved Release 1 decision; audited attempt/fetch/cache counters retained"
        ),
        "latitude_first": float(latitude[0]),
        "latitude_last": float(latitude[-1]),
        "longitude_first": float(longitude[0]),
        "longitude_last": float(longitude[-1]),
        "process_peak_rss": _process_peak_rss_metrics(),
        "reader_counter_totals": dict(sorted(counter_totals.items())),
        "source_hash_policy": (
            "pinned publisher STAC multihashes plus strict live identity/profile validation"
        ),
        "stripe_reports": stripe_reports,
        "target_cell_count": int(latitude.size * longitude.size),
        "target_tile_shape": list(TARGET_TILE_SHAPE),
    }


def _process_peak_rss_metrics() -> dict[str, int | str | None]:
    raw_value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        bytes_value, raw_units = raw_value, "bytes"
    elif sys.platform.startswith("linux"):
        bytes_value, raw_units = raw_value * 1024, "KiB"
    else:
        bytes_value, raw_units = None, "platform-dependent units"
    return {
        "bytes": bytes_value,
        "raw_ru_maxrss": raw_value,
        "raw_units": raw_units,
        "scope": "process lifetime high-water mark, sampled before bundle writing",
    }


def _remove_completed_checkpoints(root: Path, stripe_count: int) -> None:
    checkpoint_root = Path(root)
    for index in range(stripe_count):
        shutil.rmtree(
            stripe_checkpoint_path(checkpoint_root, index), ignore_errors=False
        )
    try:
        checkpoint_root.rmdir()
    except OSError:
        LOGGER.warning(
            "Checkpoint root was not empty after completed stripes were removed: %s",
            checkpoint_root,
        )


if __name__ == "__main__":
    main()
