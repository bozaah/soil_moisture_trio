import numpy as np
import pytest

from src.soil_moisture_trio.slga.integration import (
    DEPTH_CODES,
    IntegrationError,
    integrate_storage,
)


def _inputs(shape=(1, 1), awc_ev=10.0, des_ev=1.0):
    awc = {
        "05": {depth: np.full(shape, awc_ev - 2.0) for depth in DEPTH_CODES},
        "EV": {depth: np.full(shape, awc_ev) for depth in DEPTH_CODES},
        "95": {depth: np.full(shape, awc_ev + 2.0) for depth in DEPTH_CODES},
    }
    des = {
        "10": np.full(shape, max(0.0, des_ev - 0.2)),
        "EV": np.full(shape, des_ev),
        "90": np.full(shape, des_ev + 0.2),
    }
    return awc, des


def test_ev_storage_uses_thickness_and_caps_des_at_one_metre():
    awc, des = _inputs(shape=(1, 2), awc_ev=10.0, des_ev=1.2)
    des["10"][:] = 1.0
    des["EV"][:] = [1.2, 2.75]
    des["90"][:] = [1.5, 3.0]

    result = integrate_storage(awc, des)

    np.testing.assert_allclose(result.storage_mm["ev"], [[100.0, 100.0]])
    np.testing.assert_allclose(result.des_metres["EV"], [[1.2, 2.75]])
    np.testing.assert_allclose(result.represented_depth_mm["EV"], [[1000.0, 1000.0]])


def test_partial_depth_uses_only_represented_layers():
    awc, des = _inputs(awc_ev=10.0, des_ev=0.10)
    des["10"][:] = 0.05
    des["90"][:] = 0.15

    result = integrate_storage(awc, des)

    assert result.storage_mm["ev"][0, 0] == pytest.approx(10.0)
    assert result.storage_mm["mixed_lower_awc05_des10"][0, 0] == pytest.approx(4.0)
    assert result.storage_mm["mixed_upper_awc95_des90"][0, 0] == pytest.approx(18.0)


def test_nodata_below_profile_does_not_invalidate_but_required_nodata_does():
    awc, des = _inputs(shape=(1, 2), awc_ev=10.0, des_ev=0.04)
    des["10"][:] = 0.02
    des["90"][:] = 0.05
    for component in awc:
        awc[component]["060_100"][:] = np.nan
    awc["EV"]["000_005"][0, 1] = np.nan

    result = integrate_storage(awc, des)

    assert result.storage_mm["ev"][0, 0] == pytest.approx(4.0)
    assert np.isnan(result.storage_mm["ev"][0, 1])


def test_zero_depth_is_valid_zero_storage():
    awc, des = _inputs(awc_ev=10.0, des_ev=0.0)
    des["10"][:] = 0.0
    des["90"][:] = 0.0
    for component in awc:
        for depth in DEPTH_CODES:
            awc[component][depth][:] = np.nan

    result = integrate_storage(awc, des)

    assert result.storage_mm["ev"][0, 0] == 0.0


def test_component_effects_and_mixed_scenarios_are_separate():
    awc, des = _inputs(awc_ev=10.0, des_ev=0.5)
    des["10"][:] = 0.4
    des["90"][:] = 0.6

    result = integrate_storage(awc, des)

    assert result.storage_mm["awc05_des_ev"][0, 0] == pytest.approx(40.0)
    assert result.storage_mm["awc95_des_ev"][0, 0] == pytest.approx(60.0)
    assert result.storage_mm["awc_ev_des10"][0, 0] == pytest.approx(40.0)
    assert result.storage_mm["awc_ev_des90"][0, 0] == pytest.approx(60.0)
    assert result.mixed_uncertainty_width_mm[0, 0] == pytest.approx(40.0)


def test_negative_infinite_and_ordering_fail():
    awc, des = _inputs()
    awc["EV"]["000_005"][0, 0] = -1
    with pytest.raises(IntegrationError, match="negative"):
        integrate_storage(awc, des)

    awc, des = _inputs()
    des["EV"][0, 0] = np.inf
    with pytest.raises(IntegrationError, match="infinite"):
        integrate_storage(awc, des)

    awc, des = _inputs()
    awc["05"]["000_005"][0, 0] = 11
    with pytest.raises(IntegrationError, match="lower <= EV <= upper"):
        integrate_storage(awc, des)
