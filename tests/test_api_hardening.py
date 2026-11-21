import pytest
from fastapi.testclient import TestClient

from geologia.api import app

client = TestClient(app)


def test_project_and_job_inputs_reject_whitespace_only_values():
    assert client.post("/api/v1/projects", json={"name": "  "}).status_code == 422
    project = client.post("/api/v1/projects", json={"name": "Valid"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={"request": "   "},
    )
    assert response.status_code == 422


def test_upload_rejects_whitespace_dataset_name(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Valid"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=b"field,value\nA,1\n",
        headers={"X-Dataset-Name": "  ", "X-Filename": "data.csv"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        b'{"type":"Feature","properties":{"invalid":NaN},"geometry":null}',
        b'{"type":"Feature","properties":{"invalid":Infinity},"geometry":null}',
        b'{"type":"Feature","properties":{"invalid":1e999},"geometry":null}',
    ],
)
def test_upload_rejects_non_finite_json_numbers(tmp_path, monkeypatch, payload):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Strict JSON"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=payload,
        headers={"X-Dataset-Name": "Strict", "X-Filename": "strict.geojson"},
    )
    assert response.status_code == 422
