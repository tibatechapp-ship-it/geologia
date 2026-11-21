# Scientific reference and vertical CRS review

Review scope: horizontal projection control values, declared vertical CRS metadata, and reference-source provenance. This is a software/reference review, not a geological validation or an independent geodetic survey.

## Authoritative references

| Reference | Source | Used for |
|---|---|---|
| EPSG:3857 — WGS 84 / Pseudo-Mercator | [EPSG registry](https://epsg.io/3857) | CRS identifier, axis order, metre units, area of use, and operation method EPSG:1024 |
| IOGP Guidance Note 7-2 | [IOGP PDF](https://www.iogp.org/wp-content/uploads/2019/09/373-07-02.pdf) | Published pseudo-Mercator parameters and forward calculation equations |
| EPSG:5773 — EGM96 height | [EPSG registry](https://epsg.io/5773) | Vertical CRS name, EGM96 geoid datum, metre unit, upward axis, and world area |
| OGC CRS WKT standard 18-010r11 | [OGC PDF](https://docs.ogc.org/is/18-010r11/18-010r11.pdf) | Compound CRS representation as independent horizontal and vertical components |

Source identifiers, URLs, purpose, and access date are captured in `tests/data/reference_sources.json`.

## Horizontal reference controls

`tests/data/reference_projection.json` contains synthetic points, not surveyed geology. Expected EPSG:3857 values are generated from the published spherical pseudo-Mercator equations using the EPSG sphere radius:

- `x = a × longitude_radians`
- `y = a × ln(tan(π/4 + latitude_radians/2))`

The new test calculates these equations directly with Python's `math` module and compares both the checked-in expected values and pyproj output against that independent calculation. It includes a Yemen-area control, the origin, a one-degree control, and the documented northern Web Mercator limit. This avoids using pyproj as the sole oracle.

Tolerance is `0.00002 m`. The tolerance is a regression tolerance for the formula implementation, not a claim of real-world positional accuracy.

## Vertical reference control

`tests/data/vertical_crs_reference.json` uses compound CRS EPSG:9707, whose vertical component is EPSG:5773 (EGM96 height). The test asserts the declared vertical CRS identifier, datum name, metre unit, and upward axis.

The inspector reports declared vertical CRS components and bounded metadata tag values. It deliberately keeps:

- `vertical_datum_verified = false`
- `vertical_transformation_performed = false`

A CRS identifier is not proof that a dataset's height values actually use that datum. A true vertical conversion requires a valid source/target vertical CRS, an appropriate geoid/grid operation and grid file, operation availability/accuracy and area-of-use checks, and known-answer height controls. None of those vertical transformations is implemented in this stage.

## Scientific acceptance status

- Reference CRS metadata: reviewed against the cited registry/standards.
- Horizontal EPSG:3857 formula regression: implemented; CI result must be checked for the current commit.
- EGM96 declared metadata recognition: implemented; CI result must be checked for the current commit.
- Measured geological control dataset: not bundled.
- Vertical geoid grid application and known-answer height conversion: not implemented.
- Geological interpretation, measurement quality, and uncertainty propagation: not implemented.

Do not enable GemPy or MODFLOW based on these tests. Their prerequisite remains a validated, source-traceable data contract and independently reviewed domain datasets.
