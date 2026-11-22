import pytest

from geologia import store


def test_coverage_assessment_hash_chain_detects_payload_tampering(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Coverage audit", "", "en")

    first = store.save_coverage_assessment(
        project["id"],
        {"phase": "exploratory", "metrics": {"n": 60}},
        {"status": "sufficient"},
        "reviewer-1",
    )
    second = store.save_coverage_assessment(
        project["id"],
        {"phase": "confirmatory", "metrics": {"n": 120}},
        {"status": "insufficient"},
        "reviewer-2",
    )

    assert first["previous_hash"] is None
    assert second["previous_hash"] == first["record_hash"]
    assert store.verify_coverage_assessment_chain(project["id"])["valid"] is True

    with store.connect() as conn:
        conn.execute(
            "UPDATE coverage_assessments SET assessment_json=? WHERE id=?",
            ('{"status":"ready"}', first["id"]),
        )

    verification = store.verify_coverage_assessment_chain(project["id"])
    assert verification["valid"] is False
    assert any(
        error["code"] == "assessment_hash_mismatch"
        for error in verification["errors"]
    )


def test_coverage_assessment_rejects_unknown_project(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    with pytest.raises(ValueError, match="project not found"):
        store.save_coverage_assessment(
            "missing-project",
            {"phase": "exploratory"},
            {"status": "not_assessed"},
            "reviewer-1",
        )
