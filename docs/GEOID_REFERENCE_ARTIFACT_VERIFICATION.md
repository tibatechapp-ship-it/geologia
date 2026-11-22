# Geoid reference artifact verification

The reference source is GeographicLib's published `GeoidHeights.dat.gz` test data (500,000 rows). SourceForge lists the distribution SHA-256 as:

`e0b9804694b3eac78ffd0b3df9cffd30a134d72007276e732ff72f9651bc9995`

The artifact is not bundled in this repository and is not downloaded in CI.

## Verify and extract

Download the exact source artifact, then run:

```bash
python scripts/verify_geoid_reference_artifact.py GeoidHeights.dat.gz \
  --output tests/data/geoid_known_answer_points.json --model EGM2008
```

The script verifies the compressed file SHA-256 before opening it, validates gzip integrity while parsing all data rows, checks five numeric columns and finite/range-valid coordinates, requires exactly 500,000 data rows, and extracts fixed zero-based row indices. Blank lines and comment lines are excluded from the data-row index.

The output records the verified artifact digest, selected model column, row indices, coordinates, and values. Review the generated file and commit it as a small fixture only after the full source artifact has passed verification.

## Scope

This artifact is a published numerical regression reference for model values, not field-survey truth. It does not validate grid interpolation, vertical CRS operation direction, or national vertical datum conversion. The unit tests use tiny synthetic gzip files and do not claim to verify the published artifact or geoid calculations. No vertical transformation is enabled by this utility.
