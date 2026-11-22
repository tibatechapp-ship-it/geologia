"""SQLite metadata store for projects, datasets, and analysis plans."""
import hashlib
from contextlib import contextmanager
from collections.abc import Iterator
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


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield one SQLite connection and always commit/rollback then close it.

    The sqlite3 connection context manager commits or rolls back transactions,
    but does not close the connection. This wrapper centralizes the lifecycle
    for every store operation so long-running API sessions do not retain
    completed connections.
    """
    conn = sqlite3.connect(database_path(), timeout=10)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


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
            status TEXT NOT NULL CHECK(status IN (
                'planned','queued','running','succeeded','failed','cancel_requested','cancelled'
            )),
            plan_json TEXT NOT NULL, created_at TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
            max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts >= 1),
            queued_at TEXT, started_at TEXT, finished_at TEXT, updated_at TEXT NOT NULL,
            error_code TEXT, error_message TEXT
        );
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            name TEXT NOT NULL, format TEXT NOT NULL, original_filename TEXT NOT NULL,
            content_path TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
            crs TEXT, data_role TEXT, status TEXT NOT NULL, summary_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
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
        CREATE INDEX IF NOT EXISTS idx_datasets_project_created
            ON datasets(project_id, created_at DESC);
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(datasets)")}
        if "data_role" not in columns:
            conn.execute("ALTER TABLE datasets ADD COLUMN data_role TEXT")

        job_schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
        ).fetchone()["sql"]
        job_columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        required_job_columns = {
            "attempt_count", "max_attempts", "queued_at", "started_at",
            "finished_at", "updated_at", "error_code", "error_message",
        }
        schema_version = conn.execute("PRAGMA user_version").fetchone()[0]
        needs_migration = (
            schema_version < 1
            or "cancel_requested" not in job_schema
            or not required_job_columns.issubset(job_columns)
        )
        if needs_migration:
            conn.execute("BEGIN IMMEDIATE")
            job_schema = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
            ).fetchone()["sql"]
            if "cancel_requested" not in job_schema:
                conn.execute("DROP TABLE IF EXISTS jobs_new")
                conn.execute("""
                    CREATE TABLE jobs_new (
                        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                        request TEXT NOT NULL,
                        language TEXT NOT NULL CHECK(language IN ('ar','en')),
                        status TEXT NOT NULL CHECK(status IN (
                            'planned','queued','running','succeeded','failed',
                            'cancel_requested','cancelled'
                        )),
                        plan_json TEXT NOT NULL, created_at TEXT NOT NULL,
                        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
                        max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts >= 1),
                        queued_at TEXT, started_at TEXT, finished_at TEXT, updated_at TEXT NOT NULL,
                        error_code TEXT, error_message TEXT
                    )
                """)
                conn.execute("""
                    INSERT INTO jobs_new(
                        id, project_id, request, language, status, plan_json, created_at, updated_at
                    )
                    SELECT id, project_id, request, language, status, plan_json,
                           created_at, created_at
                    FROM jobs
                """)
                conn.execute("DROP TABLE jobs")
                conn.execute("ALTER TABLE jobs_new RENAME TO jobs")
            else:
                job_columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
                additions = {
                    "attempt_count": "INTEGER NOT NULL DEFAULT 0",
                    "max_attempts": "INTEGER NOT NULL DEFAULT 3",
                    "queued_at": "TEXT",
                    "started_at": "TEXT",
                    "finished_at": "TEXT",
                    "updated_at": "TEXT",
                    "error_code": "TEXT",
                    "error_message": "TEXT",
                }
                for name, definition in additions.items():
                    if name not in job_columns:
                        conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
                conn.execute("UPDATE jobs SET updated_at=created_at WHERE updated_at IS NULL")
            conn.execute("PRAGMA user_version = 1")

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_project_created "
            "ON jobs(project_id, created_at DESC)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                from_status TEXT, to_status TEXT NOT NULL,
                actor TEXT NOT NULL CHECK(actor IN ('human','worker','system')),
                detail_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_events_job_created "
            "ON job_events(job_id, id)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coverage_assessments (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL REFERENCES projects(id),
                created_by TEXT NOT NULL,
                request_json TEXT NOT NULL,
                assessment_json TEXT NOT NULL,
                request_sha256 TEXT NOT NULL,
                assessment_sha256 TEXT NOT NULL,
                previous_hash TEXT,
                record_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_coverage_assessments_project_sequence "
            "ON coverage_assessments(project_id, sequence)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accuracy_assessments (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL REFERENCES projects(id),
                created_by TEXT NOT NULL,
                request_json TEXT NOT NULL,
                assessment_json TEXT NOT NULL,
                request_sha256 TEXT NOT NULL,
                assessment_sha256 TEXT NOT NULL,
                previous_hash TEXT,
                record_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_accuracy_assessments_project_sequence "
            "ON accuracy_assessments(project_id, sequence)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readiness_assessments (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL REFERENCES projects(id),
                created_by TEXT NOT NULL,
                request_json TEXT NOT NULL,
                assessment_json TEXT NOT NULL,
                request_sha256 TEXT NOT NULL,
                assessment_sha256 TEXT NOT NULL,
                previous_hash TEXT,
                record_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_readiness_assessments_project_sequence "
            "ON readiness_assessments(project_id, sequence)"
        )
        conn.execute("PRAGMA user_version = 4")


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
            "INSERT INTO jobs(id,project_id,request,language,status,plan_json,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (item["id"], project_id, request, language, item["status"],
             json.dumps(plan, ensure_ascii=False), item["created_at"], item["created_at"]),
        )
        _insert_job_event(
            conn, item["id"], None, "planned", "system",
            {"reason": "job_created_without_execution"},
        )
    return get_job(item["id"]) or item


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


def _insert_job_event(
    conn: sqlite3.Connection,
    job_id: str,
    from_status: str | None,
    to_status: str,
    actor: str,
    detail: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "INSERT INTO job_events(job_id,from_status,to_status,actor,detail_json,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (
            job_id, from_status, to_status, actor,
            json.dumps(detail or {}, ensure_ascii=False), utc_now(),
        ),
    )


_JOB_TRANSITIONS = {
    "planned": {"queued", "cancelled"},
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancel_requested"},
    "cancel_requested": {"cancelled"},
    "failed": {"queued"},
    "succeeded": set(),
    "cancelled": set(),
}


def transition_job(
    job_id: str,
    target_status: str,
    *,
    actor: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Atomically apply one legal job-state transition and append its audit event."""
    if actor not in {"human", "worker", "system"}:
        raise ValueError("actor must be human, worker, or system")
    initialize()
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        current = row["status"]
        if target_status not in _JOB_TRANSITIONS[current]:
            raise ValueError(f"invalid job transition: {current} -> {target_status}")
        if target_status == "queued" and current == "failed":
            if row["attempt_count"] >= row["max_attempts"]:
                raise ValueError("job retry limit reached")
        updates: dict[str, Any] = {"status": target_status, "updated_at": now}
        if target_status == "queued":
            updates["queued_at"] = now
            updates["finished_at"] = None
            updates["error_code"] = None
            updates["error_message"] = None
        elif target_status == "running":
            updates["started_at"] = now
            updates["attempt_count"] = row["attempt_count"] + 1
        elif target_status in {"succeeded", "failed", "cancelled"}:
            updates["finished_at"] = now
        if target_status == "failed":
            details = detail or {}
            updates["error_code"] = str(details.get("error_code", "job.failed"))[:100]
            updates["error_message"] = str(details.get("error_message", "Job failed."))[:1000]
        assignments = ", ".join(f"{column}=?" for column in updates)
        conn.execute(
            f"UPDATE jobs SET {assignments} WHERE id=?",
            (*updates.values(), job_id),
        )
        _insert_job_event(conn, job_id, current, target_status, actor, detail)
        updated = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _job_row(updated)


