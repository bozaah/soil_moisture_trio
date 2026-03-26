import logging
from typing import Dict, Optional

import folium
import numpy as np

from src.soil_moisture_trio.risk import RISK_COLORS, RISK_LABELS, RISK_SUMMARY_ORDER, RiskLevel

LOGGER = logging.getLogger(__name__)


def _add_summary_panel(map_obj: folium.Map, summary: Dict[str, Dict[str, float]]) -> None:
    """Attach a simple HTML summary panel showing risk counts."""
    rows = []
    for key in [*RISK_SUMMARY_ORDER, "invalid"]:
        if key in summary:
            stats = summary[key]
            rows.append(
                f"<tr><td>{stats['label']}</td><td>{stats['count']}</td><td>{stats['percentage']:.1%}</td></tr>"
            )
    table_html = (
        "<div style='position: fixed; "
        "bottom: 20px; left: 20px; z-index: 9999; background: white; "
        "padding: 10px; border: 1px solid #ccc; box-shadow: 0 2px 6px rgba(0,0,0,0.3);'>"
        "<b>Risk Summary</b>"
        "<table style='margin-top: 5px; font-size: 12px;'>"
        "<tr><th style='text-align:left;'>Level</th><th>Cells</th><th>%</th></tr>"
        f"{''.join(rows)}"
        "</table>"
        "</div>"
    )
    map_obj.get_root().html.add_child(folium.Element(table_html))


def _grid_edges(values: np.ndarray) -> np.ndarray:
    """Convert grid-centre coordinates into cell edges for full-grid rectangle rendering."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1:
        raise ValueError("Grid coordinates must be 1D.")
    if values.size == 0:
        raise ValueError("Grid coordinates cannot be empty.")
    if values.size == 1:
        half_step = 0.05
        return np.array([values[0] - half_step, values[0] + half_step], dtype=float)

    diffs = np.diff(values)
    if np.any(diffs == 0):
        raise ValueError("Grid coordinates must be strictly monotonic.")
    if not (np.all(diffs > 0) or np.all(diffs < 0)):
        raise ValueError("Grid coordinates must be monotonic.")

    midpoints = values[:-1] + (diffs / 2.0)
    first_edge = values[0] - (diffs[0] / 2.0)
    last_edge = values[-1] + (diffs[-1] / 2.0)
    return np.concatenate(([first_edge], midpoints, [last_edge]))


def create_interactive_map(
    risk_map: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    risk_summary: Optional[Dict[str, Dict[str, float]]] = None,
    output_path: str = "risk_map.html",
):
    """
    Generates an interactive HTML map with the categorical risk layer.

    Args:
        risk_map: 2D numpy array of RiskLevel values.
        lats/lons: 1D arrays defining grid-cell centres.
        risk_summary: Optional dictionary of counts/percentages to show on the map.
        output_path: Target HTML filename.
    """
    if not (lats.ndim == 1 and lons.ndim == 1):
        raise ValueError("lats and lons must be 1D arrays.")
    if risk_map.shape != (len(lats), len(lons)):
        raise ValueError("risk_map shape must match (len(lats), len(lons)).")

    center_lat = float(np.mean(lats))
    center_lon = float(np.mean(lons))
    folium_map = folium.Map(location=[center_lat, center_lon], zoom_start=5)
    risk_layer = folium.FeatureGroup(name="Dry/Wet Risk").add_to(folium_map)
    lat_edges = _grid_edges(lats)
    lon_edges = _grid_edges(lons)

    for i in range(len(lats)):
        for j in range(len(lons)):
            lat_min, lat_max = sorted((lat_edges[i], lat_edges[i + 1]))
            lon_min, lon_max = sorted((lon_edges[j], lon_edges[j + 1]))

            raw_level = int(risk_map[i, j])
            if raw_level < 0:
                continue
            level = RiskLevel(raw_level)
            color = RISK_COLORS[level]
            popup_html = f"<b>Risk Level:</b> {RISK_LABELS[level]}"

            folium.Rectangle(
                bounds=[(lat_min, lon_min), (lat_max, lon_max)],
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.55,
                popup=folium.Popup(popup_html, max_width=250),
            ).add_to(risk_layer)

    folium.LayerControl().add_to(folium_map)
    if risk_summary:
        _add_summary_panel(folium_map, risk_summary)
    folium_map.save(output_path)
    LOGGER.info("Interactive risk map saved to %s", output_path)
