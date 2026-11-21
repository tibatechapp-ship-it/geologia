# GEOLOGIA | جيولوجيا

**Bilingual open-source geoscience platform** — engineering foundation, not a certified scientific analysis system.

The local, model-independent chief geoscience agent is **Ali Algomori (علي الگوموري)**. Its current routing and planning core is deterministic and evidence-backed; it is not a trained neural model or a substitute for scientific engines. The current API provides a local workspace for projects, datasets, and durable analysis-plan records. It does not execute scientific engines.

## Current source scope

- FastAPI application and health endpoint.
- SQLite-backed projects, jobs, and dataset metadata.
- Streaming dataset intake with a 50 MiB limit, filename sanitization, SHA-256, and generated storage paths.
- Structural GeoJSON validation and deterministic inspection; CSV structural inspection. Neither produces geological interpretation.
- Role-tagged datasets and a missing-input readiness report in every analysis plan.
- Bilingual Arabic RTL / English LTR web workspace for projects, dataset intake, maps, and plan display.
- Ali Algomori model-independent agent: deterministic intent classification, visible keyword evidence, heuristic confidence, and specialist-role routing.
- Local scientific text retrieval using SQLite/FTS5 (with a token-scan fallback), reviewed source metadata, chunk hashes, and citations; no embeddings or automatic source downloads.
- Deterministic Arabic/English plan routing.
- Installable PWA shell with manifest, vector icon, and offline static-shell caching; API data is deliberately not cached. See [PWA installation and limits](docs/INSTALLABLE_APP.md).
- Local installation and loopback-only launch scripts for Linux/macOS, Windows PowerShell, and Termux. See [Local installation](docs/LOCAL_INSTALL.md).
- Registry with 30 catalog cards, all explicitly `planned` and `license_status: unverified`.
- Python 3.12+ is required. CI tests Python 3.12, 3.14, and 3.15, including GIS dependencies, Ruff, JavaScript syntax, compile, and pytest. Python 3.14 remains the practical local baseline where Python 3.15 is not yet available.

## Quick start — Linux/macOS/Termux

From the repository root:

```bash
bash scripts/install-local.sh
bash scripts/start-local.sh
```

Open `http://127.0.0.1:8000`. Choose a port with `GEOLOGIA_PORT=8123 bash scripts/start-local.sh`.

For Android Termux, the one-time native build bootstrap is:

```bash
bash scripts/install-termux.sh
bash scripts/start-local.sh
```

The bootstrap may install Rust and native build tools because some Python dependencies need compilation on Android. No AI model weights are installed. For Windows, see [Local installation](docs/LOCAL_INSTALL.md).

Optional GIS dependencies are not installed by default:

```bash
bash scripts/install-local.sh --gis
```

## Local scientific knowledge index

The index is stored by default at `.geologia/knowledge.sqlite3`. Ali's analysis plans retrieve up to three matching local text chunks with source and license metadata. Retrieval is deterministic and does not call a model.

Index only UTF-8 `.txt`, `.md`, `.csv`, or `.json` text that you are legally allowed to process and have explicitly reviewed. Example:

```bash
geologia-knowledge ./references/open_hydrogeology.md \\
  --source-id open-hydro-001 \\
  --title "Open hydrogeology reference" \\
  --language en \\
  --license-name "CC BY 4.0" \\
  --license-status open_license \\
  --reviewed-by "YOUR_REVIEWER" \\
  --review-date 2026-11-21 \\
  --source-url https://example.org/reference
```

The institution catalog and Crossref candidate inbox are discovery/metadata only. They are not automatically downloaded or indexed, and the approved bibliography does not itself contain full-text knowledge.

## Developer quick start

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

## Install on phone or desktop

When served from HTTPS or localhost, supported browsers can install GEOLOGIA as a standalone web app or add it to the home screen.

This provides an installable web app shell, **not a native APK/MSI/DMG/AppImage**. Offline caching covers the static interface only; API operations require the local server. The map still depends on external Leaflet assets and map tiles and is not guaranteed to work offline. See [PWA installation and limits](docs/INSTALLABLE_APP.md).

## API

- `GET /api/v1/crs/inspect?crs=EPSG:4326` (requires optional `gis` extra)
- `POST /api/v1/datasets/{dataset_id}/reproject` with `{"target_crs":"EPSG:3857"}` (GeoJSON only; creates a derived dataset and preserves the source)
- `GET /api/v1/agent/status` (local agent identity, capabilities, and model/engine limits)
- `GET /api/v1/knowledge/status`
- `GET /api/v1/knowledge/search?q=groundwater&limit=5` (local reviewed text only)
- `GET /health`
- `GET /api/v1/engines` and `GET /api/v1/engines/{engine_id}`
- `GET /api/v1/projects`, `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/datasets`
- `GET /api/v1/projects/{project_id}/datasets`
- `GET /api/v1/datasets/{dataset_id}`
- `POST /api/v1/datasets/{dataset_id}/inspect` (GeoJSON/CSV structural metrics only)
- `POST /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/jobs/{job_id}`

## Engineering audit

See [the full-history engineering audit](docs/ENGINEERING_AUDIT.md) for verified fixes, known blockers, and the ordered remediation roadmap.

## Scientific and security honesty

The local knowledge index starts empty and only contains documents explicitly ingested after license review. The source catalog is not an ingested corpus. The 30 engine registry entries are catalog references, not integrations. Health reports `engines_integrated: 0` and `execution_enabled: false`. Jobs remain `planned`; no geologic interpretation, groundwater yield, mineral probability, or drilling recommendation is produced.

Do not expose this development API publicly. The launchers bind to loopback only. Remote deployment still requires authentication, authorization, quotas, private storage, isolated workers, and monitoring. Raster processing, general vector transformations, raster reprojection, worker isolation, and scientific engine adapters are not implemented. GeoJSON CRS inspection and vector reprojection are available through the optional `gis` extra. CRS metadata supplied by uploaders is treated as a declaration and is not inferred from coordinates. See [Phase 5](docs/PHASE5.md).

Development baseline: Python 3.14.x. Python 3.12 and 3.15 are included in CI compatibility coverage. Python 3.15 CI success does not imply Termux/Android compatibility. See [Phase 1](docs/PHASE1.md), [Phase 2](docs/PHASE2.md), [Phase 3](docs/PHASE3.md), and [Phase 4](docs/PHASE4.md).

## License

Original GEOLOGIA platform code is licensed under **AGPL-3.0-only**; see [LICENSE](LICENSE). Third-party engine licenses are separate and must be verified before each adapter is distributed. The registry's `license_status: unverified` is deliberate until that review is complete.
