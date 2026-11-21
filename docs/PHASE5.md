# Phase 5 — CRS validation and vector reprojection

## Delivered

- Optional GIS dependency: `pip install -e ".[gis]"` (or install `[dev,gis]` for tests).
- `GET /api/v1/crs/inspect?crs=EPSG:4326` normalizes CRS input and reports authority, axes and units.
- `POST /api/v1/datasets/{id}/reproject` accepts `{"target_crs":"EPSG:3857"}` and returns a transformed GeoJSON response.
- Transformation uses pyproj with explicit x/y axis order. The stored upload is never overwritten. A successful operation creates a new derived dataset in the same project, with a new SHA-256 digest, target CRS metadata, and provenance pointing to the source dataset.
- Existing GeoJSON upload now performs the same coordinate/geometry structural validation used by inspection, rejecting malformed point positions before storage.

## Limits and safety

- Reprojection currently handles GeoJSON vector geometry only; it does not reproject raster GeoTIFF or GeoPackage.
- Existing `bbox` and legacy `crs` members are removed from transformed GeoJSON because leaving them unchanged would be incorrect or misleading. Bounds are not recomputed in this phase.
- Coordinate Z values are preserved unchanged; only x/y are transformed. Vertical CRS transformation is not claimed.
- Output is returned in the API response and is not saved as a new dataset.
- CRS metadata supplied by the upload header is trusted as a declaration, not independently inferred from coordinates.
- If pyproj is not installed, CRS endpoints return HTTP 503 with installation guidance. Install `pip install -e ".[gis]`.

## Validation

CI installs the optional GIS extra and tests:
- valid/invalid CRS parsing,
- EPSG:4326 → EPSG:3857 reference coordinate,
- source dataset unchanged after reprojection,
- malformed GeoJSON rejected on intake.