def request_job_cancellation(
    job_id: str, *, actor: str = "human"
) -> dict[str, Any] | None:
    """Atomically cancel a not-yet-running job or request cooperative worker cancellation."""
    if actor not in {"human", "worker", "system"}:
        raise ValueError("actor must be human, worker, or system")
    initialize()
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        current = row["status"]
        if current in {"cancel_requested", "cancelled"}:
            return _job_row(row)
        if current == "running":
            target = "cancel_requested"
        elif current in {"planned", "queued"}:
            target = "cancelled"
        else:
            raise ValueError(f"cannot cancel job in {current} state")
        updates = {"status": target, "updated_at": now}
        if target == "cancelled":
            updates["finished_at"] = now
        assignments = ", ".join(f"{column}=?" for column in updates)
        conn.execute(
            f"UPDATE jobs SET {assignments} WHERE id=?",
            (*updates.values(), job_id),
        )
        _insert_job_event(
            conn, job_id, current, target, actor,
            {"reason": "user_requested_cancellation"},
        )
        updated = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _job_row(updated)


def list_job_events(job_id: str) -> list[dict[str, Any]]:
    initialize()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM job_events WHERE job_id=? ORDER BY id", (job_id,)
        ).fetchall()
    events = []
    for row in rows:
        item = dict(row)
        item["detail"] = json.loads(item.pop("detail_json"))
        events.append(item)
    return events


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
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            payload = {"_invalid_payload_json": True}
            chain_valid = False
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
                "external_source": summary.get("external_source", {"status": "not_provided"}),
                "source_dataset_id": summary.get("derived_from_dataset_id"),
                "source_dataset_sha256": summary.get("source_dataset_sha256"),
                "operation": summary.get("operation"),
                "source_crs": summary.get("source_crs"),
                "target_crs": summary.get("target_crs"),
                "axis_order": summary.get("axis_order"),
                "operation_description": summary.get("operation_description"),
                "operation_definition": summary.get("operation_definition"),
                "operation_accuracy_m": summary.get("operation_accuracy_m"),
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


