# Seismology data — catalog and waveform quality

Original GEOLOGIA workflow note. Event catalog parameters, waveform measurements, and hazard interpretation are different evidence types.

## Catalog and waveform metadata
- Event identifier, origin time in UTC, latitude/longitude, depth, magnitude value and magnitude type, uncertainty, and review status.
- Network/station/channel codes, station coordinates/elevation, sensor response, sample rate, units, timing quality, and data gaps.
- Processing history, filters, instrument-response removal, window definitions, and software/version.
- Geographic coverage, station geometry, and source of catalog/event associations.

## Preflight
1. Do not compare magnitude values of different types as if they were identical.
2. Confirm waveform units and instrument response before amplitude or spectral analysis.
3. Check UTC conversion, sample rate, missing segments, clipping, and station metadata consistency.
4. Keep original waveforms and catalogs; store processed traces with reproducible parameters.
5. Treat automatic event locations and magnitudes as provisional unless their review status is known.

## Safety boundary
A catalog or waveform set alone does not produce a site-specific seismic hazard assessment. Hazard calculations require validated source models, ground-motion models, site conditions, recurrence assumptions, and specialist review.

## References
- USGS ComCat/FDSN Event API: https://earthquake.usgs.gov/fdsnws/event/1/USGS
- USGS earthquake developer resources: https://earthquake.usgs.gov/data/software/
