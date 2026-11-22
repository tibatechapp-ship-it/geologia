# Persisted DEM readiness assessment API

Submit a readiness decision:

`POST /api/v1/projects/{project_id}/dem/readiness-assessments`

The request identifies the logical DEM manifest, exact declared use, mandatory product context, and an optional persisted accuracy assessment ID. The API verifies the accuracy assessment chain and rechecks:

- manifest dataset integrity and product version;
- accuracy record's manifest ID/hash and exact declared use;
- every manifest tile's current content SHA-256;
- the reference dataset's current content SHA-256;
- the AOI file and canonical AOI hash;
- the coverage inspection's exact tile IDs/hashes, AOI hash/CRS and footprint reference.

Only then does it construct typed accuracy evidence and call the readiness evaluator. A missing accuracy assessment is recorded as `not_evaluable`; it cannot produce a ready disposition.

Retrieve/list records:

- `GET /api/v1/projects/{project_id}/dem/readiness-assessments/{assessment_id}`
- `GET /api/v1/projects/{project_id}/dem/readiness-assessments?limit=50&offset=0`

Verify the readiness chain:

`GET /api/v1/projects/{project_id}/dem/readiness-assessments/chain`

Readiness decisions are stored in a separate tamper-evident chain. A ready disposition is limited to the exact declared product version, pilot area and task profile; it is not a country-wide or universal accuracy claim.
