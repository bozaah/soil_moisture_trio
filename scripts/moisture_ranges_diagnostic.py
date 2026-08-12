"""Summarise a remote AWRA-L soil-moisture dataset for manual diagnostics."""

import argparse
import json

import numpy as np
import xarray as xr


REMOTE_SM_PCT_URL = (
    "https://thredds.nci.org.au/thredds/dodsC/iu04/"
    "australian-water-outlook/historical/v1/AWRALv7/processed/values/day/sm_pct_2024.nc"
)
REMOTE_SM_PCT_VAR = "sm_pct"


def summarize_sm_pct(
    url: str = REMOTE_SM_PCT_URL,
    var_name: str = REMOTE_SM_PCT_VAR,
) -> dict[str, object]:
    """Fetch summary statistics for a remote soil-moisture diagnostic dataset."""
    with xr.open_dataset(url, decode_times=True, engine="netcdf4") as dataset:
        values = dataset[var_name]
        if "time" in values.dims:
            values = values.mean(dim="time", skipna=True)

        flat = np.asarray(values.values, dtype=np.float64).ravel()
        flat = flat[np.isfinite(flat)]
        if flat.size == 0:
            raise ValueError("No finite values found in diagnostic dataset.")

    percentiles = [0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100]
    fraction = flat / 100.0
    return {
        "percent_scale": {
            "min": float(np.nanmin(flat)),
            "max": float(np.nanmax(flat)),
            "mean": float(np.nanmean(flat)),
            "median": float(np.nanmedian(flat)),
            "percentiles": np.percentile(flat, percentiles).tolist(),
        },
        "fraction_scale": {
            "min": float(np.nanmin(fraction)),
            "max": float(np.nanmax(fraction)),
            "mean": float(np.nanmean(fraction)),
            "median": float(np.nanmedian(fraction)),
            "percentiles": np.percentile(fraction, percentiles).tolist(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarise a remote AWRA-L soil-moisture dataset."
    )
    parser.add_argument("--url", default=REMOTE_SM_PCT_URL)
    parser.add_argument("--variable", default=REMOTE_SM_PCT_VAR)
    args = parser.parse_args()
    print(json.dumps(summarize_sm_pct(args.url, args.variable), indent=2))


if __name__ == "__main__":
    main()
