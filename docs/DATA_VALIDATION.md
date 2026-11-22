# GEOLOGIA dataset validation

Status: initial deterministic validation layer
Profile version: 1.0.0
Scope: structural and explicitly declared schema checks only

## Purpose and safety boundary

Dataset validation is separate from scientific interpretation. A report with `validation_status: passed` means only that the implemented checks passed. It does not prove that measurements are accurate, representative, calibrated, geologically plausible, suitable for a model, or scientifically complete.

The data role is supplied by the user. GEOLOGIA does not infer the role from a filename or claim that a role label proves the file contents.

## API

- `POST /api/v1/datasets/{dataset_id}/validate`: run the applicable deterministic checks.
- `GET /api/v1/datasets/{dataset_id}/validation`: retrieve the most recently persisted report.

Reports include:
- `validation_level`: `structural` or `schema`.
- `validation_status`: `passed` or `failed`.
- `profile`: profile identifier and version, or null when no role-specific profile exists.
- `checks`, bounded `errors`, `warnings`, and counts.
- `scientific_interpretation: false` in every report.

Before any profile runs, GEOLOGIA re-reads the stored file and verifies its byte count and SHA-256 against the values recorded at upload. A mismatch fails validation before parsing. Reports include the source digest, source size, and validation timestamp.

A new validation report is stored in dataset metadata. It does not modify source file bytes. Dataset status changes to `validation_passed` or `validation_failed`.

## CSV checks

All CSV files supported by the validation endpoint receive structural checks:
- UTF-8 parsing with strict CSV quoting.
- Non-empty, unique column names after trimming and case normalization.
- Consistent field count for every non-empty data row.
- Blank rows are ignored and reported as warnings.
- A header-only file is reported as a warning, not as a populated dataset.

### Groundwater-level time-series profile

Activated only when the user assigns `water_levels_timeseries`.

Required fields:
- One timestamp column named `timestamp`, `datetime`, or `date`.
- A measurement column named exactly `water_level_m`; the unit must be explicit.

Checks:
- Timestamp values must parse as ISO-8601 dates or datetimes.
- `water_level_m` values must parse as finite numeric values; NaN and Infinity are rejected.
- Available columns are checked independently so one missing field does not suppress validation of the other.

The profile does **not** validate vertical datum, reference elevation, sensor calibration, time-zone policy, duplicate timestamps, well metadata, physical plausibility, measurement uncertainty, or whether the value is water depth versus water-level elevation. Those require a richer, project-specific data contract and scientific review.

## GeoJSON checks

All supported GeoJSON datasets receive the existing structural geometry checks. If the user assigns `aoi_boundary`, the versioned AOI profile additionally requires polygon or multipolygon features only and rejects null or non-polygon geometries.

These checks do not constitute complete RFC 7946 or OGC conformance, topology validation, coordinate-reference verification, boundary closure/validity analysis beyond the existing ring checks, or scientific suitability review.

## Unsupported formats and planned work

The validation endpoint currently supports CSV and GeoJSON only. GeoPackage, GeoTIFF, and LAS remain storage-only; they are not parsed or validated by this layer.

Next profile candidates must be introduced with documented schemas, explicit units and coordinate reference semantics, known-good and known-bad fixtures, and independent domain review. No profile may enable scientific execution by itself.
