from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

EXPECTED_MANIFEST_ID = "slga_awc_des_sources_v1"
EXPECTED_SOURCE_BASE_URL = (
    "https://data.tern.org.au/model-derived/slga/NationalMaps/SoilAndLandscapeGrid"
)
EXPECTED_LAYER_COUNT = 18
EXPECTED_SHAPE = (40800, 49200)
EXPECTED_TRANSFORM = (
    0.0008333333333536583,
    0.0,
    112.999583333,
    0.0,
    -0.0008333333333578432,
    -10.000416666,
)
EXPECTED_BOUNDS = (112.999583333, -44.000416667, 153.999583334, -10.000416666)
MULTIHASH_PATTERN = re.compile(r"^d50110[0-9a-f]{32}$")
TRANSFORM_ABS_TOLERANCE = 1e-12
STAC_BOUNDS_ABS_TOLERANCE = 5e-8


class CatalogueError(ValueError):
    """Raised when the pinned source catalogue is malformed or has drifted."""


@dataclass(frozen=True)
class CommonProfile:
    driver: str
    crs: str
    height: int
    width: int
    transform: tuple[float, float, float, float, float, float]
    bounds: tuple[float, float, float, float]
    band_count: int
    area_or_point: str


@dataclass(frozen=True)
class ProductSpec:
    code: str
    title: str
    version: int
    doi: str
    units: str
    dtype: str
    nodata: float
    components: tuple[str, ...]
    depths: tuple[str, ...]
    citation: str


@dataclass(frozen=True)
class LayerSpec:
    product_id: str
    property_code: str
    depth_code: str
    component: str
    url: str
    stac_url: str
    stac_multihash: str
    file_size_bytes: int
    product: ProductSpec

    @property
    def filename(self) -> str:
        return f"{self.product_id}.tif"


