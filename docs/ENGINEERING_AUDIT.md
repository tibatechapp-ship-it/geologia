# GEOLOGIA Engineering Audit

Audit date: 2026-11-21
Audited branch: `main`
Purpose: distinguish implemented behavior from claims, record defects found during the full-history review, and define safe next steps.

## Executive status

GEOLOGIA is an early-stage local geoscience workspace and planning API. It is not yet a production platform, an AI reasoning system, or a scientific analysis suite. The current application can create projects, store bounded uploads, inspect a subset of vector/table structure, record deterministic plans, and perform GeoJSON coordinate reprojection when the optional GIS dependency is installed.

The engine registry is a catalogue only. All 30 entries remain `planned` and `license_status: unverified`. The API reports zero integrated engines and keeps execution disabled.

## Development history reviewed

- Phase 1: FastAPI application, SQLite persistence, projects, and plan records.
- Phase 2: bounded streaming uploads, generated storage names, SHA-256, and GeoJSON intake checks.
- Phase 3: deterministic domain routing, specialist role labels, and required-input role coverage.
- Phase 4: bilingual Arabic RTL / English LTR web workspace.
- Phase 5: CRS inspection and GeoJSON reprojection through optional pyproj.
- Python support was raised to 3.12+, Pydantic was aligned to v2 for the modern FastAPI dependency range, and CI now covers Python 3.12, 3.14, and 3.15.
- GitHub Actions were upgraded to current major releases to avoid the runner's Node 20 deprecation path.

## Defects found and addressed in this review

1. GeoJSON coordinate validation accepted malformed geometry nesting, short LineStrings, unclosed polygon rings, and non-finite or non-numeric extra ordinates.
   - Fixed with geometry-specific structure checks and full-dimensional finite position validation.
   - Added regression tests for malformed points, multipoints, lines, polygons, Z values, and ring closure.
2. JSON parsing accepted non-standard numeric constants such as NaN and Infinity, and floating-point overflow such as 1e999.
   - Fixed with strict JSON parsing for uploaded and subsequently read GeoJSON.
   - Added API regression tests.
3. Project names, job requests, and dataset names could pass minimum-length checks while containing only whitespace.
   - Fixed by trimming and validating normalized values.
   - Added regression tests.
4. FastAPI startup used the deprecated `on_event` lifecycle API.
   - Replaced with an application lifespan context.
5. The development CLI could bind to a non-loopback interface even though the application has no authentication.
   - The CLI now rejects non-loopback bind addresses, and regression tests cover both rejection and valid localhost startup. Direct ASGI deployment can still bypass the CLI guard and remains unsafe without production controls.
6. The readiness report used `data_complete` for a check that only compared user-supplied role tags.
   - Replaced it with `required_roles_present` and explicit `content_validation: not_performed`; execution remains blocked.
7. Phase 5 documentation incorrectly said derived reprojection output was not saved.
   - Corrected to describe the actual behavior: a new derived dataset is stored, while the source remains unchanged.
8. Validation documentation referenced an obsolete commit and obsolete Python matrix.
   - Refreshed the recorded evidence and explicit limitations.

## Verified by GitHub Actions

The latest fully green code validation is [Run #51](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44916560490), on commit `41609ccfac282f32d702436a8ca4f1f54570f658`:
- Python 3.12, 3.14, and 3.15 all passed.
- Editable install with development and GIS extras passed.
- JavaScript syntax check, Ruff, compileall, and pytest passed.
- The run reported 32 passing tests per Python version.
- One upstream deprecation warning remains in Starlette's TestClient use of AnyIO's deprecated `BlockingPortal` alias. No application startup deprecation or Node 20 action warning remains.

This run includes the strict JSON handling, normalized-input validation, readiness semantics, lifespan modernization, current GitHub Actions, and engineering-audit documentation.

## Known blockers — do not represent as production-ready

### Security and operations
- No user authentication, authorization, tenant isolation, or project ownership model.
- The bundled development CLI now rejects non-loopback bind addresses. Running the ASGI app through another server can bypass this guard; public deployment remains unsafe until authentication and operational controls exist.
- No rate limiting, per-user quotas, upload concurrency limits, request timeouts, or abuse monitoring.
- No malware scanning or sandbox for uploaded content. The current application does not execute uploaded code or scientific tools.
- No production secret management, audit log, backup/restore procedure, retention policy, or deployment hardening.
- SQLite is suitable for the local foundation, not yet a validated multi-user production database.
- No formal schema migration framework; the current store contains an inline compatibility migration.

### Scientific and geospatial correctness
- No scientific engine is integrated, certified, or executed.
- A role tag is user-supplied metadata, not proof that the file contains the required scientific data.
- GeoJSON validation is structural, not a complete OGC conformance suite, topology validator, or scientific-quality review.
- CRS values supplied in upload headers are trusted declarations; they are not inferred from coordinate values.
- Reprojection supports GeoJSON vector geometry only. Raster GeoTIFF and GeoPackage are accepted for storage but not processed.
- Z and additional ordinates are preserved, not transformed using a vertical CRS.
- CSV inspection reports table structure only; it does not validate domain-specific units, schema, or measurements.
- No provenance model yet records software versions, exact transformation parameters, input snapshots, and reproducible run artifacts for scientific computations.

### Frontend and test coverage
- CI checks JavaScript syntax but does not run browser-based end-to-end tests.
- The map view depends on externally hosted map assets/tiles; local data storage does not imply a fully offline map experience.
- No accessibility audit, cross-browser/mobile interaction suite, or performance budget has been completed.

### Platform support
- GitHub-hosted Linux CI is not evidence of compatibility with Android/Termux.
- Termux installation, pyproj native dependencies, file permissions, storage paths, and actual device runtime remain unverified for this repository.

## Ordered next work

1. Close the current CI run and fix every lint, test, packaging, or runtime failure before adding features.
2. Add browser-level tests for project creation, upload, language switching, map rendering, inspection, and reprojection.
3. Add database migration tests, backup/restore checks, orphan-file cleanup, and concurrency tests.
4. Harden the local API boundary and define an explicit production security architecture before any remote deployment.
5. Build a typed data-validation layer for GeoJSON, CSV, GeoPackage, GeoTIFF, and LAS; never infer scientific validity from filenames or role tags.
6. Introduce a durable job queue and isolated workers only after job state transitions, cancellation, retries, timeouts, resource limits, and provenance are specified and tested.
7. Integrate scientific engines one at a time, with pinned versions, license review, published benchmark datasets, known-answer tests, uncertainty reporting, and independent scientific review.
8. Verify Termux separately on the user's device; record exact commands, package versions, and outputs.

## Acceptance rule

A phase is complete only when its implementation, regression tests, documentation, CI evidence, and explicitly stated limitations agree. A green syntax check or a passing unit-test suite alone does not certify scientific correctness or production readiness.
