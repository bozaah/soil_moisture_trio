import math
from datetime import date
from pathlib import Path
from typing import List, Optional, Self

from pydantic import BaseModel, Field, model_validator


class ClassifierConfig(BaseModel):
    # --- Stress component references ---
    # soil moisture values are AWRAL decile percentile ranks (0–1)
    moisture_threshold: float = Field(
        0.50,
        gt=0,
        le=1,
        description=(
            "Dryness factor reference: dryness = clip((threshold - sm_pct) / threshold, 0, 1). "
            "0.50 = climatological median; cells above median contribute zero dryness."
        ),
    )
    critical_temp_threshold: float = Field(
        40.0,
        gt=0,
        description="Temperature normalisation ceiling for the stress index (°C)",
    )
    critical_vpd_threshold: float = Field(
        32.0,
        gt=0,
        description="VPD normalisation ceiling for the stress index (hPa)",
    )

    # --- Stress index weights ---
    dryness_weight: float = Field(0.60, ge=0, le=1, description="Soil-moisture deficit weight")
    vpd_weight: float = Field(0.25, ge=0, le=1, description="VPD stress weight")
    temperature_weight: float = Field(0.15, ge=0, le=1, description="Temperature stress weight")

    # --- Risk-band thresholds ---
    watch_risk_threshold: float = Field(0.35, ge=0, le=1, description="Minimum stress index for Watch")
    alert_risk_threshold: float = Field(0.60, ge=0, le=1, description="Minimum stress index for Alert")
    critical_risk_threshold: float = Field(0.85, ge=0, le=1, description="Minimum stress index for Critical")

    # --- Spatial and temporal bounds ---
    year: int = Field(2024, ge=1900, le=2100, description="Year for data retrieval")
    start_date: Optional[date] = Field(None, description="Start of averaging window (inclusive)")
    end_date: Optional[date] = Field(None, description="End of averaging window (inclusive)")
    min_lat: float = Field(-45.0, ge=-90, le=90, description="Minimum latitude (degrees)")
    max_lat: float = Field(-8.0, ge=-90, le=90, description="Maximum latitude (degrees)")
    min_lon: float = Field(110.0, ge=-180, le=180, description="Minimum longitude (degrees)")
    max_lon: float = Field(155.0, ge=-180, le=180, description="Maximum longitude (degrees)")
    boundary_gpkg: Optional[Path] = Field(
        None,
        description=(
            "Path to a GeoPackage boundary file. When set, bbox is derived from its bounds "
            "(+0.1° buffer) and cells outside the polygon are masked."
        ),
    )

    # --- SILO loader ---
    silo_variables: List[str] = Field(
        default_factory=lambda: ["max_temp", "vp_deficit"],
        min_length=1,
        description="SILO variables to request via weather_tools",
    )
    use_silo_cog_loader: bool = Field(True, description="Fetch SILO data via weather_tools COG loader")
    silo_cache_dir: Path = Field(
        default_factory=lambda: Path.home() / ".cache" / "soil_moisture_trio" / "silo",
        description="Directory for persisting SILO GeoTIFF downloads. Created automatically if absent.",
    )
    silo_cache_max_size_mb: int = Field(200, ge=50, description="Max SILO cache size (MB)")
    silo_overview_level: Optional[int] = Field(None, ge=0, description="Overview level for lower-resolution reads")
    silo_buffer_degrees: float = Field(0.0, ge=0.0, description="Extra degrees to buffer around bounding box")

    @model_validator(mode="after")
    def validate_model_configuration(self) -> Self:
        weight_sum = self.dryness_weight + self.vpd_weight + self.temperature_weight
        if not math.isclose(weight_sum, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"Stress index weights must sum to 1.0; got {weight_sum:.12g}.")

        if not (
            self.watch_risk_threshold
            < self.alert_risk_threshold
            < self.critical_risk_threshold
        ):
            raise ValueError(
                "Risk thresholds must be strictly ordered: "
                "watch_risk_threshold < alert_risk_threshold < critical_risk_threshold."
            )

        if self.start_date is not None and self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be on or after start_date.")

        if self.min_lat >= self.max_lat:
            raise ValueError("min_lat must be less than max_lat.")
        if self.min_lon >= self.max_lon:
            raise ValueError("min_lon must be less than max_lon.")

        return self

    def risk_model_parameters(self) -> dict[str, float]:
        """Return the model parameters that define decision-support outputs."""
        keys = (
            "moisture_threshold",
            "critical_temp_threshold",
            "critical_vpd_threshold",
            "dryness_weight",
            "vpd_weight",
            "temperature_weight",
            "watch_risk_threshold",
            "alert_risk_threshold",
            "critical_risk_threshold",
        )
        return {key: float(getattr(self, key)) for key in keys}
