# GIS and coordinate reference systems — preflight

Original GEOLOGIA engineering checklist. A coordinate pair is not self-describing: never infer a CRS from plausible-looking numbers.

## Record before processing
- Source CRS authority/code or full WKT, datum/reference frame, coordinate epoch if relevant, axis order, units, and any transformation grid or operation used.
- Dataset extent, geometry type, coordinate range, vertical coordinate presence, and whether coordinates are geographic (angular) or projected (linear).
- Source filename, checksum, acquisition/creation date, and provenance.

## Safe workflow
1. Preserve the original file and metadata.
2. Inspect CRS and units before calculating distances, areas, buffers, or slopes.
3. Select a target CRS appropriate to the area and measurement; verify datum transformation availability and axis conventions.
4. Reproject into a new derived dataset. Do not overwrite source coordinates.
5. Validate output geometry, extent, units, and transformation metadata; record software/version and operation.

## Common traps
- Treating longitude/latitude degrees as meters.
- Mixing horizontal and vertical datums.
- Assuming EPSG:4326 axis order is always interpreted the same by every library.
- Using a CRS based on a guessed location or numeric range.
- Measuring large-area distances in a projection without checking distortion.

## References
- QGIS CRS reference: https://www.qgis.org/pyqgis/master/core/QgsCoordinateReferenceSystem.html
- BGS OpenGeoscience API and OGL terms: https://www.bgs.ac.uk/technologies/web-services/api/
- USGS National Map licensing/attribution: https://www.usgs.gov/faqs/what-are-terms-uselicensing-map-services-and-data-national-map
