"""SQLite online backup and offline restore regression tests."""
import sqlite3

import pytest

from geologia.database_backup import backup_database, restore_database_backup


def test_online_backup_and_restore_include_committed_wal_data(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"

    writer = sqlite3.connect(source)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE samples (id INTEGER PRIMARY KEY, value TEXT)")
    writer.execute("INSERT INTO samples(value) VALUES ('committed in WAL')")
    writer.commit()

    result = backup_database(source, backup)
    assert result["integrity"] == "ok"
    assert result["size_bytes"] > 0
    assert len(result["sha256"]) == 64

    restore = restore_database_backup(backup, restored)
    assert restore["integrity"] == "ok"
    with sqlite3.connect(restored) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT value FROM samples").fetchone()[0] == "committed in WAL"
    writer.close()


def test_backup_refuses_to_overwrite_without_explicit_permission(tmp_path):
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backup.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE data (value INTEGER)")
    destination.write_bytes(b"keep existing backup")

    with pytest.raises(FileExistsError):
        backup_database(source, destination)
    assert destination.read_bytes() == b"keep existing backup"


def test_restore_rejects_corrupt_backup_without_touching_destination(tmp_path):
    backup = tmp_path / "corrupt.sqlite3"
    destination = tmp_path / "destination.sqlite3"
    backup.write_bytes(b"not sqlite")
    destination.write_bytes(b"preserve destination")

    with pytest.raises(ValueError, match="valid readable SQLite"):
        restore_database_backup(backup, destination, overwrite=True)
    assert destination.read_bytes() == b"preserve destination"


def test_restore_requires_offline_destination_and_never_overwrites_by_default(tmp_path):
    backup = tmp_path / "backup.sqlite3"
    destination = tmp_path / "destination.sqlite3"
    with sqlite3.connect(backup) as connection:
        connection.execute("CREATE TABLE data (value INTEGER)")
    with sqlite3.connect(destination) as connection:
        connection.execute("CREATE TABLE existing (value INTEGER)")
    with pytest.raises(FileExistsError):
        restore_database_backup(backup, destination)
    (tmp_path / "destination.sqlite3-wal").write_bytes(b"active")
    with pytest.raises(RuntimeError, match="sidecars"):
        restore_database_backup(backup, destination, overwrite=True)
    with sqlite3.connect(destination) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='existing'"
        ).fetchone() is not None


def test_backup_rejects_same_source_and_destination(tmp_path):
    database = tmp_path / "same.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE data (value INTEGER)")
    with pytest.raises(ValueError, match="different files"):
        backup_database(database, database)
