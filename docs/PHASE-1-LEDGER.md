# Phase 1 — Durable project and job ledger

This branch adds a real SQLite-backed metadata core, not a scientific engine.

## Guarantees
- Project/job records survive process restarts.
- Jobs begin in `queued`; legal transitions are enforced atomically.
- Idempotency keys replay the original job and reject changed payloads with conflict.
- Audit events are append-only at the application level and record lifecycle transitions.
- SQLite uses WAL, foreign keys, a busy timeout, and immediate transactions for state changes.
- Request/result payloads are bounded to 100 KB.

## Explicit limitations
- Jobs are **recorded, not executed**. The API reports `execution_enabled: false`.
- No user authentication/authorization yet; do not expose this API to the public internet.
- No dataset storage, GIS processing, worker queue, or scientific interpretation yet.
- The audit table is not tamper-proof against a database administrator; production needs external/immutable audit export.

## Local run
```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
GEOLOGIA_DB=.geologia/ledger.sqlite3 uvicorn geologia.api:app --app-dir src --host 127.0.0.1 --port 8000
```

## API
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `POST /api/v1/projects/{project_id}/jobs` (optional `Idempotency-Key` header)
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/transition`
- `GET /api/v1/audit/{entity_id}`
