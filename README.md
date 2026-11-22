# GEOLOGIA | جيولوجيا

**Bilingual open-source geoscience platform** — engineering foundation, not a certified scientific analysis system.

The local, model-independent chief geoscience agent is **Ali Algomori (علي الگوموري)**. Its current routing and planning core is deterministic and evidence-backed; it is not a trained neural model or a substitute for scientific engines. The current API provides a local workspace for projects, datasets, and durable analysis-plan records. It does not execute scientific engines.

## Current source scope

- FastAPI application and health endpoint.
- SQLite-backed projects, jobs, and dataset metadata.
- Streaming dataset intake with a 50 MiB limit, filename sanitization, SHA-256, and generated storage paths.
- Structural GeoJSON validation and deterministic inspection; CSV structural inspection. Neither produces geological interpretation.
- Frozen v1 DEM reference-coverage sufficiency evaluator, block-wise DEM/AOI footprint and nodata-mask inspection, and project-scoped persisted assessments with upload-integrity checks and a per-project tamper-evident hash chain; it evaluates coverage only, not DEM accuracy or product readiness. See [coverage audit trail](docs/DEM_COVERAGE_AUDIT_TRAIL_V1.md).
- Role-tagged datasets and a missing-input readiness report in every analysis plan.
- Bilingual Arabic RTL / English LTR workspace with readable plan cards, specialist routing evidence, missing-input readiness, and locally retrieved references with license metadata and safe HTTPS citations.
- Ali Algomori model-independent agent: deterministic Arabic/English/Russian/Chinese intent routing, visible source-script keyword evidence, heuristic confidence, and specialist-role routing.
- Curated four-language routing regression suite with exact-domain and abstention checks; see [routing evaluation](docs/ALI_AGENT_ROUTING_EVALUATION.md).
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

The bootstrap may install Rust and native build tools because some Python dependencies need compilation on Android. No AI model weights are installed. It also creates a `~/.shortcuts/GEOLOGIA` launcher for the Termux:Widget companion app; add that shortcut to your home screen for one-tap startup. Stop the background server with `bash scripts/termux-widget-stop.sh`. For Windows, see [Local installation](docs/LOCAL_INSTALL.md).

Optional GIS and heavy geospatial format parser dependencies are not installed by default. For parser-backed metadata inspection, install the optional extra:

```bash
python -m pip install -e ".[formats]"
```

See [format inspection limits](docs/FORMAT_INSPECTION.md).

Optional GIS dependencies are not installed by default:

```bash
bash scripts/install-local.sh --gis
```

## Local scientific knowledge index

The index is stored by default at `.geologia/knowledge.sqlite3`. Ali's analysis plans retrieve up to three matching local text chunks with source and license metadata. Retrieval is deterministic and does not call a model.

On the first knowledge status/search request, GEOLOGIA automatically indexes **24 original multilingual core checklists** across groundwater, GIS/CRS, 3D geology, seismology, remote sensing, and mineral exploration. These are GEOLOGIA-authored process notes, not copied publications. You can also run `geologia-knowledge --seed-core` explicitly. This core pack is local and model-free. Chinese queries use deterministic bigram indexing in SQLite FTS; no embedding model is required.

Index locally supplied UTF-8 `.txt`, `.md`, `.csv`, or `.json` text, or text-based `.pdf` files that you are legally allowed to process and have explicitly reviewed. The installer includes the lightweight `pypdf` extra. PDF indexing is limited to 20 MiB and 500 pages, preserves PDF page locators, and does not perform OCR on scanned-image PDFs. Example:

```bash
geologia-knowledge ./references/open_hydrogeology.md \
  --source-id open-hydro-001 \
  --title "Open hydrogeology reference" \
  --language en \
  --license-name "CC BY 4.0" \
  --license-status open_license \
  --reviewed-by "YOUR_REVIEWER" \
  --review-date 2026-11-21 \
  --source-url https://example.org/reference
```

