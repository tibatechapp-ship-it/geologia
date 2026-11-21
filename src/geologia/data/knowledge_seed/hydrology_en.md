# Groundwater investigation — data readiness checklist

This is an original GEOLOGIA workflow note, not a groundwater model or a site-specific conclusion.

## Minimum evidence to organize
- Area-of-interest boundary and a declared coordinate reference system (CRS).
- Borehole/well locations, surveyed elevation and vertical datum, total depth, lithology, screened interval, casing, and construction date where available.
- Water-level observations with timestamp, time zone, measurement method, reference point, units, and pumping/recovery status.
- Pumping-test rate and duration, drawdown/recovery series, nearby pumping context, and observation-well distances when available.
- Recharge estimates with method, period, spatial support, and uncertainty; rainfall/evapotranspiration context; geology and hydrostratigraphic interpretation; DEM and surface-water boundaries where relevant.

## Preflight checks
1. Separate depth below measuring point from elevation relative to a datum. Do not mix them.
2. Check coordinates, CRS, units, duplicate well IDs, impossible dates, missing measurement status, and inconsistent well elevations.
3. Keep raw observations unchanged; store corrected/derived values as new records with method and provenance.
4. Distinguish measured, estimated, interpolated, and assumed values.
5. Record whether each dataset covers the same season, stress period, and spatial domain.

## Modeling gate
A conceptual model should identify aquifers, aquitards, boundary conditions, stresses, and calibration observations before a numerical model is proposed. Model suitability, parameter identifiability, calibration, and uncertainty require specialist review. Presence of well logs or water levels alone does not establish sustainable yield or drilling success.

## References
- USGS, Groundwater Wells: https://www.usgs.gov/water-science-school/science/groundwater-wells
- USGS, water-table measurement guidance: https://www.usgs.gov/faqs/how-can-i-find-depth-water-table-a-specific-location
- USGS MODFLOW 6.8.0 release (CC0 metadata): https://www.usgs.gov/software/modflow-version-680
