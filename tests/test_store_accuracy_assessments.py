import sqlite3

from geologia import store


def test_accuracy_assessments_are_persisted_in_separate_hash_chain(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "accuracy.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Accuracy evidence", "", "en")

    first = store.save_accuracy_assessment(
        project["id"],
        {"assessment_type": "dem_reference_residuals", "run": 1},
        {"accuracy_disposition": "not_assessed", "valid_residual_count": 10},
        "analyst-1",
    )
    second = store.save_accuracy_assessment(
        project["id"],
        {"assessment_type": "dem_reference_residuals", "run": 2},
        {"accuracy_disposition": "accuracy_requirement_met_for_declared_use"},
        "analyst-2",
    )

    assert first["previous_hash"] is None
    assert second["previous_hash"] == first["record_hash"]
    assert store.get_accuracy_assessment(first["id"])["assessment"][
        "valid_residual_count"
    ] == 10
    assert store.list_accuracy_assessments(project["id"])["count"] == 2
    assert store.verify_accuracy_assessment_chain(project["id"])["valid"] is True


def test_accuracy_assessment_chain_detects_payload_tampering(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "accuracy-tamper.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Accuracy tamper", "", "en")
    record = store.save_accuracy_assessment(
        project["id"],
        {"assessment_type": "dem_reference_residuals"},
        {"metrics": {"rmse_m": 1.25}},
        "analyst-1",
    )

    with sqlite3.connect(store.database_path()) as conn:
        conn.execute(
            "UPDATE accuracy_assessments SET assessment_json=? WHERE id=?",
            ('{"metrics":{"rmse_m":0.0}}', record["id"]),
        )

    verification = store.verify_accuracy_assessment_chain(project["id"])
    assert verification["valid"] is False
    assert {item["code"] for item in verification["errors"]} >= {
        "assessment_hash_mismatch",
        "record_hash_mismatch",
    }
