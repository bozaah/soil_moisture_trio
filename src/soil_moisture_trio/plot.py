from pathlib import Path

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

    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
    risk_display = np.ma.masked_less(risk_map, 0)
    ax.pcolormesh(
        lons,
        lats,
        risk_display,
        cmap=cmap,
        norm=norm,
        shading="nearest",
    )
    ax.set_xlabel("Longitude", fontsize=12)
    ax.set_ylabel("Latitude", fontsize=12)
    ax.set_title("Dry/Wet Risk", fontsize=14)
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
        loc="upper right",
        frameon=True,
    )

    fig.savefig(output, dpi=200)
    plt.close(fig)
    return output


__all__ = ["save_risk_plot"]
