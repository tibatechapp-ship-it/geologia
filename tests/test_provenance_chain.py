"""Provenance event-chain integrity regression tests."""

from geologia import store


def test_provenance_event_hash_detects_payload_tampering(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "ledger.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Audit", "", "en")
    path = tmp_path / "sample.csv"
    path.write_text("x\n1\n", encoding="utf-8")
    dataset = store.create_dataset(
        project["id"], name="Sample", file_format="csv",
        original_filename="sample.csv", content_path=str(path),
        sha256="a" * 64, size_bytes=4, crs=None, data_role=None, summary={},
    )
    store.save_dataset_inspection(dataset["id"], {"row_count": 1})
    valid = store.get_dataset_provenance(dataset["id"])
    assert valid["chain_integrity"] == "verified"
    assert len(valid["events"]) == 2
    with store.connect() as connection:
        connection.execute(
            "UPDATE provenance_events SET payload_json='not-json' WHERE dataset_id=? "
            "AND event_type='dataset_inspected'",
            (dataset["id"],),
        )
    invalid = store.get_dataset_provenance(dataset["id"])
    assert invalid["chain_integrity"] == "failed"


def test_validation_and_inspection_events_are_chained(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "ledger.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Audit validation", "", "en")
    path = tmp_path / "sample.csv"
    path.write_text("x\n1\n", encoding="utf-8")
    dataset = store.create_dataset(
        project["id"], name="Sample", file_format="csv",
        original_filename="sample.csv", content_path=str(path),
        sha256="b" * 64, size_bytes=4, crs=None, data_role=None, summary={},
    )
    store.save_dataset_inspection(dataset["id"], {"row_count": 1})
    store.save_dataset_validation(
        dataset["id"], {"validation_status": "passed", "profile_id": "test-v1"}
    )
    report = store.get_dataset_provenance(dataset["id"])
    assert report["chain_integrity"] == "verified"
    assert [event["event_type"] for event in report["events"]] == [
        "dataset_ingested", "dataset_inspected", "dataset_validated"
    ]


def test_provenance_api_returns_verified_event_chain(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from geologia.api import app

    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "api-ledger.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "api-uploads"))
    project = store.create_project("API audit", "", "en")
    path = tmp_path / "api.csv"
    path.write_text("x\n2\n", encoding="utf-8")
    dataset = store.create_dataset(
        project["id"], name="API sample", file_format="csv",
        original_filename="api.csv", content_path=str(path),
        sha256="c" * 64, size_bytes=4, crs=None, data_role=None, summary={},
    )
    response = TestClient(app).get(
        f"/api/v1/datasets/{dataset['id']}/provenance"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["chain_integrity"] == "verified"
    assert payload["events"][0]["event_type"] == "dataset_ingested"


def test_validation_and_inspection_events_are_chained(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "ledger.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "uploads"))
    project = store.create_project("Audit validation", "", "en")
    path = tmp_path / "sample.csv"
    path.write_text("x\\n1\\n", encoding="utf-8")
    dataset = store.create_dataset(
        project["id"], name="Sample", file_format="csv",
        original_filename="sample.csv", content_path=str(path),
        sha256="b" * 64, size_bytes=4, crs=None, data_role=None, summary={},
    )
    store.save_dataset_inspection(dataset["id"], {"row_count": 1})
    store.save_dataset_validation(
        dataset["id"], {"validation_status": "passed", "profile_id": "test-v1"}
    )
    report = store.get_dataset_provenance(dataset["id"])
    assert report["chain_integrity"] == "verified"
    assert [event["event_type"] for event in report["events"]] == [
        "dataset_ingested", "dataset_inspected", "dataset_validated"
    ]


def test_provenance_api_returns_verified_event_chain(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from geologia.api import app

    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "api-ledger.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "api-uploads"))
    project = store.create_project("API audit", "", "en")
    path = tmp_path / "api.csv"
    path.write_text("x\\n2\\n", encoding="utf-8")
    dataset = store.create_dataset(
        project["id"], name="API sample", file_format="csv",
        original_filename="api.csv", content_path=str(path),
        sha256="c" * 64, size_bytes=4, crs=None, data_role=None, summary={},
    )
    response = TestClient(app).get(
        f"/api/v1/datasets/{dataset['id']}/provenance"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["chain_integrity"] == "verified"
    assert payload["events"][0]["event_type"] == "dataset_ingested"
