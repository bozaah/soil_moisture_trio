"""Grouping-agnostic summaries of existing risk outputs (B14a structure).

Aggregates a finished risk run by any integer grouping raster on the same grid.
It never reclassifies, never edits the inputs, and reports every proportion with
its denominator named. The grouping and its validity mask are inputs: deriving
them (soil bands, coverage thresholds, polygons) is the caller's job.

Invariant (docs/architecture.md, Phase 5):

    summary_mask = risk_valid_mask & group_valid_mask

Cells in ``risk_valid_mask`` but not in ``group_valid_mask`` are reported as one
``uncovered`` row so that group counts plus uncovered equal the risk-valid domain.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.risk import RISK_LABELS, RiskLevel

UNCOVERED_KEY = "uncovered"
STRESS_QUANTILES = {"p10": 0.10, "median": 0.50, "p90": 0.90}


@dataclass(frozen=True)
class GroupRow:
    group_id: Optional[int]
    label: str
    cell_count: int
    share_of_summary_domain: Optional[float]
    share_of_risk_valid_domain: float
    category_counts: Dict[str, int]
    category_proportions: Dict[str, Optional[float]]
    share_at_or_above_threshold: Dict[str, Optional[float]]
    stress: Dict[str, Optional[float]]


@dataclass(frozen=True)
class GroupedSummary:
    grouping_name: str
    total_cells: int
    risk_valid_cells: int
    summary_cells: int
    uncovered_cells: int
    reconciled: bool
    denominators: Dict[str, str]
    thresholds: Dict[str, float]
    stress_available: bool
    groups: List[GroupRow] = field(default_factory=list)
    uncovered: Optional[GroupRow] = None

    def to_dict(self) -> Dict:
        return asdict(self)


def _validate(
    risk_map: np.ndarray,
    stress_index: Optional[np.ndarray],
    risk_valid_mask: np.ndarray,
    group_ids: np.ndarray,
    group_valid_mask: np.ndarray,
) -> None:
    shape = risk_map.shape
    if risk_map.ndim != 2:
        raise ValueError(f"risk_map must be 2D, got shape {shape}")
    for name, arr in (
        ("risk_valid_mask", risk_valid_mask),
        ("group_ids", group_ids),
        ("group_valid_mask", group_valid_mask),
    ):
        if arr.shape != shape:
            raise ValueError(f"{name} shape {arr.shape} does not match risk_map shape {shape}")
    if stress_index is not None and stress_index.shape != shape:
        raise ValueError(f"stress_index shape {stress_index.shape} does not match risk_map shape {shape}")
    if not np.issubdtype(group_ids.dtype, np.integer):
        raise ValueError(f"group_ids must be an integer array, got dtype {group_ids.dtype}")
    if risk_valid_mask.dtype != bool or group_valid_mask.dtype != bool:
        raise ValueError("risk_valid_mask and group_valid_mask must be boolean arrays")


def _stress_stats(values: np.ndarray, config: ClassifierConfig) -> Dict[str, Optional[float]]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        keys = ["count_finite", "mean", "min", "max", *STRESS_QUANTILES]
        return {k: (0 if k == "count_finite" else None) for k in keys}
    stats: Dict[str, Optional[float]] = {
        "count_finite": int(finite.size),
        "mean": float(np.mean(finite)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
    }
    for key, q in STRESS_QUANTILES.items():
        stats[key] = float(np.quantile(finite, q))
    return stats


def _share_above(values: Optional[np.ndarray], count: int, config: ClassifierConfig) -> Dict[str, Optional[float]]:
    thresholds = {
        "watch": config.watch_risk_threshold,
        "alert": config.alert_risk_threshold,
        "critical": config.critical_risk_threshold,
    }
    if values is None or count == 0:
        return {k: None for k in thresholds}
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {k: None for k in thresholds}
    return {k: float(np.mean(finite >= t)) for k, t in thresholds.items()}


def _row(
    group_id: Optional[int],
    label: str,
    cell_mask: np.ndarray,
    risk_map: np.ndarray,
    stress_index: Optional[np.ndarray],
    summary_cells: int,
    risk_valid_cells: int,
    config: ClassifierConfig,
) -> GroupRow:
    count = int(np.count_nonzero(cell_mask))
    levels = risk_map[cell_mask]
    counts = {level.name.lower(): int(np.count_nonzero(levels == level)) for level in RiskLevel}
    proportions = {k: (v / count if count else None) for k, v in counts.items()}
    stress_values = stress_index[cell_mask] if stress_index is not None else None
    return GroupRow(
        group_id=group_id,
        label=label,
        cell_count=count,
        share_of_summary_domain=(count / summary_cells if summary_cells and group_id is not None else None),
        share_of_risk_valid_domain=(count / risk_valid_cells if risk_valid_cells else 0.0),
        category_counts=counts,
        category_proportions=proportions,
        share_at_or_above_threshold=_share_above(stress_values, count, config),
        stress=(_stress_stats(stress_values, config) if stress_values is not None else {}),
    )


def summarise_by_group(
    risk_map: np.ndarray,
    stress_index: Optional[np.ndarray],
    risk_valid_mask: np.ndarray,
    group_ids: np.ndarray,
    group_valid_mask: np.ndarray,
    config: ClassifierConfig,
    grouping_name: str = "group",
    group_labels: Optional[Dict[int, str]] = None,
) -> GroupedSummary:
    """Summarise an existing risk run by an integer grouping raster.

    Args:
        risk_map: RiskLevel values per cell, negative where invalid.
        stress_index: continuous stress per cell, NaN where invalid. ``None`` when a
            saved run predates the persisted ``stress_index`` variable; stress
            statistics and threshold shares are then reported as null.
        risk_valid_mask: the run's own valid mask. Not recomputed here.
        group_ids: integer labels on the same grid. Values outside
            ``group_valid_mask`` are ignored.
        group_valid_mask: where the grouping is usable (for soil: the approved
            coverage rule). Supplied by the caller, never derived here.
        config: supplies the risk-band thresholds for the threshold shares.

    Inputs are read only. The result reconciles group counts plus uncovered
    cells to ``risk_valid_mask`` and records whether that held.
    """
    risk_map = np.asarray(risk_map)
    risk_valid_mask = np.asarray(risk_valid_mask)
    group_ids = np.asarray(group_ids)
    group_valid_mask = np.asarray(group_valid_mask)
    stress_arr = None if stress_index is None else np.asarray(stress_index, dtype=float)
    _validate(risk_map, stress_arr, risk_valid_mask, group_ids, group_valid_mask)

    summary_mask = risk_valid_mask & group_valid_mask
    uncovered_mask = risk_valid_mask & ~group_valid_mask
    risk_valid_cells = int(np.count_nonzero(risk_valid_mask))
    summary_cells = int(np.count_nonzero(summary_mask))
    uncovered_cells = int(np.count_nonzero(uncovered_mask))
    labels = group_labels or {}

    rows: List[GroupRow] = []
    for gid in np.unique(group_ids[summary_mask]):
        gid_int = int(gid)
        rows.append(
            _row(
                gid_int,
                labels.get(gid_int, str(gid_int)),
                summary_mask & (group_ids == gid),
                risk_map,
                stress_arr,
                summary_cells,
                risk_valid_cells,
                config,
            )
        )
    uncovered_row = _row(
        None, UNCOVERED_KEY, uncovered_mask, risk_map, stress_arr, summary_cells, risk_valid_cells, config
    )
    grouped_total = sum(r.cell_count for r in rows)
    reconciled = grouped_total + uncovered_cells == risk_valid_cells and grouped_total == summary_cells

    return GroupedSummary(
        grouping_name=grouping_name,
        total_cells=int(risk_map.size),
        risk_valid_cells=risk_valid_cells,
        summary_cells=summary_cells,
        uncovered_cells=uncovered_cells,
        reconciled=bool(reconciled),
        denominators={
            "share_of_summary_domain": "summary_cells (risk_valid & group_valid)",
            "share_of_risk_valid_domain": "risk_valid_cells",
            "category_proportions": "cell_count of the row",
            "share_at_or_above_threshold": "cells in the row with finite stress_index",
            "stress": "cells in the row with finite stress_index",
        },
        thresholds={
            "watch": config.watch_risk_threshold,
            "alert": config.alert_risk_threshold,
            "critical": config.critical_risk_threshold,
        },
        stress_available=stress_arr is not None,
        groups=rows,
        uncovered=uncovered_row,
    )


def grouped_summary_path(base_path: Union[str, Path], grouping_name: str) -> Path:
    """``<run>_grouped_<name>.json`` beside the run's existing outputs."""
    base = Path(base_path).expanduser()
    stem = base.stem if base.suffix else base.name
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in grouping_name)
    return base.with_name(f"{stem}_grouped_{safe}.json")


def save_grouped_summary(summary: GroupedSummary, base_path: Union[str, Path]) -> Path:
    path = grouped_summary_path(base_path, summary.grouping_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(summary.to_dict(), fp, indent=2)
    return path


__all__ = [
    "GroupRow",
    "GroupedSummary",
    "RISK_LABELS",
    "UNCOVERED_KEY",
    "grouped_summary_path",
    "save_grouped_summary",
    "summarise_by_group",
]
