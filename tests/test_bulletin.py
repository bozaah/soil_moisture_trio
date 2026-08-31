import json

from scripts.render_bulletin import render_bulletin


def test_bulletin_uses_saved_model_metadata(tmp_path) -> None:
    summary_path = tmp_path / "risk_summary.json"
    output_path = tmp_path / "bulletin.md"
    summary_path.write_text(
        json.dumps(
            {
                "summary": {
                    "critical": {"count": 1, "percentage": 0.1, "label": "Critical"},
                    "alert": {"count": 2, "percentage": 0.2, "label": "Alert"},
                    "watch": {"count": 3, "percentage": 0.3, "label": "Watch"},
                    "low": {"count": 4, "percentage": 0.4, "label": "Low"},
                    "valid_cells": {"count": 10, "percentage": 1.0, "label": "Valid"},
                    "invalid": {"count": 0, "percentage": 0.0, "label": "No Data"},
                },
                "time_metadata": {
                    "time_start": "2025-01-01T00:00:00",
                    "time_end": "2025-01-07T00:00:00",
                },
                "model_metadata": {
                    "dryness_weight": 0.5,
                    "vpd_weight": 0.3,
                    "temperature_weight": 0.2,
                    "critical_temp_threshold": 38.0,
                    "critical_vpd_threshold": 30.0,
                    "watch_risk_threshold": 0.25,
                    "alert_risk_threshold": 0.55,
                    "critical_risk_threshold": 0.8,
                },
            }
        ),
        encoding="utf-8",
    )

    render_bulletin(summary_path, None, output_path, region="Test Region")

    bulletin = output_path.read_text(encoding="utf-8")
    assert "soil moisture deficit (50% weight)" in bulletin
    assert "vapour pressure deficit (30%)" in bulletin
    assert "maximum temperature (20%)" in bulletin
    assert "38 °C; 3 kPa VPD" in bulletin
    assert "Critical ≥ 0.8" in bulletin
    assert "Watch 0.25–<0.55" in bulletin
