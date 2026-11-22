# DEM coverage assessment audit trail v1

## Purpose

Persist the exact request and result for each coverage sufficiency assessment, bound to one project and to the exact uploaded DEM and reference-observation datasets. The record supports reproducibility and later review; it does not turn a caller's coverage attestation into an independently verified scientific fact.

## Submission workflow

Use `POST /api/v1/projects/{project_id}/dem/coverage-assessments` with:

- `created_by`: caller-declared operator/reviewer identifier. The current local API does not authenticate this identity.
- `request.context.product_dataset_id` and `product_dataset_sha256`: exact uploaded DEM dataset and its upload-time SHA-256.
- `request.context.reference_dataset_id` and `reference_dataset_sha256`: exact uploaded reference dataset and its upload-time SHA-256.
- Exact product version, pilot area, reference source, primary stratum and task profile identifiers.
- Actual coverage footprint evidence and `coverage_status`.
- Frozen-gate metrics and, when coverage is declared verified, a complete `CoverageEvidenceAttestation`.

The API checks that both datasets belong to the target project, that the product role is `dem`, that the reference role is `ground_control_points` or `reference_elevation_observations`, and that stored file bytes still match the upload-time SHA-256. The metrics attestation's source checksum must equal the exact reference dataset checksum.

## Attestation fields

A verified coverage submission must preserve:

- coverage footprint evidence reference, verification method, reviewer and timezone-aware verification time;
- metrics source reference, computation method, operator and timezone-aware computation time;
- SHA-256 of the exact reference dataset;
- analysis code commit.

The API validates the presence and internal checksum binding of these fields. It does **not** independently re-run the GIS footprint extraction, count observations, reconstruct the 1 km/5 km grids, or verify the truth of the caller-declared reviewer identity and methods. A coverage sufficiency result remains an input-screening result.

## Hash-chain record

Each project has an append-only logical sequence in SQLite. Every record stores:

- canonical JSON of the request and assessment;
- SHA-256 of each canonical payload;
- the previous record hash for that project;
- a record hash over the record ID, project ID, caller-declared actor, payload hashes, previous hash and UTC timestamp.

The record is committed under `BEGIN IMMEDIATE` so concurrent writers cannot select the same predecessor. Verify the chain with:

`GET /api/v1/projects/{project_id}/dem/coverage-assessments/integrity`

Records can be listed and retrieved through the project-scoped GET routes. A detected payload change, broken predecessor link or altered record hash makes verification fail.

**Security boundary:** this is tamper-evident, not tamper-proof. An administrator who can rewrite the SQLite database and recompute the entire chain can alter history. Back up the database, restrict filesystem access, and export signed/externally archived reports before treating them as durable research records.

## Scientific boundary

- Uploaded file integrity is checked; raster contents are not yet interpreted by this coverage workflow.
- The exact product footprint and metric values are caller-attested, not independently derived by the API.
- A sufficient coverage result is not datum readiness, source independence, accuracy validation, fitness-for-purpose approval or product ranking.
- The report remains scoped to the exact product release, pilot polygon, reference source, primary stratum and task profile.
