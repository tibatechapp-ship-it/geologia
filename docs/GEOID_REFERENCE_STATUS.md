# Geoid model reference status

## Authority and model metadata

NGA Office of Geomatics is GEOLOGIA's primary reference for Earth Gravitational Model data. Its WGS 84 publication lists the EGM96 worldwide interpolation grid at 15 arc-minutes and EGM2008 at 2.5 arc-minutes. NGA identifies EGM96 as legacy and EGM2008 as its latest published model at this review; its page tentatively indicates a new EGM in 2028.

- [NGA EGM portal](https://earth-info.nga.mil/geograv)
- [NGA WGS 84 model and grid listings](https://earth-info.nga.mil/?action=wgs84&dir=wgs84)
- [EPSG:5773 — EGM96 height](https://epsg.io/5773)
- [EPSG:5171 — EGM96 geoid datum](https://epsg.io/5171-datum)
- [EPSG:3855 — EGM2008 height](https://epsg.io/3855)
- [NOAA EGM96 model-convention discussion](https://www.ngs.noaa.gov/PUBS_LIB/EGM96_GEOID_PAPER/egm96_geoid_paper.html)

The registry distinguishes vertical CRS identifiers from geoid datum metadata. A declared CRS does not prove that the values in a dataset use that datum. EGM2008 must not silently replace EGM96 when a source declares EGM96.

## Numerical reference dataset

The [GeographicLib GeoidHeights.dat.gz dataset](https://sourceforge.net/projects/geographiclib/files/testdata/GeoidHeights.dat.gz/download) is listed as a 500,000-point cross-implementation reference for EGM84, EGM96, and EGM2008. The publisher's download page reports SHA-256:

`e0b9804694b3eac78ffd0b3df9cffd30a134d72007276e732ff72f9651bc9995`

The digest is recorded as **published**, not locally verified. The artifact has not been downloaded, hashed, sampled, or run in GEOLOGIA CI. GeographicLib documents the values as computed using NGA harmonic-synthesis programs; this is not field-survey truth and is not independent of NGA model coefficients and conventions.

## Validation boundary

This registry adds source metadata and acceptance gates only. It does not bundle a geoid grid, perform vertical transformations, or claim scientific validation. Before any future transformation is enabled, GEOLOGIA must pin a licensed/authorized grid artifact, verify its SHA-256, record grid geometry and model conventions, and test grid nodes/interpolation against reproducible reference values. Missing grid, nodata, out-of-coverage, or unavailable operation must fail explicitly rather than falling back to a different model.
