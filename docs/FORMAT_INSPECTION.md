# Bounded geospatial format inspection

Status: optional parser-backed structural inspection; no scientific interpretation.

## Supported formats

- CSV: strict structural parsing and header/row metrics.
- GeoJSON: structural geometry and coordinate metrics.
- GeoPackage: SQLite integrity and layer/schema metadata.
- GeoTIFF: dimensions, bands, block layout, CRS/transform and bounded sample statistics.
- LAS: header, point-format metadata and a bounded point sample. Compressed LAZ is not supported by this inspector.

Install optional parser dependencies with:

```bash
python -m pip install -e ".[formats]"
```

The minimal install does not include GeoPandas, Pyogrio, Rasterio, or laspy. If a parser is missing, the API returns an explicit dependency-required response rather than claiming inspection succeeded.

## Resource and safety limits

- Maximum source size: 50 MiB.
- Raster dimensions are bounded by a maximum pixel count and band count.
- Raster block and sample memory are bounded.
- GeoPackage layer/field counts and metadata output are bounded.
- LAS variable-length records and sampled points are bounded.
- Parser output is metadata and sampled statistics only. The inspector does not load a complete raster for scientific processing.
- Uploaded files are never executed. Parser-backed inspection is not a substitute for parser sandboxing against hostile files.

## Scientific limitations

Inspection does not validate geological meaning, coordinate correctness, vertical datum realization, sensor calibration, sampling representativeness, model suitability, or scientific uncertainty. Declared CRS and vertical CRS metadata are reported, not independently verified.

EPSG:3857 fixtures are software known-answer controls based on published projection equations, not geological ground truth. A successful inspection means only that the supported parser and structural checks completed within the declared bounds.
