from fastapi.testclient import TestClient

from geologia.api import app

client = TestClient(app)


def test_health_is_honest():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["engines_integrated"] == 0
    assert body["execution_enabled"] is False


def test_projects_and_durable_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "db.sqlite3"))
    created = client.post("/api/v1/projects", json={"name": "Yemen Hydro", "language": "en"})
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Yemen Hydro"

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
