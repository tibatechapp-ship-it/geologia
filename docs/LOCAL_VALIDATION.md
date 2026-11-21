# Validation and repository status

Updated: 2026-11-21

## Source on GitHub

The runnable application source is committed to the default branch `main`.

Latest application commit validated by CI: `958f9ec95aa52d166009115ebde38a423d5ebea1`.

## Automated validation

GitHub Actions run #10 for commit `958f9ec95aa52d166009115ebde38a423d5ebea1` completed successfully:

- Python 3.10: passed
- Python 3.12: passed
- Ruff: passed
- `compileall`: passed
- `pytest`: 10 passed in each matrix job

Run: https://github.com/tibatechapp-ship-it/geologia/actions/runs/44913426245

Earlier runs failed during development due to lint findings, incomplete phase wiring, and a frontend smoke-test assertion. Those issues were corrected in later commits; the latest run above is green.

## Implemented

- Phase 1: FastAPI, SQLite projects/jobs, deterministic plan records.
- Phase 2: bounded streaming dataset intake, generated storage paths, SHA-256, structural GeoJSON validation.
- Phase 3: chief-agent plan identity, deterministic specialist-role routing, dataset-role readiness checks.
- Phase 4: bilingual Arabic RTL / English LTR frontend for projects, dataset intake, and plan display.
- 30 engine catalog cards, all `planned` and `license_status: unverified`.
- Root `LICENSE`: full GNU AGPL v3 text; GitHub recognizes AGPL-3.0.

## Explicitly not verified or not implemented

- CI runs on GitHub-hosted Ubuntu; **Termux/Android itself has not been tested in this session**.
- No production deployment.
- No authentication/authorization yet; keep the API bound to localhost.
- No scientific engine is integrated or certified; `engines_integrated` remains 0.
- GeoPackage, GeoTIFF, CSV, and LAS are stored only; no spatial interpretation or raster/vector processing.
- No worker queue, isolated engine containers, or LLM provider integration.
- Engine license reviews are pending individually; the platform license does not relicense third-party engines.
