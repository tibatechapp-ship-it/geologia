import json
import pytest

from geologia.ledger import Ledger, LedgerError


def test_project_job_lifecycle_and_audit(tmp_path):
    db = Ledger(tmp_path / "test.sqlite")
    project = db.create_project("Yemen AOI", "Demo")
    job = db.create_job(project["id"], "geojson.summary", {"file_id": "abc"})
    assert job["status"] == "queued"
    assert db.transition_job(job["id"], "running")["status"] == "running"
    done = db.transition_job(job["id"], "succeeded", result={"features": 4})
    assert done["result"] == {"features": 4}
    events = db.events(job["id"])
    assert [e["event_type"] for e in events] == [
        "job.queued", "job.running", "job.succeeded"
    ]


def test_idempotency_replays_same_job(tmp_path):
    db = Ledger(tmp_path / "test.sqlite")
    p = db.create_project("Project")
    first = db.create_job(p["id"], "inspect", {"x": 1}, "request-1")
    second = db.create_job(p["id"], "inspect", {"x": 1}, "request-1")
    assert first["id"] == second["id"]
    with pytest.raises(LedgerError, match="idempotency_conflict"):
        db.create_job(p["id"], "inspect", {"x": 2}, "request-1")


def test_invalid_state_transition_rejected(tmp_path):
    db = Ledger(tmp_path / "test.sqlite")
    p = db.create_project("Project")
    j = db.create_job(p["id"], "inspect", {})
    with pytest.raises(LedgerError, match="invalid_transition"):
        db.transition_job(j["id"], "succeeded")


def test_database_persists_after_reopen(tmp_path):
    path = tmp_path / "persistent.sqlite"
    one = Ledger(path)
    p = one.create_project("Persistent")
    two = Ledger(path)
    assert two.get_project(p["id"])["name"] == "Persistent"


def test_unknown_project_rejected(tmp_path):
    db = Ledger(tmp_path / "test.sqlite")
    with pytest.raises(LedgerError, match="project_not_found"):
        db.create_job("missing", "inspect", {})
