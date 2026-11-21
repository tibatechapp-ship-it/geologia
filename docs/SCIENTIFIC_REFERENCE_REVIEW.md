# Scientific reference and vertical CRS review

Review scope: horizontal projection control values, declared vertical CRS metadata, and reference-source provenance. This is a software/reference review, not a geological validation or an independent geodetic survey.

## Authoritative references

| Reference | Source | Used for |
|---|---|---|
| EPSG:3857 — WGS 84 / Pseudo-Mercator | [EPSG registry](https://epsg.io/3857) | CRS identifier, axis order, metre units, area of use, and operation method EPSG:1024 |
| IOGP Guidance Note 7-2 | [IOGP PDF](https://www.iogp.org/wp-content/uploads/2019/09/373-07-02.pdf) | Published pseudo-Mercator parameters and forward/reverse calculation equations |
| IOGP Web Mercator Guidance Note 23 | [IOGP PDF](https://www.iogp.org/bookstore/wp-content/uploads/sites/2/woocommerce_uploads/2017/01/373-23.pdf) | Distinguishes EPSG:3857 method 1024 and the conventional square-tile cutoff |
| EPSG:5773 — EGM96 height | [EPSG registry](https://epsg.io/5773) | Vertical CRS name, EGM96 geoid datum, metre unit, upward axis, and world area |
| EPSG:9707 — WGS 84 + EGM96 height | [EPSG registry](https://epsg.io/9707) | Compound CRS example connecting EPSG:4326 with vertical EPSG:5773 |
| OGC CRS WKT standard 18-010r11 | [OGC PDF](https://docs.ogc.org/is/18-010r11/18-010r11.pdf) | Compound CRS representation as independent horizontal and vertical components |

Source identifiers, URLs, purpose, and access date are captured in `tests/data/reference_sources.json`.

## Horizontal reference controls

`tests/data/reference_projection.json` contains synthetic points, not surveyed geology. Expected EPSG:3857 values are generated from the published spherical pseudo-Mercator equations using the EPSG sphere radius:

- `x = a × longitude_radians`
- `y = a × ln(tan(π/4 + latitude_radians/2))`

The new test calculates these equations directly with Python's `math` module and compares both the checked-in expected values and pyproj output against that independent calculation. It includes a Yemen-area control, the origin, a one-degree control, and the conventional square-tile northern edge at approximately 85.05112878°. This is the square-tile cutoff, not the formal EPSG area-of-use boundary (which is commonly listed as approximately ±85.06°). This avoids using pyproj as the sole oracle.

Tolerance is `0.00002 m`. The tolerance is a regression tolerance for the formula implementation, not a claim of real-world positional accuracy.

## Vertical reference control

`tests/data/vertical_crs_reference.json` uses compound CRS EPSG:9707, whose vertical component is EPSG:5773 (EGM96 height). The test asserts the declared vertical CRS identifier, datum name, metre unit, and upward axis.

The inspector reports declared vertical CRS components and bounded metadata tag values. It deliberately keeps:

- `vertical_datum_verified = false`
- `vertical_transformation_performed = false`

A CRS identifier is not proof that a dataset's height values actually use that datum. A true vertical conversion requires a valid source/target vertical CRS, an appropriate geoid/grid operation and grid file, operation availability/accuracy and area-of-use checks, and known-answer height controls. None of those vertical transformations is implemented in this stage.

## Scientific acceptance status

- Reference CRS metadata: reviewed against the cited registry/standards.
- Horizontal EPSG:3857 independent forward and inverse formula regression: passed in [CI run #44932691048](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44932691048), commit `f39fafb`.
- EGM96 declared metadata recognition and vertical CRS status distinction: passed in the same run.
- Source citation form/API capture and browser display regression: passed in the same run.
- Measured geological control dataset: not bundled.
- Vertical geoid grid application and known-answer height conversion: not implemented.
- Geological interpretation, measurement quality, and uncertainty propagation: not implemented.

Do not enable GemPy or MODFLOW based on these tests. Their prerequisite remains a validated, source-traceable data contract and independently reviewed domain datasets.

## External dataset citation capture

The web upload form exposes an expandable citation section; dataset upload also accepts optional source citation headers: URL, title, creator, publisher, DOI, license, citation, version, and access date. URL validation permits absolute HTTP(S) URLs without embedded credentials; DOI syntax and ISO access dates are checked. The service does not fetch these URLs and does not certify the source, license, citation, or supplied metadata. They are labeled `user_supplied_not_verified`, stored in the dataset summary, included in the ingestion event hash, and copied to derived reprojection lineage. Missing source information is explicitly recorded as `not_provided`.

## Real geoid model references (expanded)

The model registry in `tests/data/geoid_model_reference.json` now records real, authoritative geoid model sources:

- **NGA Office of Geomatics** is the primary source for Earth Gravitational Model definitions, coefficients, and downloadable/interpolatable grids ([NGA EGM portal](https://earth-info.nga.mil/geograv)).
- **EGM96** is the legacy global model with a published 15 arc-minute interpolation grid; the associated vertical CRS is EPSG:5773 and the geoid datum is EPSG:5171 ([NGA model downloads](https://earth-info.nga.mil/index.php?action=geoid&dir=wgs84), [EPSG:5773](https://epsg.io/5773), [EPSG:5171](https://epsg.io/5171-datum)).
- **EGM2008** is NGA's currently published model at this review and has a published 2.5 arc-minute global interpolation grid; its vertical CRS is EPSG:3855 ([NGA WGS 84 model page](https://earth-info.nga.mil/?action=wgs84&dir=wgs84), [EPSG:3855](https://epsg.io/3855)). Do not silently replace a dataset declared as EGM96 with EGM2008.
- The [OSGeo PROJ-data NGA grid inventory](https://github.com/OSGeo/PROJ-data/blob/master/us_nga/us_nga_README.txt) is used only as secondary distribution metadata for converted grid format and the public-domain statement for the listed converted NGA files. NGA remains the primary model authority.
- NOAA's [EGM96 geoid paper](https://www.ngs.noaa.gov/PUBS_LIB/EGM96_GEOID_PAPER/egm96_geoid_paper.html) documents an important scientific caveat: geopotential coefficients alone do not uniquely define a geoid undulation; the model's conventions and realization must be specified.

### Status after this reference expansion

This change adds source-grounded model metadata and a checklist, **not** a grid file or numerical height-transformation test. No EGM grid is bundled, sampled, or applied. No known-answer height point is asserted. The next implementation gate is to pin a traceable grid artifact by filename, version, SHA-256, license evidence, grid geometry, and tide/model conventions, then validate grid-node and interior interpolation against independent published values. Missing grid, outside coverage, nodata, or unavailable operation must fail explicitly rather than fall back silently.

The acceptance checklist also records the vertical sign convention to verify for the chosen operation (commonly `h = H + N` for ellipsoidal height, orthometric height, and geoid undulation) and requires operation-specific evidence; this formula must not be generalized to unrelated national vertical datums without checking their definitions.

