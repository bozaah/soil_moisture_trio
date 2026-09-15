from datetime import date

import pytest
from pydantic import ValidationError

from src.soil_moisture_trio.config import ClassifierConfig


def test_default_model_weights_and_thresholds_are_valid() -> None:
    config = ClassifierConfig()

    assert config.dryness_weight + config.vpd_weight + config.temperature_weight == pytest.approx(1.0)
    assert (
        config.watch_risk_threshold
        < config.alert_risk_threshold
        < config.critical_risk_threshold
    )


@pytest.mark.parametrize(
    "overrides, message",
    [
        (
            {"dryness_weight": 0.7, "vpd_weight": 0.25, "temperature_weight": 0.15},
            "weights must sum to 1.0",
        ),
        (
            {"watch_risk_threshold": 0.6, "alert_risk_threshold": 0.6},
            "Risk thresholds must be strictly ordered",
        ),
        (
            {"start_date": date(2025, 2, 1), "end_date": date(2025, 1, 1)},
            "end_date must be on or after start_date",
        ),
        (
            {"year": 2025, "start_date": date(2026, 1, 1)},
            "start_date must fall within retrieval year",
        ),
        (
            {"year": 2025, "end_date": date(2026, 1, 1)},
            "end_date must fall within retrieval year",
        ),
        (
            {"silo_variables": ["max_temp", "vp"]},
            "exactly max_temp and vp_deficit",
        ),
        (
            {"silo_variables": ["max_temp", "vp_deficit", "max_temp"]},
            "exactly max_temp and vp_deficit",
        ),
        (
            {"silo_variables": ["max_temp"]},
            "exactly max_temp and vp_deficit",
        ),
        (
            {"min_lat": -20.0, "max_lat": -30.0},
            "min_lat must be less than max_lat",
        ),
        (
            {"min_lon": 125.0, "max_lon": 115.0},
            "min_lon must be less than max_lon",
        ),
    ],
)
def test_invalid_model_and_range_configuration_is_rejected(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        ClassifierConfig(**overrides)


def test_custom_valid_model_configuration_is_retained() -> None:
    config = ClassifierConfig(
        dryness_weight=0.5,
        vpd_weight=0.3,
        temperature_weight=0.2,
        watch_risk_threshold=0.25,
        alert_risk_threshold=0.55,
        critical_risk_threshold=0.8,
    )

    assert config.risk_model_parameters()["dryness_weight"] == 0.5
    assert config.risk_model_parameters()["critical_risk_threshold"] == 0.8
