from fastapi.testclient import TestClient

from geologia.api import app

client = TestClient(app)


def _project(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    return client.post("/api/v1/projects", json={"name": "Validation project"}).json()


def _upload(project_id, filename, body, role):
    return client.post(
        f"/api/v1/projects/{project_id}/datasets",
        content=body,
        headers={
            "X-Dataset-Name": "Validation input",
            "X-Filename": filename,
            "X-Data-Role": role,
        },
    )


def test_water_level_validation_endpoint_persists_schema_report(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    uploaded = _upload(
        project["id"],
        "water-levels.csv",
        b"well_id,timestamp,water_level_m\nW-01,2026-01-01T00:00:00Z,125.4\n",
        "water_levels_timeseries",
    )
    assert uploaded.status_code == 201
    dataset_id = uploaded.json()["id"]

    validated = client.post(f"/api/v1/datasets/{dataset_id}/validate")
    assert validated.status_code == 200
    report = validated.json()
    assert report["validation_status"] == "passed"
    assert report["profile"]["version"] == "1.0.0"
    assert report["scientific_interpretation"] is False

    saved = client.get(f"/api/v1/datasets/{dataset_id}/validation")
    assert saved.status_code == 200
    assert saved.json() == report
    item = client.get(f"/api/v1/datasets/{dataset_id}").json()
    assert item["status"] == "validation_passed"


def test_invalid_water_level_profile_is_reported_and_persisted(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    uploaded = _upload(
        project["id"],
        "water-levels.csv",
        b"date,water_level\nnot-a-date,NaN\n",
        "water_levels_timeseries",
    )
    dataset_id = uploaded.json()["id"]

    report = client.post(f"/api/v1/datasets/{dataset_id}/validate").json()
    assert report["validation_status"] == "failed"
    assert report["error_count"] >= 2
    assert client.get(f"/api/v1/datasets/{dataset_id}").json()["status"] == "validation_failed"


def test_aoi_validation_requires_polygon_geometry(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    payload = (
        b'{"type":"Feature","properties":{},'
        b'"geometry":{"type":"Point","coordinates":[44.2,15.3]}}'
    )
    uploaded = _upload(project["id"], "boundary.geojson", payload, "aoi_boundary")
    assert uploaded.status_code == 201

    report = client.post(
        f"/api/v1/datasets/{uploaded.json()['id']}/validate"
    ).json()
    assert report["validation_status"] == "failed"
    assert report["errors"][0]["code"] == "profile.aoi.polygon_required"


def test_validation_endpoint_rejects_unsupported_format_and_unknown_dataset(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    uploaded = _upload(project["id"], "surface.tif", b"raster bytes", "dem")
    assert uploaded.status_code == 201
    dataset_id = uploaded.json()["id"]
    assert client.post(f"/api/v1/datasets/{dataset_id}/validate").status_code == 415
    assert client.post("/api/v1/datasets/missing/validate").status_code == 404
    assert client.get("/api/v1/datasets/missing/validation").status_code == 404
