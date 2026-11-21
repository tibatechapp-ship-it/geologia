"""Durable project/job ledger using SQLite only; no user code is executed."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TERMINAL = {"succeeded", "failed", "cancelled"}
TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LedgerError(ValueError):
    pass


class Ledger:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                kind TEXT NOT NULL, status TEXT NOT NULL,
                input_json TEXT NOT NULL, result_json TEXT,
                error_code TEXT, idempotency_key TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(project_id, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
                event_type TEXT NOT NULL, actor TEXT NOT NULL,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_project_created
                ON jobs(project_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_events_entity
                ON events(entity_type, entity_id, sequence);
            """)

    @staticmethod
    def _event(db: sqlite3.Connection, entity_type: str, entity_id: str,
               event_type: str, actor: str, payload: dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO events(entity_type,entity_id,event_type,actor,payload_json,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (entity_type, entity_id, event_type, actor,
             json.dumps(payload, ensure_ascii=False, sort_keys=True), utcnow()),
        )

    def create_project(self, name: str, description: str = "", actor: str = "human") -> dict:
        name = name.strip()
        if not 1 <= len(name) <= 120:
            raise LedgerError("project name must be 1..120 characters")
        if len(description) > 2000:
            raise LedgerError("description exceeds 2000 characters")
        now, project_id = utcnow(), str(uuid.uuid4())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO projects(id,name,description,created_at,updated_at) VALUES(?,?,?,?,?)",
                (project_id, name, description, now, now),
            )
            self._event(db, "project", project_id, "project.created", actor,
                        {"name": name})
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise LedgerError("project_not_found")
        return dict(row)

    def list_projects(self, limit: int = 50) -> list[dict]:
        limit = max(1, min(limit, 100))
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM projects ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def create_job(self, project_id: str, kind: str, payload: dict,
                   idempotency_key: str | None = None, actor: str = "human") -> dict:
        if not 1 <= len(kind.strip()) <= 80:
            raise LedgerError("job kind must be 1..80 characters")
        if len(json.dumps(payload, ensure_ascii=False)) > 100_000:
            raise LedgerError("job payload exceeds 100 KB")
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 160:
            raise LedgerError("invalid idempotency key")
        job_id, now = str(uuid.uuid4()), utcnow()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                raise LedgerError("project_not_found")
            if idempotency_key:
                existing = db.execute(
                    "SELECT * FROM jobs WHERE project_id=? AND idempotency_key=?",
                    (project_id, idempotency_key),
                ).fetchone()
                if existing:
                    if existing["kind"] != kind or existing["input_json"] != json.dumps(
                        payload, ensure_ascii=False, sort_keys=True
                    ):
                        raise LedgerError("idempotency_conflict")
                    return dict(existing)
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            db.execute(
                "INSERT INTO jobs(id,project_id,kind,status,input_json,idempotency_key,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (job_id, project_id, kind, "queued", encoded, idempotency_key, now, now),
            )
            self._event(db, "job", job_id, "job.queued", actor,
                        {"project_id": project_id, "kind": kind})
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise LedgerError("job_not_found")
        item = dict(row)
        item["input"] = json.loads(item.pop("input_json"))
        result_json = item.pop("result_json")
        item["result"] = json.loads(result_json) if result_json else None
        return item

    def transition_job(self, job_id: str, status: str, actor: str = "system",
                       result: dict | None = None, error_code: str | None = None) -> dict:
        if status not in TRANSITIONS:
            raise LedgerError("invalid_status")
        if result is not None and len(json.dumps(result, ensure_ascii=False)) > 100_000:
            raise LedgerError("result exceeds 100 KB")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise LedgerError("job_not_found")
            old = row["status"]
            if status not in TRANSITIONS[old]:
                raise LedgerError(f"invalid_transition:{old}->{status}")
            db.execute(
                "UPDATE jobs SET status=?,result_json=?,error_code=?,updated_at=? WHERE id=?",
                (status, json.dumps(result, ensure_ascii=False, sort_keys=True) if result is not None else None,
                 error_code, utcnow(), job_id),
            )
            self._event(db, "job", job_id, "job." + status, actor,
                        {"from": old, "to": status, "error_code": error_code})
        return self.get_job(job_id)

    def events(self, entity_id: str, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
        with self._connect() as db:
            rows = db.execute(
                "SELECT sequence,entity_type,entity_id,event_type,actor,payload_json,created_at "
                "FROM events WHERE entity_id=? ORDER BY sequence LIMIT ?", (entity_id, limit)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result
