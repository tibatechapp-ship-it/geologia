# GEOLOGIA | جيولوجيا

**Bilingual open-source geoscience platform** — Phase 1 foundation.

The chief agent is planned as **المهندس الجمهوري**. The current API is a real local workspace for projects and durable analysis-plan records. It does not execute scientific engines.

## Current verified source scope

- FastAPI application with health endpoint.
- SQLite-backed project and job records.
- Deterministic Arabic/English keyword planner (plan only).
- Registry with 30 catalog cards, all explicitly `planned` and `license_status: unverified`.
- Tests and GitHub Actions workflow.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
geologia-api
```

Open `http://127.0.0.1:8000/docs`.

Default SQLite path: `.geologia/geologia.sqlite3`. Set `GEOLOGIA_DB_PATH` to use another path.

## API

- `GET /health`
- `GET /api/v1/engines` and `GET /api/v1/engines/{engine_id}`
- `GET /api/v1/projects`, `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/jobs/{job_id}`

## Scientific and security honesty

The 30 registry entries are catalog references, not integrations. Health reports `engines_integrated: 0` and `execution_enabled: false`. Jobs remain `planned`; no geologic interpretation, groundwater yield, mineral probability, or drilling recommendation is produced.

Do not expose this development API publicly without authentication, authorization, quotas, private storage, isolated workers, and monitoring. GeoPackage/GeoTIFF processing, uploads, workers, frontend, and engine adapters are not implemented yet.

See [Phase 1 scope](docs/PHASE1.md) and [local validation record](docs/LOCAL_VALIDATION.md).
