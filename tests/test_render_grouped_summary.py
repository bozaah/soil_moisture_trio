import json

import numpy as np

from scripts.render_grouped_summary import render_grouped_summaries
from src.soil_moisture_trio.config import ClassifierConfig
from src.soil_moisture_trio.grouped_summary import save_grouped_summary, summarise_by_group


def _grouped(tmp_path, with_stress: bool, with_raster: bool):
    risk = np.array([[0, 1, 2, 3], [0, 0, -1, 1]], dtype=np.int8)
    stress = np.array([[0.1, 0.4, 0.7, 0.9], [0.2, 0.3, np.nan, 0.5]]) if with_stress else None
    gids = np.array([[1, 1, 2, 2], [1, 1, 2, 2]], dtype=np.int8)
    gvalid = np.ones(risk.shape, dtype=bool)
    gvalid[1, 3] = False
    summary = summarise_by_group(
        risk, stress, risk >= 0, gids, gvalid, ClassifierConfig(), grouping_name="halves",
        group_labels={1: "west", 2: "east"}, title="West versus east halves",
        description="Two halves of a toy grid.", notes=["Synthetic data.", "Second note."],
    )
    grouping = {"lats": np.array([0.0, 1.0]), "lons": np.array([10.0, 11.0, 12.0, 13.0]), "group_ids": gids, "group_valid_mask": gvalid, "risk_valid_mask": risk >= 0} if with_raster else None
    return save_grouped_summary(summary, tmp_path / "risk_test", grouping)["json"]


def test_renders_self_contained_html(tmp_path):
    with_all = _grouped(tmp_path / "a", True, True)
    bare = _grouped(tmp_path / "b", False, False)
    risk_png = tmp_path / "risk.png"
    risk_png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    out = render_grouped_summaries(
        [with_all, bare], tmp_path / "report.html", "Test report", intro="An intro.",
        risk_png=risk_png, diagnostics_png=tmp_path / "missing.png", scope_note="Review input only.",
    )
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert "<script" not in text and 'src="http' not in text and 'href="http' not in text
    assert text.count("<h2>West versus east halves</h2>") == 2
    assert "Two halves of a toy grid." in text and "Second note." in text
    assert "An intro." in text and "Review input only." in text and "How to read this page" in text
    assert "Groups plus uncovered equal the valid cells." in text and "NOT reconciled" not in text
    assert "west (n=4)" in text and "east (n=2)" in text and "uncovered (n=1)" in text
    assert "Stress mean" in text and "has no <code>stress_index</code>" in text
    assert text.count('src="data:image/png;base64,') == 2  # embedded risk PNG + one group map
    assert "Figure not found" in text  # missing diagnostics PNG is reported, not silently dropped
    assert "No grouping raster beside the JSON" in text  # the bare section has no map
    payload = json.loads(with_all.read_text())
    assert payload["denominators"]["category_proportions"] in text


def test_flags_unreconciled_payload(tmp_path):
    path = _grouped(tmp_path, True, False)
    payload = json.loads(path.read_text())
    payload["reconciled"] = False
    path.write_text(json.dumps(payload))
    assert "NOT reconciled" in render_grouped_summaries([path], tmp_path / "r.html", "t").read_text()
