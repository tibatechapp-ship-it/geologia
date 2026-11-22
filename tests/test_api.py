from pathlib import Path

from fastapi.testclient import TestClient

from geologia.api import app

client = TestClient(app)


def test_health_is_honest():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["engines_integrated"] == 0
    assert body["execution_enabled"] is False


def test_registry_is_explicitly_planned():
    response = client.get("/api/v1/engines")
    assert response.status_code == 200
    cards = response.json()["engines"]
    assert len(cards) == 30
    assert all(card["status"] == "planned" for card in cards)
    assert all(card["license_status"] == "unverified" for card in cards)
    assert client.get("/api/v1/engines/gempy").status_code == 200
    assert client.get("/api/v1/engines/unknown").status_code == 404


def test_projects_and_durable_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    created = client.post("/api/v1/projects", json={"name": "Yemen Hydro", "language": "en"})
    assert created.status_code == 201
    project = created.json()
    job_response = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={"request": "Groundwater assessment for this area", "language": "en"},
    )
    assert job_response.status_code == 201
    job = job_response.json()
    assert job["status"] == "planned"
    assert job["plan"]["plan_only"] is True
    assert job["plan"]["no_results_computed"] is True
    assert "hydrology" in job["plan"]["matched_domains"]
    readback = client.get(f"/api/v1/jobs/{job['id']}")
    assert readback.status_code == 200
    assert readback.json()["plan"] == job["plan"]


def test_safe_geojson_upload_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Yemen GIS"}).json()
    geojson = (
        b'{"type":"FeatureCollection","features":[{"type":"Feature",'
        b'"geometry":null,"properties":{}}]}'
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=geojson,
        headers={"X-Dataset-Name": "Study area", "X-Filename": "../../study.geojson"},
    )
    assert response.status_code == 201
    item = response.json()
    assert item["original_filename"] == "study.geojson"
    assert item["status"] == "stored_not_analyzed"
    assert item["summary"]["feature_count"] == 1
    assert item["crs"] == "EPSG:4326"
    assert item["data_role"] is None
    assert len(item["sha256"]) == 64
    assert "content_path" not in item
    assert client.get(f"/api/v1/datasets/{item['id']}").json()["id"] == item["id"]


