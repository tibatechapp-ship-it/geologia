# Phase 1 — Durable workspace

This commit adds a real SQLite-backed project and analysis-plan record API.

## Implemented

- Create and list projects; retrieve a project by ID.
- Create an analysis job record linked to a project.
- Retrieve and list jobs from SQLite after API restart.
- Deterministic bilingual keyword planner.
- Honest state: jobs are `planned`; no scientific engine runs.
- Health endpoint explicitly reports `engines_integrated: 0` and `execution_enabled: false`.

## API

- `GET /health`
- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/jobs/{job_id}`

## Run

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
geologia-api
```

Set `GEOLOGIA_DB_PATH` to move the SQLite database. Default: `.geologia/geologia.sqlite3`.

## Explicitly not implemented

Authentication, file upload, GIS execution, workers/queue, frontend, and external engine adapters.
Do not expose this API to the public internet without authentication and deployment hardening.
