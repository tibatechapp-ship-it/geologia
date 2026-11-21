import sqlite3

import pytest
from fastapi.testclient import TestClient

from geologia import store
from geologia.api import app

client = TestClient(app)


def _new_job(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "geologia.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Lifecycle project", "", "en")
    return store.create_job(project["id"], "Map groundwater", "en", {"required_inputs": []})


def test_job_state_machine_records_attempts_and_events(tmp_path, monkeypatch):
    job = _new_job(tmp_path, monkeypatch)

    queued = store.transition_job(job["id"], "queued", actor="system")
    assert queued["status"] == "queued"
    running = store.transition_job(job["id"], "running", actor="worker")
    assert running["status"] == "running"
    assert running["attempt_count"] == 1

    failed = store.transition_job(
        job["id"],
        "failed",
        actor="worker",
        detail={"error_code": "worker.timeout", "error_message": "Worker timed out."},
    )
    assert failed["status"] == "failed"
    assert failed["error_code"] == "worker.timeout"

    retried = store.transition_job(job["id"], "queued", actor="human")
    assert retried["status"] == "queued"
    assert retried["error_code"] is None
    running_again = store.transition_job(job["id"], "running", actor="worker")
    assert running_again["attempt_count"] == 2

    events = store.list_job_events(job["id"])
    assert [event["to_status"] for event in events] == [
        "planned", "queued", "running", "failed", "queued", "running"
    ]
    assert all(event["actor"] for event in events)


def test_job_state_machine_rejects_illegal_transitions_and_retry_overflow(
    tmp_path, monkeypatch
):
    job = _new_job(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="invalid job transition"):
        store.transition_job(job["id"], "succeeded", actor="worker")

    for attempt in range(3):
        if attempt == 0:
            store.transition_job(job["id"], "queued", actor="system")
        else:
            store.transition_job(job["id"], "queued", actor="human")
        store.transition_job(job["id"], "running", actor="worker")
        store.transition_job(job["id"], "failed", actor="worker")

    with pytest.raises(ValueError, match="retry limit"):
        store.transition_job(job["id"], "queued", actor="human")


def test_running_job_cancellation_is_a_request_not_a_false_success(
    tmp_path, monkeypatch
):
    job = _new_job(tmp_path, monkeypatch)
    store.transition_job(job["id"], "queued", actor="system")
    store.transition_job(job["id"], "running", actor="worker")

    result = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert result.status_code == 200
    payload = result.json()
    assert payload["job"]["status"] == "cancel_requested"
    assert payload["cancellation"] == "requested"
    assert payload["execution_stopped"] is False

    events = client.get(f"/api/v1/jobs/{job['id']}/events").json()
    assert events["count"] == 4
    assert events["events"][-1]["to_status"] == "cancel_requested"


def test_legacy_job_database_is_migrated_without_losing_records(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(db_path))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL CHECK(language IN ('ar','en')), created_at TEXT NOT NULL
        );
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            request TEXT NOT NULL, language TEXT NOT NULL CHECK(language IN ('ar','en')),
            status TEXT NOT NULL CHECK(
                status IN ('planned','queued','running','succeeded','failed')
            ), plan_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT INTO projects VALUES(
            'project-1','Legacy project','','en','2026-01-01T00:00:00+00:00'
        );
        INSERT INTO jobs VALUES(
            'job-1','project-1','Legacy request','en','planned','{}',
            '2026-01-01T00:00:00+00:00'
        );
        """
    )
    connection.commit()
    connection.close()

    store.initialize()
    store.initialize()
    migrated = store.get_job("job-1")
    assert migrated is not None
    assert migrated["status"] == "planned"
    assert migrated["attempt_count"] == 0
    assert migrated["max_attempts"] == 3
    assert migrated["updated_at"] == migrated["created_at"]
    assert store.transition_job("job-1", "cancelled", actor="human")["status"] == "cancelled"


def test_planned_job_cancellation_is_confirmed_and_idempotent(tmp_path, monkeypatch):
    job = _new_job(tmp_path, monkeypatch)
    first = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    second = client.post(f"/api/v1/jobs/{job['id']}/cancel")

    assert first.status_code == second.status_code == 200
    assert first.json()["job"]["status"] == "cancelled"
    assert first.json()["execution_stopped"] is True
    assert second.json()["cancellation"] == "confirmed"
    events = client.get(f"/api/v1/jobs/{job['id']}/events").json()["events"]
    assert [event["to_status"] for event in events] == ["planned", "cancelled"]


def test_worker_acknowledges_requested_cancellation(tmp_path, monkeypatch):
    job = _new_job(tmp_path, monkeypatch)
    store.transition_job(job["id"], "queued", actor="system")
    store.transition_job(job["id"], "running", actor="worker")
    requested = store.request_job_cancellation(job["id"])
    assert requested["status"] == "cancel_requested"
    assert requested["finished_at"] is None

    acknowledged = store.transition_job(job["id"], "cancelled", actor="worker")
    assert acknowledged["status"] == "cancelled"
    assert acknowledged["finished_at"] is not None
