"""SQLite metadata store for projects, datasets, and analysis plans."""
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
    """Persist a computed structural inspection report without changing file bytes."""
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT summary_json FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
        if row is None:
            return
        summary = json.loads(row["summary_json"])
        summary["inspection"] = report
        conn.execute(
            "UPDATE datasets SET status=?, summary_json=? WHERE id=?",
            ("inspected_structural_metrics", json.dumps(summary, ensure_ascii=False), dataset_id),
        )


def save_dataset_validation(dataset_id: str, report: dict[str, Any]) -> None:
    """Persist a validation report separately from structural inspection metrics."""
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT summary_json FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
        if row is None:
            return
        summary = json.loads(row["summary_json"])
        summary["validation_report"] = report
        status = (
            "validation_passed"
            if report.get("validation_status") == "passed"
            else "validation_failed"
        )
        conn.execute(
            "UPDATE datasets SET status=?, summary_json=? WHERE id=?",
            (status, json.dumps(summary, ensure_ascii=False), dataset_id),
        )


def get_dataset_validation(dataset_id: str) -> dict[str, Any] | None:
    """Return the last persisted validation report, if one exists."""
    item = get_dataset(dataset_id)
    if item is None:
        return None
    return item["summary"].get("validation_report")
