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
            "UPDATE provenance_events SET payload_json='{}' WHERE dataset_id=? "
            "AND event_type='dataset_inspected'",
            (dataset["id"],),
        )
    invalid = store.get_dataset_provenance(dataset["id"])
    assert invalid["chain_integrity"] == "failed"
