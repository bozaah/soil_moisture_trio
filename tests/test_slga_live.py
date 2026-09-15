"""Opt-in authenticated SLGA integration check; excluded from default network access."""

import os
from pathlib import Path

import numpy as np
import pytest

from src.soil_moisture_trio.slga.catalogue import load_source_catalogue
from src.soil_moisture_trio.slga.cog import AuthenticatedCogReader

RUN_LIVE = os.environ.get("RUN_SLGA_LIVE_TESTS") == "1" and bool(
    os.environ.get("TERN_API_KEY")
)


@pytest.mark.skipif(
    not RUN_LIVE,
    reason="set RUN_SLGA_LIVE_TESTS=1 and TERN_API_KEY to run authenticated SLGA checks",
)
def test_live_awc_window_matches_pinned_contract():
    catalogue = load_source_catalogue(Path("manifests/slga_awc_des_sources_v1.json"))
    product_id = "AWC_000_005_EV_N_P_AU_TRN_N_20210614"

    result = AuthenticatedCogReader(catalogue).read_window(
        product_id,
        (116.0, -32.0, 116.005, -31.995),
    )

    assert result.layer.product_id == product_id
    assert result.values.shape == (9, 9)
    assert np.isfinite(result.values).any()
    assert np.nanmin(result.values) >= 0
