# Yemen DEM coverage and reference-readiness report — initial inventory

**Report version:** 1  
**Assessment date:** 2026-11-22  
**Repository snapshot:** `0d3bd12a4e92bc8f905f8257c59f2f082aef57bf`  
**Protocol:** `docs/YEMEN_DEM_VALIDATION_PROTOCOL.md`, version 1  
**Frozen screening thresholds:** Sections 13, 17 and 20; implementation freeze 2026-11-22  
**Overall status:** `not_assessed`  
**Accuracy ranking:** `not_generated` — prohibited until product-file, regional-coverage and independent-reference gates pass.

## 1. Executive finding

This is an inventory/readiness report, not an accuracy report. The repository snapshot contains no DEM raster or point-cloud candidate product. The only geospatial observation file found in the repository is `tests/data/reference_points.geojson`, a small test fixture containing generic test points; it has no survey provenance, datum, epoch, uncertainty, quality metadata or independent campaign record. It is not eligible reference data.

Therefore, no actual DEM product footprint, Yemen pilot coverage map, valid reference-observation count, density, block occupancy, temporal match, datum eligibility, source independence or DEM residual can be reported from the repository contents. No candidate can be ranked, declared accurate, or marked ready.

The correct result is **not assessed / not evaluable**, not “DEM failed”. Missing files and missing reference evidence do not demonstrate that a product is unsuitable.

## 2. Candidate inventory

| Candidate | Protocol role | Exact product file in repository | Yemen footprint verified for exact release | Current disposition |
|---|---|---:|---:|---|
| Copernicus GLO-30 | Primary open comparison candidate | No | No | Candidate only; not assessed |
| ALOS AW3D30 | Primary open comparison candidate | No | No | Candidate only; not assessed |
| FABDEM | Terrain-adjusted derivative candidate | No | No | Candidate only; source-dependent on Copernicus; not an independent reference |
| NCD Arabian Peninsula 30 m DEM | Supplementary regional layer | No | No | Metadata/access/license and exact footprint require verification |
| Saudi national 5 m DEM from Makkah study | Neighboring-region case study | No | No Yemen footprint established | Makkah study evidence only; no accuracy transfer to Asir, Najran or Yemen |
| GF-7 / LuTan-1 | Literature/technology candidates | No | No Yemen-ready deliverable established | Literature-only pending lawful, usable product/data |
| WorldDEM Neo | Commercial benchmark | No | No | Excluded from open v1 baseline pending exact product and license |

Candidate roles above follow the screening distinctions in protocol Sections 39 and 42. They are not product validation results. A provider's global coverage statement, product family name or study-area label does not replace exact release/tile footprint evidence.

## 3. Reference-source readiness

No repository file qualifies as a primary independent Yemen reference dataset. The test fixture at `tests/data/reference_points.geojson` is excluded from scientific use.

The following evidence is still required per candidate DEM × pilot polygon × primary stratum:

- Exact reference collection/product and release; acquisition/observation dates; footprint/track/shot geometry; quality filters and immutable identifiers.
- Independent spatial locations, occupied 5 km blocks, eligible-block denominator, 1 km density denominator and per-primary-cell counts.
- Horizontal/vertical uncertainty, confidence level, frame/realization/epoch, vertical datum, geoid model and transformation provenance.
- DSM/DTM compatibility, reference spatial support, time compatibility and source-lineage/independence assessment.
- A pre-residual report committed before any candidate DEM residual is calculated or inspected.

ICESat-2 and GEDI are not automatically independent votes. Their actual coverage must be measured for each pilot area and DEM epoch. GNSS/benchmark data require documented survey method, datum, epoch, uncertainty and geoid dependencies.

## 4. Frozen v1 coverage gates

The evaluator uses the thresholds already fixed in protocol v1:

| Gate | Exploratory | Confirmatory |
|---|---:|---:|
| Independent observations per primary cell | 30 | 50 |
| Valid independent locations per km² | 20 | 40 |
| Occupied independent 5 km blocks | 20 | 30 |
| Eligible blocks occupied | 60% | 75% |
| Maximum observations in one block | 50% | 50% |
| Observations within five years of DEM epoch | Not required | 70% |

Report the occupied-cell fraction on the registered 1 km grid descriptively; protocol v1 does not set a universal pass/fail threshold for that fraction. The spatial block bootstrap uses 5 km primary blocks, sensitivity widths 2.5 km and 10 km, and 2,000 replicates. These are operational screening gates, not universal standards or power guarantees. The confirmatory phase still requires a separate precision/power assessment.

The stateless preview is exposed at `POST /api/v1/dem/coverage-assessments`; frozen thresholds are available at `GET /api/v1/dem/coverage-thresholds`. Project-scoped records are persisted through `POST /api/v1/projects/{project_id}/dem/coverage-assessments`, listed with `GET /api/v1/projects/{project_id}/dem/coverage-assessments`, and checked with the `/integrity` subroute. The persisted workflow verifies the uploaded product/reference file hashes and binds the request to those exact datasets. It records a caller-attributed coverage/method attestation and stores request/result hashes in a per-project chain. The request schema has no input for `analogue_region` or `yemen_target_stratum`; a Saudi analogue cannot satisfy a Yemen product-coverage gate. The hash chain is tamper-evident, not tamper-proof, and does not independently extract raster footprints or validate the caller's coverage metrics.

## 5. Required next evidence collection

1. Obtain exact, lawfully usable DEM releases/tiles for the registered Yemen pilot polygons; preserve source metadata, license, checksums, acquisition dates, native grid, DSM/DTM semantics and vertical datum.
2. Obtain candidate reference datasets and authoritative coverage/quality metadata for each pilot polygon. Do not treat the repository's test fixture as observations.
3. Freeze the pilot polygons, target strata, equal-area CRS, 1 km and 5 km grids, data releases, filters and analysis commit before coverage mapping.
4. Generate one coverage unit per exact DEM release × pilot polygon × reference source × primary stratum.
5. Run the frozen coverage evaluator; retain every failed or not-assessed gate and its reason code.
6. Only after coverage is checked, assess reference datum, quality, temporal compatibility, source independence and scale support. The status `reference_ready` requires those separate gates.
7. Commit the coverage/readiness report before any residual analysis. Accuracy analysis and product ranking remain blocked until all release gates pass.

## 6. Decision

**No DEM ranking is issued. No local accuracy claim is made.** The current evidence supports only a candidate inventory and an explicit statement of missing product/reference evidence. The absence of those files is not evidence of DEM inaccuracy or unsuitability.
