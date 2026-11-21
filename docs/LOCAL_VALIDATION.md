# Validation and repository status

Updated: 2026-11-21

Current implementation branches: `phase-6-browser-e2e` and `phase-7-data-validation`. Phase 7 review: [PR #4](https://github.com/tibatechapp-ship-it/geologia/pull/4).

## Source on GitHub

The phase 6 browser-test implementation is on branch `phase-6-browser-e2e`, pending review before merging to `main`.

## Latest full validation

GitHub Actions run #87 for commit `f048828256e403ba8e925a83eae717364ac5d280` completed successfully:

- Python 3.12: 43 passed, 1 optional browser-directory skip, 1 upstream warning
- Python 3.14: 43 passed, 1 optional browser-directory skip, 1 upstream warning
- Python 3.15: 43 passed, 1 optional browser-directory skip, 1 upstream warning
- JavaScript syntax check: passed
- Ruff: passed
- `compileall`: passed
- Chromium/Playwright: 2 browser end-to-end tests passed

The browser tests launch a real Uvicorn process with temporary SQLite and upload storage. They cover:
- Loading the bilingual UI and verifying API health.
- Graceful map fallback when the externally hosted Leaflet CDN is unavailable.
- Project creation through the browser.
- CSV upload and structural inspection, including row and column metrics.
- Analysis-plan creation while confirming execution remains disabled and scientific content validation is not claimed.
- Arabic RTL to English LTR switching while preserving selected project.
- Rejection of malformed CSV during inspection.
- No uncaught browser JavaScript exceptions in the main user journey.

Run: https://github.com/tibatechapp-ship-it/geologia/actions/runs/44918428819

## Implemented

- Phase 7 foundation: versioned CSV/GeoJSON validation profiles, persisted reports, and a bilingual UI validation action. Details: [DATA_VALIDATION.md](DATA_VALIDATION.md).

- Phase 1: FastAPI, SQLite projects/jobs, deterministic plan records.
- Phase 2: bounded streaming dataset intake, generated storage paths, SHA-256, strict JSON and structural GeoJSON validation.
- Phase 3: deterministic domain routing, specialist role labels, and required-role coverage reporting that explicitly does not claim content validation.
- Phase 4: bilingual Arabic RTL / English LTR frontend for projects, dataset intake, and plan display.
- Phase 5: CRS inspection and GeoJSON reprojection using optional pyproj; derived datasets are stored without overwriting source datasets.
- Phase 6: real Chromium/Playwright end-to-end coverage for key workspace flows.
- Phase 7 foundation: versioned CSV/GeoJSON validation profiles, persisted reports, and a bilingual UI validation action. Details: [DATA_VALIDATION.md](DATA_VALIDATION.md).
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
- Successful Leaflet rendering, map interaction, CRS reprojection through the browser, accessibility, and mobile browser behavior still require end-to-end coverage.
- Role-specific schema validation currently covers only groundwater-level CSV and AOI GeoJSON; it does not establish scientific validity.
