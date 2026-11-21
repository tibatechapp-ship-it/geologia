"""SQLite metadata store for projects, datasets, and analysis plans."""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def database_path() -> Path:
    path = Path(os.environ.get("GEOLOGIA_DB_PATH", ".geologia/geologia.sqlite3")).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def storage_path() -> Path:
    path = Path(os.environ.get("GEOLOGIA_UPLOAD_DIR", ".geologia/uploads")).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize() -> None:
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL CHECK(language IN ('ar','en')),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            request TEXT NOT NULL, language TEXT NOT NULL CHECK(language IN ('ar','en')),
            status TEXT NOT NULL CHECK(
                status IN ('planned','queued','running','succeeded','failed')
            ),
            plan_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_project_created
            ON jobs(project_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            name TEXT NOT NULL, format TEXT NOT NULL, original_filename TEXT NOT NULL,
            content_path TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
            crs TEXT, data_role TEXT, status TEXT NOT NULL, summary_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_datasets_project_created
            ON datasets(project_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS provenance_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            project_id TEXT NOT NULL REFERENCES projects(id),
            dataset_id TEXT NOT NULL REFERENCES datasets(id),
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT,
            event_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_provenance_project_sequence
            ON provenance_events(project_id, sequence);
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(datasets)")}
        if "data_role" not in columns:
            conn.execute("ALTER TABLE datasets ADD COLUMN data_role TEXT")


def create_project(name: str, description: str, language: str) -> dict[str, Any]:
    item = {"id": str(uuid4()), "name": name, "description": description,
            "language": language, "created_at": utc_now()}
    initialize()
    with connect() as conn:
        conn.execute(
            "INSERT INTO projects(id,name,description,language,created_at) VALUES(?,?,?,?,?)",
            (item["id"], item["name"], item["description"], item["language"], item["created_at"]),
        )
    return item


def list_projects() -> list[dict[str, Any]]:
    initialize()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def get_project(project_id: str) -> dict[str, Any] | None:
    initialize()
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row) if row else None


def create_job(project_id: str, request: str, language: str, plan: dict) -> dict[str, Any]:
    item = {"id": str(uuid4()), "project_id": project_id, "request": request,
            "language": language, "status": "planned",
            "plan": plan, "created_at": utc_now()}
    initialize()
    with connect() as conn:
        conn.execute(
            "INSERT INTO jobs(id,project_id,request,language,status,plan_json,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (item["id"], project_id, request, language, item["status"],
             json.dumps(plan, ensure_ascii=False), item["created_at"]),
        )
    return item


def list_jobs(project_id: str) -> list[dict[str, Any]]:
    initialize()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC", (project_id,)
        ).fetchall()
    return [_job_row(row) for row in rows]


def get_job(job_id: str) -> dict[str, Any] | None:
    initialize()
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _job_row(row) if row else None


def _job_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["plan"] = json.loads(item.pop("plan_json"))
    return item


def create_dataset(project_id: str, *, name: str, file_format: str,
                   original_filename: str, content_path: str, sha256: str,
                   size_bytes: int, crs: str | None, data_role: str | None,
                   summary: dict) -> dict[str, Any]:
    item = {
        "id": str(uuid4()), "project_id": project_id, "name": name,
        "format": file_format, "original_filename": original_filename,
        "sha256": sha256, "size_bytes": size_bytes, "crs": crs,
        "data_role": data_role, "status": "stored_not_analyzed",
        "summary": summary, "created_at": utc_now(),
    }
    initialize()
    with connect() as conn:
        conn.execute(
            "INSERT INTO datasets(id,project_id,name,format,original_filename,content_path,"
            "sha256,size_bytes,crs,data_role,status,summary_json,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item["id"], project_id, name, file_format, original_filename, content_path,
             sha256, size_bytes, crs, data_role, item["status"],
             json.dumps(summary, ensure_ascii=False), item["created_at"]),
        )
        event_type = "dataset_derived" if summary.get("operation") else "dataset_ingested"
        _append_provenance_event(
            conn, project_id, item["id"], event_type,
            {
                "sha256": sha256,
                "format": file_format,
                "original_filename": original_filename,
                "size_bytes": size_bytes,
                "declared_crs": crs,
                "data_role": data_role,
                "source_dataset_id": summary.get("derived_from_dataset_id"),
                "operation": summary.get("operation"),
                "tool_versions": summary.get("tool_versions", {}),
            },
            item["created_at"],
        )
    return item


