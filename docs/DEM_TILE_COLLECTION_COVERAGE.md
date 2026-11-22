# DEM tile-collection coverage inspection

This workflow measures the footprint and valid-data mask of an uploaded collection of aligned DEM tiles against one registered AOI. It is a coverage inspection only; it does not establish vertical datum, source independence, or elevation accuracy.

## API

Inspect and persist:

`POST /api/v1/projects/{project_id}/dem/tile-collection-coverage-inspection`

Request:

```json
{
  "dem_dataset_ids": ["dataset-tile-01", "dataset-tile-02"],
  "aoi_dataset_id": "dataset-aoi",
  "aoi_crs": "EPSG:32638"
}
```

Retrieve the latest report attached to the AOI dataset:

`GET /api/v1/projects/{project_id}/dem/tile-collection-coverage-inspection/{aoi_dataset_id}`

Each DEM dataset must belong to the project, have `data_role=dem`, and be a GeoTIFF or HGT upload. The AOI must be a project-owned GeoJSON/JSON dataset with `data_role=aoi_boundary`. Stored bytes are checked against their upload-time size and SHA-256 before inspection.

The report includes every tile's filename, size, SHA-256, dimensions, affine transform and mosaic-grid offset; the union footprint; AOI intersection and uncovered area; overlap area; and valid AOI pixel-centre counts. A canonical report SHA-256 is assigned as the coverage-footprint reference. The report is stored with an AOI dataset provenance event.

## Grid and resource gates

- Up to 256 tiles per collection.
- One common horizontal CRS, pixel resolution/orientation and integer-aligned grid origins. No silent resampling.
- Per tile: at most 100 million pixels and 2 GiB.
- Collection total: at most 50 GiB.
- Mosaic processing: at most 1 billion grid pixels.
- Valid masks are unioned in 512 × 512 windows; overlapping tile centres are counted once.
- The API upload limit remains 50 MiB per file. Typical 3601 × 3601 SRTM HGT tiles fit; larger GeoTIFFs may need local processing or a future file-based import workflow.

Geographic HGT grids are supported when the installed GDAL SRTMHGT driver exposes valid CRS and transform metadata. Antimeridian-crossing AOIs must be split into non-crossing polygons.

## Interpretation

`full_aoi_extent_and_valid_pixels` means the AOI is covered by the union of tile footprints and all AOI pixel centres on the common grid have valid masks. The pixel-centre rule is not fractional boundary-pixel clipping. Pixel area is a local estimate.

A successful report is not a DEM accuracy result and must not by itself set `validation_status=independently_reviewed` or a readiness disposition to `ready`.
