from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap

from src.soil_moisture_trio.risk import RISK_COLORS, RISK_LABELS, RiskLevel


# ---------------------------------------------------------------------
# Main combined plot: categorical map + continuous dryness panel
# ---------------------------------------------------------------------
def save_risk_plot(
    risk_map: np.ndarray,
    stress_index: Optional[np.ndarray],
    lats: np.ndarray,
    lons: np.ndarray,
    output_path: str = "risk_map.png",
    time_metadata: Optional[Dict[str, str]] = None,
) -> Path:
    """
    Render a two-panel PNG figure:
      - Left: Categorical Dry/Wet Risk map
      - Right: Continuous Dryness–Stress Index map

    Args:
        risk_map: 2D array of integer risk levels.
        stress_index: 2D array of continuous dryness–stress values (0–1).
        lats/lons: 1D coordinate arrays aligned with the grid.
        output_path: Filepath for PNG.
        time_metadata: Optional date metadata dict.
    """
    # Backwards-compatibility: older callers used signature
    # save_risk_plot(risk_map, lats, lons, output_path)
    # while newer callers pass stress_index as second arg. Detect the legacy
    # positional ordering and reorder arguments accordingly.
    def _is_arraylike(x):
        return isinstance(x, (list, tuple, np.ndarray))

    # If the third positional arg (lons) is not array-like but the first two are,
    # it's likely the caller used the old signature: (risk_map, lats, lons, output)
    if not _is_arraylike(lons) and _is_arraylike(stress_index) and _is_arraylike(lats):
        output_path = lons  # third positional was actually output_path
        lons = lats  # second positional was actually lons
        lats = stress_index  # first positional after risk_map was lats
        stress_index = None

    risk_map = np.asarray(risk_map)
    # Allow callers to omit the continuous stress index (None). In that case derive a
    # numeric fallback from the categorical `risk_map` so plotting still works.
    if stress_index is None:
        # create float array filled with NaN and populate from risk categories
        stress_index = np.full(risk_map.shape, np.nan, dtype=float)
        try:
            # Map RiskLevel enum values to representative continuous stress scores
            mapping = {
                RiskLevel.LOW: 0.15,
                RiskLevel.WATCH: 0.45,
                RiskLevel.ALERT: 0.7,
                RiskLevel.CRITICAL: 0.92,
            }
            for lvl, val in mapping.items():
                stress_index[risk_map == lvl] = val
        except Exception:
            # If risk_map is not categorical (e.g., raw integers), attempt safe coercion
            stress_index = np.asarray(stress_index)
    else:
        stress_index = np.asarray(stress_index)
    lats = np.asarray(lats)
    lons = np.asarray(lons)

    if risk_map.shape != (len(lats), len(lons)):
        raise ValueError("Risk map shape must match (len(lats), len(lons)).")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # ---- Color setups ----
    cmap_class = ListedColormap([RISK_COLORS[l] for l in RiskLevel])
    cmap_class.set_bad("#bdbdbd")
    bounds = np.arange(len(RiskLevel) + 1) - 0.5
    norm_class = BoundaryNorm(bounds, cmap_class.N)

    cmap_cont = plt.cm.RdYlBu_r  # continuous dryness scale
    cmap_cont.set_bad("#bdbdbd")

    # ---- Layout ----
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5), constrained_layout=True)

    # --- Panel A: categorical risk ---
    ax1 = axes[0]
    risk_display = np.ma.masked_less(risk_map, 0)
    mesh1 = ax1.pcolormesh(lons, lats, risk_display, cmap=cmap_class, norm=norm_class, shading="auto")
    ax1.set_xlabel("Longitude")
    ax1.set_ylabel("Latitude")
    title = "Dryness–Stress Risk (Physics-Based)"
    if time_metadata and time_metadata.get("time_start") and time_metadata.get("time_end"):
        title = _format_title_with_dates(time_metadata["time_start"], time_metadata["time_end"])
    ax1.set_title(title)
    cbar1 = fig.colorbar(mesh1, ax=ax1, orientation="vertical", pad=0.02, fraction=0.046)
    cbar1.set_ticks(np.arange(len(RiskLevel)))
    cbar1.set_ticklabels([RISK_LABELS[l] for l in RiskLevel])
    cbar1.set_label("Risk Level")
    cbar1.ax.tick_params(labelsize=9)

    # --- Panel B: continuous dryness index ---
    ax2 = axes[1]
    cont_disp = np.ma.masked_invalid(stress_index)
    mesh2 = ax2.pcolormesh(lons, lats, cont_disp, cmap=cmap_cont, vmin=0, vmax=1, shading="auto")
    ax2.set_xlabel("Longitude")
    ax2.set_ylabel("Latitude")
    ax2.set_title("Continuous Dryness–Stress Index (0–1)")
    cbar2 = fig.colorbar(mesh2, ax=ax2, orientation="vertical", pad=0.02, fraction=0.046)
    cbar2.set_label("Dryness–Stress Index")
    cbar2.ax.tick_params(labelsize=9)

    for ax in axes:
        ax.set_xlim(np.min(lons), np.max(lons))
        ax.set_ylim(np.min(lats), np.max(lats))
        ax.set_aspect("equal", adjustable="box")
        ax.tick_params(labelsize=10)

    fig.savefig(output, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output


# ---------------------------------------------------------------------
# Diagnostic plots: histogram + scatter
# ---------------------------------------------------------------------
def plot_dryness_diagnostics(
    soil_moisture: np.ndarray,
    vpd: np.ndarray,
    stress_index: Optional[np.ndarray],
    output_path: str = "stress_diagnostics.png",
) -> Path:
    """
    Create diagnostic plots showing distribution and relationships
    between soil moisture, VPD (vapour pressure deficit), and
    the dryness–stress index.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)

    # Ensure stress_index is numeric. If missing or non-numeric, derive a simple
    # proxy from soil moisture (1 - soil_moisture) clipped to [0,1]. This keeps
    # diagnostics working even when the physics-based stress index isn't available.
    if stress_index is None:
        stress_index = np.clip(1.0 - np.asarray(soil_moisture, dtype=float), 0.0, 1.0)
    else:
        try:
            stress_index = np.asarray(stress_index, dtype=float)
        except Exception:
            stress_index = np.clip(1.0 - np.asarray(soil_moisture, dtype=float), 0.0, 1.0)

    # Flatten arrays so masking is consistent and robust to minor shape mismatches
    soil_flat = np.asarray(soil_moisture, dtype=float).flatten()
    vpd_flat = np.asarray(vpd, dtype=float).flatten()
    stress_flat = stress_index.flatten()

    # Detect and mask obviously-bad VPD values (e.g., unit/scale errors)
    extreme_mask = np.abs(vpd_flat) > 10000
    if extreme_mask.any():
        print(f"Warning: {int(extreme_mask.sum())} extreme VPD values detected; masking for diagnostics.")
        vpd_flat[extreme_mask] = np.nan

    # Build final valid mask
    valid = np.isfinite(stress_flat) & np.isfinite(soil_flat) & np.isfinite(vpd_flat)

    # Histogram of dryness–stress
    ax1 = axes[0]
    ax1.hist(stress_flat[valid], bins=40, color="steelblue", alpha=0.8)
    ax1.set_xlabel("Dryness–Stress Index (0–1)")
    ax1.set_ylabel("Frequency")
    ax1.set_title("Distribution of Dryness–Stress Index")

    # Scatter of soil moisture vs. VPD colored by stress
    ax2 = axes[1]
    sc = ax2.scatter(
        soil_flat[valid],
        vpd_flat[valid],
        c=stress_flat[valid],
        cmap="RdYlBu_r",
        vmin=0,
        vmax=1,
        s=10,
        alpha=0.7,
        edgecolor="none",
    )
    ax2.set_xlabel("Soil Moisture (fraction)")
    ax2.set_ylabel("VPD (hPa)")
    ax2.set_title("Soil Moisture vs. VPD\ncolored by Dryness–Stress Index")
    cbar = fig.colorbar(sc, ax=ax2)
    cbar.set_label("Dryness–Stress Index")

    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output


# ---------------------------------------------------------------------
# Helper for date formatting
# ---------------------------------------------------------------------
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


__all__ = ["save_risk_plot", "plot_dryness_diagnostics"]