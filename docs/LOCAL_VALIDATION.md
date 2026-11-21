# Validation and repository status

Updated: 2026-11-21

## Source on GitHub

The runnable application source is committed to the default branch `main`.

## Latest code validation

GitHub Actions run #51 for commit `41609ccfac282f32d702436a8ca4f1f54570f658` completed successfully:

- Python 3.12: passed
- Python 3.14: passed
- Python 3.15: passed
- JavaScript syntax check: passed
- Ruff: passed
- `compileall`: passed
- `pytest`: 32 passed on each Python version

One upstream Starlette TestClient deprecation warning remains: AnyIO's `BlockingPortal` alias is deprecated. Application startup no longer uses FastAPI's deprecated `on_event` API. Current GitHub Actions no longer emit the Node 20 deprecation warning.

Run: https://github.com/tibatechapp-ship-it/geologia/actions/runs/44916560490

## Implemented

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
