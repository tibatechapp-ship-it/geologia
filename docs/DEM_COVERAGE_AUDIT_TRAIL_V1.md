# DEM coverage assessment audit trail v1

## Purpose

Persist the exact request and result for each coverage sufficiency assessment, bound to one project and to the exact uploaded DEM and reference-observation datasets. The record supports reproducibility and later review; it does not turn a caller's coverage attestation into an independently verified scientific fact.

## DEM/AOI footprint inspection

Upload the exact DEM as `data_role=dem` and the registered AOI polygon as `data_role=aoi_boundary`. Then call `POST /api/v1/datasets/{dem_dataset_id}/coverage-inspection` with the AOI dataset ID and its explicitly declared CRS.

The inspection:
- verifies both uploaded file hashes before reading;
- requires a projected DEM CRS with linear units;
- intersects the raster's affine footprint with the AOI polygon;
- scans the first-band validity mask block-by-block without reading elevation values;
- reports exact polygon extent-intersection area and pixel-centre valid-mask counts/area estimates separately;
- records whether the AOI is fully within the raster extent and whether every AOI pixel centre in the rasterized AOI is valid.

A `CoverageStatus.VERIFIED` assessment is accepted only when the persisted inspection reports full AOI containment and all AOI pixel centres valid. Partial extent or nodata cases must not be labelled verified. The pixel-area estimate is approximate at AOI boundaries and is not a terrain-accuracy statistic.

## Submission workflow

Use `POST /api/v1/projects/{project_id}/dem/coverage-assessments` with:

- `created_by`: caller-declared operator/reviewer identifier. The current local API does not authenticate this identity.
- `request.context.product_dataset_id` and `product_dataset_sha256`: exact uploaded DEM dataset and its upload-time SHA-256.
- `request.context.reference_dataset_id` and `reference_dataset_sha256`: exact uploaded reference dataset and its upload-time SHA-256.
- `request.context.aoi_dataset_id` and `aoi_dataset_sha256`: exact uploaded AOI boundary and its upload-time SHA-256.
- Exact product version, pilot area, reference source, primary stratum and task profile identifiers.
- Actual coverage footprint evidence and `coverage_status`.
- Frozen-gate metrics and, when coverage is declared verified, a complete `CoverageEvidenceAttestation`.

The API checks that all three datasets belong to the target project, that the product role is `dem`, the AOI role is `aoi_boundary`, the reference role is `ground_control_points` or `reference_elevation_observations`, and that stored file bytes still match the upload-time SHA-256. The metrics attestation's source checksum must equal the exact reference dataset checksum. The attested footprint reference must match the latest persisted DEM/AOI inspection for the same product and AOI dataset IDs/checksums.

## Attestation fields

A verified coverage submission must preserve:

- coverage footprint evidence reference, verification method, reviewer and timezone-aware verification time;
- metrics source reference, computation method, operator and timezone-aware computation time;
- SHA-256 of the exact reference dataset;
- analysis code commit.

The API validates the presence and internal checksum binding of these fields. It does **not** independently re-run the GIS footprint extraction, count observations, reconstruct the 1 km/5 km grids, or verify the truth of the caller-declared reviewer identity and methods. A coverage sufficiency result remains an input-screening result.

Dataset roles are declarations recorded at upload time. This workflow checks the declared role and the file's upload-time checksum; it does not inspect raster pixels or observation semantics to prove that the file truly is a DEM or a valid reference dataset.

## Hash-chain record

Each project has an append-only logical sequence in SQLite. Every record stores:

- canonical JSON of the request and assessment;
- SHA-256 of each canonical payload;
- the previous record hash for that project;
- a record hash over the record ID, project ID, caller-declared actor, payload hashes, previous hash and UTC timestamp.

The record is committed under `BEGIN IMMEDIATE` so concurrent writers cannot select the same predecessor. The SQLite schema version is advanced to 2. Verify the chain with:

`GET /api/v1/projects/{project_id}/dem/coverage-assessments/integrity`

Records can be listed and retrieved through the project-scoped GET routes. A detected payload change, broken predecessor link or altered record hash makes verification fail.

**Security boundary:** this is tamper-evident, not tamper-proof. An administrator who can rewrite the SQLite database and recompute the entire chain can alter history. Back up the database, restrict filesystem access, and export signed/externally archived reports before treating them as durable research records.

## Scientific boundary

- Uploaded file integrity is checked. The DEM coverage inspector reads the first-band validity mask and affine metadata, but not elevation values; it does not derive reference-observation counts from the reference file.
- The exact product footprint and metric values are caller-attested, not independently derived by the API.
- A sufficient coverage result is not datum readiness, source independence, accuracy validation, fitness-for-purpose approval or product ranking.
- The report remains scoped to the exact product release, pilot polygon, reference source, primary stratum and task profile.