def save_dataset_validation(dataset_id: str, report: dict[str, Any]) -> None:
    """Persist a deterministic validation report in dataset metadata."""
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT project_id, summary_json FROM datasets WHERE id=?", (dataset_id,)
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
        _append_provenance_event(
            conn, row["project_id"], dataset_id, "dataset_validated", report, utc_now()
        )


def get_dataset_validation(dataset_id: str) -> dict[str, Any] | None:
    """Return the latest persisted validation report, if present."""
    item = get_dataset(dataset_id)
    if item is None:
        return None
    return item["summary"].get("validation_report")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _coverage_record_hash(
    *,
    record_id: str,
    project_id: str,
    created_by: str,
    request_sha256: str,
    assessment_sha256: str,
    previous_hash: str | None,
    created_at: str,
) -> str:
    payload = {
        "id": record_id,
        "project_id": project_id,
        "created_by": created_by,
        "request_sha256": request_sha256,
        "assessment_sha256": assessment_sha256,
        "previous_hash": previous_hash,
        "created_at": created_at,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def save_coverage_assessment(
    project_id: str,
    request: dict[str, Any],
    assessment: dict[str, Any],
    created_by: str,
) -> dict[str, Any]:
    """Persist a coverage assessment in a per-project tamper-evident hash chain."""
    if not created_by.strip():
        raise ValueError("created_by must not be empty")
    request_json = _canonical_json(request)
    assessment_json = _canonical_json(assessment)
    request_sha256 = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
    assessment_sha256 = hashlib.sha256(assessment_json.encode("utf-8")).hexdigest()
    record_id = str(uuid4())
    created_at = utc_now()
    initialize()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None:
            raise ValueError("project not found")
        previous = conn.execute(
            "SELECT record_hash FROM coverage_assessments "
            "WHERE project_id=? ORDER BY sequence DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        previous_hash = previous["record_hash"] if previous else None
        record_hash = _coverage_record_hash(
            record_id=record_id,
            project_id=project_id,
            created_by=created_by.strip(),
            request_sha256=request_sha256,
            assessment_sha256=assessment_sha256,
            previous_hash=previous_hash,
            created_at=created_at,
        )
        conn.execute(
            "INSERT INTO coverage_assessments("
            "id,project_id,created_by,request_json,assessment_json,request_sha256,"
            "assessment_sha256,previous_hash,record_hash,created_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                record_id,
                project_id,
                created_by.strip(),
                request_json,
                assessment_json,
                request_sha256,
                assessment_sha256,
                previous_hash,
                record_hash,
                created_at,
            ),
        )
    result = get_coverage_assessment(record_id)
    if result is None:
        raise RuntimeError("coverage assessment was not persisted")
    return result


def _coverage_assessment_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "created_by": row["created_by"],
        "request": json.loads(row["request_json"]),
        "assessment": json.loads(row["assessment_json"]),
        "request_sha256": row["request_sha256"],
        "assessment_sha256": row["assessment_sha256"],
        "previous_hash": row["previous_hash"],
        "record_hash": row["record_hash"],
        "created_at": row["created_at"],
    }


def get_coverage_assessment(record_id: str) -> dict[str, Any] | None:
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM coverage_assessments WHERE id=?", (record_id,)
        ).fetchone()
    return _coverage_assessment_row(row) if row else None


