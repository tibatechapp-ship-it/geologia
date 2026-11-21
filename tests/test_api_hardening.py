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


def test_role_coverage_never_claims_dataset_content_is_validated(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = client.post("/api/v1/projects", json={"name": "Readiness honesty"}).json()
    roles = ["well_logs", "water_levels_timeseries", "recharge_estimate", "dem", "geology_map"]
    for index, role in enumerate(roles):
        uploaded = client.post(
            f"/api/v1/projects/{project['id']}/datasets",
            content=f"unverified placeholder {index}".encode(),
            headers={
                "X-Dataset-Name": f"Placeholder {index}",
                "X-Filename": f"placeholder-{index}.tif",
                "X-Data-Role": role,
            },
        )
        assert uploaded.status_code == 201
    job = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={"request": "Groundwater assessment", "language": "en"},
    ).json()
    readiness = job["plan"]["data_readiness"]
    assert readiness["required_roles_present"] is True
    assert readiness["content_validation"] == "not_performed"
    assert readiness["execution_allowed"] is False


def test_development_cli_rejects_non_loopback_binding(monkeypatch):
    import sys

    import geologia.api as api_module

    monkeypatch.setattr(sys, "argv", ["geologia-api", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit) as exc:
        api_module.run()
    assert exc.value.code == 2


def test_development_cli_starts_on_loopback(monkeypatch):
    import sys

    import geologia.api as api_module

    calls = []
    monkeypatch.setattr(sys, "argv", ["geologia-api", "--host", "127.0.0.1", "--port", "8123"])
    monkeypatch.setattr(api_module.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    api_module.run()
    assert calls[0][1]["host"] == "127.0.0.1"
    assert calls[0][1]["port"] == 8123
