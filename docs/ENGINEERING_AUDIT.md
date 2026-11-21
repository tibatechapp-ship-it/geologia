# GEOLOGIA Engineering Audit

Audit date: 2026-11-21
Audited branch: `phase-6-browser-e2e-20261121` (draft PR #7)
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
- Python support was raised to 3.12+, Pydantic was aligned to v2 for the modern FastAPI dependency range, and CI covers Python 3.12, 3.14, and 3.15.
- GitHub Actions were upgraded to current major releases to avoid the runner's Node 20 deprecation path.

## Defects found and addressed in this review

9. GeoJSON upload accepted CRS header text without validating the CRS or checking coordinate plausibility. Explicit horizontal CRS declarations are now canonicalized through pyproj and transformed to WGS84 for Earth-bound checks; default GeoJSON WGS84 coordinates are range-checked. This does not infer CRS or prove scientific correctness.
10. CSV upload stored malformed quoting and invalid UTF-8 until a later inspection request. Upload now performs a streaming structural parse, rejects malformed CSV, and records ragged-row warnings without pretending to validate scientific schema or units.
11. JSON ingestion accepted duplicate object keys and deeply nested input could raise an unhandled recursion error. The parser now rejects duplicate keys and converts excessive nesting into a validation error. GeoJSON coordinate bounds are accumulated incrementally, and oversized integer ordinates are rejected safely.

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

The latest fully green main-branch validation is [Run #54](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44916671711), on commit `29ba9f8dddef22f95c1b2049c9272ae26a2d25a5`:
- Python 3.12, 3.14, and 3.15 all passed.
- Editable install with development and GIS extras passed.
- JavaScript syntax check, Ruff, compileall, and pytest passed.
- The run reported 32 passing tests per Python version.
- One upstream deprecation warning remains in Starlette's TestClient use of AnyIO's deprecated `BlockingPortal` alias. This is a warning, not a failing test.

This run validates the current main-branch code, including strict JSON handling, normalized-input validation, readiness semantics, lifespan modernization, and the CLI loopback guard. It does not include browser automation.

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
- CRS plausibility checks only detect some obvious coordinate/CRS mismatches. They cannot reliably infer a missing CRS or detect every wrong but numerically plausible declaration; non-GeoJSON formats still do not receive content-level CRS checks.
- No scientific engine is integrated, certified, or executed.
- A role tag is user-supplied metadata, not proof that the file contains the required scientific data.
- GeoJSON validation is structural, not a complete OGC conformance suite, topology validator, or scientific-quality review.
- GeoJSON upload now canonicalizes an explicitly declared horizontal CRS and checks that transformed coordinates fall within Earth longitude/latitude bounds; this is a plausibility check, not CRS inference or scientific validation. When no CRS header is supplied, GeoJSON is treated as WGS84 and checked against longitude/latitude bounds. Other formats still retain user-declared CRS metadata without content-level CRS verification.
- GeoJSON reprojection remains the only coordinate transformation. Draft PR #7 adds optional parser-backed structural inspection for GeoPackage, GeoTIFF, and LAS, including bounded layer/raster/point samples; these changes are not merged to `main` and do not perform geological interpretation.
- Z and additional ordinates are preserved, not transformed using a vertical CRS.
- CSV upload now rejects invalid UTF-8 and malformed quoting, and records header/row structure plus ragged-row warnings. CSV checks do not validate domain-specific units, schema, or measurements.
- PR #7 now proposes an initial provenance ledger: dataset SHA-256/source metadata, parser and Python versions, inspection timestamp, transformation parameters, pyproj version, and a project-scoped SHA-256 event chain. This is tamper-evident within the database, not tamper-proof; external anchoring, full input snapshots, and scientific run artifacts remain future work.

### Frontend and test coverage
- Main currently has API-level frontend checks and JavaScript syntax validation, but no merged browser-based end-to-end suite.
- Draft PR #7 adds Playwright coverage for project creation, language switching, GeoJSON upload/inspection, and plan-only behavior. The browser suite previously passed in run #44925167509. The upload/CRS hardening and regression tests passed all four jobs in run #44926170500.
- The map view depends on externally hosted map assets/tiles; local data storage does not imply a fully offline map experience.
- No accessibility audit, cross-browser/mobile interaction suite, or performance budget has been completed.

### Platform support
- GitHub-hosted Linux CI is not evidence of compatibility with Android/Termux.
- Termux installation, pyproj native dependencies, file permissions, storage paths, and actual device runtime remain unverified for this repository.

## Ordered next work

1. Extend browser coverage to map rendering and reprojection interaction after the current API-level upload validation changes pass CI.
2. Add database migration tests, backup/restore checks, orphan-file cleanup, and concurrency tests.
3. Harden the local API boundary and define an explicit production security architecture before any remote deployment.
4. Complete review and CI for the optional GeoPackage/GeoTIFF/LAS inspectors in draft PR #7, add malformed internal-record fixtures and independent reference datasets, and verify resource limits against adversarial samples; never infer scientific validity from filenames or role tags.
5. Introduce a durable job queue and isolated workers only after job state transitions, cancellation, retries, timeouts, resource limits, and provenance are specified and tested.
6. Integrate scientific engines one at a time, with pinned versions, license review, published benchmark datasets, known-answer tests, uncertainty reporting, and independent scientific review.
7. Verify Termux separately on the user's device; record exact commands, package versions, and outputs.

## Acceptance rule

A phase is complete only when its implementation, regression tests, documentation, CI evidence, and explicitly stated limitations agree. A green syntax check or a passing unit-test suite alone does not certify scientific correctness or production readiness.

## Draft PR #7 — format inspection and provenance

The current PR branch adds optional parser-backed inspectors for GeoPackage (SQLite integrity, required metadata tables, layer metadata and bounded feature samples), GeoTIFF (dimensions, CRS, transform, units, nodata, metadata, block-size guard and bounded sample read), and uncompressed LAS (header/point-record extent checks, scales/offsets, CRS/VLR metadata and bounded point sample). Inspection reports explicitly set scientific validation to false and do not verify vertical datums.

The branch also adds a known-answer EPSG:4326 ↔ EPSG:3857 transformation fixture with tolerances; records source SHA-256, declared CRS, parser/Python/GEOLOGIA versions and inspection time; records pyproj operation details for reprojection; and appends dataset ingestion/inspection/derivation events to a project-scoped SHA-256 chain. The chain detects accidental or unsophisticated modification but is not an external immutable audit system.

This work remains in draft PR #7. GitHub Actions run [#44931186563](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44931186563) completed successfully on commit `dba5a29`: Python 3.12/3.14/3.15, browser end-to-end, and parser-backed format validation all passed. The specialized format test module reported 14 passed. This is software/file-structure evidence only, not scientific certification.


## Scientific reference review — follow-up

A dedicated [scientific reference review](SCIENTIFIC_REFERENCE_REVIEW.md) records authoritative EPSG/IOGP/OGC sources, synthetic control-point provenance, the independent EPSG:3857 equation oracle, and an EPSG:9707/EPSG:5773 vertical CRS metadata control. The vertical inspector now exposes declared vertical CRS components (authority/code, datum name, units, axis direction) and bounded vertical metadata values. It explicitly does not verify actual dataset height datum or perform vertical transformation. GitHub Actions [run #44932691048](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44932691048) passed on commit `f39fafb`: all five jobs passed, including 16 parser-backed format tests and 3 Playwright browser tests. This verifies the implemented checks and UI workflow, not geological truth or vertical datum conversion.
