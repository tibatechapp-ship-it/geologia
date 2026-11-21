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
    assert "المهندس الجمهوري" in home.text
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



def test_upload_rejects_default_wgs84_coordinates_outside_earth_bounds(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "CRS bounds"}).json()
    payload = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [500000, 4000000]},
    }
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=__import__("json").dumps(payload).encode(),
        headers={"X-Dataset-Name": "Mismatched coordinates", "X-Filename": "wrong.geojson"},
    )
    assert response.status_code == 422
    assert "WGS84" in response.json()["detail"]


def test_upload_validates_declared_crs_and_canonicalizes_it(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Declared CRS"}).json()
    payload = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [4920321.493, 1723798.499]},
    }
    headers = {
        "X-Dataset-Name": "Projected point",
        "X-Filename": "projected.geojson",
        "X-CRS": "epsg:3857",
    }
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=__import__("json").dumps(payload).encode(),
        headers=headers,
    )
    assert response.status_code == 201
    item = response.json()
    assert item["crs"] == "EPSG:3857"
    assert item["summary"]["crs_validation"]["coordinate_count_checked"] == 1
    assert item["summary"]["crs_validation"]["scientific_validation"] is False


def test_upload_rejects_unknown_and_incompatible_declared_crs(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Invalid CRS"}).json()
    payload = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [500000, 4000000]},
    }
    body = __import__("json").dumps(payload).encode()
    base_headers = {"X-Dataset-Name": "Bad CRS", "X-Filename": "bad.geojson"}
    unknown = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=body,
        headers={**base_headers, "X-CRS": "not-a-real-crs"},
    )
    assert unknown.status_code == 422

    incompatible = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=body,
        headers={**base_headers, "X-CRS": "EPSG:4326"},
    )
    assert incompatible.status_code == 422


def test_upload_rejects_malformed_csv_and_reports_ragged_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "CSV integrity"}).json()
    malformed = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=b'col1,col2\n"unterminated,2\n',
        headers={"X-Dataset-Name": "Malformed CSV", "X-Filename": "malformed.csv"},
    )
    assert malformed.status_code == 422

    ragged = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=b"station,depth\nA,12\nB\n",
        headers={"X-Dataset-Name": "Ragged CSV", "X-Filename": "ragged.csv"},
    )
    assert ragged.status_code == 201
    assert ragged.json()["summary"]["ragged_row_count"] == 1
    assert "rows_have_inconsistent_column_counts" in ragged.json()["summary"]["warnings"]



def test_upload_rejects_duplicate_json_keys_and_excessive_numeric_values(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Strict JSON"}).json()
    headers = {"X-Dataset-Name": "Ambiguous JSON", "X-Filename": "ambiguous.geojson"}
    duplicate = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=b'{"type":"Feature","type":"FeatureCollection","features":[]}',
        headers=headers,
    )
    assert duplicate.status_code == 422

    huge_number = (
        b'{"type":"Feature","properties":{},'
        b'"geometry":{"type":"Point","coordinates":[' + b"9" * 5000 + b",1]}}"
    )
    oversized = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=huge_number,
        headers={**headers, "X-Filename": "huge.geojson"},
    )
    assert oversized.status_code == 422
