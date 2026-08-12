import numpy as np

from src.soil_moisture_trio.risk import RiskLevel
from src.soil_moisture_trio.visualize import create_interactive_map


def test_create_interactive_map_renders_all_valid_cells(tmp_path) -> None:
    risk_map = np.array(
        [
            [RiskLevel.LOW, RiskLevel.WATCH, RiskLevel.ALERT],
            [RiskLevel.CRITICAL, -1, RiskLevel.LOW],
            [RiskLevel.WATCH, RiskLevel.ALERT, RiskLevel.CRITICAL],
        ],
        dtype=np.int8,
    )
    lats = np.array([-35.0, -34.0, -33.0])
    lons = np.array([115.0, 116.0, 117.0])
    summary = {
        "critical": {"count": 2, "percentage": 0.25, "label": "Critical"},
        "alert": {"count": 2, "percentage": 0.25, "label": "Alert"},
        "watch": {"count": 2, "percentage": 0.25, "label": "Watch"},
        "low": {"count": 2, "percentage": 0.25, "label": "Low"},
        "invalid": {"count": 1, "percentage": 1 / 9, "label": "No Data"},
    }
    output = tmp_path / "risk_map.html"

    create_interactive_map(risk_map, lats, lons, risk_summary=summary, output_path=str(output))

    html = output.read_text(encoding="utf-8")
    assert html.count("L.rectangle(") == 8
    assert "Critical" in html
    assert "Alert" in html
    assert "Watch" in html
    assert "Low" in html
    assert "No Data" in html
