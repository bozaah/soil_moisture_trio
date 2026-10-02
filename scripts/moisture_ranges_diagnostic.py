"""Summarise the remote AWRA-L soil-moisture percentile-rank product."""

import argparse
import json

import numpy as np
import xarray as xr


REMOTE_SM_PCT_URL = (
    "https://thredds.nci.org.au/thredds/dodsC/iu04/"
    "australian-water-outlook/historical/v1/AWRALv7/processed/deciles/day/sm_pct_2024.nc"
)
REMOTE_SM_PCT_VAR = "sm_pct"


def summarize_sm_pct(
    url: str = REMOTE_SM_PCT_URL,
    var_name: str = REMOTE_SM_PCT_VAR,
) -> dict[str, object]:
    """Fetch summary statistics for a remote percentile-rank dataset."""
    with xr.open_dataset(url, decode_times=True, engine="netcdf4") as dataset:
        values = dataset[var_name]
        if "time" in values.dims:
            values = values.mean(dim="time", skipna=True)

        flat = np.asarray(values.values, dtype=np.float64).ravel()
        flat = flat[np.isfinite(flat)]
        if flat.size == 0:
            raise ValueError("No finite values found in diagnostic dataset.")

    minimum = float(np.nanmin(flat))
    maximum = float(np.nanmax(flat))
    if minimum < 0 or maximum > 1.1:
        raise ValueError(
            "Expected AWRA-L percentile ranks on a 0-1 scale; "
            f"observed range {minimum:.3f} to {maximum:.3f}."
        )

    percentile_points = [0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100]
    return {
        "count": int(flat.size),
        "min": minimum,
        "max": maximum,
        "mean": float(np.nanmean(flat)),
        "median": float(np.nanmedian(flat)),
        "distribution_percentiles": dict(
            zip(
                (str(point) for point in percentile_points),
                np.percentile(flat, percentile_points).tolist(),
                strict=True,
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarise a remote AWRA-L soil-moisture percentile-rank dataset."
    )
    parser.add_argument("--url", default=REMOTE_SM_PCT_URL)
    parser.add_argument("--variable", default=REMOTE_SM_PCT_VAR)
    args = parser.parse_args()
    print(json.dumps(summarize_sm_pct(args.url, args.variable), indent=2))


if __name__ == "__main__":
    main()
