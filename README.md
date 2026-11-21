# GEOLOGIA | جيولوجيا

**Bilingual open-source geoscience platform** — engineering foundation, not a certified scientific analysis system.

The planned chief agent is **المهندس الجمهوري**. The current API provides a local workspace for projects, datasets, and durable analysis-plan records. It does not execute scientific engines.

## Current source scope

- FastAPI application and health endpoint.
- SQLite-backed projects, jobs, and dataset metadata.
- Streaming dataset intake with a 50 MiB limit, filename sanitization, SHA-256, and generated storage paths.
- Structural GeoJSON validation and deterministic inspection; CSV structural inspection. Neither produces geological interpretation.
- Role-tagged datasets and a missing-input readiness report in every analysis plan.
- Bilingual Arabic RTL / English LTR web workspace for projects, dataset intake, maps, and plan display.
- Chief-agent identity and specialist-role routing by deterministic rules (not an LLM).
- Deterministic Arabic/English plan routing.
- Registry with 30 catalog cards, all explicitly `planned` and `license_status: unverified`.
- Python 3.12+ is required. CI tests Python 3.12, 3.14, and 3.15, including GIS dependencies, Ruff, JavaScript syntax, compile, and pytest. Python 3.14 remains the practical local baseline where Python 3.15 is not yet available (including the current Termux validation target).

## Contact

For platform inquiries and project communication: [aigeologia@gmail.com](mailto:aigeologia@gmail.com).

## Quick start

```bash
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,gis]"
python -m ruff check src tests
python -m compileall -q src tests
python -m pytest
geologia-api
```

Open `http://127.0.0.1:8000/docs`.

Default SQLite path: `.geologia/geologia.sqlite3`. Set `GEOLOGIA_DB_PATH` to move it. Default upload directory: `.geologia/uploads`; set `GEOLOGIA_UPLOAD_DIR` to change it.

## API

- `GET /api/v1/crs/inspect?crs=EPSG:4326` (requires optional `gis` extra)
- `POST /api/v1/datasets/{dataset_id}/reproject` with `{"target_crs":"EPSG:3857"}` (GeoJSON only; creates a derived dataset and preserves the source)
- `GET /health`
- `GET /api/v1/engines` and `GET /api/v1/engines/{engine_id}`
- `GET /api/v1/projects`, `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/datasets`
- `GET /api/v1/projects/{project_id}/datasets`
- `GET /api/v1/datasets/{dataset_id}`
- `POST /api/v1/datasets/{dataset_id}/inspect` (GeoJSON/CSV structural metrics; GeoPackage, GeoTIFF, and LAS require the optional `formats` extra)
- `GET /api/v1/datasets/{dataset_id}/provenance` (dataset events and project-wide SHA-256 chain verification)
- `POST /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/jobs/{job_id}`

## Engineering audit

See [the full-history engineering audit](docs/ENGINEERING_AUDIT.md) for verified fixes, known blockers, and the ordered remediation roadmap.

## Scientific and security honesty

The 30 registry entries are catalog references, not integrations. Health reports `engines_integrated: 0` and `execution_enabled: false`. Jobs remain `planned`; no geologic interpretation, groundwater yield, mineral probability, or drilling recommendation is produced.

Do not expose this development API publicly. The bundled development CLI now rejects non-loopback bind addresses. Running the ASGI app through another server can bypass that CLI guard, so remote deployment still requires authentication, authorization, quotas, private storage, isolated workers, and monitoring. Raster processing, general vector transformations, raster reprojection, worker isolation, and scientific engine adapters are not implemented. GeoJSON CRS inspection and vector reprojection are available through the optional `gis` extra. CRS metadata supplied by uploaders is treated as a declaration and is not inferred from coordinates. See [Phase 5](docs/PHASE5.md).

Development baseline: Python 3.14.x. Python 3.12 and 3.15 are included in CI compatibility coverage. Python 3.15 CI success does not imply Termux/Android compatibility. See [Phase 1](docs/PHASE1.md), [Phase 2](docs/PHASE2.md), [Phase 3](docs/PHASE3.md), and [Phase 4](docs/PHASE4.md).

## License

Original GEOLOGIA platform code is licensed under **AGPL-3.0-only**; see [LICENSE](LICENSE). Third-party engine licenses are separate and must be verified before each adapter is distributed. The registry's `license_status: unverified` is deliberate until that review is complete.

## Optional GeoPackage, GeoTIFF, and LAS inspection

Install the specialized parsers:

```bash
python -m pip install -e ".[gis,formats]"
```

Upload remains a bounded storage operation. Then call `POST /api/v1/datasets/{dataset_id}/inspect` to run parser-backed structural checks. GeoPackage inspection checks SQLite integrity and required metadata tables, reads layer metadata, and decodes a bounded feature sample. GeoTIFF inspection checks dimensions, CRS, coordinate units, transform, bounds, band units, nodata and metadata, and reads a bounded raster sample. LAS inspection checks header and point-record extent consistency, coordinate scales/offsets, declared CRS/VLR metadata, and a bounded point sample.

The inspectors enforce resource limits and report source SHA-256, parser/tool versions, and inspection time. Known-answer reprojection fixtures test EPSG:4326 ↔ EPSG:3857 output against expected coordinates and tolerances. Dataset ingestion, inspection, and derivation events are recorded in a project-scoped SHA-256 chain, available through `GET /api/v1/datasets/{dataset_id}/provenance`. The chain is tamper-evident, not tamper-proof.

These checks do **not** verify geological validity, measurement suitability, topology, or vertical datum correctness. Vertical CRS and datum metadata may be reported when declared, but no vertical transformation or datum verification is performed. See [the engineering audit](docs/ENGINEERING_AUDIT.md).
