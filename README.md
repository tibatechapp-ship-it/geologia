# GEOLOGIA | جيولوجيا

**Bilingual open-source geoscience platform** — Phase 1/2 foundation.

The planned chief agent is **المهندس الجمهوري**. The current API provides a local workspace for projects, datasets, and durable analysis-plan records. It does not execute scientific engines.

## Current source scope

- FastAPI application and health endpoint.
- SQLite-backed projects, jobs, and dataset metadata.
- Streaming dataset intake with a 50 MiB limit, filename sanitization, SHA-256, and generated storage paths.
- Structural-only GeoJSON validation; other supported formats are stored but not analyzed.
- Role-tagged datasets and a missing-input readiness report in every analysis plan.
- Bilingual Arabic RTL / English LTR web workspace for projects, dataset intake, and plan display.
- Chief-agent identity and specialist-role routing by deterministic rules (not an LLM).
- Deterministic Arabic/English plan routing.
- Registry with 30 catalog cards, all explicitly `planned` and `license_status: unverified`.
- CI on Python 3.10 and 3.12, including Ruff, compile, and pytest.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
geologia-api
```

Open `http://127.0.0.1:8000/docs`.

Default SQLite path: `.geologia/geologia.sqlite3`. Set `GEOLOGIA_DB_PATH` to move it. Default upload directory: `.geologia/uploads`; set `GEOLOGIA_UPLOAD_DIR` to change it.

## API

- `GET /health`
- `GET /api/v1/engines` and `GET /api/v1/engines/{engine_id}`
- `GET /api/v1/projects`, `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/datasets`
- `GET /api/v1/projects/{project_id}/datasets`
- `GET /api/v1/datasets/{dataset_id}`
- `POST /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/jobs/{job_id}`

## Scientific and security honesty

The 30 registry entries are catalog references, not integrations. Health reports `engines_integrated: 0` and `execution_enabled: false`. Jobs remain `planned`; no geologic interpretation, groundwater yield, mineral probability, or drilling recommendation is produced.

Do not expose this development API publicly without authentication, authorization, quotas, private storage, isolated workers, and monitoring. Spatial analysis, raster/vector processing, frontend, and engine adapters are not implemented yet.

See [Phase 1](docs/PHASE1.md), [Phase 2](docs/PHASE2.md), [Phase 3](docs/PHASE3.md), and [Phase 4](docs/PHASE4.md).

## License

Original GEOLOGIA platform code is licensed under **AGPL-3.0-only**; see [LICENSE](LICENSE). Third-party engine licenses are separate and must be verified before each adapter is distributed. The registry's `license_status: unverified` is deliberate until that review is complete.