def list_coverage_assessments(
    project_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("invalid coverage assessment pagination")
    initialize()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM coverage_assessments WHERE project_id=? "
            "ORDER BY sequence DESC LIMIT ? OFFSET ?",
            (project_id, limit, offset),
        ).fetchall()
        count = conn.execute(
            "SELECT COUNT(*) FROM coverage_assessments WHERE project_id=?",
            (project_id,),
        ).fetchone()[0]
    return {
        "count": count,
        "limit": limit,
        "offset": offset,
        "assessments": [_coverage_assessment_row(row) for row in rows],
    }


def verify_coverage_assessment_chain(project_id: str) -> dict[str, Any]:
    """Verify per-project sequence links and canonical payload/record hashes."""
    initialize()
    errors: list[dict[str, Any]] = []
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM coverage_assessments WHERE project_id=? ORDER BY sequence",
            (project_id,),
        ).fetchall()
    previous_hash = None
    for row in rows:
        request_json = row["request_json"]
        assessment_json = row["assessment_json"]
        request_hash = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        assessment_hash = hashlib.sha256(assessment_json.encode("utf-8")).hexdigest()
        if request_hash != row["request_sha256"]:
            errors.append({"record_id": row["id"], "code": "request_hash_mismatch"})
        if assessment_hash != row["assessment_sha256"]:
            errors.append({"record_id": row["id"], "code": "assessment_hash_mismatch"})
        if row["previous_hash"] != previous_hash:
            errors.append({"record_id": row["id"], "code": "previous_hash_mismatch"})
        expected = _coverage_record_hash(
            record_id=row["id"],
            project_id=row["project_id"],
            created_by=row["created_by"],
            request_sha256=row["request_sha256"],
            assessment_sha256=row["assessment_sha256"],
            previous_hash=row["previous_hash"],
            created_at=row["created_at"],
        )
        if expected != row["record_hash"]:
            errors.append({"record_id": row["id"], "code": "record_hash_mismatch"})
        previous_hash = row["record_hash"]
    return {
        "project_id": project_id,
        "valid": not errors,
        "record_count": len(rows),
        "last_record_hash": previous_hash,
        "errors": errors,
        "tamper_evident_not_tamper_proof": True,
    }


def _accuracy_record_hash(
    *,
    record_id: str,
    project_id: str,
    created_by: str,
    request_sha256: str,
    assessment_sha256: str,
    previous_hash: str | None,
    created_at: str,
) -> str:
    payload = {
        "id": record_id,
        "project_id": project_id,
        "created_by": created_by,
        "request_sha256": request_sha256,
        "assessment_sha256": assessment_sha256,
        "previous_hash": previous_hash,
        "created_at": created_at,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def save_accuracy_assessment(
    project_id: str,
    request: dict[str, Any],
    assessment: dict[str, Any],
    created_by: str,
) -> dict[str, Any]:
    """Persist DEM accuracy residuals in a separate tamper-evident project chain."""
    if not created_by.strip():
        raise ValueError("created_by must not be empty")
    request_json = _canonical_json(request)
    assessment_json = _canonical_json(assessment)
    request_sha256 = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
    assessment_sha256 = hashlib.sha256(assessment_json.encode("utf-8")).hexdigest()
    record_id = str(uuid4())
    created_at = utc_now()
    initialize()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None:
            raise ValueError("project not found")
        previous = conn.execute(
            "SELECT record_hash FROM accuracy_assessments "
            "WHERE project_id=? ORDER BY sequence DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        previous_hash = previous["record_hash"] if previous else None
        record_hash = _accuracy_record_hash(
            record_id=record_id,
            project_id=project_id,
            created_by=created_by.strip(),
            request_sha256=request_sha256,
            assessment_sha256=assessment_sha256,
            previous_hash=previous_hash,
            created_at=created_at,
        )
        conn.execute(
            "INSERT INTO accuracy_assessments("
            "id,project_id,created_by,request_json,assessment_json,request_sha256,"
            "assessment_sha256,previous_hash,record_hash,created_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                record_id,
                project_id,
                created_by.strip(),
                request_json,
                assessment_json,
                request_sha256,
                assessment_sha256,
                previous_hash,
                record_hash,
                created_at,
            ),
        )
    result = get_accuracy_assessment(record_id)
    if result is None:
        raise RuntimeError("accuracy assessment was not persisted")
    return result


def _accuracy_assessment_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "created_by": row["created_by"],
        "request": json.loads(row["request_json"]),
        "assessment": json.loads(row["assessment_json"]),
        "request_sha256": row["request_sha256"],
        "assessment_sha256": row["assessment_sha256"],
        "previous_hash": row["previous_hash"],
        "record_hash": row["record_hash"],
        "created_at": row["created_at"],
    }


