# Phase 4 — Bilingual local workspace UI

The source package serves a bilingual Arabic RTL / English LTR web workspace.

## UI capabilities
- API health and integrated-engine count.
- Create and select local projects.
- Upload supported files using the raw-body intake endpoint.
- Set a dataset role and optional CRS.
- List stored dataset metadata.
- Create and display a plan-only analysis job, including missing-data readiness and agent assignments.

## Runtime
FastAPI serves the packaged `geologia/web` directory at `/`. The UI uses same-origin
API calls and requires no separate frontend build tool.

## Limitations
This is a functional local MVP, not a public production deployment. It has no login,
role-based access control, remote storage, worker execution, or scientific engine
integrations. Keep it on localhost until deployment security is implemented.


## Phase 5A — GeoJSON inspection tool

A real deterministic inspection operation is available at
`POST /api/v1/datasets/{dataset_id}/inspect`.

It reads the stored GeoJSON and calculates feature count, geometry-type counts,
null-geometry count, coordinate count, XY bounding box, and unique property keys.
The report is stored in dataset metadata and the status becomes
`inspected_structural_metrics`.

This operation does not modify uploaded bytes, reproject coordinates, validate
topology, infer geology, or produce scientific conclusions. Raster processing and
isolated scientific workers remain future work.
