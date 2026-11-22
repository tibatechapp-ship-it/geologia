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

Use a pre-declared pilot design of **up to four distinct environments**, subject to safe access and reference readiness:
- Urban/built-up (candidate: Sana'a or Taiz; exact footprint to be fixed before sampling).
- Steep western highlands (candidate: Haraz; exact footprint to be fixed before sampling).
- Arid coastal plain (candidate: Tihama; exact footprint to be fixed before sampling).
- Wadi environment (a named catchment and footprint to be fixed before sampling).

These are candidate environments, not a claim that suitable control data exist. The final polygons must be selected by documented terrain/use-case rationale and data-readiness criteria **before inspecting product residuals**. If resources allow only three, retain urban, steep-highland and coastal environments; document the omitted wadi as an explicit coverage limitation. Do not substitute a region after seeing favorable/unfavorable accuracy results.

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


## 12. Coverage and reference-readiness report (before accuracy analysis)

Coverage is multi-dimensional, not a yes/no flag and not a raw point count. For each pre-registered pilot polygon and each candidate reference source, report:

### Spatial distribution
- Number of valid observations and density per square kilometre, with the denominator and footprint/segment definition stated.
- Track/shot/footprint geometry, along-track clustering, gaps and distance between independent spatial blocks.
- Coverage maps and a spatial coverage statistic (for example, percentage of pre-defined spatial blocks containing usable observations); do not let dense clusters imply uniform coverage.
- For ICESat-2, report actual ATL08 segment/track coverage and quality-filtered counts. For GEDI, report actual usable footprints and quality-filtered counts. Do not infer local coverage from mission latitude limits alone.

### Temporal distribution
- Observation-date histogram and counts/percentages within 0–3, 3–5, 5–10 and >10 years of the selected DEM/reference epoch, or other bins fixed in the registration.
- Earliest/latest dates, time span, and whether the source was operating/collecting in the required period. Record known mission or acquisition gaps from authoritative metadata.
- A download date is not an observation date. Never treat the product's release date as its acquisition date.

### Stratum distribution
- Valid counts per pre-defined slope × land-cover × elevation primary stratum, with missing/unknown land-cover and slope classes shown explicitly.
- Report whether each cell meets the planned threshold and whether spatial independence is plausible.
- A cell below the threshold is marked **insufficient coverage**, not pooled post hoc into a favorable neighboring class.

### Reference quality classes
Classify reference observations before residual analysis, using metadata-defined categories such as:
- surveyed control / static GNSS;
- RTK or PPK;
- published benchmark or authoritative control;
- spaceborne lidar (ICESat-2 ATL08 or GEDI);
- other / quality uncertain.

For every class, report vertical and horizontal uncertainty, confidence level, datum/frame/epoch, processing method, quality flags and date. OPUS is a processing service/solution type, not a blanket accuracy class; record the actual solution and uncertainty. CORS data are not automatically a surveyed point at the DEM comparison location.

### Vertical-reference eligibility
A point without a documented vertical reference, transformation, and compatible epoch is **not eligible for absolute vertical validation**. Exclude it using a pre-registered rule and report the count/reason. It may be retained for a separately labeled relative or exploratory analysis only if that analysis is scientifically appropriate.

The coverage report must be committed before calculating or viewing DEM residuals. Its status may be:
- `coverage_checked`
- `reference_ready`
- `coverage_insufficient`
- `datum_limited`

## 13. Sample-size and insufficient-coverage rules

- At least 30 valid, spatially suitable observations per primary cell may be used for **exploratory** summaries only.
- At least 50 observations per primary cell is a **minimum reporting floor** for a confirmatory accuracy claim, not a guarantee of adequate power.
- Before confirmatory analysis, conduct a power/precision assessment using a justified expected error scale, spatial dependence and target confidence-interval width. Increase the sample or downgrade the claim if precision is inadequate.
- Count independent spatial blocks/effective sample size, not only raw observations. A thousand points along one track may provide much less independent information than a thousand spatially distributed controls.
- If a pre-registered region or stratum lacks coverage, report **“not evaluable with available reference data”** and preserve the original scope. Do not silently replace it after examining residuals. A replacement is allowed only through a documented amendment based on coverage/safety criteria, with the original result and reason retained.

## 14. Statistical analysis plan (freeze before residuals)

The registration must specify the primary endpoint, paired comparison design, confidence interval method and any hypothesis tests before residuals are examined.

Recommended default:
1. Primary summaries: signed bias, RMSE, MAE, NMAD, residual dispersion, absolute-error quantiles and spatial coverage, with denominators and missingness.
2. Confidence intervals: spatial block bootstrap (block size and resampling unit chosen from spatial autocorrelation/design, documented before final analysis); use a suitable alternative when the data do not support bootstrap assumptions.
3. Product comparison: paired comparisons at the same valid reference locations. Estimate the difference in the selected primary metric with a confidence interval; do not compare unrelated samples as if paired.
4. If formal tests are needed, pre-specify them. A paired permutation test or Wilcoxon signed-rank test may be considered for paired residual differences when assumptions/interpretation are appropriate. Kruskal–Wallis is not a substitute for a paired design.
5. Define the family of comparisons and control multiplicity in advance (for example, Holm family-wise correction for confirmatory comparisons or Benjamini–Hochberg FDR for explicitly exploratory families). Report raw and adjusted p-values where tests are used. Do not run dozens of unregistered tests and highlight only significant results.
6. Do not use statistical significance alone as acceptance. Define use-case-specific tolerances for bias, error/precision and coverage before analysis; if no defensible threshold exists, report the estimate and uncertainty without a pass/fail label.
7. Define outlier handling, missing-data treatment, tie handling, test direction and software/package versions before analysis. No residual-based exclusions unless explicitly pre-registered and fully reported.

## 15. Dataset release and processing freeze

For every reference source, freeze:
- Product/collection and exact release/version (for example, the specific ICESat-2 ATL08 or GEDI L2A release available at registration).
- Query/collection IDs, quality filters, geospatial footprint, processing options and download date.
- Original source metadata and checksums for downloaded files where licensing and size permit; otherwise preserve immutable identifiers, metadata and a reproducible retrieval record.
- DEM release/tile IDs, acquisition/production dates, vertical reference, checksum, resampling method and analysis code commit.

Do not hardcode a version label merely because it is mentioned in a review. Verify the selected release against the authoritative data catalog at the time of registration, then freeze it for that analysis.

## 16. Region selection rationale and limits of claim

The pilot environments are selected to span contrasting surface and terrain conditions, not because they are assumed to represent Yemen:
- Urban: tests DSM/DTM semantics and built structures.
- Steep highlands: tests slope-related error and vertical-reference sensitivity.
- Arid coastal plain: tests a comparatively low-relief environment.
- Wadi: tests narrow valley geometry, vegetation, mixed pixels and possible DEM void/filling effects.

If the wadi is omitted, GEOLOGIA must state that wadi behavior was not evaluated. Likewise, results do not cover untested coastal, island, desert, urban, agricultural or mountain environments merely because they share a broad regional label.

### What GEOLOGIA may claim

After all release gates pass, GEOLOGIA may report product performance **only** for the exact product/version, reference method/datum, time window, pilot polygon and adequately sampled strata that were evaluated, including uncertainty and limitations.

It may not claim:
- country-wide Yemen accuracy from a few pilot areas;
- accuracy in untested regions or under-sampled strata;
- that a remote sensing source is ground truth without independent quality evidence;
- that an accuracy estimate is DEM-only when datum/reference/temporal contributions have not been defensibly separated;
- that DSM performance establishes bare-earth DTM accuracy, or vice versa.

The pre-registered scope and any amendments must be visible alongside every GEOLOGIA accuracy statement.

## 17. Frozen coverage sufficiency gates (before any coverage map)

The following **operational screening thresholds are fixed for protocol version 1**. They are not universal geodetic standards and do not, by themselves, establish statistical power. Record them in the dated registration before producing coverage maps; changing any threshold requires a timestamped amendment made before viewing DEM residuals.

- Spatial density is computed on a pre-defined equal-area 1 km × 1 km grid, with valid independent reference locations—not raw lidar returns or repeated samples counted as independent. Report both total density and occupied-cell fraction. The screening floor is **20 valid locations/km² for exploratory coverage** and **40 valid locations/km² for confirmatory coverage**, but these floors cannot override the independent-block and per-stratum requirements below.
- Spatial spread is assessed on the same registered 5 km equal-area block grid: at least **20 occupied independent blocks for exploratory** coverage and **30 for confirmatory** coverage, with at least **60% of the pre-defined eligible blocks occupied for exploratory** and **75% for confirmatory** coverage. These area-coverage ratios use the full pre-registered polygon/block denominator, not a post hoc trimmed boundary. If a pilot polygon is too small to contain the required blocks, it cannot satisfy this v1 confirmatory gate; amend the design before mapping rather than changing the denominator afterward.
- To prevent a single dense cluster from representing a whole stratum, no single pre-defined spatial block may contain more than **50% of its valid observations**. If it does, mark the stratum as spatially_clustered unless a registered sampling design justifies a different block scheme before residuals are inspected.
- At least **70% of eligible reference observations** must fall within **5 years** of the DEM acquisition epoch for confirmatory temporal matching. The remainder must be reported and analyzed only under the registered temporal-mismatch rule. If the DEM acquisition epoch is unknown, the temporal gate is not met for confirmatory absolute validation.
- Each primary stratum must meet the applicable independent sample floor in Section 13 and the registered precision/power target. Meeting a raw density threshold is not a substitute for sample size, spatial distribution, reference quality, or precision.
- Coverage gates are evaluated per registered polygon, source, product epoch and primary stratum. A failed gate yields the relevant non-evaluable reason; thresholds must not be relaxed after viewing coverage or residual maps to obtain a pass.

## 18. Frozen geodetic reference and transformation manifest

Before the coverage report, freeze a transformation manifest for each DEM/reference pairing. It must identify:

- Horizontal reference frame and realization (for example, the exact WGS 84 realization or named ITRF realization), coordinate epoch, and any plate-motion/epoch transformation. A generic label such as “WGS84” without realization/epoch metadata is recorded as incomplete where that distinction materially affects the required accuracy.
- Native vertical datum/reference for the DEM and every reference source; target vertical datum; height type (ellipsoidal or orthometric); geoid/quasigeoid model name, release, grid resolution, checksum and interpolation method when used.
- Transformation operation/pipeline, direction, parameters and grid dependencies; PROJ or GeographicLib version and relevant database/grid package versions; full software environment lock or reproducible version record.
- Horizontal and vertical uncertainty before and after transformation, including uncertainty introduced by datum conversion and epoch propagation.

Do not choose EGM2008, EGM2020, a grid resolution, or a software operation after seeing DEM residuals. Select the exact model and operation based on the product's documented native reference and the reference data's documented frame, then freeze them before coverage maps. If no defensible common datum transformation exists, absolute validation is datum_undocumented or datum_limited; do not substitute a convenient global model silently.

## 19. Mixed vertical-reference policy

All eligible observations must be transformed to one registered target vertical reference using a documented, reproducible operation:

- Orthometric heights and ellipsoidal heights must not be mixed directly. Where the required geoid is known and supported, use the registered height relation (commonly orthometric height H = ellipsoidal height h − geoid undulation N, subject to the exact datum convention) and record sign convention and operation.
- EGM96 and EGM2008 observations may be harmonized only with an identified, versioned conversion/difference grid or authoritative transformation and a defensible uncertainty estimate. Add conversion uncertainty to the budget; do not assume the difference is zero or remove it by subtracting variances without valid independence assumptions.
- Local/legacy vertical datums may be included only if their realization and transformation to the target are documented and independently defensible. Otherwise they are excluded from absolute validation under the pre-registered rule and counted as datum_undocumented.
- Unknown ellipsoidal-height realization/epoch, undocumented local datum, missing geoid model, or incompatible vertical units makes a point ineligible for absolute validation. Preserve it only for clearly labeled exploratory/relative work if scientifically appropriate.
- Never silently mix EGM96, EGM2008, EGM2020, ellipsoidal heights or local datums in one absolute metric. Publish the per-source eligibility and exclusion counts.

## 20. Spatial dependence and uncertainty method (locked before residuals)

For protocol v1, the primary interval method is a **spatial block bootstrap**, not an unspecified “spatially aware CI”:

- Primary resampling unit: the registered spatial block, not individual points or lidar shots.
- Default block width: **5 km** in the registered equal-area projected CRS. Before residual analysis, inspect the sampling geometry and spatial dependence of the reference/sampling design (not DEM residuals) and record whether this block is defensible.
- Pre-registered sensitivity widths: **2.5 km and 10 km**. Report the sensitivity results alongside the 5 km primary result. If dependence clearly extends beyond 10 km or the design makes these widths inappropriate, pause and issue a dated protocol amendment before inspecting DEM residuals; do not select a block size based on the most favorable accuracy result.
- Bootstrap replicates: **2,000**, with a fixed recorded random seed. Resample spatial blocks within the registered primary stratum and preserve paired product/reference observations when comparing products.
- If there are too few independent blocks for a stable bootstrap, report precision_inadequate / spatial_support_insufficient; do not substitute point-wise bootstrap intervals. Any alternative interval method must be specified in a dated amendment before residual inspection.

Spatial cross-validation is not the default for a descriptive DEM validation. If GEOLOGIA later fits a predictive correction or model, it must use a separately registered spatial validation design (for example, buffered spatial blocks) and must not reuse calibration observations as held-out validation.

## 21. Wadi inclusion/omission decision log

The wadi environment is part of the intended four-environment design. Any decision to omit or replace it must be made **before residual inspection** and recorded with:

- decision date/time and responsible reviewer;
- named catchment/polygon considered;
- reason category: safety/security, access/permissions, logistics/equipment, or absence/inadequacy of reference data;
- supporting evidence and whether the decision changes the registered scope;
- amendment identifier and explicit statement that wadi conditions remain untested.

A practical constraint may justify omission, but it must not be concealed or presented as a scientific finding. No post-residual omission, replacement or reclassification is permitted to improve the result.

## 22. Disaggregated non-evaluable status codes

“Not evaluable” is an umbrella conclusion, not a diagnosis. GEOLOGIA must emit one or more reason codes, with counts and affected polygon/stratum/source:

- no_reference_data: no eligible reference observations found;
- insufficient_sample: fewer than the registered independent sample floor;
- spatially_clustered: spatial coverage or block-distribution gate failed;
- temporal_mismatch: reference dates fail the registered epoch window;
- datum_undocumented: vertical datum/frame/epoch or transformation is unknown or incompatible;
- reference_conflict: independent eligible references disagree beyond the pre-registered compatibility tolerance, or conflict cannot be resolved with available uncertainty metadata;
- precision_inadequate: sample exists but confidence interval/power/precision target is not met;
- source_quality_failed: source-specific quality flags or uncertainty exceed the registered eligibility limit;
- environment_omitted: the registered environment (including wadi) was not sampled.

For reference_conflict, define the comparison pair, independence assumption and tolerance before examining DEM residuals. If uncertainties are compatible and independent, a standardized difference such as the absolute difference divided by the combined standard uncertainty may be used with a pre-registered cutoff; otherwise report the conflict without forcing a pooled reference. Do not label any of these statuses as evidence that the DEM itself is inaccurate.

A stratum is evaluable only when all applicable coverage, temporal, datum, source-quality, spatial-support and precision gates pass. Record the exact failed gates and do not collapse them into one opaque status.

## 23. Decision path when coverage gates are not achievable

Failure to meet a v1 coverage gate is an expected possible outcome in Yemen, not a protocol failure and not evidence that the DEM is inaccurate. In particular, ICESat-2 ATL08 and GEDI observations follow orbital tracks and sampling footprints; they are not spatially random point samples. Repeated observations along a track, nearby footprints, and orbit-crossing concentrations must not be treated as independent areal coverage.

For each registered polygon, DEM product/epoch and primary stratum:

1. Evaluate all frozen gates at the same reporting unit that will receive an accuracy claim. A region-wide average cannot compensate for an under-sampled slope, land-cover, elevation or terrain stratum.
2. If any mandatory gate fails, retain the original gate and report the applicable non-evaluable reason codes. Do not lower the threshold, redefine the polygon, merge unlike strata, or replace the area after inspecting the coverage map to obtain a pass.
3. A separately labeled exploratory track-supported analysis may be reported only if its estimand, sampling limitations and uncertainty method were registered in advance. It must not be promoted to confirmatory areal accuracy or generalized into unobserved areas.
4. If confirmatory coverage remains insufficient, the valid result is “not evaluable under the registered design.” GEOLOGIA may recommend a new independent campaign or a new protocol version; it must not manufacture a confirmatory result from the available tracks.
5. Report coverage geometry explicitly: track/footprint distribution, orbit and repeat-cycle identifiers where available, crossing concentration, occupied spatial blocks, empty blocks and strata. A high point count concentrated at orbit crossings is not equivalent to representative coverage.

These rules are applied per DEM and per stratum. Density thresholds are not assumed achievable from satellite-track sources across all Yemen terrain.

## 24. Temporal eligibility is evaluated separately for each DEM

The five-year / 70% rule applies independently to each named DEM product and acquisition epoch, each registered polygon and each primary stratum. It is not a global rule for a collection of DEMs.

- Record the exact acquisition interval or epoch for each DEM, not merely its publication date.
- If at least 70% of eligible reference observations do not fall within the registered five-year window for that DEM, assign temporal_mismatch for confirmatory validation in that reporting unit.
- Do not relax the time window or substitute modern ICESat-2/GEDI observations to validate an older DEM such as SRTM solely to obtain an accuracy number. Such comparisons may be separately reported as temporal-change-confounded or exploratory if registered.
- For mosaics or products with heterogeneous acquisition dates, evaluate the time gate by tile/pixel epoch where reliable metadata exist; otherwise document the unknown epoch and fail the confirmatory temporal gate.

A temporally non-evaluable DEM may still be useful for historical mapping; this status does not imply poor DEM quality.

## 25. Geoid selection and comparison plan

Protocol v1 does not declare EGM2008 or EGM2020 universally correct for Yemen. The target vertical reference is selected from the documented native vertical reference of the DEM and the reference observations, not from which geoid produces the smallest DEM residual.

Before coverage maps and before DEM residual inspection:

- Freeze the candidate geoid model(s), exact release, grid resolution, checksum, interpolation method and software operation. Include EGM2008 and/or EGM2020 only where the required authoritative grids and metadata are available and compatible with the registered transformation.
- The primary transformation must match the DEM's documented vertical reference or a documented conversion to the registered target datum. If the DEM datum is unknown, classify the absolute comparison as datum_undocumented; do not infer the datum from residuals.
- As a readiness analysis, compare candidate geoid undulations at independently surveyed Yemen GNSS/benchmark locations with documented ellipsoidal heights, orthometric heights, frame/epoch and uncertainty. Report coverage, residual/bias and uncertainty for each model without using DEM residuals to select the model.
- If suitable GNSS/benchmark observations are absent or their datum/epoch is unresolved, report geoid_comparison_unavailable or datum_undocumented. Do not claim that one model is more accurate in Yemen based only on model-to-model differences.
- Geoid/model uncertainty and any transformation uncertainty must be included in the vertical uncertainty budget, with covariance treated when relevant. A model difference between two global grids is not itself an estimate of geoid error.

The selected geoid and transformation are frozen in the manifest for the entire registered analysis. Any change requires a documented amendment and a new analysis version.

## 26. Spatial block size: operational default and pre-residual review

The 5 km primary block width is an operational v1 starting value, not a universal correlation length for DEM errors. It is retained only if a pre-residual review of the sampling geometry and available reference/design information supports its use.

- Freeze the variogram/correlation diagnostic method before examining DEM residuals: estimator, distance bins, directionality, minimum pair counts and decision rule for interpreting range must be recorded.
- Where independent reference data or a defensible prior study provides a correlation-range estimate, use it to assess whether 5 km blocks are adequate. Do not estimate a favorable block width from DEM residuals and then report it as if pre-registered.
- If no independent estimate is available, retain 5 km as the declared operational default and report sensitivity at 2.5 and 10 km. State that the true residual correlation range is unknown; if sensitivity or block count indicates inadequate support, report spatial_support_insufficient / precision_inadequate.
- If the pre-residual diagnostic clearly indicates dependence beyond the registered sensitivity range, pause before residual analysis and publish a dated amendment specifying a justified block design. No post hoc selection of the block size that gives the narrowest interval is allowed.
- Different terrain/product strata may have different correlation structures. Any stratum-specific block sizes must be justified by the same pre-residual rule and frozen before its DEM residuals are inspected.

## 27. Horizontal accuracy scope

Protocol v1 validates vertical elevation accuracy only. Horizontal accuracy is outside the primary claim and must not be implied by vertical RMSE, slope agreement or visual alignment.

- Record the horizontal reference frame, realization and coordinate epoch for every DEM and reference source.
- Where horizontal uncertainty can materially affect vertical residuals on steep terrain, estimate or bound the induced vertical component using local slope and documented horizontal uncertainty, and include it in the uncertainty budget or flag the result as limited.
- A future horizontal-accuracy module requires its own registered reference design, independent horizontal control, metric and acceptance criteria. Until then, GEOLOGIA must label horizontal accuracy as not_assessed.

## 28. Field GNSS sampling and reference independence

If a field GNSS campaign is undertaken, the primary sampling design must be registered before field collection:

- Use stratified random sampling within the registered terrain/land-cover/elevation strata where feasible, with randomly generated candidate locations and documented replacement rules.
- If safety, access or permissions require convenience points or transects, label those samples as access-constrained; document the selection mechanism, excluded areas and resulting representativeness limits. Do not describe convenience samples as random or country-representative.
- Record instrument, antenna setup, occupation duration, processing method, correction source, solution quality, horizontal/vertical uncertainty, coordinate frame/realization, epoch, height type, geoid/datum conversion and raw/processed data checksums.
- Do not count repeated occupations at one site as independent spatial locations. Retain them for precision assessment at the site level.

A reference-independence register must identify for each DEM/reference pair: data lineage, source sensor/processing, whether the reference was used to calibrate/correct the DEM, shared control points, shared geoid or datum dependencies, and any known derivative relationship.

- ICESat-2/GEDI may be considered source-distinct from a DEM only after the exact product lineage and processing dependencies are checked; source-distinct does not automatically mean statistically independent.
- A local DEM, benchmark surface or corrected product derived from the candidate DEM or from shared control data is not an independent validation reference for that candidate.
- GNSS heights converted with a geoid share uncertainty with that geoid model. Record this dependency and include covariance/shared uncertainty where material.
- If independence cannot be established, label the comparison reference_dependency and restrict it to consistency/relative analysis, not independent accuracy validation.

## 29. Protocol amendment governance

Any change to a frozen threshold, sampling design, polygon, time window, geoid/datum operation, block size, source quality filter, exclusion rule or acceptance criterion must create a versioned amendment containing:

1. rationale and supporting evidence;
2. date/time and author/reviewer approval;
3. exact prior and new rule;
4. whether coverage maps, source availability, or DEM residuals had already been viewed;
5. affected products, polygons, strata and analyses;
6. whether results are exploratory, confirmatory, or superseded.

Amendments made after viewing coverage but before residuals must be clearly marked as coverage-informed and cannot be represented as fully blind pre-registration. Amendments after residual inspection are post hoc; the original registered result remains reported, and the amended analysis is labeled exploratory or a new independent confirmation is required. Preserve all protocol versions and decision logs in the release.

## 30. Purpose-specific point-level independence matrix

Independence is assessed for each observation/reference point (or point-level lineage group) relative to a specific validation purpose and candidate product. A source-wide label such as independent GNSS is insufficient.

For every point or point group, the readiness register must identify its dependencies and assign one of these statuses for each purpose:

| Purpose | Independent | Not independent | Conditional / unresolved |
|---|---|---|---|
| DEM vertical validation | Not used to calibrate, correct, select or tune the candidate DEM; no material shared control/derivative dependency | Used in candidate DEM calibration/correction, or derived from it/shared controls | Product lineage, correction history, or shared controls cannot be verified |
| Geoid validation | Not used to fit, calibrate or validate the candidate geoid; height/datum evidence is independently surveyed | Used in geoid fitting/calibration or shares the same control data in a circular comparison | Geoid, datum, frame/epoch or control lineage is unclear |
| Horizontal validation | Independent horizontal control not used to georeference/correct the candidate | Used in georeferencing/correction or shares the control points | Horizontal control lineage or coordinate realization is unresolved |
| Temporal/change validation | Independent observation with a documented date and change history | Used to construct the temporal correction/label being evaluated | Date, epoch or intervening-change history is uncertain |

This matrix is applied per candidate product and intended claim; the same point may be independent for one purpose and non-independent for another. Record point/reference ID, purpose, candidate product/version, status, rationale, evidence/lineage, reviewer and date. A conditional or unresolved status cannot support a confirmatory independent-accuracy claim until resolved. For dense sources, use a documented lineage group (such as a survey campaign, track segment or shared-control cluster) and preserve its mapping to observations. Shared geoid, sensor, processing, calibration and spatial/temporal dependencies must be carried into uncertainty/covariance or explicitly limit the claim.

## 31. Cross-sensor dependence: ICESat-2 and GEDI

ICESat-2 and GEDI are different missions and instruments, but their agreement is not automatically independent confirmation. Both are spaceborne lidar observations and may share relevant error mechanisms or environmental sensitivities, including slope/terrain effects, canopy/footprint effects, atmospheric corrections, geolocation and processing assumptions. Correlated errors may produce agreement while both differ from the true surface.

- Report ICESat-2–GEDI agreement as cross-source consistency, not as two fully independent votes for DEM accuracy, unless the specific error dependencies have been assessed and justified.
- In steep/high-relief terrain, do not treat their agreement alone as successful independent validation. Seek a reference from a materially different measurement approach where feasible (for example, independently surveyed GNSS/benchmarks, suitable airborne lidar, or independently processed SAR/interferometric evidence with its own limitations).
- Document instrument/product lineage, quality filters, terrain and canopy sensitivities, geolocation/footprint uncertainty, and known shared or correlated error sources for each pairing.
- If no technically independent reference method is available, retain the comparison as consistency evidence and label the independent-validation gate reference_dependency or not_evaluable; do not upgrade it to independent accuracy validation.

## 32. Reference DEM policy and resolution/accuracy ceiling

A DEM is not a primary independent reference in protocol v1. The primary reference types are point/footprint observations with documented quality and datum (such as eligible GNSS/benchmarks and qualified satellite-lidar observations), subject to the independence and coverage gates above.

If a reference DEM or gridded elevation surface is proposed in a later version:
- Treat it as a secondary comparison source unless its independent acquisition, processing lineage and validation are documented.
- Register its exact product/version, spatial resolution, effective support/footprint, vertical accuracy and uncertainty by relevant terrain/land-cover strata, datum/frame/epoch, acquisition date, calibration/control lineage and checksum.
- State explicitly that the reference uncertainty and spatial support limit what errors in the candidate DEM can be resolved. Nominal pixel spacing (for example, 5 m) is not equivalent to 5 m accuracy and does not establish a particular vertical-error floor.
- Do not claim the candidate DEM is validated below the reference's defensible uncertainty/precision or infer a numerical detection threshold without a propagation/power analysis.
- A reference DEM derived from the candidate DEM, its corrections, or shared control points is not independent for that comparison. Use it only for labeled consistency/relative analysis unless independence is established.

Any reference-DEM use requires a versioned protocol amendment before residual inspection.

## 33. GEDI operational and temporal availability

The readiness report must verify GEDI's actual operational/data-collection status and the selected product's observation dates from authoritative mission/product metadata at the time of registration. Do not assume a mission-wide status or availability from a prior statement, and do not treat a processing/release date as the acquisition date.

- Report GEDI's usable observation-date range and coverage separately for each pilot polygon, DEM epoch and stratum.
- Apply the registered temporal eligibility rule to each DEM independently, without silently excluding GEDI or relaxing the time window solely to obtain a pass.
- If GEDI observations do not meet the registered temporal gate for a given DEM/stratum, mark temporal_mismatch for that confirmatory pairing; retain suitable older observations only for a separately labeled temporal-consistency or exploratory analysis if registered.
- Record the effect of mission collection gaps or operational changes on coverage and explain whether ICESat-2/GNSS or another independent method is needed to fill the reference-design gap. Do not assume another source provides equivalent spatial representativeness.

## 34. Pre-registration timestamp and immutable archive

After PR #57 is merged, publish the exact protocol version as a release/tag and archive that version with a persistent identifier where possible (for example, a Zenodo or OSF deposit with DOI or stable accession).

The archive record must include:
- Exact Git commit SHA, release/tag, protocol file checksum (SHA-256), and release date/time in UTC.
- The complete protocol and associated registration metadata, not merely a mutable repository link.
- Archive DOI/stable identifier and repository URL, with the archive's versioning and preservation terms.
- Any later amendment as a new version linked to the original; never overwrite the original registration.

A GitHub commit/tag provides a useful public timestamp and version history, but the persistent archive strengthens citability and preservation. Do not claim that the protocol was registered before data collection or residual inspection unless the timestamped record and project chronology support that statement. If coverage/source availability was already examined, label the document accurately as a protocol or pre-analysis plan informed by coverage—not as a fully blind preregistration.
