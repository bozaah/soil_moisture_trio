from datetime import date
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

# Pydantic Config Schema (for validation & easy tweaking)
class ClassifierConfig(BaseModel):
    moisture_threshold: float = Field(0.25, ge=0, le=1, description="Dry if soil moisture < this")
    temp_threshold: float = Field(30.0, ge=0, description="High temp threshold")
    ndvi_threshold: float = Field(0.3, ge=0, le=1, description="Low vegetation threshold")
    vpd_threshold: float = Field(20.0, ge=0, description="High VPD threshold")
    severe_moisture_threshold: float = Field(
        0.15, ge=0, le=1, description="Critical dryness threshold for risk layer"
    )
    critical_temp_threshold: float = Field(
        35.0, ge=0, description="Critical heat threshold for risk layer"
    )
    critical_vpd_threshold: float = Field(
        30.0, ge=0, description="Critical VPD threshold for risk layer"
    )
    watch_margin: float = Field(
        0.05, ge=0, description="Moisture margin above dryness threshold for watch state"
    )
    lr: float = Field(0.01, ge=0)
    epochs: int = Field(30, ge=1)
    batch_size: int = Field(32, ge=1)
    catboost_iterations: Optional[int] = Field(
        None, ge=1, description="Override CatBoost iterations (defaults to epochs)"
    )
    catboost_depth: int = Field(6, ge=1, le=16, description="CatBoost tree depth")
    catboost_learning_rate: Optional[float] = Field(
        None, ge=0, description="Override CatBoost learning rate (defaults to lr)"
    )
    year: int = Field(2024, ge=1900, le=2100, description="Year for data retrieval")
    start_date: Optional[date] = Field(
        None, description="Start date for averaging (inclusive). Defaults to first timestep."
    )
    end_date: Optional[date] = Field(
        None, description="End date for averaging (inclusive). Defaults to start_date or first timestep."
    )
    min_lat: float = Field(-45.0, description="Minimum latitude for clipping (degrees)")
    max_lat: float = Field(-8.0, description="Maximum latitude for clipping (degrees)")
    min_lon: float = Field(110.0, description="Minimum longitude for clipping (degrees)")
    max_lon: float = Field(155.0, description="Maximum longitude for clipping (degrees)")
    silo_variables: List[str] = Field(
        default_factory=lambda: ["max_temp", "vp_deficit"],
        min_length=1,
        description="List of SILO variables to request via weather_tools",
    )
    use_silo_cog_loader: bool = Field(
        True,
        description="If true, fetch SILO data via weather_tools COG loader instead of NetCDF.",
    )
    silo_cache_dir: Optional[Path] = Field(
        None,
        description="Optional directory for persisting SILO GeoTIFF downloads (default uses temp cache).",
    )
    silo_cache_max_size_mb: int = Field(
        200,
        ge=50,
        description="Maximum size of the SILO cache directory before pruning (in MB).",
    )
    silo_overview_level: Optional[int] = Field(
        None,
        ge=0,
        description="Optional overview level passed to weather_tools for lower-resolution reads.",
    )
    silo_buffer_degrees: float = Field(
        0.0,
        ge=0.0,
        description="Extra degrees to buffer around the bounding box when requesting SILO COG subsets.",
    )
