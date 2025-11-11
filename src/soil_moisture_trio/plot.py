from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")  # Ensure headless rendering
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap

from src.soil_moisture_trio.risk import RISK_COLORS, RISK_LABELS, RiskLevel


def save_risk_plot(
    risk_map: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    output_path: str = "risk_map.png",
    time_metadata: Optional[Dict[str, str]] = None,
) -> Path:
    """
    Render a PNG heatmap of the risk layer with readable labels.

    Args:
        risk_map: 2D numpy array of RiskLevel values.
        lats/lons: 1D coordinate arrays that align with the grid.
        output_path: Path for the PNG file.

    Returns:
        Path to the written PNG file.
    """
    risk_map = np.asarray(risk_map)
    lats = np.asarray(lats)
    lons = np.asarray(lons)

    if risk_map.shape != (len(lats), len(lons)):
        raise ValueError("Risk map shape must match (len(lats), len(lons)).")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    colors = [RISK_COLORS[level] for level in RiskLevel]
    cmap = ListedColormap(colors)
    cmap.set_bad("#bdbdbd")
    bounds = np.arange(len(RiskLevel) + 1) - 0.5
    norm = BoundaryNorm(bounds, cmap.N)

    lon_extent = float(np.max(lons) - np.min(lons))
    lat_extent = float(np.max(lats) - np.min(lats))
    base_height = 6
    aspect = lon_extent / (lat_extent or 1)
    aspect = min(max(aspect, 0.75), 2.5)
    fig_width = base_height * aspect

    fig, ax = plt.subplots(figsize=(fig_width + 2.5, base_height), constrained_layout=False)
    risk_display = np.ma.masked_less(risk_map, 0)
    ax.pcolormesh(
        lons,
        lats,
        risk_display,
        cmap=cmap,
        norm=norm,
        shading="nearest",
    )
    ax.set_xlim(np.min(lons), np.max(lons))
    ax.set_ylim(np.min(lats), np.max(lats))
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Longitude", fontsize=12)
    ax.set_ylabel("Latitude", fontsize=12)
    if time_metadata and time_metadata.get("time_start") and time_metadata.get("time_end"):
        title = _format_title_with_dates(time_metadata["time_start"], time_metadata["time_end"])
    else:
        title = "Dry/Wet Risk"
    ax.set_title(title, fontsize=14, pad=12)
    ax.tick_params(labelsize=10)

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=RISK_COLORS[level]) for level in RiskLevel
    ]
    labels = [RISK_LABELS[level] for level in RiskLevel]
    if np.any(risk_map < 0):
        handles.append(plt.Rectangle((0, 0), 1, 1, color="#bdbdbd"))
        labels.append("No Data")
    ax.legend(
        handles,
        labels,
        title="Risk Levels",
        fontsize=10,
        title_fontsize=11,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        borderaxespad=0.0,
        frameon=True,
    )

    fig.subplots_adjust(left=0.12, right=0.85, top=0.92, bottom=0.12)

    fig.savefig(output, dpi=200)
    plt.close(fig)
    return output


def _format_title_with_dates(start_iso: str, end_iso: str) -> str:
    start_dt = _parse_iso_datetime(start_iso)
    end_dt = _parse_iso_datetime(end_iso)
    if not start_dt or not end_dt:
        return f"Dry/Wet Risk ({start_iso} – {end_iso})"

    same_year = start_dt.year == end_dt.year
    if same_year:
        start_label = _format_date_label(start_dt, include_year=False)
        end_label = _format_date_label(end_dt, include_year=True)
    else:
        start_label = _format_date_label(start_dt, include_year=True)
        end_label = _format_date_label(end_dt, include_year=True)
    return f"Dry/Wet Risk · {start_label} – {end_label}"


def _format_date_label(dt: datetime, include_year: bool) -> str:
    month_str = dt.strftime("%b")
    label = f"{dt.day} {month_str}"
    if include_year:
        label += f" {dt.year}"
    return label


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


__all__ = ["save_risk_plot"]
