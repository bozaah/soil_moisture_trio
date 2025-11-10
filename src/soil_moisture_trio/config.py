from pydantic import BaseModel, Field

# Pydantic Config Schema (for validation & easy tweaking)
class ClassifierConfig(BaseModel):
    moisture_threshold: float = Field(0.25, ge=0, le=1, description="Dry if soil moisture < this")
    temp_threshold: float = Field(30.0, ge=0, description="High temp threshold")
    ndvi_threshold: float = Field(0.3, ge=0, le=1, description="Low vegetation threshold")
    vpd_threshold: float = Field(20.0, ge=0, description="High VPD threshold")
    lr: float = Field(0.01, ge=0)
    epochs: int = Field(30, ge=1)
    batch_size: int = Field(32, ge=1)
    year: int = Field(2024, ge=1900, le=2100, description="Year for data retrieval")