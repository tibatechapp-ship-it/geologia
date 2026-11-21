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
    assert readiness["data_complete"] is False
    assert readiness["execution_allowed"] is False


def test_bilingual_frontend_is_served():
    home = client.get("/")
    assert home.status_code == 200
    assert "GEOLOGIA" in home.text
    script = client.get("/app.js")
    assert script.status_code == 200
    assert "المهندس الجمهوري" in script.text
