# Phase 5 — CRS validation and vector reprojection

## Delivered

- Optional GIS dependency: `pip install -e ".[gis]"`.
- `GET /api/v1/crs/inspect?crs=EPSG:4326` normalizes CRS input and reports authority, axes and units.
- `POST /api/v1/datasets/{id}/reproject` accepts `{"target_crs":"EPSG:3857"}`.
- Transformation uses pyproj with explicit x/y axis order. The stored upload is never overwritten. A successful operation creates and stores a new derived dataset in the same project, with a new SHA-256 digest, target CRS metadata, and provenance pointing to the source dataset.
- GeoJSON intake and inspection validate geometry-specific coordinate nesting, line minimums, closed polygon rings, and finite numeric ordinates.

## Limits and safety

- Reprojection currently handles GeoJSON vector geometry only; it does not reproject raster GeoTIFF or GeoPackage.
- Existing `bbox` and legacy `crs` members are removed from transformed GeoJSON because leaving them unchanged would be incorrect or misleading. Bounds are recomputed for the derived dataset's structural summary, not embedded back into the GeoJSON.
- Coordinate Z and additional ordinates are preserved unchanged; only x/y are transformed. Vertical CRS transformation is not claimed.
- CRS metadata supplied by the upload header is trusted as a declaration, not independently inferred from coordinates. Incorrect source CRS metadata can produce incorrect coordinates.
- The current validator is a structural GeoJSON validator, not a complete OGC conformance suite and not a topology or scientific-quality validator.
- If pyproj is not installed, CRS endpoints return HTTP 503 with installation guidance.

## Validation

CI installs the optional GIS extra and tests:
- valid/invalid CRS parsing,
- EPSG:4326 → EPSG:3857 reference coordinate,
- source dataset unchanged after reprojection,
- malformed GeoJSON rejected on intake,
- invalid geometry nesting, unclosed rings, and non-finite extra ordinates rejected.
