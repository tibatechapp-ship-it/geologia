import pytest
from pydantic import ValidationError

from geologia.dem_readiness.manifest import DEMTileManifest


def valid_manifest(**overrides):
    values = {
        "schema": "geologia.dem-tile-manifest.v1",
        "product_version_id": "dem-release-2026-01",
        "tile_dataset_ids": ("tile-a", "tile-b"),
        "tile_dataset_sha256s": ("a" * 64, "b" * 64),
    }
    values.update(overrides)
    return DEMTileManifest(**values)


def test_dem_tile_manifest_binds_each_tile_to_its_checksum():
    manifest = valid_manifest()
    assert manifest.tile_dataset_ids == ("tile-a", "tile-b")
    assert manifest.tile_dataset_sha256s == ("a" * 64, "b" * 64)


def test_dem_tile_manifest_rejects_duplicate_tile_ids():
    with pytest.raises(ValidationError, match="must be unique"):
        valid_manifest(tile_dataset_ids=("tile-a", "tile-a"))


def test_dem_tile_manifest_rejects_mismatched_id_and_hash_counts():
    with pytest.raises(ValidationError, match="exactly one SHA-256"):
        valid_manifest(tile_dataset_sha256s=("a" * 64,))


def test_dem_tile_manifest_rejects_invalid_checksum():
    with pytest.raises(ValidationError):
        valid_manifest(tile_dataset_sha256s=("not-a-sha", "b" * 64))


def test_dem_tile_manifest_rejects_unknown_schema_fields():
    with pytest.raises(ValidationError):
        valid_manifest(untrusted_metadata="ignored")