The institution catalog and Crossref candidate inbox are discovery/metadata only. They are not automatically downloaded or indexed, and the approved bibliography does not itself contain full-text knowledge. The external research corpus remains empty until an operator reviews and explicitly ingests lawful source text. The scheduled Crossref inbox now searches English, Arabic, Russian, and Chinese query groups and preserves the publication language when available; every candidate remains unapproved metadata.

## Developer quick start

```bash
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,gis,pdf]"
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

## Portable desktop binaries

The [GEOLOGIA Desktop Build workflow](https://github.com/tibatechapp-ship-it/geologia/actions/workflows/desktop-build.yml) builds one-file executables for Windows, Linux, and macOS. After a successful workflow run, download the matching `geologia-desktop-<OS>-<arch>` artifact from the run's **Artifacts** section. Artifacts are retained for 30 days.

The executable starts the API on `127.0.0.1`, opens the local workspace, and stores persistent files under `~/.geologia`. It includes no AI model weights. These are unsigned portable binaries, not MSI/DMG/AppImage installers; Windows SmartScreen or macOS Gatekeeper may display a warning. Android remains a Termux + browser-installed PWA workflow; no native APK is built.

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
- `GET /api/v1/datasets/{dataset_id}/provenance` (project-wide hash-chain integrity, dataset events only)
- `POST /api/v1/datasets/{dataset_id}/inspect` (bounded CSV/GeoJSON; optional GeoPackage/GeoTIFF/LAS metadata inspection)
- `POST /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/projects/{project_id}/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/events` (append-only lifecycle event history)
- `POST /api/v1/jobs/{job_id}/cancel` (immediate cancellation before execution; cooperative request for running jobs)
- `POST /api/v1/datasets/{dataset_id}/validate` and `GET /api/v1/datasets/{dataset_id}/validation` (structural/schema checks only)

## Engineering audit

See [the full-history engineering audit](docs/ENGINEERING_AUDIT.md) for verified fixes, known blockers, and the ordered remediation roadmap. See the [job lifecycle contract](docs/JOB_LIFECYCLE.md), [worker isolation architecture](docs/WORKER_ARCHITECTURE.md), and [security threat model](docs/SECURITY_THREAT_MODEL.md) for the execution safety gates.

## Scientific and security honesty

The index includes the 24 original GEOLOGIA core notes after first use. External full-text research remains empty until explicitly ingested after license review; the source catalog is not an ingested corpus. See the [international source/license matrix](docs/ALI_SOURCE_LICENSE_MATRIX.md). The 30 engine registry entries are catalog references, not integrations. Health reports `engines_integrated: 0` and `execution_enabled: false`. Job records default to `planned`; the durable state machine and cancellation/event APIs are infrastructure only and do not start a worker or execute an engine. No geologic interpretation, groundwater yield, mineral probability, or drilling recommendation is produced.

Do not expose this development API publicly. The launchers bind to loopback only. Remote deployment still requires authentication, authorization, quotas, private storage, isolated workers, and monitoring. Raster processing, general vector transformations, raster reprojection, worker isolation, and scientific engine adapters are not implemented. GeoJSON CRS inspection and vector reprojection are available through the optional `gis` extra. CRS metadata supplied by uploaders is treated as a declaration and is not inferred from coordinates. See [Phase 5](docs/PHASE5.md).

Development baseline: Python 3.14.x. Python 3.12 and 3.15 are included in CI compatibility coverage. Python 3.15 CI success does not imply Termux/Android compatibility. See [Phase 1](docs/PHASE1.md), [Phase 2](docs/PHASE2.md), [Phase 3](docs/PHASE3.md), and [Phase 4](docs/PHASE4.md).

## License

Original GEOLOGIA platform code is licensed under **AGPL-3.0-only**; see [LICENSE](LICENSE). Third-party engine licenses are separate and must be verified before each adapter is distributed. The registry's `license_status: unverified` is deliberate until that review is complete.
