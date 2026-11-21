from fastapi.testclient import TestClient
from geologia.api import app

client = TestClient(app)


def test_api_project_job_flow():
    project = client.post("/api/v1/projects", json={"name": "API Project"})
    assert project.status_code == 201
    pid = project.json()["id"]
    job = client.post(
        f"/api/v1/projects/{pid}/jobs",
        headers={"Idempotency-Key": "api-req-01"},
        json={"kind": "geojson.summary", "payload": {"dataset": "sample"}},
    )
    assert job.status_code == 201
    jid = job.json()["id"]
    assert client.get(f"/api/v1/jobs/{jid}").json()["status"] == "queued"
    assert client.post(f"/api/v1/jobs/{jid}/transition",
                       json={"status": "running"}).status_code == 200
    assert client.post(f"/api/v1/jobs/{jid}/transition",
                       json={"status": "succeeded", "result": {"count": 1}}).status_code == 200


def test_health_does_not_claim_execution():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["execution_enabled"] is False
