# Persisted DEM accuracy assessment API

The accuracy endpoint computes residuals from stored raster and reference files, then records the report in a separate project-scoped tamper-evident chain.

## Endpoint

`POST /api/v1/projects/{project_id}/dem/accuracy-assessments`

The request references:
- a project-owned `dem_tile_manifest` JSON dataset,
- a project-owned `reference_elevation_observations` CSV dataset,
- a project-owned AOI GeoJSON/JSON dataset,
- exact DEM metadata and reference-source metadata,
- declared product version, pilot area and task profile,
- an independent review record bound to that exact scope,
- the coverage-footprint reference from the persisted tile collection inspection,
- an optional frozen task-specific `AccuracyRequirement`.

Before computation, the API checks stored file integrity, manifest tile membership and SHA-256 values, the coverage report's exact tile list and AOI hash, and full AOI coverage. It also requires the AOI CRS to match the CRS recorded by the coverage inspection.

Retrieve one record:

`GET /api/v1/projects/{project_id}/dem/accuracy-assessments/{assessment_id}`

List records:

`GET /api/v1/projects/{project_id}/dem/accuracy-assessments?limit=50&offset=0`

Verify the separate accuracy hash chain:

`GET /api/v1/projects/{project_id}/dem/accuracy-assessments/chain`

## Meaning of the result

The API stores the computed residuals, exclusion counts, metrics, metadata, independent review record and requirement. A metric passing its frozen requirement does not imply product readiness; the report always retains `readiness_disposition=not_assessed`.

The chain is tamper-evident, not tamper-proof. Reviewer identity, referenced source contents, license, vertical transformation and scientific independence still require external evidence and review.
