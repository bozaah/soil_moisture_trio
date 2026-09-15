import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from scripts.grouped_soil_context import run_groupings
from src.soil_moisture_trio.slga.artifact import DEFAULT_ARTIFACT_FILENAME

REAL_BUNDLE = Path("data/processed/slga_awral/slga_awc_des_awral_swaz_0p05deg_v1")
REAL_RUN = Path("outputs/risk_2026_jul25-sep13_SWAZ_boundary/risk_2026_jul25-sep13_SWAZ_boundary.nc")


@pytest.mark.skipif(
    not (REAL_BUNDLE / DEFAULT_ARTIFACT_FILENAME).is_file() or not REAL_RUN.is_file(),
    reason="local SWAZ review bundle and 50-day run not present",
)
def test_groupings_reconcile_and_persist_rasters(tmp_path):
    # Copy the run so the script writes beside a temporary file, not into outputs/.
    run_copy = tmp_path / REAL_RUN.name
    run_copy.write_bytes(REAL_RUN.read_bytes())
    written = run_groupings(run_copy, REAL_BUNDLE)
    assert [p["json"].name for p in written] == [
        f"{run_copy.stem}_grouped_coverage_split.json",
        f"{run_copy.stem}_grouped_awc_terciles.json",
    ]
    for paths in written:
        payload = json.loads(paths["json"].read_text())
        assert payload["reconciled"] is True
        assert payload["stress_available"] is True
        assert payload["description"] and payload["notes"]
        ds = xr.load_dataset(paths["netcdf"])
        assert ds["group_id"].shape == (156, 186)
    terciles = json.loads(written[1]["json"].read_text())
    counts = [g["cell_count"] for g in terciles["groups"]]
    assert max(counts) - min(counts) <= 10
    assert np.isclose(sum(counts) + terciles["uncovered_cells"], terciles["risk_valid_cells"])
