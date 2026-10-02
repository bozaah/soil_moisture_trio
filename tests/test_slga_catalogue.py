import copy
import json
from pathlib import Path

import pytest

from src.soil_moisture_trio.slga.catalogue import CatalogueError, load_source_catalogue

MANIFEST_PATH = Path("manifests/slga_awc_des_sources_v1.json")


def _write_manifest(tmp_path: Path, mutate) -> Path:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mutate(payload)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _stac_item(catalogue, layer):
    profile = catalogue.profile
    band = {"data_type": layer.product.dtype}
    if layer.property_code == "DES":
        band["nodata"] = "nan"
    component = {
        "EV": "Estimated Value",
        "05": "5th percentile confidence limit",
        "95": "95th percentile confidence limit",
        "10": "10th percentile confidence limit",
        "90": "90th percentile confidence limit",
    }[layer.component]
    soil_property = {
        "AWC": "Available Water Capacity",
        "DES": "Depth of Soil",
    }[layer.property_code]
    depth_top, depth_bottom = layer.depth_code.split("_")
    return {
        "type": "Feature",
        "id": layer.product_id,
        "bbox": list(profile.bounds),
        "properties": {
            "proj:epsg": 4326,
            "proj:shape": [profile.width, profile.height],
            "proj:transform": list(profile.transform),
            "UNITS": layer.product.units,
            "Soil Property": soil_property,
            "Component": component,
            "Depth": f"{depth_top} - {depth_bottom} cm",
            "AREA_OR_POINT": profile.area_or_point,
            "sci:citation": layer.product.citation,
        },
        "assets": {
            layer.filename: {
                "href": f"./{layer.filename}",
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "file:size": layer.file_size_bytes,
                "file:checksum": layer.stac_multihash,
                "proj:epsg": 4326,
                "proj:shape": [profile.width, profile.height],
                "proj:transform": list(profile.transform),
                "raster:bands": [band],
            }
        },
    }


def test_loads_exact_pinned_catalogue():
    catalogue = load_source_catalogue(MANIFEST_PATH)

    assert catalogue.manifest_id == "slga_awc_des_sources_v1"
    assert len(catalogue.layers) == 18
    assert len(catalogue.sha256) == 64
    assert {layer.property_code for layer in catalogue.layers.values()} == {
        "AWC",
        "DES",
    }
    assert {
        layer.component
        for layer in catalogue.layers.values()
        if layer.property_code == "DES"
    } == {
        "EV",
        "10",
        "90",
    }


def test_catalogue_rejects_version_drift(tmp_path):
    path = _write_manifest(
        tmp_path, lambda payload: payload["products"]["AWC"].update(version=3)
    )

    with pytest.raises(CatalogueError, match="AWC v2"):
        load_source_catalogue(path)


def test_catalogue_rejects_duplicate_or_missing_layer(tmp_path):
    def duplicate(payload):
        payload["layers"][-1] = copy.deepcopy(payload["layers"][0])

    path = _write_manifest(tmp_path, duplicate)

    with pytest.raises(CatalogueError, match="Duplicate source product ID"):
        load_source_catalogue(path)


def test_catalogue_rejects_source_redirect(tmp_path):
    path = _write_manifest(
        tmp_path,
        lambda payload: payload.update(source_base_url="https://example.invalid/slga"),
    )

    with pytest.raises(CatalogueError, match="source base URL"):
        load_source_catalogue(path)


def test_catalogue_requires_full_ids_not_shorthand():
    catalogue = load_source_catalogue(MANIFEST_PATH)

    with pytest.raises(CatalogueError, match="not approved"):
        catalogue.require("AWC")


def test_stac_validation_accepts_only_documented_awc_nodata_omission():
    catalogue = load_source_catalogue(MANIFEST_PATH)
    layer = next(
        layer for layer in catalogue.layers.values() if layer.property_code == "AWC"
    )
    item = _stac_item(catalogue, layer)

    catalogue.validate_stac_item(layer, item)
    item["assets"][layer.filename]["raster:bands"][0]["nodata"] = 65535

    with pytest.raises(CatalogueError, match="AWC STAC nodata changed"):
        catalogue.validate_stac_item(layer, item)


def test_stac_validation_rejects_identity_and_checksum_drift():
    catalogue = load_source_catalogue(MANIFEST_PATH)
    layer = next(iter(catalogue.layers.values()))
    item = _stac_item(catalogue, layer)
    item["id"] = "unexpected"

    with pytest.raises(CatalogueError, match="STAC ID mismatch"):
        catalogue.validate_stac_item(layer, item)

    item = _stac_item(catalogue, layer)
    item["assets"][layer.filename]["file:checksum"] = "d50110" + "0" * 32
    with pytest.raises(CatalogueError, match="multihash mismatch"):
        catalogue.validate_stac_item(layer, item)
