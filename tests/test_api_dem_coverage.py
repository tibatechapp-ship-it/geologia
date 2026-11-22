import json

from fastapi.testclient import TestClient

from geologia.api import app


client = TestClient(app)


def _coverage_payload():
    return {
        "context": {
            "product_dataset_id": "dataset-dem-1",
            "product_dataset_sha256": "b" * 64,
            "reference_dataset_id": "dataset-reference-1",
            "reference_dataset_sha256": "a" * 64,
            "aoi_dataset_id": "dataset-aoi-1",
            "aoi_dataset_sha256": "c" * 64,
            "product_version_id": "copernicus-glo30-release-x",
            "dem_epoch": "2025-01-01",
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
            "coverage_footprint_reference": "coverage://glo30/release-x/yemen-pilot-west-01",
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



def _aoi_geojson_bytes():
    return json.dumps({
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [500000, 1699700],
                [500300, 1699700],
                [500300, 1700000],
                [500000, 1700000],
                [500000, 1699700],
            ]],
        },
    }).encode("utf-8")


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




def _save_test_coverage_inspection(product, aoi, *, full=True):
    from geologia import store

    reference = f"coverage-inspection:{product['id']}:test-record"
    report = {
        "inspection_status": "measured",
        "coverage_status": (
            "full_aoi_extent_and_valid_pixels"
            if full
            else "partial_valid_data_within_raster_extent"
        ),
        "aoi_fully_within_raster_extent": full,
        "all_aoi_pixel_centres_valid": full,
        "product_dataset_id": product["id"],
        "product_dataset_sha256": product["sha256"],
        "aoi_dataset_id": aoi["id"],
        "aoi_dataset_sha256": aoi["sha256"],
        "coverage_footprint_reference": reference,
        "inspected_at_utc": "2026-11-22T02:00:00+00:00",
    }
    store.save_dataset_coverage_inspection(product["id"], report)
    return reference




def _save_test_reference_metrics(reference, aoi, payload):
    from geologia import store
    from geologia.dem_readiness.coverage import CoverageMetrics

    report_reference = f"reference-coverage-metrics:{reference['id']}:test-record"
    report = {
        "status": "measured",
        "independence_review_status": "attested_complete",
        "reference_dataset_sha256": reference["sha256"],
        "aoi_dataset_id": aoi["id"],
        "aoi_dataset_sha256": aoi["sha256"],
        "dem_epoch": payload["context"]["dem_epoch"],
        "metrics": CoverageMetrics.model_validate(
            payload["metrics"]
        ).model_dump(mode="json"),
        "metrics_reference": report_reference,
        "computation_method": "reference-coverage-v1.0",
        "computed_by": "analyst-1",
        "computed_at_utc": "2026-11-22T02:05:00+00:00",
        "analysis_code_commit": "a1b2c3d4",
    }
    store.save_reference_coverage_metrics(reference["id"], report)
    payload["evidence"]["metrics_source_reference"] = report_reference
    payload["evidence"]["metrics_computation_method"] = report["computation_method"]
    payload["evidence"]["metrics_computed_by"] = report["computed_by"]
    payload["evidence"]["metrics_computed_at"] = report["computed_at_utc"]
    payload["evidence"]["analysis_code_commit"] = report["analysis_code_commit"]

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
    aoi = _upload_coverage_dataset(
        project["id"],
        "pilot-aoi.geojson",
        _aoi_geojson_bytes(),
        "aoi_boundary",
    )
    assert reference.status_code == 201
    assert aoi.status_code == 201

    payload = _coverage_payload()
    payload["context"]["product_dataset_id"] = product.json()["id"]
    payload["context"]["product_dataset_sha256"] = product.json()["sha256"]
    payload["context"]["reference_dataset_id"] = reference.json()["id"]
    payload["context"]["reference_dataset_sha256"] = reference.json()["sha256"]
    payload["context"]["aoi_dataset_id"] = aoi.json()["id"]
    payload["context"]["aoi_dataset_sha256"] = aoi.json()["sha256"]
    payload["evidence"]["source_sha256"] = reference.json()["sha256"]
    footprint_reference = _save_test_coverage_inspection(product.json(), aoi.json())
    payload["actual_coverage"]["value"] = footprint_reference
    payload["evidence"]["coverage_footprint_reference"] = footprint_reference
    _save_test_reference_metrics(reference.json(), aoi.json(), payload)
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
    aoi = _upload_coverage_dataset(
        project["id"],
        "pilot-aoi.geojson",
        _aoi_geojson_bytes(),
        "aoi_boundary",
    )
    assert aoi.status_code == 201
    payload = _coverage_payload()
    payload["context"]["product_dataset_id"] = product.json()["id"]
    payload["context"]["product_dataset_sha256"] = product.json()["sha256"]
    payload["context"]["reference_dataset_id"] = reference.json()["id"]
    payload["context"]["reference_dataset_sha256"] = reference.json()["sha256"]
    payload["context"]["aoi_dataset_id"] = aoi.json()["id"]
    payload["context"]["aoi_dataset_sha256"] = aoi.json()["sha256"]
    payload["evidence"]["source_sha256"] = reference.json()["sha256"]
    footprint_reference = _save_test_coverage_inspection(product.json(), aoi.json())
    payload["actual_coverage"]["value"] = footprint_reference
    payload["evidence"]["coverage_footprint_reference"] = footprint_reference
    product_path = store.get_dataset_content_path(product.json()["id"])
    with open(product_path, "ab") as target:
        target.write(b"tampered")
    response = client.post(
        f"/api/v1/projects/{project['id']}/dem/coverage-assessments",
        json={"created_by": "operator-1", "request": payload},
    )
    assert response.status_code == 409


