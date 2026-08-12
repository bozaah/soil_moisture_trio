from __future__ import annotations

import base64
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
import rasterio
from rasterio import Affine
from rasterio.crs import CRS
from rasterio.errors import RasterioIOError
from rasterio.windows import Window, from_bounds

from src.soil_moisture_trio.slga.catalogue import (
    TRANSFORM_ABS_TOLERANCE,
    CatalogueError,
    LayerSpec,
    SourceCatalogue,
)

RETRYABLE_HTTP_CODES = {408, 425, 429, 500, 502, 503, 504}
RETRY_DELAYS_SECONDS = (0.5, 1.0)


class SourceAccessError(RuntimeError):
    """Raised when an approved source cannot be read safely."""


class SourceValidationError(ValueError):
    """Raised when a live COG no longer matches its pinned contract."""


@dataclass(frozen=True)
class RasterWindowData:
    layer: LayerSpec
    values: np.ndarray
    transform: Affine
    crs: CRS
    window: Window
    retrieved_at: str


class AuthenticatedCogReader:
    """Read validated full-resolution windows from the pinned TERN COGs."""

    def __init__(
        self,
        catalogue: SourceCatalogue,
        *,
        environment: Mapping[str, str] | None = None,
        attempts: int = 3,
        timeout_seconds: float = 30.0,
    ) -> None:
        if attempts < 1 or attempts > 3:
            raise ValueError("attempts must be between 1 and 3.")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive.")
        self.catalogue = catalogue
        self.environment = os.environ if environment is None else environment
        self.attempts = attempts
        self.timeout_seconds = timeout_seconds

    def read_window(
        self,
        product_id: str,
        bounds: tuple[float, float, float, float],
    ) -> RasterWindowData:
        layer = self.catalogue.require(product_id)
        key = self._require_api_key()
        checked_bounds = validate_bounds(bounds)
        stac_item = self._fetch_stac(layer, key)
        try:
            self.catalogue.validate_stac_item(layer, stac_item)
        except CatalogueError as exc:
            raise SourceValidationError(str(exc)) from exc

        gdal_options = {
            "GDAL_HTTP_AUTH": "BASIC",
            "GDAL_HTTP_USERPWD": f"apikey:{key}",
            "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        }
        last_retryable_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                with rasterio.Env(**gdal_options):
                    with rasterio.open(layer.url) as dataset:
                        validate_cog_dataset(dataset, self.catalogue, layer)
                        window = expanded_window_for_bounds(dataset, checked_bounds)
                        masked = dataset.read(1, window=window, masked=True)
                        values = _normalise_values(masked, layer)
                        transform = dataset.window_transform(window)
                        crs = dataset.crs
                break
            except SourceValidationError:
                raise
            except (RasterioIOError, OSError) as exc:
                # Do not include low-level GDAL text: environment options can contain credentials.
                last_retryable_error = exc
                if attempt < self.attempts - 1:
                    time.sleep(RETRY_DELAYS_SECONDS[attempt])
        else:
            raise SourceAccessError(
                f"Failed to read approved COG {product_id} after {self.attempts} attempts."
            ) from last_retryable_error

        return RasterWindowData(
            layer=layer,
            values=values,
            transform=transform,
            crs=crs,
            window=window,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    def _require_api_key(self) -> str:
        key = self.environment.get(self.catalogue.credential_environment_variable, "")
        if not isinstance(key, str) or not key.strip():
            raise SourceAccessError(
                f"{self.catalogue.credential_environment_variable} is required for TERN access."
            )
        if any(character in key for character in ("\r", "\n", "\x00")):
            raise SourceAccessError("TERN_API_KEY contains invalid control characters.")
        return key

    def _fetch_stac(self, layer: LayerSpec, key: str) -> Mapping[str, Any]:
        auth = base64.b64encode(f"apikey:{key}".encode("utf-8")).decode("ascii")
        request = Request(
            layer.stac_url,
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        last_retryable_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.load(response)
                if not isinstance(payload, Mapping):
                    raise SourceValidationError(
                        f"Malformed STAC response for {layer.product_id}: expected an object."
                    )
                return payload
            except HTTPError as exc:
                if exc.code not in RETRYABLE_HTTP_CODES:
                    raise SourceAccessError(
                        f"STAC request failed for {layer.product_id} with HTTP {exc.code}."
                    ) from exc
                last_retryable_error = exc
            except URLError as exc:
                last_retryable_error = exc
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise SourceValidationError(
                    f"Malformed STAC JSON for {layer.product_id}."
                ) from exc

            if attempt < self.attempts - 1:
                time.sleep(RETRY_DELAYS_SECONDS[attempt])

        raise SourceAccessError(
            f"STAC request failed for {layer.product_id} after {self.attempts} attempts."
        ) from last_retryable_error


def validate_bounds(
    bounds: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if not isinstance(bounds, tuple) or len(bounds) != 4:
        raise ValueError("bounds must be a (west, south, east, north) tuple.")
    try:
        west, south, east, north = (float(value) for value in bounds)
    except (TypeError, ValueError) as exc:
        raise ValueError("bounds must contain numeric values.") from exc
    if not all(math.isfinite(value) for value in (west, south, east, north)):
        raise ValueError("bounds must contain finite values.")
    if west >= east or south >= north:
        raise ValueError("bounds must satisfy west < east and south < north.")
    return west, south, east, north


def expanded_window_for_bounds(
    dataset: rasterio.io.DatasetReader,
    bounds: tuple[float, float, float, float],
) -> Window:
    west, south, east, north = validate_bounds(bounds)
    source_bounds = dataset.bounds
    clipped_west = max(west, source_bounds.left)
    clipped_south = max(south, source_bounds.bottom)
    clipped_east = min(east, source_bounds.right)
    clipped_north = min(north, source_bounds.top)
    if clipped_west >= clipped_east or clipped_south >= clipped_north:
        raise SourceValidationError(
            "Requested bounds do not overlap the pinned SLGA grid."
        )

    fractional = from_bounds(
        clipped_west,
        clipped_south,
        clipped_east,
        clipped_north,
        transform=dataset.transform,
    )
    col_start = max(0, math.floor(fractional.col_off) - 1)
    row_start = max(0, math.floor(fractional.row_off) - 1)
    col_stop = min(dataset.width, math.ceil(fractional.col_off + fractional.width) + 1)
    row_stop = min(
        dataset.height, math.ceil(fractional.row_off + fractional.height) + 1
    )
    if col_start >= col_stop or row_start >= row_stop:
        raise SourceValidationError("Requested bounds produced an empty source window.")
    return Window(
        col_off=col_start,
        row_off=row_start,
        width=col_stop - col_start,
        height=row_stop - row_start,
    )


def validate_cog_dataset(
    dataset: rasterio.io.DatasetReader,
    catalogue: SourceCatalogue,
    layer: LayerSpec,
) -> None:
    profile = catalogue.profile
    if dataset.driver != profile.driver:
        raise SourceValidationError(f"COG driver mismatch for {layer.product_id}.")
    if dataset.count != profile.band_count:
        raise SourceValidationError(f"COG band-count mismatch for {layer.product_id}.")
    if dataset.width != profile.width or dataset.height != profile.height:
        raise SourceValidationError(f"COG shape mismatch for {layer.product_id}.")
    if dataset.crs != CRS.from_string(profile.crs):
        raise SourceValidationError(f"COG CRS mismatch for {layer.product_id}.")
    if not _affine_close(dataset.transform, Affine(*profile.transform)):
        raise SourceValidationError(f"COG transform mismatch for {layer.product_id}.")
    actual_bounds = tuple(dataset.bounds)
    if len(actual_bounds) != 4 or not all(
        math.isclose(actual, expected, rel_tol=0.0, abs_tol=TRANSFORM_ABS_TOLERANCE)
        for actual, expected in zip(actual_bounds, profile.bounds, strict=True)
    ):
        raise SourceValidationError(f"COG bounds mismatch for {layer.product_id}.")
    if dataset.dtypes != (layer.product.dtype,):
        raise SourceValidationError(f"COG dtype mismatch for {layer.product_id}.")
    if layer.property_code == "AWC":
        if dataset.nodata != layer.product.nodata:
            raise SourceValidationError(f"COG nodata mismatch for {layer.product_id}.")
    elif dataset.nodata is None or not math.isnan(float(dataset.nodata)):
        raise SourceValidationError(f"COG nodata mismatch for {layer.product_id}.")
    block_shapes = dataset.block_shapes
    is_internally_tiled = (
        len(block_shapes) == 1
        and 0 < block_shapes[0][0] < dataset.height
        and 0 < block_shapes[0][1] < dataset.width
    )
    if not is_internally_tiled or not dataset.overviews(1):
        raise SourceValidationError(
            f"Source is not an internally tiled COG for {layer.product_id}."
        )

    tags = dataset.tags()
    if tags.get("UNITS") != layer.product.units:
        raise SourceValidationError(f"COG units mismatch for {layer.product_id}.")
    if tags.get("AREA_OR_POINT") != profile.area_or_point:
        raise SourceValidationError(
            f"COG AREA_OR_POINT mismatch for {layer.product_id}."
        )

    description = dataset.descriptions[0]
    if description != layer.product_id:
        stale_des_id = layer.product_id.replace("_TRN_", "_NAT_")
        if layer.property_code != "DES" or description != stale_des_id:
            raise SourceValidationError(
                f"COG band-description mismatch for {layer.product_id}."
            )


def assert_common_window_grid(windows: Mapping[str, RasterWindowData]) -> None:
    if not windows:
        raise SourceValidationError("At least one source window is required.")
    first = next(iter(windows.values()))
    for product_id, window in windows.items():
        if window.values.shape != first.values.shape:
            raise SourceValidationError(
                f"Source window shape mismatch for {product_id}."
            )
        if window.crs != first.crs:
            raise SourceValidationError(f"Source window CRS mismatch for {product_id}.")
        if window.window != first.window or not _affine_close(
            window.transform, first.transform
        ):
            raise SourceValidationError(
                f"Source window grid mismatch for {product_id}."
            )


def _normalise_values(masked: np.ma.MaskedArray, layer: LayerSpec) -> np.ndarray:
    values = np.asarray(masked.data, dtype=np.float64)
    mask = np.ma.getmaskarray(masked).copy()
    if layer.property_code == "DES":
        mask |= np.isnan(values)
    elif np.any(np.isnan(values)):
        raise SourceValidationError(
            f"Unexpected NaN in integer AWC source {layer.product_id}."
        )
    if np.any(np.isinf(values) & ~mask):
        raise SourceValidationError(
            f"Infinite valid value in source {layer.product_id}."
        )
    if np.any((values < 0) & ~mask):
        raise SourceValidationError(
            f"Negative valid value in source {layer.product_id}."
        )
    values[mask] = np.nan
    return values


def _affine_close(actual: Affine, expected: Affine) -> bool:
    return all(
        math.isclose(a, b, rel_tol=0.0, abs_tol=TRANSFORM_ABS_TOLERANCE)
        for a, b in zip(tuple(actual)[:6], tuple(expected)[:6], strict=True)
    )
