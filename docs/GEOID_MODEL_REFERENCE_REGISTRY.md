# Geoid model reference registry

This document records source-backed geoid model metadata and the acceptance gates for a future numerical implementation. It is not a scientific validation report, geoid grid, or vertical transformation.

## Model registry

Machine-readable metadata lives in `tests/data/geoid_model_reference.json`; source records are in `tests/data/reference_sources.json`.

- **NGA Office of Geomatics** is the primary authority for Earth Gravitational Model definitions and published grids. Its current EGM portal identifies EGM2008 as the latest published model and notes a tentative future model release; do not treat this as a promise or release schedule.
- **EGM96** is a legacy model with a 15 arc-minute interpolation grid. Its vertical CRS is EPSG:5773; the associated geoid datum is EPSG:5171.
- **EGM2008** is the currently published NGA model at the time this registry was reviewed. NGA publishes a 2.5 arc-minute interpolation grid; its vertical CRS is EPSG:3855.
- OSGeo PROJ-data is included only as secondary packaging/format information for converted NGA grids, not as the model authority.
- NOAA's EGM96 discussion is recorded as a caution: model coefficients alone do not fully specify geoid undulation; realization and conventions matter.

## Numerical reference dataset identified

GeographicLib publishes `GeoidHeights.dat.gz`, a 500,000-point test dataset with EGM84, EGM96, and EGM2008 geoid-height columns. The distribution listing reports SHA-256:

`e0b9804694b3eac78ffd0b3df9cffd30a134d72007276e732ff72f9651bc9995`

The registry pins the reported checksum and describes the dataset as a cross-implementation numerical regression reference, not field-survey truth and not independent of NGA's model coefficients/conventions.

## Required gates before implementing vertical conversion

1. Obtain a complete, traceable grid artifact; record exact source, retrieval date, filename, checksum, license evidence, dimensions, extent, row/longitude order, nodata, units, and model/tide conventions.
2. Verify the checksum before parsing. Do not download grids dynamically in CI.
3. Pin exact numerical reference rows, model column, reference artifact hash, and tolerance. Label the oracle's independence and provenance.
4. Test grid nodes and interior interpolation separately, including axis order, longitude wrap, edge, outside coverage, nodata, and missing-grid cases.
5. Verify operation direction and sign with a known source/target pair and operation metadata. Do not generalize a geoid formula to unrelated national vertical datums.
6. Report operation, grid, area of use, uncertainty, and provenance; fail explicitly if an operation is unavailable or outside coverage.

## Current implementation status

- Reference registry and integrity tests: present.
- Geoid grid bundled: **no**.
- Numerical known-answer point fixture: **no**.
- Published numerical reference artifact downloaded and digest-verified in CI: **no**.
- Vertical transformation implemented: **no**.
- Scientific validation or geological interpretation: **not performed**.

The metadata tests verify consistency and explicit status only. They do not compute geoid heights, apply a grid, or prove a dataset's declared vertical CRS matches its actual measurements.