def test_upload_rejects_bad_geojson_and_unsupported_type(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Validation"}).json()
    headers = {"X-Dataset-Name": "Bad data", "X-Filename": "bad.geojson"}
    assert client.post(
        f"/api/v1/projects/{project['id']}/datasets", content=b"not json", headers=headers
    ).status_code == 422
    headers["X-Filename"] = "unsafe.exe"
    assert client.post(
        f"/api/v1/projects/{project['id']}/datasets", content=b"x", headers=headers
    ).status_code == 415


def test_upload_size_limit(tmp_path, monkeypatch):
    import geologia.api as api_module

    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(api_module, "MAX_UPLOAD_BYTES", 8)
    project = client.post("/api/v1/projects", json={"name": "Limit test"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=b"123456789",
        headers={"X-Dataset-Name": "Large", "X-Filename": "large.csv"},
    )
    assert response.status_code == 413


def test_missing_project_and_job_return_404(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    assert client.get("/api/v1/projects/missing").status_code == 404
    assert client.get("/api/v1/jobs/missing").status_code == 404
    assert client.post(
        "/api/v1/projects/missing/jobs", json={"request": "study geology"}
    ).status_code == 404


def test_input_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    assert client.post("/api/v1/projects", json={"name": "x"}).status_code == 422
    assert client.post(
        "/api/v1/projects", json={"name": "Valid", "language": "fr"}
    ).status_code == 422


def test_data_role_drives_readiness_but_never_enables_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Readiness"}).json()
    uploaded = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=b"raster placeholder bytes",
        headers={
            "X-Dataset-Name": "Elevation", "X-Filename": "elevation.tif",
            "X-Data-Role": "dem", "X-CRS": "EPSG:4326",
        },
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["data_role"] == "dem"
    job = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={"request": "Groundwater study", "language": "en"},
    ).json()
    readiness = job["plan"]["data_readiness"]
    assert "dem" in readiness["available_inputs"]
    assert "dem" not in readiness["missing_inputs"]
    assert readiness["required_roles_present"] is False
    assert readiness["content_validation"] == "not_performed"
    assert readiness["execution_allowed"] is False


def test_bilingual_frontend_is_served():
    home = client.get("/")
    assert home.status_code == 200
    assert "GEOLOGIA" in home.text
    script = client.get("/app.js")
    assert script.status_code == 200
    assert "agentName" in script.text
    assert "علي الگوموري" in home.text
    script_text = script.text
    assert '/api/v1/datasets/"+encodeURIComponent(d.id)+"/inspect' in script_text
    assert "inspectDataset" in script_text


def test_crs_inspection_and_reprojection_preserve_source(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    crs_response = client.get("/api/v1/crs/inspect", params={"crs": "epsg:4326"})
    assert crs_response.status_code == 200
    crs_info = crs_response.json()
    assert crs_info["canonical"] == "EPSG:4326"
    assert crs_info["is_geographic"] is True
    assert client.get("/api/v1/crs/inspect", params={"crs": "not-a-crs"}).status_code == 422

    project = client.post("/api/v1/projects", json={"name": "CRS test"}).json()
    payload = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"id": 1},
                      "geometry": {"type": "Point", "coordinates": [44.2, 15.3]}}],
    }
    upload = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=__import__("json").dumps(payload).encode(),
        headers={"X-Dataset-Name": "Point", "X-Filename": "point.geojson"},
    )
    dataset_id = upload.json()["id"]
    response = client.post(
        f"/api/v1/datasets/{dataset_id}/reproject",
        json={"target_crs": "EPSG:3857"},
    )
    assert response.status_code == 201
    result = response.json()
    derived = result["dataset"]
    assert derived["summary"]["coordinate_count"] == 1
    bbox = derived["summary"]["bbox_xy"]
    assert abs(bbox[0] - 4920321.493) < 1
    assert abs(bbox[1] - 1723798.499) < 1
    assert result["source_crs"] == "EPSG:4326"
    assert result["target_crs"] == "EPSG:3857"
    assert result["source_dataset_modified"] is False
    assert derived["crs"] == "EPSG:3857"
    assert derived["format"] == "geojson"
    assert derived["summary"]["derived_from_dataset_id"] == dataset_id
    assert client.get(f"/api/v1/datasets/{dataset_id}/geojson").json() == payload
    stored_derived = client.get(f"/api/v1/datasets/{derived['id']}/geojson")
    assert stored_derived.status_code == 200
    display_coords = stored_derived.json()["features"][0]["geometry"]["coordinates"]
    assert abs(display_coords[0] - 44.2) < 1e-6
    assert abs(display_coords[1] - 15.3) < 1e-6


def test_upload_rejects_invalid_geojson_geometry(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Invalid geometry"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=b'{"type":"Feature","geometry":{"type":"Point","coordinates":[1]},"properties":{}}',
        headers={"X-Dataset-Name": "Bad point", "X-Filename": "bad.geojson"},
    )
    assert response.status_code == 422
    assert "invalid GeoJSON" in response.json()["detail"]


def test_geojson_map_endpoint_returns_validated_data_and_hides_path(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Map layer"}).json()
    payload = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"label": "site"},
                      "geometry": {"type": "Point", "coordinates": [44.2, 15.3]}}],
    }
    uploaded = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=__import__("json").dumps(payload).encode(),
        headers={"X-Dataset-Name": "Sites", "X-Filename": "sites.geojson"},
    )
    dataset_id = uploaded.json()["id"]
    response = client.get(f"/api/v1/datasets/{dataset_id}/geojson")
    assert response.status_code == 200
    assert response.json() == payload
    assert "content_path" not in response.text
    csv_upload = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=b"a,b\n1,2\n",
        headers={"X-Dataset-Name": "Table", "X-Filename": "table.csv"},
    )
    assert client.get(f"/api/v1/datasets/{csv_upload.json()['id']}/geojson").status_code == 415


