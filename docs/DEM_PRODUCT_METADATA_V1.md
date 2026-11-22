# DEM product metadata v1

Product metadata is uploaded as a project dataset with role `dem_product_metadata` and JSON format.

Schema identifier: `geologia.dem-product-metadata.v1`.

Required fields include:
- exact `product_version_id` and horizontal CRS;
- specification source/date and metric type;
- vertical datum and DSM/DTM surface type;
- declared X/Y resolution and its CRS-native unit;
- license reference and explicit compatibility disposition;
- evidence reference, reviewer and timezone-aware review timestamp.

The readiness API no longer accepts a caller-supplied `MandatoryProductContext`. It derives specification fields from this stored metadata, coverage and coverage status from the persisted tile collection inspection, and resolution from the actual raster affine transforms. The declared resolution and unit must match the raster files.

License disposition `incompatible` becomes a mandatory failure; `unresolved` becomes an unresolved item. A `compatible` value is still a reviewed metadata assertion, not cryptographic proof of license terms.

The metadata file is integrity-checked and its dataset ID and SHA-256 are included in the readiness record. It must identify the exact manifest product version.
