from datetime import date
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class ClassifierConfig(BaseModel):
    # --- Stress index thresholds ---
    # soil moisture values are AWRAL decile percentile ranks (0–1)
    moisture_threshold: float = Field(0.50, ge=0, le=1, description="Dryness factor reference: dryness = clip((threshold - sm_pct) / threshold, 0, 1). 0.50 = climatological median; cells above median contribute zero dryness.")

    # --- Stress index normalisation + category thresholds ---
    critical_temp_threshold: float = Field(40.0, ge=0, description="Temperature normalisation ceiling for the stress index (°C)")
    critical_vpd_threshold: float = Field(32.0, ge=0, description="VPD normalisation ceiling for the stress index (hPa)")

    # --- Spatial bounds ---
    year: int = Field(2024, ge=1900, le=2100, description="Year for data retrieval")
    start_date: Optional[date] = Field(None, description="Start of averaging window (inclusive)")
    end_date: Optional[date] = Field(None, description="End of averaging window (inclusive)")
    min_lat: float = Field(-45.0, description="Minimum latitude (degrees)")
    max_lat: float = Field(-8.0, description="Maximum latitude (degrees)")
    min_lon: float = Field(110.0, description="Minimum longitude (degrees)")
    max_lon: float = Field(155.0, description="Maximum longitude (degrees)")
    boundary_gpkg: Optional[Path] = Field(None, description="Path to a GeoPackage boundary file. When set, bbox is derived from its bounds (+0.1° buffer) and cells outside the polygon are masked.")

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
