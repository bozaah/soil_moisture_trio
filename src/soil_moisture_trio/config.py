from datetime import date
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class ClassifierConfig(BaseModel):
    # --- Dry/wet classification thresholds ---
    moisture_threshold: float = Field(0.25, ge=0, le=1, description="Dry if soil moisture (fraction) < this")
    temp_threshold: float = Field(30.0, ge=0, description="High temperature threshold (°C)")
    vpd_threshold: float = Field(20.0, ge=0, description="High VPD threshold (hPa)")

    # --- Risk level thresholds ---
    severe_moisture_threshold: float = Field(0.10, ge=0, le=1, description="Critical dryness threshold")
    critical_temp_threshold: float = Field(40.0, ge=0, description="Critical heat threshold (°C)")
    critical_vpd_threshold: float = Field(32.0, ge=0, description="Critical VPD threshold (hPa)")
    watch_margin: float = Field(0.08, ge=0, description="Moisture margin above dryness threshold for Watch state")
    alert_moisture_threshold: float = Field(0.18, ge=0, le=1, description="Moisture threshold for Alert level")
    alert_temp_threshold: float = Field(32.0, ge=0, description="Temperature threshold for Alert level (°C)")
    alert_vpd_threshold: float = Field(24.0, ge=0, description="VPD threshold for Alert level (hPa)")

    # --- Spatial bounds ---
    year: int = Field(2024, ge=1900, le=2100, description="Year for data retrieval")
    start_date: Optional[date] = Field(None, description="Start of averaging window (inclusive)")
    end_date: Optional[date] = Field(None, description="End of averaging window (inclusive)")
    min_lat: float = Field(-45.0, description="Minimum latitude (degrees)")
    max_lat: float = Field(-8.0, description="Maximum latitude (degrees)")
    min_lon: float = Field(110.0, description="Minimum longitude (degrees)")
    max_lon: float = Field(155.0, description="Maximum longitude (degrees)")

    # --- SILO loader ---
    silo_variables: List[str] = Field(
        default_factory=lambda: ["max_temp", "vp_deficit"],
        min_length=1,
        description="SILO variables to request via weather_tools",
    )
    use_silo_cog_loader: bool = Field(True, description="Fetch SILO data via weather_tools COG loader")
    silo_cache_dir: Optional[Path] = Field(None, description="Directory for persisting SILO GeoTIFF downloads")
    silo_cache_max_size_mb: int = Field(200, ge=50, description="Max SILO cache size (MB)")
    silo_overview_level: Optional[int] = Field(None, ge=0, description="Overview level for lower-resolution reads")
    silo_buffer_degrees: float = Field(0.0, ge=0.0, description="Extra degrees to buffer around bounding box")
