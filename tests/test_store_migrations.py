"""Upgrade tests for historical SQLite job schemas."""
import sqlite3

from geologia import store


def _create_legacy_database(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL CHECK(language IN ('ar','en')),
            created_at TEXT NOT NULL
        );
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            request TEXT NOT NULL,
            language TEXT NOT NULL CHECK(language IN ('ar','en')),
            status TEXT NOT NULL CHECK(status IN (
                'planned','queued','running','succeeded','failed','cancelled'
            )),
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            from_status TEXT,
            to_status TEXT NOT NULL,
            actor TEXT NOT NULL CHECK(actor IN ('human','worker','system')),
            detail_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        INSERT INTO projects VALUES ('legacy-project','Legacy','','en','2026-01-01T00:00:00+00:00');
        INSERT INTO jobs VALUES (
            'legacy-job','legacy-project','legacy request','en','planned','{}',
            '2026-01-01T00:00:00+00:00'
        );
        INSERT INTO job_events(
            job_id,from_status,to_status,actor,detail_json,created_at
        ) VALUES (
            'legacy-job',NULL,'planned','system','{"reason":"legacy"}',
            '2026-01-01T00:00:00+00:00'
        );
        """
    )
    connection.commit()
    connection.close()


def test_legacy_jobs_migration_preserves_job_and_event_history(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite3"
    _create_legacy_database(path)
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(path))

    store.initialize()

    with store.connect() as connection:
        job = connection.execute("SELECT * FROM jobs WHERE id='legacy-job'").fetchone()
        events = connection.execute(
            "SELECT job_id,to_status,detail_json FROM job_events WHERE job_id='legacy-job'"
        ).fetchall()
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert job is not None
    assert job["status"] == "planned"
    assert job["attempt_count"] == 0
    assert job["max_attempts"] == 3
    assert job["updated_at"] == job["created_at"]
    assert len(events) == 1
    assert events[0]["to_status"] == "planned"
    assert '"legacy"' in events[0]["detail_json"]
    assert violations == []
    assert version == 4


def test_legacy_jobs_migration_is_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite3"
    _create_legacy_database(path)
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(path))

    store.initialize()
    store.initialize()

    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM job_events").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
