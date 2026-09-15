import json

import numpy as np

from scripts.render_grouped_summary import render_grouped_summaries
from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.grouped_summary import save_grouped_summary, summarise_by_group


def _grouped_json(tmp_path, with_stress: bool):
    risk = np.array([[0, 1, 2, 3], [0, 0, -1, 1]], dtype=np.int8)
    stress = np.array([[0.1, 0.4, 0.7, 0.9], [0.2, 0.3, np.nan, 0.5]]) if with_stress else None
    gids = np.array([[1, 1, 2, 2], [1, 1, 2, 2]], dtype=np.int8)
    gvalid = np.ones(risk.shape, dtype=bool)
    gvalid[1, 3] = False
    summary = summarise_by_group(
        risk, stress, risk >= 0, gids, gvalid, ClassifierConfig(), grouping_name="halves", group_labels={1: "west", 2: "east"}
    )
    return save_grouped_summary(summary, tmp_path / "risk_test")


def test_renders_self_contained_html_with_and_without_stress(tmp_path):
    with_stress = _grouped_json(tmp_path / "a", True)
    without = _grouped_json(tmp_path / "b", False)
    out = render_grouped_summaries([with_stress, without], tmp_path / "report.html", "Test report")
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert "<script" not in text and 'src="http' not in text and 'href="http' not in text
    assert text.count("<h2>Grouping: halves</h2>") == 2
    assert "reconciled: groups + uncovered" in text
    assert "NOT reconciled" not in text
    assert "west (n=4)" in text and "east (n=2)" in text and "uncovered (n=1)" in text
    assert "Stress mean" in text  # first section has stress
    assert "No <code>stress_index</code>" in text  # second section says so
    payload = json.loads(with_stress.read_text())
    assert payload["denominators"]["category_proportions"] in text


def test_flags_unreconciled_payload(tmp_path):
    path = _grouped_json(tmp_path, True)
    payload = json.loads(path.read_text())
    payload["reconciled"] = False
    path.write_text(json.dumps(payload))
    text = render_grouped_summaries([path], tmp_path / "r.html", "t").read_text()
    assert "NOT reconciled" in text