@dataclass(frozen=True)
class SourceCatalogue:
    path: Path
    sha256: str
    manifest_id: str
    credential_environment_variable: str
    profile: CommonProfile
    products: Mapping[str, ProductSpec]
    layers: Mapping[str, LayerSpec]

    def require(self, product_id: str) -> LayerSpec:
        try:
            return self.layers[product_id]
        except KeyError as exc:
            raise CatalogueError(
                f"Product ID is not approved by {self.manifest_id}: {product_id!r}."
            ) from exc

    def validate_stac_item(self, layer: LayerSpec, item: Mapping[str, Any]) -> None:
        """Validate public STAC identity/profile fields against the pinned catalogue."""
        if item.get("id") != layer.product_id:
            raise CatalogueError(
                f"STAC ID mismatch for {layer.product_id}: {item.get('id')!r}."
            )
        if item.get("type") != "Feature":
            raise CatalogueError(
                f"Malformed STAC item for {layer.product_id}: type must be 'Feature'."
            )

        _require_float_sequence_close(
            item.get("bbox"),
            self.profile.bounds,
            f"STAC bounds mismatch for {layer.product_id}.",
            abs_tolerance=STAC_BOUNDS_ABS_TOLERANCE,
        )
        properties = _require_mapping(item, "properties", layer.product_id)
        if properties.get("proj:epsg") != 4326:
            raise CatalogueError(f"STAC CRS mismatch for {layer.product_id}.")
        _require_sequence_equal(
            properties.get("proj:shape"),
            [self.profile.width, self.profile.height],
            f"STAC shape mismatch for {layer.product_id}.",
        )
        _require_float_sequence_close(
            properties.get("proj:transform"),
            self.profile.transform,
            f"STAC transform mismatch for {layer.product_id}.",
        )
        if properties.get("UNITS") != layer.product.units:
            raise CatalogueError(f"STAC units mismatch for {layer.product_id}.")
        expected_soil_property = {
            "AWC": "Available Water Capacity",
            "DES": "Depth of Soil",
        }[layer.property_code]
        if properties.get("Soil Property") != expected_soil_property:
            raise CatalogueError(f"STAC soil-property mismatch for {layer.product_id}.")
        expected_component = {
            "EV": "Estimated Value",
            "05": "5th percentile confidence limit",
            "95": "95th percentile confidence limit",
            "10": "10th percentile confidence limit",
            "90": "90th percentile confidence limit",
        }[layer.component]
        if str(properties.get("Component", "")).lower() != expected_component.lower():
            raise CatalogueError(f"STAC component mismatch for {layer.product_id}.")
        depth_top, depth_bottom = layer.depth_code.split("_")
        if properties.get("Depth") != f"{depth_top} - {depth_bottom} cm":
            raise CatalogueError(f"STAC depth mismatch for {layer.product_id}.")
        if properties.get("AREA_OR_POINT") != self.profile.area_or_point:
            raise CatalogueError(f"STAC AREA_OR_POINT mismatch for {layer.product_id}.")
        if (
            layer.product.doi.lower()
            not in str(properties.get("sci:citation", "")).lower()
        ):
            raise CatalogueError(f"STAC citation/DOI mismatch for {layer.product_id}.")

        assets = _require_mapping(item, "assets", layer.product_id)
        asset = assets.get(layer.filename)
        if not isinstance(asset, Mapping):
            raise CatalogueError(f"Pinned COG asset is missing for {layer.product_id}.")
        if asset.get("href") not in {layer.url, f"./{layer.filename}", layer.filename}:
            raise CatalogueError(f"STAC asset URL mismatch for {layer.product_id}.")
        if (
            asset.get("type")
            != "image/tiff; application=geotiff; profile=cloud-optimized"
        ):
            raise CatalogueError(
                f"STAC asset media type mismatch for {layer.product_id}."
            )
        if asset.get("file:size") != layer.file_size_bytes:
            raise CatalogueError(f"STAC file size mismatch for {layer.product_id}.")
        if asset.get("file:checksum") != layer.stac_multihash:
            raise CatalogueError(f"STAC multihash mismatch for {layer.product_id}.")
        if asset.get("proj:epsg") != 4326:
            raise CatalogueError(f"STAC asset CRS mismatch for {layer.product_id}.")
        _require_sequence_equal(
            asset.get("proj:shape"),
            [self.profile.width, self.profile.height],
            f"STAC asset shape mismatch for {layer.product_id}.",
        )
        _require_float_sequence_close(
            asset.get("proj:transform"),
            self.profile.transform,
            f"STAC asset transform mismatch for {layer.product_id}.",
        )

        bands = asset.get("raster:bands")
        if (
            not isinstance(bands, list)
            or len(bands) != 1
            or not isinstance(bands[0], Mapping)
        ):
            raise CatalogueError(f"Malformed STAC raster:bands for {layer.product_id}.")
        band = bands[0]
        if band.get("data_type") != layer.product.dtype:
            raise CatalogueError(f"STAC dtype mismatch for {layer.product_id}.")
        if layer.property_code == "AWC":
            # Narrowly approved upstream exception: AWC STAC omits nodata.
            if "nodata" in band:
                raise CatalogueError(
                    f"AWC STAC nodata changed for {layer.product_id}; review the pinned exception."
                )
        elif not _is_nan_token(band.get("nodata")):
            raise CatalogueError(f"STAC nodata mismatch for {layer.product_id}.")


