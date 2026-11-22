# Yemen DEM validation protocol (pre-registration template)

**Status:** proposal only; no field campaign or accuracy result is claimed.  
**Scope:** evaluate elevation products in selected Yemen pilot areas before making any country-wide accuracy claim.

## 1. Questions and estimands

For each exact product, tile/version and pilot area, estimate:
- Absolute vertical agreement with a documented reference frame and vertical datum.
- Relative terrain-shape agreement separately from absolute offset.
- Bias, residual dispersion, robust error and uncertainty—not RMSE alone.
- Whether the product represents a DSM (surface including objects) or DTM (bare-earth terrain), and whether that representation matches the intended use.

Do not generalize a pilot result to all Yemen or to another product version without evidence.

## 2. Pilot design and pre-registration

Begin with at most three pilot environments, subject to safe access and available reference data:
- Urban/built-up pilot (candidate: Sana'a; exact footprint to be fixed before sampling).
- Highland or wadi pilot (exact catchment and footprint to be fixed before sampling).
- Coastal plain pilot (candidate: Tihama; exact footprint to be fixed before sampling).

Before inspecting DEM residuals, publish or commit a dated protocol record containing:
- Pilot polygon geometry and CRS.
- Products, tile identifiers, versions, licenses, source URLs and acquisition/production dates.
- Target reference datum, epoch, coordinate system and geoid model/realization.
- Point-selection, exclusion and matching rules.
- Pre-defined strata and primary metrics.
- Planned minimum sample and stopping rule.
- Analysis script version and random seed, if sampling is randomized.

Any later change must be logged as a protocol amendment with reason and timestamp; retain the original analysis.

## 3. Terrain, land-cover and elevation strata

Use these pre-defined bins where data support them:

- Slope: <2°, 2–5°, 5–15°, 15–30°, >30°.
- Land cover: bare, agricultural/vegetated, built-up, water/shoreline.
- Elevation: <500 m, 500–1500 m, 1500–2500 m, >2500 m.

Do not automatically analyze the full Cartesian product: sparse combinations can create unstable estimates. Declare primary strata in advance, report sample counts for every cell, and label under-sampled cells as insufficient evidence. A target of **at least 50 independent reference locations per reported primary stratum** is a planning floor, not a guarantee of statistical power. Spatially clustered points are not independent; use spatial blocks and effective sample size when estimating uncertainty.

Exclude water, shoreline mixed pixels, cliffs, buildings or vegetation only according to pre-declared rules relevant to the product/use. Report exclusions and counts; do not silently remove outliers.

## 4. Reference quality and non-circular comparison

Every reference point/track must carry:
- Reference method (static GNSS, RTK/PPK, surveyed benchmark, lidar, ICESat-2 ATL08, GEDI, etc.).
- Horizontal and vertical uncertainty, confidence level, and how uncertainty was estimated.
- Reference frame, realization, epoch, vertical datum, geoid model and applied transformation.
- Survey date, instrument/processing metadata, quality flags and provenance.

GNSS is not automatically truth. Prefer independent, documented control or survey products with uncertainty materially smaller than the DEM error being evaluated. Do not claim sub-decimeter DEM validation from a reference whose uncertainty is several decimeters.

Do not treat agreement between ICESat-2, GEDI and a DEM as independent ground truth by default. Check actual footprint/track coverage in each pilot polygon before design; assess slope, canopy, footprint size, quality flags and sampling density. If no suitable spaceborne observations cover a stratum, record a coverage gap rather than interpolating a validation claim.

## 5. Vertical datum and geoid handling

Record the product's native vertical reference and the reference observations' vertical reference explicitly. Transform both to the same target datum only through a documented, reproducible operation.

- Do not assume EGM2008 or EGM2020 is locally validated for Yemen merely because it is global or newer.
- Do not assert the existence or absence of a national geoid without a source inventory and authority confirmation.
- Geoid/model uncertainty must be estimated from independent local/regional evidence when available; otherwise mark it unknown or use a clearly stated provisional bound.
- Keep geoid model/version, grid checksum, interpolation method, operation direction and software version in the report.
- A global geoid grid's internal model test values are not field-survey truth and do not establish Yemen datum accuracy.

If geoid uncertainty is unknown, absolute-height validation is **datum-limited** and must not be presented as fully corrected DEM accuracy.

## 6. DSM versus DTM and product semantics

For every product, identify the exact release and its documented surface type:
- DSM: surface may include buildings, trees and other objects.
- DTM: intended bare-earth terrain representation, subject to source and processing limitations.

Do not label Copernicus GLO-30 or ALOS AW3D30 as bare-earth DTM without evidence for the exact product/version. FABDEM is a terrain-adjusted derivative of Copernicus and is not a direct independent survey. Compare like with like: DSM with suitable surface observations, or DTM with bare-earth control.

Urban/vegetated residuals may reflect surface semantics, not just sensor error. Report these separately.

## 7. Temporal matching

For each product and reference, record acquisition/observation date or date range, not only download date. Compare time-compatible observations wherever possible.

Flag or exclude locations with plausible intervening changes using pre-registered criteria: construction, excavation, road works, erosion, landslide, flood deposition, quarrying or vegetation change. Keep temporal mismatch as a separate uncertainty component; do not attribute detected surface change automatically to DEM error.

## 8. Residuals and required metrics

Define residual consistently, for example:

    d_i = z_product,i - z_reference,i

Positive values mean the product is higher than the reference under this convention.

For each product and stratum report:
- n and spatial coverage.
- Mean signed bias and median bias.
- Standard deviation of residuals after bias removal (state population/sample convention).
- RMSE, MAE and NMAD (1.4826 × median absolute deviation from median).
- Median and 90th/95th percentile of absolute residuals.
- Confidence intervals, preferably spatial block bootstrap when spatial autocorrelation is material.
- Exclusions, missing-data rate and reference uncertainty.

Decompose RMSE using the observed residual distribution: RMSE² = bias² + residual_variance when variance is defined consistently. Report bias separately from dispersion. A nearly constant offset may be correctable for a defined region/datum; do not apply correction to held-out validation points or imply it fixes local terrain distortions.

Report absolute and relative accuracy separately. Relative assessment may include local differences, slope/shape agreement, profile or drainage checks with suitable reference data. State the scale/window; relative accuracy is not interchangeable with absolute vertical accuracy.

## 9. Uncertainty budget (do not over-correct)

For independent, zero-mean components expressed in the same vertical quantity, a first-order budget may use:

    u_observed² ≈ u_product² + u_reference² + u_geoid² + u_temporal² + u_horizontal_to_vertical²

This is an approximation, not a universal correction formula. If components are correlated, include covariance terms; if distributions are non-Gaussian or biases are present, use an appropriate propagation/model instead. Horizontal position uncertainty can create vertical mismatch on slopes; estimate it using local terrain gradient and horizontal uncertainty where justified.

Never compute u_product = sqrt(RMSE² - u_reference² - ...) unless the components, independence, bias treatment and compatible statistical definitions are defensible. If not, report observed residual statistics plus the uncertainty budget without claiming a deconvolved DEM-only RMSE.

## 10. Acceptance, reporting and reproducibility

No product is declared “best for Yemen” from one pilot or one aggregate statistic. Acceptance is use-case-specific and must be defined before results are examined.

Every GEOLOGIA validation record should include:
- Country/region and polygon identifier.
- Dataset name, exact release, tile IDs, acquisition dates and checksum (SHA-256).
- DSM/DTM classification and native vertical reference.
- Reference source, datum, uncertainty and date.
- Pre-registration and amendment identifiers.
- Analysis software/version, configuration and code commit.
- Per-stratum metrics, confidence intervals, coverage and limitations.
- Status: planned, coverage_checked, reference_ready, analyzed, independently_reviewed.

The first phase should produce a **coverage and reference-readiness report**, not a fabricated accuracy ranking. Field work must be subject to local safety, access, permissions and equipment constraints. Remote-only evidence must be labeled remote validation and must not be described as a substitute for unavailable ground control.

## 11. Release gates

A pilot accuracy claim may be published only after:
1. Product semantics, version and date are verified.
2. Reference datum and uncertainty are documented.
3. Coverage and sample design are recorded before residual analysis.
4. Time mismatch and DSM/DTM mismatch are addressed.
5. Metrics and uncertainty intervals are generated reproducibly.
6. Limitations and spatial scope are prominent.
7. Independent review confirms that the conclusion does not exceed the evidence.

Until these gates pass, GEOLOGIA must display **“local accuracy not yet validated”** for the relevant Yemen area.
