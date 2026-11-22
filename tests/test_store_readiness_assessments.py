import sqlite3

from geologia import store


def test_readiness_assessments_persist_and_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "readiness.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Readiness evidence", "", "en")

    first = store.save_readiness_assessment(
        project["id"],
        {"assessment_type": "dem_readiness", "run": 1},
        {"disposition": "not_evaluable"},
        "reviewer-1",
    )
    second = store.save_readiness_assessment(
        project["id"],
        {"assessment_type": "dem_readiness", "run": 2},
        {"disposition": "ready_for_declared_use"},
        "reviewer-2",
    )

    assert first["previous_hash"] is None
    assert second["previous_hash"] == first["record_hash"]
    assert store.get_readiness_assessment(first["id"])["assessment"][
        "disposition"
    ] == "not_evaluable"
    assert store.list_readiness_assessments(project["id"])["count"] == 2
    assert store.verify_readiness_assessment_chain(project["id"])["valid"] is True


def test_readiness_assessment_chain_detects_payload_tampering(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "readiness-tamper.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Readiness tamper", "", "en")
    record = store.save_readiness_assessment(
        project["id"],
        {"assessment_type": "dem_readiness"},
        {"disposition": "not_evaluable"},
        "reviewer-1",
    )

    with sqlite3.connect(store.database_path()) as conn:
        conn.execute(
            "UPDATE readiness_assessments SET assessment_json=? WHERE id=?",
            ('{"disposition":"ready_for_declared_use"}', record["id"]),
        )

    verification = store.verify_readiness_assessment_chain(project["id"])
    assert verification["valid"] is False
    assert "assessment_hash_mismatch" in {
        item["code"] for item in verification["errors"]
    }
