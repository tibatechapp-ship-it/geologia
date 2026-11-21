# Validation and repository status

Updated: 2026-11-21

## Source on GitHub

The runnable application source is committed to the default branch `main`.

## Latest main-branch validation

GitHub Actions run #54 for commit `29ba9f8dddef22f95c1b2049c9272ae26a2d25a5` completed successfully:

- Python 3.12: passed
- Python 3.14: passed
- Python 3.15: passed
- Editable install with development and GIS extras: passed
- JavaScript syntax check: passed
- Ruff: passed
- `compileall`: passed
- `pytest`: 32 passed on each Python version

One upstream Starlette TestClient deprecation warning remains: AnyIO's `BlockingPortal` alias is deprecated. Application startup no longer uses FastAPI's deprecated `on_event` API.

Run: https://github.com/tibatechapp-ship-it/geologia/actions/runs/44916671711

## Browser end-to-end status

Draft [PR #7](https://github.com/tibatechapp-ship-it/geologia/pull/7) adds a dedicated Chromium/Playwright CI job with browser scenarios for:
- Project creation and Arabic/English language switching.
- GeoJSON upload and structural inspection through the visible interface.
- Analysis-plan creation while asserting that no scientific results were computed.

These tests are proposed on the PR branch and are **not yet verified or merged**. The PR must remain unmerged until the Chromium job and existing Python matrix pass. Map rendering and reprojection browser scenarios remain follow-up coverage.

## Implemented on main

- Phase 1: FastAPI, SQLite projects/jobs, deterministic plan records.
- Phase 2: bounded streaming dataset intake, generated storage paths, SHA-256, strict JSON and structural GeoJSON validation.
- Phase 3: deterministic domain routing, specialist role labels, and required-role coverage reporting that explicitly does not claim content validation.
- Phase 4: bilingual Arabic RTL / English LTR frontend for projects, dataset intake, and plan display.
- Phase 5: CRS inspection and GeoJSON reprojection using optional pyproj; derived datasets are stored without overwriting source datasets.
- Development CLI rejects non-loopback bind addresses.
- 30 engine catalog cards, all `planned` and `license_status: unverified`.
- Root `LICENSE`: GNU AGPL v3.
- Full-history findings and remaining blockers: [ENGINEERING_AUDIT.md](ENGINEERING_AUDIT.md).

## Explicitly not verified or not implemented

- CI runs on GitHub-hosted Ubuntu; **Termux/Android itself has not been tested for this repository**.
- No production deployment or production authentication/authorization; keep the API bound to localhost.
- No scientific engine is integrated or certified; `engines_integrated` remains 0.
- GeoPackage, GeoTIFF, and LAS are stored only. CSV receives structural inspection; it is not scientifically interpreted.
- No worker queue, isolated engine containers, or LLM provider integration.
- Engine license reviews are pending individually; the platform license does not relicense third-party engines.
- GeoJSON checks are structural only, not complete OGC conformance, topology, or scientific validation.


## Upload and CRS hardening — draft PR #7

GitHub Actions run [#44926170500](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44926170500) passed:
- Python 3.12, 3.14, and 3.15.
- Ruff, compileall, JavaScript syntax validation, and pytest.
- Playwright Chromium browser end-to-end tests.

Additional API regression coverage verifies:
- Default WGS84 GeoJSON rejects coordinates outside longitude/latitude bounds.
- Explicit CRS values are parsed and canonicalized; coordinates are transformed to WGS84 for plausibility checks.
- Unknown CRS declarations and obvious CRS/coordinate mismatches are rejected.
- Malformed CSV quoting is rejected at upload; ragged rows are recorded as warnings.
- Duplicate JSON object keys and oversized numeric coordinate values are rejected.

These checks are structural and plausibility checks only. They do not infer a missing CRS, establish scientific validity, or validate GeoPackage, GeoTIFF, or LAS contents.

## Draft PR #7 — specialized file inspection and provenance

The branch adds optional `formats` dependencies and parser-backed inspection for GeoPackage, GeoTIFF, and LAS. Upload remains a bounded storage operation; explicit `POST /api/v1/datasets/{id}/inspect` performs format-specific inspection. Reports include parser metadata and state that scientific interpretation and vertical-datum verification were not performed.

The branch includes real parser-generated fixtures, malformed/truncated-file cases, file/raster/point sample limits, and a known-answer CRS transformation with declared tolerance. Dataset provenance records the source SHA-256 and declared CRS; inspection records parser/Python/GEOLOGIA versions and UTC time; reprojection records source hash, source/target CRS, axis order, pyproj version, operation description, and reported accuracy. A project-scoped SHA-256 event chain is exposed at `GET /api/v1/datasets/{id}/provenance`; it is tamper-evident, not tamper-proof.

CI for the new format-validation job is pending. No scientific engine is integrated, and these checks are not a scientific certification.


## Scientific reference controls — follow-up

See [SCIENTIFIC_REFERENCE_REVIEW.md](SCIENTIFIC_REFERENCE_REVIEW.md). Added tests independently compute EPSG:3857 coordinates from the published formula and recognize declared EGM96 vertical CRS metadata through compound EPSG:9707. The latest changes require a fresh CI run; no green status is claimed until it completes.


## Source citation UI — pending current-head validation

The workspace has an expandable bilingual source citation form for dataset uploads, displays source citation status in the dataset list, and sends optional source metadata headers to the API. Playwright supplies a source URL, citation, and access date and asserts the citation/status are visible. [CI run #44932691048](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44932691048) passed all five jobs on commit `f39fafb`: Python 3.12/3.14/3.15, parser-backed format tests (16 passed), and browser E2E (3 passed). Two upstream warnings were reported; no test failures.