def test_geojson_inspection_computes_real_metrics_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "GIS inspection"}).json()
    data = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"site": "A"},
             "geometry": {"type": "Point", "coordinates": [44.2, 15.3]}},
            {"type": "Feature", "properties": {"site": "B", "depth": 12},
             "geometry": {"type": "Point", "coordinates": [44.5, 15.8]}},
        ],
    }
    uploaded = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=__import__("json").dumps(data).encode(),
        headers={"X-Dataset-Name": "Survey points", "X-Filename": "points.geojson"},
    )
    assert uploaded.status_code == 201
    dataset_id = uploaded.json()["id"]
    inspected = client.post(f"/api/v1/datasets/{dataset_id}/inspect")
    assert inspected.status_code == 200
    report = inspected.json()
    assert report["feature_count"] == 2
    assert report["geometry_counts"] == {"Point": 2}
    assert report["coordinate_count"] == 2
    assert report["bbox_xy"] == [44.2, 15.3, 44.5, 15.8]
    assert report["property_keys"] == ["depth", "site"]
    assert report["scientific_interpretation"] is False
    stored = client.get(f"/api/v1/datasets/{dataset_id}").json()
    assert stored["status"] == "inspected_structural_metrics"
    assert stored["summary"]["inspection"] == report


def test_csv_inspection_streams_structure_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "CSV inspection"}).json()
    csv_data = b"station,depth\nA,12.5\nB,\"14,2\"\nC\n\n"
    uploaded = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=csv_data,
        headers={"X-Dataset-Name": "Samples", "X-Filename": "samples.csv"},
    )
    assert uploaded.status_code == 201
    dataset_id = uploaded.json()["id"]
    response = client.post(f"/api/v1/datasets/{dataset_id}/inspect")
    assert response.status_code == 200
    report = response.json()
    assert report["operation"] == "csv_inspection"
    assert report["row_count"] == 3
    assert report["column_count"] == 2
    assert report["headers"] == ["station", "depth"]
    assert report["ragged_row_count"] == 1
    assert report["blank_row_count"] == 1
    assert report["scientific_interpretation"] is False
    status = client.get(f"/api/v1/datasets/{dataset_id}").json()["status"]
    assert status == "inspected_structural_metrics"


def test_geojson_inspection_rejects_non_finite_coordinates():
    from geologia.vector import inspect_geojson

    malformed = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [float("nan"), 1]},
    }
    try:
        inspect_geojson(malformed)
    except ValueError as exc:
        assert "finite" in str(exc)
    else:
        raise AssertionError("non-finite coordinates must be rejected")


def test_agent_status_endpoint_reports_model_independent_runtime():
    response = client.get("/api/v1/agent/status")
    assert response.status_code == 200
    status = response.json()
    assert status["agent_id"] == "ali-algomori"
    assert status["name_en"] == "Ali Algomori"
    assert status["model_required"] is False
    assert status["network_required"] is False
    assert status["scientific_execution_enabled"] is False