def list_datasets(project_id: str) -> list[dict[str, Any]]:
    initialize()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM datasets WHERE project_id=? ORDER BY created_at DESC", (project_id,)
        ).fetchall()
    return [_dataset_row(row) for row in rows]


def list_dataset_roles(project_id: str) -> list[str]:
    initialize()
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT data_role FROM datasets WHERE project_id=? AND data_role IS NOT NULL",
            (project_id,),
        ).fetchall()
    return sorted(row["data_role"] for row in rows)


def get_dataset(dataset_id: str) -> dict[str, Any] | None:
    initialize()
    with connect() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    return _dataset_row(row) if row else None


def _dataset_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["summary"] = json.loads(item.pop("summary_json"))
    item.pop("content_path", None)
    return item


def get_dataset_content_path(dataset_id: str) -> str | None:
    """Internal-only lookup of the stored file path; never include it in API responses."""
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT content_path FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
    return row["content_path"] if row else None


def save_dataset_inspection(dataset_id: str, report: dict[str, Any]) -> None:
    """Persist an inspection report and append its provenance event."""
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT project_id, summary_json FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
        if row is None:
            return
        summary = json.loads(row["summary_json"])
        summary["inspection"] = report
        conn.execute(
            "UPDATE datasets SET status=?, summary_json=? WHERE id=?",
            ("inspected_structural_metrics", json.dumps(summary, ensure_ascii=False), dataset_id),
        )
        _append_provenance_event(
            conn, row["project_id"], dataset_id, "dataset_inspected",
            report, utc_now(),
        )


def _append_provenance_event(
    conn: sqlite3.Connection,
    project_id: str,
    dataset_id: str,
    event_type: str,
    payload: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Append a canonical SHA-256 chained event within the current SQLite transaction."""
    previous = conn.execute(
        "SELECT event_hash FROM provenance_events WHERE project_id=? "
        "ORDER BY sequence DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    previous_hash = previous["event_hash"] if previous else None
    event_id = str(uuid4())
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    envelope = {
        "event_id": event_id,
        "project_id": project_id,
        "dataset_id": dataset_id,
        "event_type": event_type,
        "payload": json.loads(payload_json),
        "previous_hash": previous_hash,
        "created_at": created_at,
    }
    canonical = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    event_hash = hashlib.sha256(canonical).hexdigest()
    conn.execute(
        "INSERT INTO provenance_events(event_id,project_id,dataset_id,event_type,"
        "payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (event_id, project_id, dataset_id, event_type, payload_json,
         previous_hash, event_hash, created_at),
    )
    return {**envelope, "event_hash": event_hash}


def get_dataset_provenance(dataset_id: str) -> dict[str, Any] | None:
    """Return dataset events and verify the entire project event hash chain."""
    initialize()
    with connect() as conn:
        dataset = conn.execute(
            "SELECT project_id FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
        if dataset is None:
            return None
        rows = conn.execute(
            "SELECT * FROM provenance_events WHERE project_id=? ORDER BY sequence",
            (dataset["project_id"],),
        ).fetchall()

    expected_previous = None
    chain_valid = True
    selected = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        envelope = {
            "event_id": row["event_id"],
            "project_id": row["project_id"],
            "dataset_id": row["dataset_id"],
            "event_type": row["event_type"],
            "payload": payload,
            "previous_hash": row["previous_hash"],
            "created_at": row["created_at"],
        }
        canonical = json.dumps(
            envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        actual_hash = hashlib.sha256(canonical).hexdigest()
        if row["previous_hash"] != expected_previous or row["event_hash"] != actual_hash:
            chain_valid = False
        expected_previous = row["event_hash"]
        if row["dataset_id"] == dataset_id:
            selected.append({**envelope, "event_hash": row["event_hash"]})
    return {
        "dataset_id": dataset_id,
        "project_event_count": len(rows),
        "chain_integrity": "verified" if chain_valid else "failed",
        "events": selected,
        "tamper_evident_not_tamper_proof": True,
    }