def test_dem_aoi_coverage_inspection_api_persists_measured_footprint(tmp_path, monkeypatch):
    import pytest

    rasterio = pytest.importorskip("rasterio")
    numpy = pytest.importorskip("numpy")
    from rasterio.transform import from_origin

    from geologia import store

    project = _create_project(tmp_path, monkeypatch)
    raster_path = tmp_path / "candidate.tif"
    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype="uint8",
        crs="EPSG:32638",
        transform=from_origin(500000, 1700000, 30, 30),
        nodata=0,
    ) as dataset:
        dataset.write(numpy.ones((10, 10), dtype=numpy.uint8), 1)
    product = _upload_coverage_dataset(
        project["id"], "candidate.tif", raster_path.read_bytes(), "dem"
    )
    aoi_payload = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [500000, 1699700],
                [500300, 1699700],
                [500300, 1700000],
                [500000, 1700000],
                [500000, 1699700],
            ]],
        },
    }
    aoi = _upload_coverage_dataset(
        project["id"],
        "pilot-aoi.geojson",
        json.dumps(aoi_payload).encode("utf-8"),
        "aoi_boundary",
    )
    assert product.status_code == 201
    assert aoi.status_code == 201

    response = client.post(
        f"/api/v1/datasets/{product.json()['id']}/coverage-inspection",
        json={"aoi_dataset_id": aoi.json()["id"], "aoi_crs": "EPSG:32638"},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["coverage_status"] == "full_aoi_extent_and_valid_pixels"
    assert report["aoi_fully_within_raster_extent"] is True
    assert report["all_aoi_pixel_centres_valid"] is True
    assert report["product_dataset_sha256"] == product.json()["sha256"]
    assert report["aoi_dataset_sha256"] == aoi.json()["sha256"]

    saved = client.get(f"/api/v1/datasets/{product.json()['id']}/coverage-inspection")
    assert saved.status_code == 200
    assert saved.json()["coverage_footprint_reference"] == report["coverage_footprint_reference"]
    provenance = store.get_dataset_provenance(product.json()["id"])
    assert any(
        event["event_type"] == "dataset_coverage_inspected"
        for event in provenance["events"]
    )


def test_verified_assessment_rejects_partial_dem_footprint(tmp_path, monkeypatch):
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
    aoi = _upload_coverage_dataset(
        project["id"], "pilot-aoi.geojson", _aoi_geojson_bytes(), "aoi_boundary"
    )
    payload = _coverage_payload()
    payload["context"]["product_dataset_id"] = product.json()["id"]
    payload["context"]["product_dataset_sha256"] = product.json()["sha256"]
    payload["context"]["reference_dataset_id"] = reference.json()["id"]
    payload["context"]["reference_dataset_sha256"] = reference.json()["sha256"]
    payload["context"]["aoi_dataset_id"] = aoi.json()["id"]
    payload["context"]["aoi_dataset_sha256"] = aoi.json()["sha256"]
    payload["evidence"]["source_sha256"] = reference.json()["sha256"]
    footprint_reference = _save_test_coverage_inspection(
        product.json(), aoi.json(), full=False
    )
    payload["actual_coverage"]["value"] = footprint_reference
    payload["evidence"]["coverage_footprint_reference"] = footprint_reference
    _save_test_reference_metrics(reference.json(), aoi.json(), payload)

    response = client.post(
        f"/api/v1/projects/{project['id']}/dem/coverage-assessments",
        json={"created_by": "operator-1", "request": payload},
    )
    assert response.status_code == 409


def test_reference_coverage_metrics_api_computes_and_persists_counts(tmp_path, monkeypatch):
    import pytest

    pytest.importorskip("pyproj")
    pytest.importorskip("shapely")
    from geologia import store

    project = _create_project(tmp_path, monkeypatch)
    aoi_payload = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [0, 0],
                [10000, 0],
                [10000, 10000],
                [0, 10000],
                [0, 0],
            ]],
        },
    }
    observations = [
        (1, 100, 100, "2024-01-01T00:00:00Z"),
        (2, 1100, 100, "2023-01-01T00:00:00Z"),
        (3, 5100, 100, "2022-01-01T00:00:00Z"),
        (4, 6100, 100, "2021-01-01T00:00:00Z"),
        (5, 100, 5100, "2020-06-01T00:00:00Z"),
    ]
    reference_payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "observation_id": f"obs-{index}",
                    "site_id": f"site-{index}",
                    "source_id": "reference-source-1",
                    "observed_at": observed_at,
                    "primary_stratum_id": "steep-bare",
                    "independence_group_id": "reviewed-group-1",
                    "independence_status": "independent",
                    "quality_flag": "accepted",
                    "vertical_datum": "EGM2008",
                    "reference_method": "static GNSS",
                    "horizontal_uncertainty_m": 0.02,
                    "vertical_uncertainty_m": 0.03,
                    "horizontal_reference_frame": "ITRF2014",
                    "coordinate_epoch": "2020.0",
                    "geoid_model": "EGM2008",
                },
                "geometry": {"type": "Point", "coordinates": [x, y]},
            }
            for index, x, y, observed_at in observations
        ],
    }
    aoi = _upload_coverage_dataset(
        project["id"],
        "pilot-aoi.geojson",
        json.dumps(aoi_payload).encode("utf-8"),
        "aoi_boundary",
    )
    reference = _upload_coverage_dataset(
        project["id"],
        "reference-observations.geojson",
        json.dumps(reference_payload).encode("utf-8"),
        "reference_elevation_observations",
    )
    assert aoi.status_code == 201
    assert reference.status_code == 201

    request = {
        "aoi_dataset_id": aoi.json()["id"],
        "aoi_crs": "EPSG:6933",
        "reference_crs": "EPSG:6933",
        "dem_epoch": "2025-01-01",
        "computed_by": "analyst-1",
        "analysis_code_commit": "a1b2c3d4",
        "independence_review": {
            "reference": "review://independence/1",
            "reviewer": "reviewer-1",
            "reviewed_at": "2026-11-22T02:00:00Z",
            "definition": "Unique sites reviewed for source lineage and spatial independence.",
            "source_lineage_reviewed": True,
            "spatial_independence_reviewed": True,
            "source_dependence_conflicts": False,
        },
    }
    response = client.post(
        f"/api/v1/datasets/{reference.json()['id']}/reference-coverage-metrics",
        json=request,
    )
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "measured"
    assert report["metrics"]["valid_independent_locations"] == 5
    assert report["metrics"]["polygon_area_km2"] == pytest.approx(100)
    assert report["metrics"]["occupied_1km_cells"] == 5
    assert report["metrics"]["eligible_1km_cells"] == 100
    assert report["metrics"]["occupied_5km_blocks"] == 3
    assert report["metrics"]["eligible_5km_blocks"] == 4
    assert report["metrics"]["max_block_observation_fraction"] == pytest.approx(0.4)
    assert report["metrics"]["temporal_match_fraction"] == 1
    assert report["metadata_completeness"]["complete_for_all_fields"] is True

    saved = client.get(
        f"/api/v1/datasets/{reference.json()['id']}/reference-coverage-metrics"
    )
    assert saved.status_code == 200
    assert saved.json()["metrics_reference"] == report["metrics_reference"]
    provenance = store.get_dataset_provenance(reference.json()["id"])
    assert any(
        event["event_type"] == "reference_coverage_metrics_computed"
        for event in provenance["events"]
    )
