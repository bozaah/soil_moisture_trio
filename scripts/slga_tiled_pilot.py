#!/usr/bin/env python3
"""Run a bounded authenticated SLGA tiled pilot without writing an artifact."""

from __future__ import annotations

import argparse
import json
import logging
import resource
import time
from pathlib import Path

import numpy as np

from src.soil_moisture_trio.slga.builder import build_tiled_artifact_data
from src.soil_moisture_trio.slga.catalogue import load_source_catalogue
from src.soil_moisture_trio.slga.cog import AuthenticatedCogReader
from src.soil_moisture_trio.slga.grid import (
    load_canonical_grid,
    select_exact_coordinate_range,
)

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--awral-grid-input", type=Path, required=True)
    parser.add_argument("--latitude-first", type=float, required=True)
    parser.add_argument("--latitude-last", type=float, required=True)
    parser.add_argument("--longitude-first", type=float, required=True)
    parser.add_argument("--longitude-last", type=float, required=True)
    parser.add_argument("--tile-rows", type=int, default=1)
    parser.add_argument("--tile-cols", type=int, default=2)
    parser.add_argument(
        "--tile-order", choices=("row-major", "reverse"), default="row-major"
    )
    parser.add_argument("--cache-mb", type=int, default=256)
    parser.add_argument("--max-target-cells", type=int, default=25)
    parser.add_argument("--verify-opposite-order", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    grid = load_canonical_grid(args.awral_grid_input)
    latitude = select_exact_coordinate_range(
        grid.latitude, args.latitude_first, args.latitude_last, "latitude"
    )
    longitude = select_exact_coordinate_range(
        grid.longitude, args.longitude_first, args.longitude_last, "longitude"
    )
    target_cells = int(latitude.size * longitude.size)
    if target_cells > args.max_target_cells:
        raise ValueError(
            f"Pilot requests {target_cells} target cells, above the safety limit "
            f"{args.max_target_cells}."
        )
    if args.tile_rows <= 0 or args.tile_cols <= 0:
        raise ValueError("Pilot tile dimensions must be positive.")
    if args.cache_mb < 0:
        raise ValueError("Pilot cache size must be non-negative.")

    LOGGER.info(
        "Starting bounded pilot for %d target cells in %dx%d target tiles.",
        target_cells,
        args.tile_rows,
        args.tile_cols,
    )
    catalogue = load_source_catalogue(Path("manifests/slga_awc_des_sources_v1.json"))
    reader = AuthenticatedCogReader(
        catalogue,
        window_cache_max_bytes=args.cache_mb * 1024 * 1024,
    )
    started = time.perf_counter()
    result = build_tiled_artifact_data(
        catalogue,
        reader,
        latitude,
        longitude,
        target_tile_shape=(args.tile_rows, args.tile_cols),
        tile_order=args.tile_order,
    )
    elapsed = time.perf_counter() - started
    data = result.artifact_data
    opposite_order_verification = None
    if args.verify_opposite_order:
        opposite_order = "reverse" if args.tile_order == "row-major" else "row-major"
        verification_started = time.perf_counter()
        verification = build_tiled_artifact_data(
            catalogue,
            reader,
            latitude,
            longitude,
            target_tile_shape=(args.tile_rows, args.tile_cols),
            tile_order=opposite_order,
        )
        _require_exact_artifact_data(data, verification.artifact_data)
        opposite_order_verification = {
            "cache_hits": verification.source_cache_hits - result.source_cache_hits,
            "cache_misses": (
                verification.source_cache_misses - result.source_cache_misses
            ),
            "cog_window_fetches": (
                verification.cog_window_fetches - result.cog_window_fetches
            ),
            "elapsed_seconds": time.perf_counter() - verification_started,
            "exactly_equal": True,
            "tile_order": opposite_order,
        }
    summary = {
        "canonical_grid_contract_id": grid.contract_id,
        "canonical_grid_source_sha256": grid.source_sha256,
        "elapsed_seconds": elapsed,
        "latitude": latitude.tolist(),
        "longitude": longitude.tolist(),
        "max_resident_set_size_platform_units": resource.getrusage(
            resource.RUSAGE_SELF
        ).ru_maxrss,
        "source_cache_bytes": result.source_cache_bytes,
        "source_cache_hits": result.source_cache_hits,
        "source_cache_misses": result.source_cache_misses,
        "source_cog_window_fetches": result.cog_window_fetches,
        "opposite_order_verification": opposite_order_verification,
        "source_manifest_id": catalogue.manifest_id,
        "source_manifest_sha256": catalogue.sha256,
        "source_retrieval_timestamps_utc": dict(
            sorted(result.source_retrieval_timestamps_utc.items())
        ),
        "source_window_reads": result.source_window_reads,
        "storage_cases": {
            case: _finite_summary(values) for case, values in data.storage_mm.items()
        },
        "target_cell_count": target_cells,
        "target_tile_order": args.tile_order,
        "target_tile_shape": [args.tile_rows, args.tile_cols],
        "valid_source_coverage": {
            case: _finite_summary(values)
            for case, values in data.source_coverage_fraction.items()
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    LOGGER.info(
        "Pilot completed in %.2f seconds; summary written to %s.",
        elapsed,
        args.output_json,
    )


def _require_exact_artifact_data(first, second) -> None:
    mappings = (
        (first.storage_mm, second.storage_mm),
        (first.mapped_prediction_sd_mm, second.mapped_prediction_sd_mm),
        (first.valid_source_area_m2, second.valid_source_area_m2),
        (first.source_coverage_fraction, second.source_coverage_fraction),
    )
    for first_mapping, second_mapping in mappings:
        if set(first_mapping) != set(second_mapping):
            raise RuntimeError("Opposite tile order changed artifact variable names.")
        for name in first_mapping:
            if not np.array_equal(
                first_mapping[name], second_mapping[name], equal_nan=True
            ):
                raise RuntimeError(
                    f"Opposite tile order changed artifact values for {name}."
                )
    for name, first_values, second_values in (
        ("full_cell_area_m2", first.full_cell_area_m2, second.full_cell_area_m2),
        (
            "mixed_uncertainty_width_mm",
            first.mixed_uncertainty_width_mm,
            second.mixed_uncertainty_width_mm,
        ),
    ):
        if not np.array_equal(first_values, second_values, equal_nan=True):
            raise RuntimeError(
                f"Opposite tile order changed artifact values for {name}."
            )


def _finite_summary(values: np.ndarray) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return {"finite_count": 0}
    return {
        "finite_count": int(finite.size),
        "maximum": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "minimum": float(np.min(finite)),
    }


if __name__ == "__main__":
    main()
