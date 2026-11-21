"""Small durable SQLite store for projects and jobs; no scientific execution."""
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
    configured = os.environ.get("GEOLOGIA_DB_PATH", ".geologia/geologia.sqlite3")
    path = Path(configured).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
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
            status TEXT NOT NULL CHECK(status IN ('planned','queued','running','succeeded','failed')),
            plan_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_project_created
            ON jobs(project_id, created_at DESC);
        """)


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
