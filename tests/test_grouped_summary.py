"""B14a grouping-agnostic summaries and the reconciliation invariants."""

import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.grouped_summary import (
    UNCOVERED_KEY,
    grouped_summary_path,
    save_grouped_summary,
    summarise_by_group,
)
from src.soil_moisture_trio.risk import RiskLevel, save_risk_outputs
from src.soil_moisture_trio.slga.artifact import DEFAULT_ARTIFACT_FILENAME, load_soil_context

CONFIG = ClassifierConfig()  # watch 0.35, alert 0.60, critical 0.85


def _fixture():
    # 3 x 4 grid. Row 0 is group 1, row 1 group 2, row 2 group 3 except one uncovered cell.
    risk_map = np.array(
        [
            [RiskLevel.LOW, RiskLevel.WATCH, RiskLevel.ALERT, RiskLevel.CRITICAL],
            [RiskLevel.LOW, RiskLevel.LOW, -1, RiskLevel.WATCH],
            [RiskLevel.ALERT, RiskLevel.ALERT, RiskLevel.CRITICAL, -1],
        ],
        dtype=np.int8,
    )
    stress = np.array(
        [
            [0.10, 0.40, 0.70, 0.90],
            [0.20, 0.30, np.nan, 0.50],
            [0.65, 0.75, 0.95, np.nan],
        ]
    )
    valid = risk_map >= 0
    group_ids = np.array([[1, 1, 1, 1], [2, 2, 2, 2], [3, 3, 3, 3]], dtype=np.int16)
    group_valid = np.ones_like(valid)
    group_valid[2, 0] = False  # a valid risk cell the grouping does not cover
    return risk_map, stress, valid, group_ids, group_valid


def test_hand_computed_groups_and_reconciliation():
    risk_map, stress, valid, gids, gvalid = _fixture()
    out = summarise_by_group(risk_map, stress, valid, gids, gvalid, CONFIG, grouping_name="rows")

    assert out.total_cells == 12
    assert out.risk_valid_cells == 10
    assert out.uncovered_cells == 1
    assert out.summary_cells == 9
    assert out.reconciled is True
    assert out.stress_available is True
    assert [g.group_id for g in out.groups] == [1, 2, 3]

    g1 = out.groups[0]
    assert g1.cell_count == 4
    assert g1.category_counts == {"low": 1, "watch": 1, "alert": 1, "critical": 1}
    assert g1.category_proportions["alert"] == pytest.approx(0.25)
    assert g1.share_of_summary_domain == pytest.approx(4 / 9)
    assert g1.share_of_risk_valid_domain == pytest.approx(4 / 10)
    assert g1.stress["mean"] == pytest.approx(np.mean([0.10, 0.40, 0.70, 0.90]))
    assert g1.stress["min"] == pytest.approx(0.10)
    assert g1.stress["max"] == pytest.approx(0.90)
    assert g1.stress["count_finite"] == 4
    assert g1.share_at_or_above_threshold == {
        "watch": pytest.approx(3 / 4),
        "alert": pytest.approx(2 / 4),
        "critical": pytest.approx(1 / 4),
    }

    g2 = out.groups[1]
    assert g2.cell_count == 3  # the invalid risk cell is excluded
    assert g2.category_counts == {"low": 2, "watch": 1, "alert": 0, "critical": 0}
    assert g2.stress["count_finite"] == 3

    g3 = out.groups[2]
    assert g3.cell_count == 2  # one uncovered, one invalid
    assert g3.category_counts == {"low": 0, "watch": 0, "alert": 1, "critical": 1}

    unc = out.uncovered
    assert unc.label == UNCOVERED_KEY
    assert unc.group_id is None
    assert unc.cell_count == 1
    assert unc.category_counts["alert"] == 1
    assert unc.share_of_summary_domain is None
    assert unc.share_of_risk_valid_domain == pytest.approx(1 / 10)

    assert sum(g.cell_count for g in out.groups) + out.uncovered_cells == out.risk_valid_cells


def test_inputs_are_not_mutated():
    risk_map, stress, valid, gids, gvalid = _fixture()
    copies = [a.copy() for a in (risk_map, stress, valid, gids, gvalid)]
    summarise_by_group(risk_map, stress, valid, gids, gvalid, CONFIG)
    for before, after in zip(copies, (risk_map, stress, valid, gids, gvalid)):
        assert before.tobytes() == after.tobytes()


def test_all_uncovered_and_empty_group_rows():
    risk_map, stress, valid, gids, _ = _fixture()
    out = summarise_by_group(risk_map, stress, valid, gids, np.zeros_like(valid), CONFIG)
    assert out.groups == []
    assert out.summary_cells == 0
    assert out.uncovered_cells == out.risk_valid_cells == 10
    assert out.reconciled is True
    assert out.uncovered.category_counts == {"low": 3, "watch": 2, "alert": 3, "critical": 2}