def load_source_catalogue(path: str | Path) -> SourceCatalogue:
    manifest_path = Path(path)
    raw_bytes = manifest_path.read_bytes()
    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise CatalogueError(
            f"Malformed source manifest JSON: {manifest_path}."
        ) from exc
    if not isinstance(payload, dict):
        raise CatalogueError("Source manifest root must be a JSON object.")

    if payload.get("manifest_schema_version") != 1:
        raise CatalogueError("Unsupported source manifest schema version.")
    if payload.get("manifest_id") != EXPECTED_MANIFEST_ID:
        raise CatalogueError(
            f"Unexpected source manifest ID: {payload.get('manifest_id')!r}."
        )
    if payload.get("credential_environment_variable") != "TERN_API_KEY":
        raise CatalogueError(
            "Unexpected credential environment variable in source manifest."
        )

    profile_payload = _require_mapping(payload, "common_profile", EXPECTED_MANIFEST_ID)
    shape = profile_payload.get("shape")
    if not isinstance(shape, list) or len(shape) != 2:
        raise CatalogueError(
            "Manifest common_profile.shape must contain [height, width]."
        )
    transform = _float_tuple(
        profile_payload.get("transform"), 6, "common_profile.transform"
    )
    bounds = _float_tuple(profile_payload.get("bounds"), 4, "common_profile.bounds")
    profile = CommonProfile(
        driver=_require_string(profile_payload, "driver"),
        crs=_require_string(profile_payload, "crs"),
        height=_positive_int(shape[0], "common_profile.shape[0]"),
        width=_positive_int(shape[1], "common_profile.shape[1]"),
        transform=transform,
        bounds=bounds,
        band_count=_positive_int(profile_payload.get("band_count"), "band_count"),
        area_or_point=_require_string(profile_payload, "area_or_point"),
    )
    if (
        profile.driver != "GTiff"
        or profile.crs != "EPSG:4326"
        or (profile.height, profile.width) != EXPECTED_SHAPE
        or not _float_sequences_close(profile.transform, EXPECTED_TRANSFORM)
        or not _float_sequences_close(profile.bounds, EXPECTED_BOUNDS)
        or profile.band_count != 1
        or profile.area_or_point != "Area"
    ):
        raise CatalogueError("Pinned common profile identity has changed.")

    products_payload = _require_mapping(payload, "products", EXPECTED_MANIFEST_ID)
    if set(products_payload) != {"AWC", "DES"}:
        raise CatalogueError("Source manifest must contain only AWC and DES products.")
    products = {
        code: _parse_product(code, _require_mapping(products_payload, code, code))
        for code in ("AWC", "DES")
    }
    _validate_products(products)

    layer_payloads = payload.get("layers")
    if (
        not isinstance(layer_payloads, list)
        or len(layer_payloads) != EXPECTED_LAYER_COUNT
    ):
        raise CatalogueError(
            f"Source manifest must contain exactly {EXPECTED_LAYER_COUNT} layers."
        )

    source_base = _require_string(payload, "source_base_url").rstrip("/")
    if source_base != EXPECTED_SOURCE_BASE_URL:
        raise CatalogueError("Pinned TERN source base URL has changed.")
    layers: dict[str, LayerSpec] = {}
    observed_combinations: set[tuple[str, str, str]] = set()
    for layer_payload in layer_payloads:
        if not isinstance(layer_payload, dict):
            raise CatalogueError("Every source layer must be a JSON object.")
        product_id = _require_string(layer_payload, "product_id")
        if product_id in layers:
            raise CatalogueError(f"Duplicate source product ID: {product_id}.")
        property_code = _require_string(layer_payload, "property")
        if property_code not in products:
            raise CatalogueError(
                f"Unapproved property for {product_id}: {property_code!r}."
            )
        product = products[property_code]
        depth_code = _require_string(layer_payload, "depth_code")
        component = _require_string(layer_payload, "component")
        url = _require_string(layer_payload, "url")
        parsed_url = urlparse(url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
            or not url.startswith(source_base + "/")
            or not url.endswith(f"/{product_id}.tif")
        ):
            raise CatalogueError(f"Unsafe or mismatched pinned URL for {product_id}.")
        expected_product_id = _expected_product_id(property_code, depth_code, component)
        if product_id != expected_product_id:
            raise CatalogueError(
                f"Pinned full product ID mismatch: expected {expected_product_id}, got {product_id}."
            )
        combination = (property_code, depth_code, component)
        if combination in observed_combinations:
            raise CatalogueError(f"Duplicate source layer combination: {combination}.")
        observed_combinations.add(combination)
        multihash = _require_string(layer_payload, "stac_multihash")
        if not MULTIHASH_PATTERN.fullmatch(multihash):
            raise CatalogueError(f"Malformed STAC multihash for {product_id}.")
        layers[product_id] = LayerSpec(
            product_id=product_id,
            property_code=property_code,
            depth_code=depth_code,
            component=component,
            url=url,
            stac_url=url.removesuffix(".tif") + ".json",
            stac_multihash=multihash,
            file_size_bytes=_positive_int(
                layer_payload.get("file_size_bytes"),
                f"file_size_bytes for {product_id}",
            ),
            product=product,
        )

    expected_combinations = {
        (code, depth, component)
        for code, product in products.items()
        for depth in product.depths
        for component in product.components
    }
    if observed_combinations != expected_combinations:
        missing = sorted(expected_combinations - observed_combinations)
        extra = sorted(observed_combinations - expected_combinations)
        raise CatalogueError(
            f"Source layer set mismatch; missing={missing}, extra={extra}."
        )

    return SourceCatalogue(
        path=manifest_path,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        manifest_id=EXPECTED_MANIFEST_ID,
        credential_environment_variable="TERN_API_KEY",
        profile=profile,
        products=products,
        layers=layers,
    )


def _expected_product_id(property_code: str, depth_code: str, component: str) -> str:
    if property_code == "AWC":
        return f"AWC_{depth_code}_{component}_N_P_AU_TRN_N_20210614"
    if property_code == "DES":
        return f"DES_{depth_code}_{component}_N_P_AU_TRN_C_20190901"
    raise CatalogueError(f"Unsupported source property: {property_code}.")