def test_unmatched_job_requests_clarification_without_false_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    project = client.post("/api/v1/projects", json={"name": "Clarification"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={"request": "Please analyze this area", "language": "en"},
    )
    assert response.status_code == 201
    plan = response.json()["plan"]
    assert plan["needs_clarification"] is True
    assert plan["matched_domains"] == []
    readiness = plan["data_readiness"]
    assert readiness["readiness_status"] == "not_assessed"
    assert readiness["required_roles_present"] is None
    assert readiness["execution_allowed"] is False


def test_local_knowledge_api_search_and_status(tmp_path, monkeypatch):
    from geologia import knowledge

    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_DISABLE_CORE_SEED", "1")
    source = tmp_path / "open_hydro.txt"
    source.write_text(
        "Groundwater recharge is assessed from aquifer and water-level evidence.",
        encoding="utf-8",
    )
    knowledge.ingest_document(
        source,
        {
            "source_id": "api-hydro-01",
            "title": "Open hydrogeology note",
            "language": "en",
            "license_name": "CC BY 4.0",
            "license_status": "open_license",
            "reviewed_by": "test reviewer",
            "review_date": "2026-11-21",
            "source_url": "https://example.org/hydro-note",
        },
    )

    status = client.get("/api/v1/knowledge/status")
    assert status.status_code == 200
    assert status.json()["document_count"] == 1
    assert status.json()["model_required"] is False

    response = client.get(
        "/api/v1/knowledge/search", params={"q": "aquifer recharge", "limit": 3}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["count"] >= 1
    assert result["model_used"] is False
    assert result["results"][0]["source_id"] == "api-hydro-01"


def test_analysis_plan_retrieves_local_source_chunks_without_model(tmp_path, monkeypatch):
    from geologia import knowledge

    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_DISABLE_CORE_SEED", "1")
    source = tmp_path / "groundwater.txt"
    source.write_text("Groundwater recharge and aquifer storage are related.", encoding="utf-8")
    knowledge.ingest_document(
        source,
        {
            "source_id": "plan-hydro-01",
            "title": "Local groundwater note",
            "language": "en",
            "license_name": "Original work",
            "license_status": "original_work",
            "reviewed_by": "test author",
            "review_date": "2026-11-21",
        },
    )
    project = client.post("/api/v1/projects", json={"name": "Knowledge retrieval"}).json()
    job = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={"request": "Groundwater recharge study", "language": "en"},
    )
    assert job.status_code == 201
    retrieval = job.json()["plan"]["knowledge_retrieval"]
    assert retrieval["status"] == "local_references_found"
    assert retrieval["model_used"] is False
    assert retrieval["scientific_conclusion"] is False
    assert retrieval["evidence_summary"]["matched_query_terms"]
    assert retrieval["evidence_summary"]["coverage_scope"] == "returned_results"
    assert retrieval["evidence_interpretation"].startswith("local lexical retrieval only")
    assert retrieval["results"][0]["source_id"] == "plan-hydro-01"


def test_api_seeds_original_core_notes_without_external_downloads(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "core.sqlite3"))
    monkeypatch.delenv("GEOLOGIA_KNOWLEDGE_DB_PATH", raising=False)
    monkeypatch.delenv("GEOLOGIA_DISABLE_CORE_SEED", raising=False)

    status = client.get("/api/v1/knowledge/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["document_count"] == 24
    assert payload["core_seed_count"] == 24
    assert payload["core_seeded_count"] == 24
    assert payload["automatic_downloads_enabled"] is False
    assert payload["model_required"] is False

    result = client.get("/api/v1/knowledge/search", params={"q": "groundwater"})
    assert result.status_code == 200
    assert any(
        item["source_id"] == "geologia-core-hydrology-en-v1"
        for item in result.json()["results"]
    )


def test_modified_dataset_bytes_are_rejected_before_inspection_and_reads(tmp_path, monkeypatch):
    from geologia import store

    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "integrity.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "integrity-uploads"))
    project = client.post(
        "/api/v1/projects", json={"name": "Integrity guard", "language": "en"}
    ).json()
    source = (
        b'{"type":"FeatureCollection","features":[]}'
    )
    upload = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=source,
        headers={"X-Dataset-Name": "Integrity sample", "X-Filename": "sample.geojson"},
    )
    assert upload.status_code == 201
    dataset_id = upload.json()["id"]
    stored_path = store.get_dataset_content_path(dataset_id)
    assert stored_path is not None

    tampered = source.replace(b"FeatureCollection", b"FeatureCollectioN")
    assert len(tampered) == len(source)
    Path(stored_path).write_bytes(tampered)

    for endpoint, method in (
        (f"/api/v1/datasets/{dataset_id}/inspect", "post"),
        (f"/api/v1/datasets/{dataset_id}/geojson", "get"),
        (f"/api/v1/datasets/{dataset_id}/reproject", "post"),
    ):
        response = getattr(client, method)(
            endpoint,
            json={"target_crs": "EPSG:3857"} if method == "post" and endpoint.endswith("/reproject") else None,
        )
        assert response.status_code == 409
        assert "integrity mismatch" in response.json()["detail"]

    provenance = client.get(
        f"/api/v1/datasets/{dataset_id}/provenance"
    ).json()
    assert provenance["chain_integrity"] == "verified"
    assert [event["event_type"] for event in provenance["events"]] == [
        "dataset_ingested"
    ]
