"""Tests for read-only geoid GeoTIFF metadata inspection."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.inspect_geoid_grid_metadata import inspect_directory, inspect_grid

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
Affine = pytest.importorskip("affine").Affine
from_origin = rasterio.transform.from_origin


def write_grid(path: Path, *, crs="EPSG:4326", transform=None, width=8, height=4):
    if transform is None:
        transform = from_origin(-180.0, 90.0, 45.0, 45.0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
    ) as dataset:
        dataset.write(np.zeros((height, width), dtype="float32"), 1)


def test_inspection_accepts_matching_global_geographic_metadata(tmp_path):
    path = tmp_path / "fixture.tif"
    write_grid(path)
    spec = {
        "model_id": "fixture",
        "file_name": path.name,
        "width": 8,
        "height": 4,
        "horizontal_crs": "EPSG:4326",
    }
    result = inspect_grid(path, spec)
    assert result["status"] == "metadata_matches_pinned_expectations"
    assert all(result["checks"].values())
    assert result["actual_crs"] == "EPSG:4326"


def test_inspection_rejects_wrong_crs_and_dimensions(tmp_path):
    path = tmp_path / "fixture.tif"
    write_grid(path, crs="EPSG:3857", width=7)
    spec = {
        "model_id": "fixture",
        "file_name": path.name,
        "width": 8,
        "height": 4,
        "horizontal_crs": "EPSG:4326",
    }
    result = inspect_grid(path, spec)
    assert result["status"] == "rejected"
    assert not result["checks"]["dimensions_match"]
    assert not result["checks"]["horizontal_crs_matches"]


def test_inspection_rejects_rotated_grid(tmp_path):
    path = tmp_path / "fixture.tif"
    transform = Affine(45, 1, -180, 0, -45, 90)
    write_grid(path, transform=transform)
    spec = {
        "model_id": "fixture",
        "file_name": path.name,
        "width": 8,
        "height": 4,
        "horizontal_crs": "EPSG:4326",
    }
    result = inspect_grid(path, spec)
    assert result["status"] == "rejected"
    assert not result["checks"]["north_up_unrotated"]


def test_missing_file_fails_closed(tmp_path):
    result = inspect_grid(
        tmp_path / "missing.tif",
        {"model_id": "fixture", "file_name": "missing.tif"},
    )
    assert result["status"] == "rejected"


def test_report_never_authorizes_scientific_transform(tmp_path):
    path = tmp_path / "fixture.tif"
    write_grid(path)
    manifest = {
        "schema": "geologia-geoid-grid-integrity/1",
        "grids": [
            {
                "model_id": "fixture",
                "file_name": path.name,
                "width": 8,
                "height": 4,
                "horizontal_crs": "EPSG:4326",
            }
        ],
    }
    report = inspect_directory(tmp_path, manifest)
    assert report["metadata_checks_passed"]
    assert report["scientific_validation"] is False
    assert report["vertical_transformation_enabled"] is False
    assert len(report["limitations"]) == 4