def get_accuracy_assessment(record_id: str) -> dict[str, Any] | None:
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM accuracy_assessments WHERE id=?", (record_id,)
        ).fetchone()
    return _accuracy_assessment_row(row) if row else None


def list_accuracy_assessments(
    project_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("invalid accuracy assessment pagination")
    initialize()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM accuracy_assessments WHERE project_id=? "
            "ORDER BY sequence DESC LIMIT ? OFFSET ?",
            (project_id, limit, offset),
        ).fetchall()
        count = conn.execute(
            "SELECT COUNT(*) FROM accuracy_assessments WHERE project_id=?",
            (project_id,),
        ).fetchone()[0]
    return {
        "count": count,
        "limit": limit,
        "offset": offset,
        "assessments": [_accuracy_assessment_row(row) for row in rows],
    }


def verify_accuracy_assessment_chain(project_id: str) -> dict[str, Any]:
    """Verify canonical payload hashes and sequence links for DEM accuracy records."""
    initialize()
    errors: list[dict[str, Any]] = []
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM accuracy_assessments WHERE project_id=? ORDER BY sequence",
            (project_id,),
        ).fetchall()
    previous_hash = None
    for row in rows:
        request_hash = hashlib.sha256(row["request_json"].encode("utf-8")).hexdigest()
        assessment_hash = hashlib.sha256(
            row["assessment_json"].encode("utf-8")
        ).hexdigest()
        if request_hash != row["request_sha256"]:
            errors.append({"record_id": row["id"], "code": "request_hash_mismatch"})
        if assessment_hash != row["assessment_sha256"]:
            errors.append({"record_id": row["id"], "code": "assessment_hash_mismatch"})
        if row["previous_hash"] != previous_hash:
            errors.append({"record_id": row["id"], "code": "previous_hash_mismatch"})
        expected = _accuracy_record_hash(
            record_id=row["id"],
            project_id=row["project_id"],
            created_by=row["created_by"],
            request_sha256=row["request_sha256"],
            assessment_sha256=row["assessment_sha256"],
            previous_hash=row["previous_hash"],
            created_at=row["created_at"],
        )
        if expected != row["record_hash"]:
            errors.append({"record_id": row["id"], "code": "record_hash_mismatch"})
        previous_hash = row["record_hash"]
    return {
        "project_id": project_id,
        "valid": not errors,
        "record_count": len(rows),
        "last_record_hash": previous_hash,
        "errors": errors,
        "tamper_evident_not_tamper_proof": True,
    }


def _readiness_record_hash(
    *,
    record_id: str,
    project_id: str,
    created_by: str,
    request_sha256: str,
    assessment_sha256: str,
    previous_hash: str | None,
    created_at: str,
) -> str:
    payload = {
        "id": record_id,
        "project_id": project_id,
        "created_by": created_by,
        "request_sha256": request_sha256,
        "assessment_sha256": assessment_sha256,
        "previous_hash": previous_hash,
        "created_at": created_at,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def save_readiness_assessment(
    project_id: str,
    request: dict[str, Any],
    assessment: dict[str, Any],
    created_by: str,
) -> dict[str, Any]:
    """Persist a readiness decision in a separate tamper-evident project chain."""
    if not created_by.strip():
        raise ValueError("created_by must not be empty")
    request_json = _canonical_json(request)
    assessment_json = _canonical_json(assessment)
    request_sha256 = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
    assessment_sha256 = hashlib.sha256(assessment_json.encode("utf-8")).hexdigest()
    record_id = str(uuid4())
    created_at = utc_now()
    initialize()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None:
            raise ValueError("project not found")
        previous = conn.execute(
            "SELECT record_hash FROM readiness_assessments "
            "WHERE project_id=? ORDER BY sequence DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        previous_hash = previous["record_hash"] if previous else None
        record_hash = _readiness_record_hash(
            record_id=record_id,
            project_id=project_id,
            created_by=created_by.strip(),
            request_sha256=request_sha256,
            assessment_sha256=assessment_sha256,
            previous_hash=previous_hash,
            created_at=created_at,
        )
        conn.execute(
            "INSERT INTO readiness_assessments("
            "id,project_id,created_by,request_json,assessment_json,request_sha256,"
            "assessment_sha256,previous_hash,record_hash,created_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                record_id,
                project_id,
                created_by.strip(),
                request_json,
                assessment_json,
                request_sha256,
                assessment_sha256,
                previous_hash,
                record_hash,
                created_at,
            ),
        )
    result = get_readiness_assessment(record_id)
    if result is None:
        raise RuntimeError("readiness assessment was not persisted")
    return result


def _readiness_assessment_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "created_by": row["created_by"],
        "request": json.loads(row["request_json"]),
        "assessment": json.loads(row["assessment_json"]),
        "request_sha256": row["request_sha256"],
        "assessment_sha256": row["assessment_sha256"],
        "previous_hash": row["previous_hash"],
        "record_hash": row["record_hash"],
        "created_at": row["created_at"],
    }


