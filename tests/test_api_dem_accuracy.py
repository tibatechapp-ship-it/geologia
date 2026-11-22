import csv
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from geologia.api import app

client = TestClient(app)


def _create_project(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "accuracy-api.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    response = client.post("/api/v1/projects", json={"name": "DEM accuracy evidence"})
    assert response.status_code == 201
    return response.json()


def _upload(project_id, filename, content, role):
    return client.post(
        f"/api/v1/projects/{project_id}/datasets",
        content=content,
        headers={
            "X-Dataset-Name": filename,
            "X-Filename": filename,
            "X-Data-Role": role,
        },
    )


def test_api_computes_and_persists_manifest_bound_dem_accuracy(tmp_path, monkeypatch):
    rasterio = pytest.importorskip("rasterio")
    numpy = pytest.importorskip("numpy")
    from rasterio.transform import from_origin

    project = _create_project(tmp_path, monkeypatch)
    tile_ids = []
    tile_hashes = []
    for filename, left in (("tile-a.tif", 500000), ("tile-b.tif", 500300)):
        raster_path = tmp_path / filename
        with rasterio.open(
            raster_path,
            "w",
            driver="GTiff",
            width=10,
            height=10,
            count=1,
            dtype="float32",
            crs="EPSG:32638",
            transform=from_origin(left, 1700000, 30, 30),
            nodata=-9999,
        ) as dataset:
            dataset.write(
                numpy.full((10, 10), 100, dtype=numpy.float32), 1
            )
        uploaded = _upload(
            project["id"], filename, raster_path.read_bytes(), "dem"
        )
        assert uploaded.status_code == 201
        tile_ids.append(uploaded.json()["id"])
        tile_hashes.append(uploaded.json()["sha256"])

    aoi_payload = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [500000, 1699700],
                [500600, 1699700],
                [500600, 1700000],
                [500000, 1700000],
                [500000, 1699700],
            ]],
        },
    }
    aoi = _upload(
        project["id"],
        "accuracy-aoi.geojson",
        json.dumps(aoi_payload).encode("utf-8"),
        "aoi_boundary",
    )
    points = [
        ("p1", 500015, 1699985, 98),
        ("p2", 500045, 1699955, 99),
        ("p3", 500075, 1699925, 100),
        ("p4", 500105, 1699895, 101),
    ]
    reference_path = tmp_path / "reference.csv"
    with reference_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow([
            "point_id", "x", "y", "elevation_m", "terrain_stratum", "uncertainty_m"
        ])
        for point in points:
            writer.writerow([*point, "steep_bare", 0.2])
    reference = _upload(
        project["id"],
        "reference.csv",
        reference_path.read_bytes(),
        "reference_elevation_observations",
    )
    assert aoi.status_code == 201
    assert reference.status_code == 201

    manifest_payload = {
        "schema": "geologia.dem-tile-manifest.v1",
        "product_version_id": "dem-release-2026-01",
        "tile_dataset_ids": tile_ids,
        "tile_dataset_sha256s": tile_hashes,
    }
    manifest = _upload(
        project["id"],
        "dem-manifest.json",
        json.dumps(manifest_payload).encode("utf-8"),
        "dem_tile_manifest",
    )
    assert manifest.status_code == 201

    coverage = client.post(
        f"/api/v1/projects/{project['id']}/dem/tile-collection-coverage-inspection",
        json={
            "dem_dataset_ids": tile_ids,
            "aoi_dataset_id": aoi.json()["id"],
            "aoi_crs": "EPSG:32638",
        },
    )
    assert coverage.status_code == 200, coverage.text
    coverage_reference = coverage.json()["coverage_footprint_reference"]
    reviewed_at = datetime.now(UTC).isoformat()

    request = {
        "product_manifest_dataset_id": manifest.json()["id"],
        "reference_dataset_id": reference.json()["id"],
        "aoi_dataset_id": aoi.json()["id"],
        "metadata": {
            "product_version_id": "dem-release-2026-01",
            "dem_vertical_datum": "NAVD88",
            "reference_vertical_datum": "NAVD88",
            "dem_vertical_unit": "m",
            "reference_vertical_unit": "m",
            "dem_surface_type": "DTM",
            "reference_surface_type": "DTM",
            "dem_epoch": "2020",
            "reference_epoch": "2020",
            "reference_source_id": "gnss-control-network-1",
            "reference_release": "release-2026-01",
            "reference_horizontal_crs": "EPSG:32638",
            "aoi_crs": "EPSG:32638",
            "dem_metadata_reference": "metadata://dem/release-1",
            "reference_metadata_reference": "metadata://reference/release-1",
            "independence_status": "independent_confirmed",
            "independence_evidence_reference": "evidence://independence/review-1",
            "independence_reviewer": "reviewer-1",
            "independence_reviewed_at": reviewed_at,
        },
        "declared_use": {
            "product_name": "Example DEM",
            "product_version_id": "dem-release-2026-01",
            "pilot_area_id": "pilot-1",
            "task_profile_id": "regional-recon-v1",
            "intended_user": "geological researcher",
            "declared_scale": "regional reconnaissance",
        },
        "independent_review": {
            "product_version_id": "dem-release-2026-01",
            "pilot_area_id": "pilot-1",
            "task_profile_id": "regional-recon-v1",
            "reviewer": "reviewer-1",
            "evidence_reference": "evidence://independence/review-1",
            "reviewed_at": reviewed_at,
        },
        "coverage_footprint_reference": coverage_reference,
        "requirement": {
            "metric": "rmse_m",
            "maximum_value_m": 1.5,
            "minimum_valid_observations": 4,
            "requirement_reference": "task-profile://regional-recon-v1/accuracy",
            "approved_by": "reviewer-1",
            "frozen_at": reviewed_at,
        },
        "created_by": "analyst-1",
    }
    saved = client.post(
        f"/api/v1/projects/{project['id']}/dem/accuracy-assessments",
        json=request,
    )
    assert saved.status_code == 201, saved.text
    record = saved.json()
    assert record["assessment"]["accuracy_disposition"] == (
        "accuracy_requirement_met_for_declared_use"
    )
    assert record["assessment"]["metrics"]["rmse_m"] == pytest.approx((1.5) ** 0.5)
    assert record["assessment"]["readiness_disposition"] == "not_assessed"

    mismatched_request = json.loads(json.dumps(request))
    mismatched_request["independent_review"]["pilot_area_id"] = "pilot-other"
    mismatched = client.post(
        f"/api/v1/projects/{project['id']}/dem/accuracy-assessments",
        json=mismatched_request,
    )
    assert mismatched.status_code == 409

    chain = client.get(
        f"/api/v1/projects/{project['id']}/dem/accuracy-assessments/chain"
    )
    assert chain.status_code == 200
    assert chain.json()["valid"] is True
    assert chain.json()["record_count"] == 1
    retrieved = client.get(
        f"/api/v1/projects/{project['id']}/dem/accuracy-assessments/{record['id']}"
    )
    assert retrieved.status_code == 200
    assert retrieved.json()["record_hash"] == record["record_hash"]