def _parse_product(code: str, payload: Mapping[str, Any]) -> ProductSpec:
    components_payload = _require_mapping(payload, "components", code)
    depths_payload = payload.get("included_depths_cm")
    if not isinstance(depths_payload, list):
        raise CatalogueError(f"Product {code} included_depths_cm must be a list.")
    depths: list[str] = []
    for bounds in depths_payload:
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or not all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in bounds
            )
            or bounds[0] < 0
            or bounds[1] <= bounds[0]
        ):
            raise CatalogueError(
                f"Malformed depth bounds for product {code}: {bounds!r}."
            )
        depths.append(f"{bounds[0]:03d}_{bounds[1]:03d}")

    nodata_raw = payload.get("nodata")
    if _is_nan_token(nodata_raw):
        nodata = math.nan
    elif isinstance(nodata_raw, (int, float)) and not isinstance(nodata_raw, bool):
        nodata = float(nodata_raw)
    else:
        raise CatalogueError(f"Malformed nodata for product {code}.")

    if payload.get("current_status_at_verification") is not True:
        raise CatalogueError(
            f"Product {code} is not pinned as current at verification time."
        )

    return ProductSpec(
        code=code,
        title=_require_string(payload, "title"),
        version=_positive_int(payload.get("version"), f"version for {code}"),
        doi=_require_string(payload, "doi"),
        units=_require_string(payload, "units"),
        dtype=_require_string(payload, "dtype"),
        nodata=nodata,
        components=tuple(str(component) for component in components_payload),
        depths=tuple(depths),
        citation=_require_string(payload, "citation"),
    )


def _validate_products(products: Mapping[str, ProductSpec]) -> None:
    awc = products["AWC"]
    des = products["DES"]
    if (
        awc.version != 2
        or awc.doi != "10.25919/4jwj-na34"
        or awc.units != "Percent"
        or awc.dtype != "uint16"
        or awc.nodata != 65535.0
        or awc.components != ("EV", "05", "95")
        or awc.depths != ("000_005", "005_015", "015_030", "030_060", "060_100")
    ):
        raise CatalogueError("Pinned AWC v2 product contract has changed.")
    if (
        des.version != 2
        or des.doi != "10.25919/djdn-5x77"
        or des.units != "metres"
        or des.dtype != "float32"
        or not math.isnan(des.nodata)
        or des.components != ("EV", "10", "90")
        or des.depths != ("000_200",)
    ):
        raise CatalogueError("Pinned DES v2 product contract has changed.")


def _require_mapping(
    payload: Mapping[str, Any], key: str, context: str
) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise CatalogueError(f"Missing or malformed {key!r} in {context}.")
    return value


def _require_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogueError(f"Missing or malformed string field: {key}.")
    return value


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CatalogueError(f"{field} must be a positive integer.")
    return value


def _float_tuple(value: Any, length: int, field: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise CatalogueError(f"{field} must contain {length} numbers.")
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise CatalogueError(f"{field} contains a non-numeric value.") from exc
    if not all(math.isfinite(item) for item in result):
        raise CatalogueError(f"{field} contains a non-finite value.")
    return result


def _require_sequence_equal(actual: Any, expected: list[int], message: str) -> None:
    if not isinstance(actual, list) or actual != expected:
        raise CatalogueError(message)


def _require_float_sequence_close(
    actual: Any,
    expected: tuple[float, ...],
    message: str,
    *,
    abs_tolerance: float = TRANSFORM_ABS_TOLERANCE,
) -> None:
    if not isinstance(actual, list) or not _float_sequences_close(
        actual, expected, abs_tolerance=abs_tolerance
    ):
        raise CatalogueError(message)


def _float_sequences_close(
    actual: Any,
    expected: tuple[float, ...],
    *,
    abs_tolerance: float = TRANSFORM_ABS_TOLERANCE,
) -> bool:
    if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
        return False
    try:
        return all(
            math.isclose(float(value), reference, rel_tol=0.0, abs_tol=abs_tolerance)
            for value, reference in zip(actual, expected, strict=True)
        )
    except (TypeError, ValueError):
        return False


def _is_nan_token(value: Any) -> bool:
    return (isinstance(value, str) and value.lower() == "nan") or (
        isinstance(value, float) and math.isnan(value)
    )
