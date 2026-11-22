"""Regression tests for the SQLite connection context lifecycle."""
import sqlite3

import pytest

from geologia import store


def test_store_connection_commits_and_closes(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "store.sqlite3"))
    store.initialize()

    with store.connect() as connection:
        connection.execute(
            "INSERT INTO projects(id,name,description,language,created_at) "
            "VALUES(?,?,?,?,?)",
            ("commit-check", "Committed", "", "en", store.utc_now()),
        )

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")

    with store.connect() as connection:
        row = connection.execute(
            "SELECT name FROM projects WHERE id=?", ("commit-check",)
        ).fetchone()
    assert row["name"] == "Committed"


def test_store_connection_rolls_back_and_closes_on_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "store.sqlite3"))
    store.initialize()

    with pytest.raises(RuntimeError, match="abort transaction"):
        with store.connect() as connection:
            connection.execute(
                "INSERT INTO projects(id,name,description,language,created_at) "
                "VALUES(?,?,?,?,?)",
                ("rollback-check", "Rolled back", "", "en", store.utc_now()),
            )
            raise RuntimeError("abort transaction")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")

    with store.connect() as connection:
        row = connection.execute(
            "SELECT id FROM projects WHERE id=?", ("rollback-check",)
        ).fetchone()
    assert row is None
