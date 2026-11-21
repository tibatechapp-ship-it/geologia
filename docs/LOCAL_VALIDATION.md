# Validation and repository status

Updated: 2026-11-21

## Source on GitHub

The application source is now committed to the default branch `main`; it is no longer only a local bootstrap package.

Latest verified source commit: `525c4c1334f954178ce989fb0b832cd4e85fdcb6`.

## Automated validation

GitHub Actions run #7 for commit `525c4c1334f954178ce989fb0b832cd4e85fdcb6` completed successfully:

- Python 3.10: passed
- Python 3.12: passed
- Ruff: passed
- `compileall`: passed
- `pytest`: 9 passed in each matrix job

Run: https://github.com/tibatechapp-ship-it/geologia/actions/runs/44912938806

Earlier runs failed during development due to Ruff findings and incomplete phase wiring. Those failures were corrected in later commits; the latest run above is green.

## Implemented

- Phase 1: FastAPI, SQLite projects/jobs, deterministic plan records.
- Phase 2: bounded streaming dataset intake, safe generated storage path, SHA-256, structural GeoJSON validation.
- Phase 3: named chief-agent plan, deterministic specialist role assignment, dataset-role readiness check.
- 30 engine catalog cards, all `planned` and `license_status: unverified`.

## Explicitly not verified or not implemented

- The workflow runs on GitHub-hosted Ubuntu; **Termux/Android itself has not been tested in this session**.
- No deployment or live production server.
- No authentication/authorization yet; keep the API bound to localhost.
- No scientific engine is integrated or certified; `engines_integrated` remains 0.
- GeoPackage, GeoTIFF, CSV, and LAS are stored only; no spatial interpretation or raster/vector processing.
- No frontend yet.
- Engine license reviews are pending individually; the platform license does not relicense third-party engines.