def test_stress_absent_reports_null_stats():
    risk_map, _, valid, gids, gvalid = _fixture()
    out = summarise_by_group(risk_map, None, valid, gids, gvalid, CONFIG)
    assert out.stress_available is False
    assert out.reconciled is True
    assert out.groups[0].stress == {}
    assert out.groups[0].share_at_or_above_threshold == {"watch": None, "alert": None, "critical": None}
    assert out.groups[0].category_counts["critical"] == 1


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda a: a["gids"].__setitem__(slice(None), a["gids"].astype(float)), "integer"),
        (lambda a: a.update(gids=a["gids"][:, :3]), "shape"),
        (lambda a: a.update(gvalid=a["gvalid"].astype(np.int8)), "boolean"),
        (lambda a: a.update(stress=a["stress"][:2]), "shape"),
    ],
)
def test_rejects_bad_inputs(mutate, message):
    risk_map, stress, valid, gids, gvalid = _fixture()
    args = {"risk_map": risk_map, "stress": stress, "valid": valid, "gids": gids, "gvalid": gvalid}
    if message == "integer":
        args["gids"] = gids.astype(float)
    else:
        mutate(args)
    with pytest.raises(ValueError, match=message):
        summarise_by_group(args["risk_map"], args["stress"], args["valid"], args["gids"], args["gvalid"], CONFIG)


def test_save_grouped_summary_is_a_separate_file(tmp_path):
    risk_map, stress, valid, gids, gvalid = _fixture()
    out = summarise_by_group(risk_map, stress, valid, gids, gvalid, CONFIG, grouping_name="coverage ge 0.5")
    base = tmp_path / "run" / "risk_2026_test"
    path = save_grouped_summary(out, base)
    assert path == tmp_path / "run" / "risk_2026_test_grouped_coverage_ge_0_5.json"
    assert grouped_summary_path(base.with_suffix(".nc"), "x") == tmp_path / "run" / "risk_2026_test_grouped_x.json"
    payload = json.loads(path.read_text())
    assert payload["reconciled"] is True
    assert payload["denominators"]["category_proportions"] == "cell_count of the row"
    assert payload["uncovered"]["label"] == UNCOVERED_KEY
    assert not (tmp_path / "run" / "risk_2026_test_summary.json").exists()


def test_persisting_stress_index_leaves_risk_level_identical(tmp_path):
    risk_map, stress, _, _, _ = _fixture()
    lats = np.array([0.0, 1.0, 2.0])
    lons = np.array([10.0, 11.0, 12.0, 13.0])
    summary = {"total_cells": {"count": 12, "percentage": 1.0, "label": "Total grid cells"}}
    without = save_risk_outputs(risk_map, lats, lons, summary, tmp_path / "a" / "risk")
    with_stress = save_risk_outputs(risk_map, lats, lons, summary, tmp_path / "b" / "risk", stress_index=stress)
    ds_a = xr.load_dataset(without["netcdf"])
    ds_b = xr.load_dataset(with_stress["netcdf"])
    assert "stress_index" not in ds_a
    assert ds_a["risk_level"].values.tobytes() == ds_b["risk_level"].values.tobytes()
    assert ds_b["stress_index"].dtype == np.float32
    np.testing.assert_allclose(ds_b["stress_index"].values, stress.astype(np.float32), equal_nan=True)
    with pytest.raises(ValueError, match="shape"):
        save_risk_outputs(risk_map, lats, lons, summary, tmp_path / "c" / "risk", stress_index=stress[:2])


REAL_BUNDLE = Path("data/processed/slga_awral/slga_awc_des_awral_swaz_0p05deg_v1")
REAL_RISK = Path(
    "outputs/risk_2026_mar_SWAZ_boundary_2026-03-26/risk_2026_mar_SWAZ_boundary_2026-03-26.nc"
)


@pytest.mark.skipif(
    not (REAL_BUNDLE / DEFAULT_ARTIFACT_FILENAME).is_file() or not REAL_RISK.is_file(),
    reason="local SWAZ review bundle and March risk output not present",
)
def test_real_march_run_grouped_by_trivial_coverage_split():
    # A trivial grouping (coverage >= 0.5 or not) over the real bundle. Not a soil band.
    with xr.open_dataset(REAL_RISK) as risk:
        lats = risk.lat.values.copy()
        lons = risk.lon.values.copy()
        risk_map = risk.risk_level.values.copy()
        stress = risk["stress_index"].values.copy() if "stress_index" in risk else None
    valid = risk_map >= 0
    subset = load_soil_context(REAL_BUNDLE, lats, lons)
    coverage = subset["source_coverage_fraction"].isel(storage_case=0).values
    gvalid = np.isfinite(coverage)
    gids = np.where(coverage >= 0.5, 1, 0).astype(np.int8)
    out = summarise_by_group(
        risk_map, stress, valid, gids, gvalid, CONFIG, grouping_name="coverage_ge_0p5",
        group_labels={1: "coverage >= 0.5", 0: "coverage < 0.5"},
    )
    assert out.reconciled is True
    assert out.risk_valid_cells == int(valid.sum())
    assert out.uncovered_cells <= 1
    high = next(g for g in out.groups if g.group_id == 1)
    assert high.share_of_risk_valid_domain > 0.99
    # Category counts across groups plus uncovered equal the run's own summary.
    for level in RiskLevel:
        key = level.name.lower()
        total = sum(g.category_counts[key] for g in out.groups) + out.uncovered.category_counts[key]
        assert total == int(np.count_nonzero(risk_map == level))