def get_readiness_assessment(record_id: str) -> dict[str, Any] | None:
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM readiness_assessments WHERE id=?", (record_id,)
        ).fetchone()
    return _readiness_assessment_row(row) if row else None


def list_readiness_assessments(
    project_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("invalid readiness assessment pagination")
    initialize()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM readiness_assessments WHERE project_id=? "
            "ORDER BY sequence DESC LIMIT ? OFFSET ?",
            (project_id, limit, offset),
        ).fetchall()
        count = conn.execute(
            "SELECT COUNT(*) FROM readiness_assessments WHERE project_id=?",
            (project_id,),
        ).fetchone()[0]
    return {
        "count": count,
        "limit": limit,
        "offset": offset,
        "assessments": [_readiness_assessment_row(row) for row in rows],
    }


def verify_readiness_assessment_chain(project_id: str) -> dict[str, Any]:
    """Verify canonical payload hashes and sequence links for readiness records."""
    initialize()
    errors: list[dict[str, Any]] = []
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM readiness_assessments WHERE project_id=? ORDER BY sequence",
            (project_id,),
        ).fetchall()
    previous_hash = None
    for row in rows:
        request_hash = hashlib.sha256(row["request_json"].encode("utf-8")).hexdigest()
        assessment_hash = hashlib.sha256(
            row["assessment_json"].encode("utf-8")
        ).hexdigest()
        if request_hash != row["request_sha256"]:
            errors.append({"record_id": row["id"], "code": "request_hash_mismatch"})
        if assessment_hash != row["assessment_sha256"]:
            errors.append({"record_id": row["id"], "code": "assessment_hash_mismatch"})
        if row["previous_hash"] != previous_hash:
            errors.append({"record_id": row["id"], "code": "previous_hash_mismatch"})
        expected = _readiness_record_hash(
            record_id=row["id"],
            project_id=row["project_id"],
            created_by=row["created_by"],
            request_sha256=row["request_sha256"],
            assessment_sha256=row["assessment_sha256"],
            previous_hash=row["previous_hash"],
            created_at=row["created_at"],
        )
        if expected != row["record_hash"]:
            errors.append({"record_id": row["id"], "code": "record_hash_mismatch"})
        previous_hash = row["record_hash"]
    return {
        "project_id": project_id,
        "valid": not errors,
        "record_count": len(rows),
        "last_record_hash": previous_hash,
        "errors": errors,
        "tamper_evident_not_tamper_proof": True,
    }


def save_dataset_coverage_inspection(dataset_id: str, report: dict[str, Any]) -> None:
    """Persist a DEM/AOI coverage inspection and append its dataset provenance event."""
    initialize()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT project_id, summary_json FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
        if row is None:
            raise ValueError("dataset not found")
        summary = json.loads(row["summary_json"])
        summary["coverage_inspection"] = report
        conn.execute(
            "UPDATE datasets SET summary_json=? WHERE id=?",
            (json.dumps(summary, ensure_ascii=False, allow_nan=False), dataset_id),
        )
        _append_provenance_event(
            conn,
            row["project_id"],
            dataset_id,
            "dataset_coverage_inspected",
            report,
            utc_now(),
        )


def get_dataset_coverage_inspection(dataset_id: str) -> dict[str, Any] | None:
    """Return the latest persisted DEM/AOI coverage inspection, if present."""
    item = get_dataset(dataset_id)
    if item is None:
        return None
    return item["summary"].get("coverage_inspection")
