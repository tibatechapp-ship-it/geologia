from fastapi.testclient import TestClient

from geologia.api import app


client = TestClient(app)


def _coverage_payload():
    return {
        "context": {
            "product_dataset_id": "dataset-dem-1",
            "reference_dataset_id": "dataset-reference-1",
            "product_version_id": "copernicus-glo30-release-x",
            "pilot_area_id": "yemen-pilot-west-01",
            "reference_source_id": "icesat2-atl08-release-x",
            "primary_stratum_id": "steep-bare",
            "task_profile_id": "regional-reconnaissance-v1",
        },
        "phase": "exploratory",
        "actual_coverage": {
            "availability": "available",
            "value": "coverage://glo30/release-x/yemen-pilot-west-01",
        },
        "coverage_status": "verified",
        "evidence": {
            "coverage_footprint_reference": "evidence://coverage-footprint/1",
            "coverage_verification_method": "Raster footprint intersected with registered AOI.",
            "coverage_reviewer": "reviewer-1",
            "coverage_verified_at": "2026-11-22T02:00:00Z",
            "metrics_source_reference": "evidence://reference-observations/1",
            "metrics_computation_method": "Frozen equal-area grid count script.",
            "metrics_computed_by": "analyst-1",
            "metrics_computed_at": "2026-11-22T02:05:00Z",
            "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "analysis_code_commit": "a1b2c3d4",
        },
        "metrics": {
            "valid_independent_locations": 60,
            "polygon_area_km2": 3.0,
            "occupied_1km_cells": 40,
            "eligible_1km_cells": 60,
            "occupied_5km_blocks": 20,
            "eligible_5km_blocks": 30,
            "max_block_observation_fraction": 0.5,
            "primary_cell_observation_counts": {
                "steep_bare": 30,
                "moderate_bare": 30,
            },
        },
    }


def test_dem_coverage_assessment_api_returns_contextual_gates():
    response = client.post("/api/v1/dem/coverage-assessments", json=_coverage_payload())
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "sufficient"
    assert result["context"]["pilot_area_id"] == "yemen-pilot-west-01"
    assert result["valid_independent_locations_per_km2"] == 20
    assert result["occupied_1km_cell_fraction"] == 2 / 3


def test_dem_coverage_api_rejects_analogue_region_as_coverage_evidence():
    payload = _coverage_payload()
    payload["analogue_region"] = "Asir western highlands"
    response = client.post("/api/v1/dem/coverage-assessments", json=payload)
    assert response.status_code == 422


def test_dem_coverage_threshold_endpoint_exposes_frozen_protocol():
    response = client.get("/api/v1/dem/coverage-thresholds")
    assert response.status_code == 200
    thresholds = response.json()
    assert thresholds["protocol_version"] == "1"
    assert thresholds["section_17"]["confirmatory_valid_locations_per_km2"] == 40
    assert thresholds["section_20"]["bootstrap_replicates"] == 2000


def _create_project(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "coverage.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    response = client.post("/api/v1/projects", json={"name": "DEM coverage audit"})
    assert response.status_code == 201
    return response.json()


def _upload_coverage_dataset(project_id, filename, data, role):
    return client.post(
        f"/api/v1/projects/{project_id}/datasets",
        content=data,
        headers={
            "X-Dataset-Name": filename,
            "X-Filename": filename,
            "X-Data-Role": role,
        },
    )


def test_project_coverage_assessment_is_persisted_and_chain_verified(tmp_path, monkeypatch):
    project = _create_project(tmp_path, monkeypatch)
    product = _upload_coverage_dataset(
        project["id"], "candidate.tif", b"dem-placeholder-bytes", "dem"
    )
    reference = _upload_coverage_dataset(
        project["id"],
        "reference.geojson",
        b'{"type":"FeatureCollection","features":[]}',
        "reference_elevation_observations",
    )
    assert product.status_code == 201
    assert reference.status_code == 201

    payload = _coverage_payload()
    payload["context"]["product_dataset_id"] = product.json()["id"]
    payload["context"]["reference_dataset_id"] = reference.json()["id"]
    saved = client.post(
        f"/api/v1/projects/{project['id']}/dem/coverage-assessments",
        json={"created_by": "operator-1", "request": payload},
    )
    assert saved.status_code == 201
    record = saved.json()
    assert record["assessment"]["status"] == "sufficient"
    assert record["created_by"] == "operator-1"
    assert record["record_hash"]

    listed = client.get(
        f"/api/v1/projects/{project['id']}/dem/coverage-assessments"
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["assessments"][0]["id"] == record["id"]

    detail = client.get(
        f"/api/v1/projects/{project['id']}/dem/coverage-assessments/{record['id']}"
    )
    assert detail.status_code == 200
    assert detail.json()["record_hash"] == record["record_hash"]

    integrity = client.get(
        f"/api/v1/projects/{project['id']}/dem/coverage-assessments/integrity"
    )
    assert integrity.status_code == 200
    assert integrity.json()["valid"] is True
    assert integrity.json()["record_count"] == 1


def test_persistent_assessment_rejects_dataset_integrity_mismatch(tmp_path, monkeypatch):
    from geologia import store

    project = _create_project(tmp_path, monkeypatch)
    product = _upload_coverage_dataset(
        project["id"], "candidate.tif", b"dem-placeholder-bytes", "dem"
    )
    reference = _upload_coverage_dataset(
        project["id"],
        "reference.geojson",
        b'{"type":"FeatureCollection","features":[]}',
        "reference_elevation_observations",
    )
    payload = _coverage_payload()
    payload["context"]["product_dataset_id"] = product.json()["id"]
    payload["context"]["reference_dataset_id"] = reference.json()["id"]
    product_path = store.get_dataset_content_path(product.json()["id"])
    with open(product_path, "ab") as target:
        target.write(b"tampered")
    response = client.post(
        f"/api/v1/projects/{project['id']}/dem/coverage-assessments",
        json={"created_by": "operator-1", "request": payload},
    )
    assert response.status_code == 409
