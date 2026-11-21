# Validation and repository status

Updated: 2026-11-21

## Source on GitHub

The runnable application source is committed to the default branch `main`.

## Latest automated validation

GitHub Actions run #27 for commit `f959a7de0e35863f7a7befc868df9e50ee717347` completed successfully:

- Python 3.12: passed
- Python 3.14: passed
- Experimental Python 3.15: passed
- JavaScript syntax check: passed
- Ruff: passed
- `compileall`: passed
- `pytest`: passed

Run: https://github.com/tibatechapp-ship-it/geologia/actions/runs/44915420794

The next commits add stricter GeoJSON geometry validation and regression tests. Their CI result must be checked separately; the run above does not validate those later commits.

## Implemented

- Phase 1: FastAPI, SQLite projects/jobs, deterministic plan records.
- Phase 2: bounded streaming dataset intake, generated storage paths, SHA-256, structural GeoJSON validation.
- Phase 3: chief-agent plan identity, deterministic specialist-role routing, dataset-role readiness checks.
- Phase 4: bilingual Arabic RTL / English LTR frontend for projects, dataset intake, and plan display.
- Phase 5: CRS inspection and GeoJSON reprojection using optional pyproj; derived datasets are stored without overwriting source datasets.
- 30 engine catalog cards, all `planned` and `license_status: unverified`.
- Root `LICENSE`: GNU AGPL v3.

## Explicitly not verified or not implemented

- CI runs on GitHub-hosted Ubuntu; **Termux/Android itself has not been tested for this repository**.
- No production deployment or production authentication/authorization; keep the API bound to localhost.
- No scientific engine is integrated or certified; `engines_integrated` remains 0.
- GeoPackage, GeoTIFF, and LAS are stored only. CSV receives structural inspection; it is not scientifically interpreted.
- No worker queue, isolated engine containers, or LLM provider integration.
- Engine license reviews are pending individually; the platform license does not relicense third-party engines.
- The GeoJSON validator checks structure and coordinate constraints, not complete OGC conformance, topology, or scientific validity.
