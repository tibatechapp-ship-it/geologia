# Phase 2 — Safe dataset intake

## Implemented
- Streaming raw-body upload with a hard 50 MiB cap.
- Allowlist: GeoJSON/JSON, GeoPackage, GeoTIFF, CSV, LAS.
- Generated storage IDs; user filenames are sanitized and never used as paths.
- SHA-256, size, format, CRS metadata, and creation timestamp.
- Structural-only GeoJSON validation and feature count.
- Dataset metadata endpoints. Stored source files are not exposed by a public path.
- GeoPackage, GeoTIFF, CSV, and LAS are stored but not interpreted.

## Upload protocol

```http
POST /api/v1/projects/{project_id}/datasets
Content-Type: application/octet-stream
X-Dataset-Name: Area study
X-Filename: area.geojson
X-CRS: EPSG:4326

<raw file bytes>
```

GeoJSON/JSON defaults to EPSG:4326 per RFC 7946 unless `X-CRS` is provided. Other formats may omit CRS, but are not eligible for spatial analysis until it is defined and validated.

## Endpoints
- `POST /api/v1/projects/{project_id}/datasets`
- `GET /api/v1/projects/{project_id}/datasets`
- `GET /api/v1/datasets/{dataset_id}`

## Safety limits
- Maximum upload size: 50 MiB.
- No archive extraction.
- No execution of uploaded content.
- No GIS processing in this phase.
- Upload is streamed to a temporary file and atomically moved to generated storage.
- Raw content paths are not returned by metadata APIs.
