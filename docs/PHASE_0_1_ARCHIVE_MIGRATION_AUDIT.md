# Phase 0/1 source archive — migration audit

**Audit date:** 2026-11-22  
**Artifact reviewed:** `geologia-phase-0-1.zip` (Library artifact, 23,817 bytes)  
**Disposition:** superseded foundation; do not copy the archived application tree into the active package.

## Why the archive is not copied verbatim

The archive uses an earlier application layout and storage/API design:

- `apps/api/app/` with `app.main:app` as the ASGI entry point;
- SQLite tables defined directly in `app/db.py`;
- a separate `app/routes/` set for projects, datasets, analysis, jobs, and tools;
- its own dataset storage and provenance implementation.

The current repository's authoritative application is under `src/geologia/`, with its API, store, validation, job lifecycle, geospatial inspection, DEM assessment, and evidence-chain workflows. Copying the old package into `apps/api/app` would create a second entry point and competing persistence/validation paths. It would not be a safe source transfer or a migration.

The archived `LICENSE` is explicitly a placeholder. The active repository's root `LICENSE` is the complete AGPL-3.0 text; the placeholder must not replace it.

## Feature mapping

| Archived Phase 0/1 capability | Current implementation / verification point | Migration decision |
|---|---|---|
| Project create/read and language validation | `src/geologia/api.py` project routes and project API tests | Keep current implementation; no duplicate route module |
| Dataset upload, extension/size limits, filename sanitization, content hashing | Current dataset upload routes, dataset validation and API hardening tests | Preserve current storage and validation contracts |
| GeoJSON structural validation/inspection | `/api/v1/datasets/{dataset_id}/geojson`, `/inspect`, validation and vector hardening paths | Use current implementation; archive code is reference only |
| Job creation/status/events/cancel | Current project job routes and job lifecycle tests | Keep current job state model |
| Tool registry | Current tool/agent registry and related API modules | Do not create a second static registry |
| Provenance record | Current dataset provenance and assessment evidence/hash-chain models | Keep current provenance schema |
| TIFF registration without scientific analysis | Current DEM dataset/manifest workflow with explicit validation/readiness gates | Do not import archived claims or bypass current scientific gates |

This mapping establishes architectural overlap, not a claim that every archived test is byte-for-byte or behavior-for-behavior equivalent. Feature-specific regression tests in the current tree remain the acceptance evidence.

## Archived test inventory

The bundle's tests cover project creation/language validation, health/platform claims, GeoJSON upload/summary/provenance, invalid GeoJSON, missing dataset, TIFF registration boundaries, unsupported extensions, upload size cleanup, filename sanitization, and storage-path concealment.

The current repository has dedicated project, dataset validation, API hardening, GeoJSON/vector, job lifecycle, provenance, and DEM test modules. When a future regression is discovered, add it to the current tests against the current API rather than importing the archived test harness.

## Security and scientific boundaries retained

- The archive's static registration/structural summary is not a geological interpretation.
- Do not execute uploaded source code or external engines during static validation.
- Do not expose a local development API publicly without authentication/authorization, quotas, safe storage, isolated workers, monitoring, and a security review.
- The archive does not establish that external GIS engines are integrated or validated.
- No transfer of archive code constitutes a DEM accuracy or product-readiness claim.

## Final disposition

The source archive has been inspected and retained as a migration reference. The active application source is already committed in the current architecture. This issue is superseded by the current implementation; any unique missing behavior must be raised as a focused, test-backed change against `src/geologia/`, not as a wholesale copy of the older application.
