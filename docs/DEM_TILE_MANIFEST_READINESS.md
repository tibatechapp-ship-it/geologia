# DEM tile manifest and coverage assessment binding

A DEM product distributed as multiple raster files must have one logical product identity. Use a JSON dataset with `data_role=dem_tile_manifest` and the schema below:

```json
{
  "schema": "geologia.dem-tile-manifest.v1",
  "product_version_id": "product-release-2026-01",
  "tile_dataset_ids": ["dataset-tile-01", "dataset-tile-02"],
  "tile_dataset_sha256s": ["<64-hex-sha256-1>", "<64-hex-sha256-2>"]
}
```

The manifest binds each exact dataset ID to its upload-time SHA-256. IDs must be unique, each ID must have one checksum, and the manifest product version must match the declared product version in a coverage assessment.

## Assessment gate

For a persisted assessment whose product dataset is a tile manifest, the API verifies:

1. The manifest bytes match the registered manifest dataset SHA-256.
2. The manifest schema, tile IDs and SHA-256 values are valid.
3. Every tile belongs to the same project, has `data_role=dem`, has an allowed raster format, and matches the manifest checksum and stored bytes.
4. The latest AOI-attached tile collection inspection names the same ordered tile IDs and hashes, the same AOI ID/hash, and the same coverage-footprint reference.
5. A `verified` coverage claim is accepted only when the inspection reports full AOI extent coverage and all AOI pixel centres valid.

The assessment is then recorded in the project's tamper-evident coverage-assessment chain using the manifest dataset as the logical product dataset.

## Limits

The manifest is a product-membership record, not a source license or accuracy certificate. It does not prove independent reference status, vertical datum compatibility, or DEM accuracy. Those remain separate evidence gates.
