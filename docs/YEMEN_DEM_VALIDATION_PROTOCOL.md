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

## 35. Operational disposition of unresolved independence

Any observation or lineage group whose independence status is conditional, unresolved or unknown is excluded from the primary confirmatory independent-accuracy dataset. It may be retained in a separately labeled exploratory/consistency dataset, with its status and reason attached to every result. It must not be silently pooled with eligible observations.

An unresolved observation may be promoted to confirmatory eligibility only after written, dated evidence resolves the relevant dependency for the specific candidate product and validation purpose; the register must record the reviewer and evidence. If the dependency cannot be resolved, keep it excluded. Sensitivity results with and without unresolved observations may be reported only as secondary analyses and cannot override the primary eligibility decision.

## 36. Spatial support and scale matching for reference observations

Each comparison must document the spatial support of both measurements, not only their nominal resolution:
- DEM pixel size, grid alignment, resampling history and the elevation statistic represented by the cell (as documented or operationally defined).
- Reference support type and effective dimensions: point/occupation, footprint, segment/profile, or aggregated area; include the product-specific footprint/segment definition and uncertainty from authoritative product metadata.
- Reference geolocation uncertainty, position within the DEM cell, local slope/roughness and whether the reference support crosses multiple terrain/land-cover classes.

A point, lidar footprint, along-track segment and DEM cell do not necessarily measure the same spatial quantity. Before residual calculation, register a support-matching rule for each reference type and DEM resolution. Where justified, aggregate DEM elevations over the reference support using a pre-declared statistic and sampling method; alternatively, use a pre-declared point-to-cell rule and explicitly label the support mismatch. Do not choose the aggregation statistic after viewing residuals.

In steep or heterogeneous terrain, assess scale mismatch using the local DEM/reference terrain gradient and within-support elevation variability, with the method and neighborhood fixed before residual inspection. Include a defensible scale/geolocation contribution in the uncertainty budget where it can be quantified. If it cannot be quantified and is material to the intended claim, mark the pairing scale_limited or not_evaluable rather than attributing the mismatch to DEM error. Do not assume a universal numeric error floor from nominal pixel spacing or footprint size.

## 37. Archive and analysis chronology fields

The protocol registration and final readiness/validation record must explicitly record, in UTC where available:
- protocol commit SHA, protocol file SHA-256, release/tag and archive timestamp/identifier;
- date/time of the first inspection of reference-source availability or coverage geometry for the registered study area;
- date/time of the first generation or inspection of any candidate DEM–reference residual, including exploratory residuals;
- date/time and scope of each amendment, coverage-informed decision and archive update.

The claim of fully prospective preregistration is permitted only if the immutable archive timestamp precedes both the first coverage/source-availability inspection relevant to the registered design and the first residual calculation/inspection. If coverage was inspected first, describe the record as a coverage-informed protocol or pre-analysis plan; if residuals were inspected first, identify it as post hoc and preserve the original chronology. Do not backdate, overwrite, or imply that a later archive proves an earlier blind registration.

## 38. Cross-source disagreement: ICESat-2 versus GEDI

Before residual analysis, define the spatial/temporal matching window, quality filters, uncertainty compatibility rule and comparison statistic for overlapping ICESat-2 and GEDI observations. Do not select the matching window or tolerance after inspecting which source agrees better with the candidate DEM.

If matched ICESat-2 and GEDI observations disagree beyond the pre-registered compatibility criterion, classify the affected point/lineage group as reference_conflict and reference_uncertainty for the candidate pairing. The disagreement is not, by itself, evidence that the DEM is wrong or that either lidar source is wrong.

- Exclude the conflicted pair from the primary confirmatory independent-accuracy dataset until the conflict is resolved using documented quality/uncertainty evidence or a materially independent reference method.
- Retain and report the disagreement, both source estimates, their uncertainty metadata, matching geometry and reason for unresolved status in the readiness/quality report.
- Do not choose whichever lidar agrees with the DEM, average the two sources automatically, or count agreement elsewhere as a reason to dismiss a local conflict.
- If no defensible resolution is possible, keep the location non-evaluable for confirmatory validation; a separately labeled sensitivity/consistency analysis may show each source independently but must not be presented as a resolved reference.


## 39. Regional and non-global DEM candidate screening (Yemen v1)

This section is a **candidate-screening register**, not a ranking of Yemen accuracy. A product's country of origin, nominal grid spacing, or accuracy reported in another country does not establish its accuracy in Yemen.

### 39.1 Yemen-coverage candidates

The primary open comparison remains the exact, obtainable versions of Copernicus GLO-30, ALOS AW3D30 and FABDEM, subject to licensing and product-semantic checks. Record tile/version, native grid, surface type, datum, source lineage and license before analysis. FABDEM is derived from Copernicus GLO-30 and is therefore a useful alternative terrain representation, but **not an independent reference** against Copernicus; shared source errors and correction effects must be disclosed. Published comparative studies show that relative performance varies by land cover and slope, and FABDEM may be less favorable than GLO-30 in steep terrain. Do not import a study's ranking as a Yemen result.

### 39.2 Chinese Arabian Peninsula 30 m DEM (NCD)

The National Cryosphere Desert Data Center lists a 30 m Arabian Peninsula DEM dataset, with access conditions and source lineage to be checked at acquisition. It may be catalogued as a **regional supplementary elevation layer** after obtaining its actual metadata and file. The reported vertical accuracy of approximately 20 m has not yet been independently confirmed from an authoritative product specification and local validation record in this protocol. Therefore:

- Do not accept it as a primary vertical reference or claim it is more accurate than GLO-30/AW3D30.
- Do not permanently exclude it solely on an unverified quoted accuracy figure. If the authoritative specification confirms an error level unsuitable for the target use, classify it as non-competitive for that use, while retaining it for visualization or contextual comparison if appropriate.
- Record access restrictions, complete data lineage, version, vertical datum, reported accuracy metric/confidence level, test geography and independent control source.

Catalog record: https://www.ncdc.ac.cn/portal/metadata?af=SRTM30&current_page=1&org=Platform+service+center

### 39.3 Chinese sensors/products without a public Yemen-ready product

Gaofen-7 and LuTan-1 may be discussed in the literature/technology review, but do not enter the Yemen candidate comparison unless an actual product covering the pre-registered pilot area is obtainable with documented license, metadata, processing lineage and reference validation. A sensor's local test accuracy or a China-only product does not establish a public, globally available Yemen DEM.

### 39.4 Saudi national 5 m DEM — regional case study only

A published Makkah study evaluated a 5 m national DEM against 200 first-order GPS control points and reported mean height difference 0.01 m and standard deviation 2.95 m. This is evidence for that product and study area, not Yemen. The value 2.95 m is not a universal accuracy ceiling, transferable performance estimate, or acceptance threshold for Yemen. If the dataset and permission become available, document its actual footprint and use only for a separate cross-boundary/neighboring-region case study; do not include it as Yemen coverage unless it physically covers the pre-registered Yemen sites.

Reference: https://indianjournals.com/article/ijggs-1-4-010

### 39.5 WorldDEM Neo — commercial candidate, not v1 open baseline

WorldDEM Neo is a commercial Airbus elevation product with approximately 5 m grid spacing and global/off-the-shelf coverage subject to restrictions and ordering. Product documentation describes DSM/DTM offerings; the exact ordered product, surface semantics, area restrictions and license must be confirmed. Published specification sources do not present a single fully consistent vertical-accuracy figure: one distribution specification reports 1.4 m LE90, while NASA's CSDA vendor summary reports <2.5 m absolute vertical LE90. Record the exact official technical product description and quote its metric/version before using any number. These figures are not RMSE and must not be compared directly with RMSE values.

WorldDEM Neo may be listed in a **commercial procurement/benchmarking** section, but it is excluded from the open/free v1 baseline unless an appropriate license is obtained. If acquired, test it against independent Yemen reference data; do not assume superiority from nominal resolution or vendor specification alone.

References:
- https://api.oneatlas.airbus.com/guides/worlddem/g-wd-about/
- https://science.nasa.gov/earth-science/csda/vendor-airbus/
- https://docs.up42.com/data/worlddem-neo

### 39.6 Decision rule

Candidate status is assigned per product and purpose:

- **Primary open comparison:** obtainable products with Yemen coverage and documented version/semantics (currently GLO-30, AW3D30 and FABDEM, subject to license and data-readiness checks).
- **Supplementary regional layer:** product covers Yemen but metadata, lineage, access or local accuracy evidence is insufficient for primary ranking (e.g., NCD Arabian Peninsula DEM until verified).
- **Regional case study:** product has a documented validation in a neighboring/similar region but no Yemen coverage (e.g., Saudi national 5 m DEM).
- **Literature-only technology:** sensor or national product without an obtainable Yemen-ready dataset (e.g., GF-7/LuTan-1 claims absent a matching deliverable).
- **Commercial benchmark:** obtainable only under paid/restricted terms (e.g., WorldDEM Neo).

No candidate may be promoted to primary independent reference solely because it has finer pixels, a better quoted accuracy in another geography, or a different national origin. The primary validation reference remains independently sourced and assessed under Sections 4 and 30–38.


## 40. Published accuracy metrics, product specification context and candidate status

### 40.1 Metric comparability is a hard reporting rule

Do not directly rank or numerically compare published accuracy values that use different metrics or definitions (including LE90, RMSE, MAE, standard deviation/STD, CE90, and bias) unless a documented conversion is valid for the source distribution and assumptions. In particular:

- LE90 is a 90th-percentile absolute-error statistic under the product's stated definition and validation convention; it does not by itself identify bias, dispersion, or the residual distribution.
- RMSE is the square root of mean squared residuals and is sensitive to large errors; it combines bias and residual dispersion unless explicitly decomposed.
- MAE, standard deviation and bias describe different properties and are not interchangeable with either LE90 or RMSE.
- Do not convert LE90 to RMSE using a generic factor unless the distributional model, bias treatment, sample and confidence convention are justified and recorded. If not, state **not directly comparable**.

When a product specification reports LE90 and an external study reports RMSE, any discussion of their relative magnitude must be labeled **indicative/contextual only**, not a product ranking or evidence that one product is more accurate. Keep metric-specific columns and do not sort mixed metrics into a single accuracy leaderboard.

### 40.2 Product-specification provenance and scope

For every quoted manufacturer/provider accuracy claim, readiness metadata must preserve:

- Exact product name, product type (DSM/DTM), release/version and relevant processing baseline.
- Official specification/document URL, document title/version and publication or access date.
- Exact metric and inequality/value as stated, confidence/percentile convention, and whether the statistic is absolute or relative.
- The stated reference vertical datum/frame and definition of absolute accuracy, where disclosed.
- Validation geography, terrain/land-cover conditions, reference method, sample design and known limitations, where disclosed.
- Whether the specification describes global performance, a particular test area, or a vendor-defined validation sample; record **not disclosed** rather than infer missing context.

A quoted global or vendor specification is a product-level context claim, not a Yemen-specific accuracy result. Do not use it as a default acceptance threshold or as a substitute for local validation. For Copernicus GLO-30, preserve the exact applicable release/specification and its stated LE90 convention; the commonly quoted <4 m LE90 must not be treated as RMSE or as demonstrated performance in Yemen.

### 40.3 Saudi 5 m DEM — conditional terrain representation

The Makkah result is a regional case study only. Before citing it as relevant to a Yemen terrain class, characterize the study footprint using documented slope, elevation, land-cover/built-up composition and reference-point distribution, to the extent the publication or data permits. Explicitly state which Yemen class it may inform (if any) and which it does not represent. Do not generalize it to all western highlands, and do not treat it as representative of Tihama, wadis, or other Yemen environments without evidence of terrain/land-cover and sampling comparability. If the study does not report sufficient terrain statistics, mark representativeness **unquantified**.

### 40.4 Reconsideration trigger for GF-7 and LuTan-1

Review the literature/access status at each documented candidate-inventory update. Reconsider GF-7 or LuTan-1 for the Yemen candidate list only when at least one trigger is met:

1. A public or otherwise lawfully obtainable DEM product is released that demonstrably covers a pre-registered Yemen pilot area; or
2. Raw/processing-level data are lawfully obtainable and GEOLOGIA has a documented feasible processing route for the pilot area.

Record review date, trigger evidence, access/license, coverage, metadata, processing requirements and decision. A sensor publication or accuracy result from a non-Yemen test area alone does not trigger inclusion in the candidate comparison.

### 40.5 Candidate exclusion and unresolved-status reason codes

The readiness report must store status separately from a structured reason code; do not collapse all non-eligible products into one “rejected” label. Initial controlled codes:

- geographic_coverage_missing — no coverage of the defined pilot area.
- accuracy_requirement_not_met — a pre-declared, use-case-specific accuracy requirement is demonstrably not met by a compatible metric and applicable evidence. Do not invent a universal 10 m threshold or compare incompatible metrics to decide this.
- license_incompatible — terms do not permit the intended use, redistribution or workflow.
- technical_format_incompatible — data cannot be read/transformed by the supported workflow, with the limitation recorded.
- source_dependence_conflict — lineage overlaps with another candidate/reference in a way that prevents the intended independent comparison.
- temporal_mismatch — acquisition/epoch is incompatible with the declared reference/use case and cannot be adequately handled.
- metadata_insufficient — required product/version/datum/metric/lineage information is missing.
- access_unavailable — required data cannot currently be obtained lawfully or reliably.
- not_assessed — screening has not been completed.
- unresolved — evidence is conflicting or insufficient for a defensible decision.

A product may carry multiple reason codes. Preserve source evidence, reviewer, timestamp and disposition for each. unresolved or metadata_insufficient is not a claim that the product is inaccurate; it means GEOLOGIA cannot currently establish eligibility. Any accuracy threshold must be set before examining local residuals and must be tied to a declared use case.


## 41. Declared v1 use scope and fitness-for-purpose

### 41.1 Primary declared use

For v1, GEOLOGIA evaluates DEM products as **regional reconnaissance-scale elevation inputs for geological and geomorphological interpretation** in explicitly named Yemen pilot areas. The validation objective is to characterize vertical agreement, bias, terrain-shape behavior, surface semantics and spatial/temporal limitations against eligible independent references. The result is a product-and-area-specific evidence statement to help users decide whether a DEM is suitable for this declared reconnaissance purpose; it is not a universal product ranking.

The primary v1 assessment is not a certification for every downstream operation. A product's readiness is evaluated for the tuple **(exact product/version, pilot area, declared task profile, reference/data conditions)**. Readiness for one tuple must not be transferred to another product version, area, terrain stratum or task profile without evidence.

### 41.2 Explicitly out-of-scope uses

Unless a separate task-specific protocol and validation dataset are approved, v1 readiness does **not** establish suitability for:

- production of precise topographic contour maps at a specified cartographic scale;
- cadastral, surveying, construction, engineering design or other safety-critical elevation decisions;
- detailed catchment, channel, flood-routing, hydraulic or drainage-network modelling where channel geometry and hydrological conditioning are decisive;
- detection or quantification of elevation change, landslide movement, erosion, subsidence or other time-dependent processes;
- claims of horizontal positional accuracy, which remains outside the v1 validation estimand;
- any country-wide accuracy or fitness claim beyond the actually evaluated pilot polygons and strata.

These uses may be supported by future, separately registered validation profiles. They must not inherit a v1 pass label.

### 41.3 Task-specific interpretation within v1

Geological/geomorphological reconnaissance may include terrain visualization, broad landform interpretation and preliminary regional slope/relief screening, subject to the reported resolution, surface type, slope strata, reference quality and uncertainty. A DEM that performs acceptably in broad regional relief may still be unsuitable for local scarps, narrow channels, small landslide features or other sub-pixel phenomena. Such limitations must be stated at the relevant scale.

Hydrological and channel-related observations in v1 are descriptive/exploratory only. A general vertical-accuracy result does not demonstrate channel elevation fidelity, flow connectivity, culvert/bridge handling, sink treatment or flood-model suitability. A future hydrology profile must define channel-specific reference coverage, conditioning procedures, spatial support and task-relevant outcomes before any readiness decision.

Temporal change detection requires at least two appropriately dated and co-registered elevation surfaces plus a change-detection uncertainty model and independent temporal evidence. A single-epoch DEM accuracy assessment cannot establish change-detection readiness.

### 41.4 Fitness-for-purpose decision rule

“Ready” means **the exact product/version meets the pre-declared requirements of the named task profile for the evaluated area and strata, with adequate reference quality, coverage, uncertainty and license/technical eligibility**. It does not mean “best DEM”, “accurate everywhere”, or “ready for all GEOLOGIA tools”.

Before residual inspection, each task profile must declare its operational scale, required spatial support, relevant terrain/land-cover strata, vertical and (if applicable) horizontal tolerances, temporal window, surface semantics (DSM/DTM), required confidence/precision, and the evidence needed to assess each requirement. Numeric tolerances are set from the task's scientific or operational needs and documented source requirements; this protocol imposes no universal metre threshold. If a defensible requirement or compatible evidence is unavailable, report the relevant dimension as **not assessed** or **not evaluable**, not pass/fail.

The readiness report must therefore show a separate disposition for each product × pilot area × task profile, using at least: ready_for_declared_use, conditional_limited_use, not_ready_for_declared_use, not_evaluable, or not_assessed. Each disposition must cite the requirement, evidence, limitations, reason codes, reviewer and timestamp. A product may be ready for regional reconnaissance while remaining not assessed or not ready for detailed hydrology, contouring or change detection.


### 41.5 Intended primary user and interpretation boundary

The primary intended user of the v1 assessment is a **geological researcher or geospatial analyst preparing regional exploratory geological/geomorphological maps and interpretations** for research, screening and hypothesis development. The assessment is written to support that professional analytical workflow; it is not a general-purpose assurance statement for every GEOLOGIA platform user, public end user, government land-use decision-maker, or engineering practitioner.

GEOLOGIA may display the assessment to other audiences, but the interface and exported report must preserve the intended-user statement, evaluated area, task profile, limitations and disposition together. A bare “ready” label must never be shown without its declared use and scope. Any government planning, operational land allocation, infrastructure, engineering or other materially different decision context requires a separately specified task profile and fit-for-purpose assessment before the product is represented as suitable for that context.

## 42. Terrain representativeness of the Makkah 5 m DEM case study

This section defines how the Makkah study may, and may not, inform interpretation of Yemen terrain classes. It does not transfer the study's reported accuracy to Yemen and does not create a Yemen DEM ranking.

### 42.1 What the published study actually establishes

Mirza, Dawod and Al-Ghamdi (2011) describe a Makkah metropolitan study area of approximately 1,593 km², bounded by 39°35′–40°02′ E and 21°09′–21°37′ N. The paper describes the metropolitan terrain as complex and notes several mountainous areas. It reports 200 first-order terrestrial GPS control points with known orthometric heights distributed across the metropolitan study area.

The paper reports the following elevation ranges for the DEM surfaces, which must not be mistaken for the distribution of the 200 GPS control-point elevations:

| Dataset surface | Published elevation range | Interpretation |
|---|---:|---|
| ASTER DEM | 117–914 m | Raster-surface range reported by the study |
| SRTM3 DEM | 84–933 m | Raster-surface range reported by the study |
| National 5 m DEM | 80–982 m | Raster-surface range reported by the study |

The publication does not provide a machine-readable control-point file, a tabulated elevation distribution for the 200 control points, a quantitative slope-class distribution for those points, or a quantified land-cover composition of the point sample. The map showing control-point locations is not a substitute for those missing point-level data. Accordingly, the study's terrain representativeness for a specific Yemen stratum is **unquantified** until the original point data and suitable ancillary characterization data are obtained and checked.

### 42.2 Required comparison dimensions

A representativeness assessment must compare the Makkah study sample and the target Yemen pilot stratum using the same documented definitions and spatial support. Record at least:

| Requirement | Value to report | Source | Note |
|---|---|---|---|
| Study footprint | Published polygon/bounds and area | Original study and georeferenced study boundary | The published bounds are not the control-point distribution |
| Control-point sample | Valid point count, coordinates, spatial blocks and point-level elevations | Original GPS control data and study metadata | The paper reports 200 points but does not publish a reusable point table in the cited text |
| Elevation distribution | Min, max, median, quartiles and declared elevation-bin proportions | Original point elevations; target Yemen reference data | Do not substitute DEM-wide elevation extrema for point elevations |
| Slope distribution | Slope definition, derivation surface, support, class counts and proportions | Independently documented terrain characterization for both areas | Do not derive the comparison from the DEM being evaluated |
| Land-cover composition | Class definitions, observation date, sample counts and proportions | Date-appropriate authoritative land-cover data or documented interpretation | Urban/built-up, agricultural/vegetated, bare, water/shoreline and unknown must remain distinguishable |
| Spatial sampling | Point density, spatial-block occupancy, clustering and unsampled areas | Original point coordinates and pilot polygon | A nominal total of 200 does not establish uniform or independent coverage |
| Surface semantics | DSM/DTM status and correspondence to control-point surface | Exact product metadata and survey description | Urban structures and vegetation can create semantic mismatch |
| Temporal compatibility | Survey date, DEM acquisition/production date and land-cover observation date | Original study metadata and product records | Publication date is not acquisition date |

### 42.3 Reproducible representativeness procedure

When original control-point coordinates and suitable ancillary data are available:

1. Freeze the exact Makkah study footprint, original GPS point set, target Yemen pilot polygon, coordinate reference systems, terrain-class definitions and ancillary-data versions before examining DEM residuals.
2. Characterize both point samples using the same independently sourced elevation, slope and land-cover layers. Do not use the candidate DEM under evaluation as the sole source for the terrain covariates used to establish its own representativeness.
3. Match spatial support to the intended comparison. Record whether covariates are sampled at point locations or summarized over a declared neighborhood/footprint; do not silently mix point and raster-cell support.
4. Report sample counts, missingness, empirical distributions, class proportions, quantiles and spatial-block coverage separately for Makkah and each Yemen target stratum.
5. Quantify distributional overlap and differences using named statistics selected in the pre-analysis record. State their definitions, units, sample sizes and uncertainty. Do not invent universal cutoffs for elevation difference, slope similarity or land-cover proportion.
6. Set any threshold for calling two environments sufficiently comparable from the declared geological/geomorphological task and a cited methodological or operational requirement before viewing DEM residuals. If no defensible threshold exists, publish the descriptive comparisons without a pass/fail representativeness label.

### 42.4 Permitted interpretation and current disposition

Until the missing point-level terrain characterization is obtained, assign the Makkah case study:

- \`representativeness_status = unquantified\`
- \`evidence_scope = urban_metropolitan_study_with_complex_and_mountainous_terrain\`
- \`transfer_to_yemen_accuracy = prohibited\`

The study may be cited as a neighboring-region case study demonstrating that a national 5 m DEM was evaluated against first-order GPS controls in a complex urban/metropolitan setting in western Saudi Arabia. It may motivate a future comparison with a Yemen urban or urban-adjacent mountainous task profile, but it does not establish that the study sample represents Yemen's western highlands, Tihama coastal plain, wadis, agricultural areas or any other Yemen class.

If point-level data later become available, the status may be revised only through a dated, evidence-linked amendment reporting the full comparison dimensions above. A partial match must be named as partial and limited to the dimensions and strata actually supported. Missing evidence remains \`unquantified\`; it must not be converted into either a claim of representativeness or a claim that the Saudi product is unsuitable.

Reference: Mirza, M., Dawod, G. and Al-Ghamdi, K. (2011), “Accuracy and relevance of Digital Elevation Models for Geomatics applications – A case study of Makkah Municipality, Saudi Arabia,” *International Journal of Geomatics and Geosciences*, 1(4), 803–812. The original paper reports the study footprint, sample count, terrain description and DEM elevation ranges; it does not supply the point-level terrain distributions required for a quantitative transferability test.

### 42.5 Cross-border southern highlands: Saudi regional analogues

The southern Asir–Sarawat highlands and the western Yemeni highlands form a connected regional physiographic belt along the western Arabian Peninsula. The USGS regional synthesis describes the Great Escarpment and adjacent highlands extending south through the Asir highlands into Yemen, overlooking the Red Sea coastal plain and the Tihama sectors. This supports treating selected southern Saudi terrain as a **regional geomorphic analogue candidate** for selected Yemen pilot strata.

This regional continuity is a reason to include Saudi comparison areas, not a substitute for measured terrain equivalence. It does not establish that all Asir, Najran and Yemen terrain classes are interchangeable. Najran includes both elevated western terrain and lower eastern basin/plains; these must not be collapsed into one “mountain” class. Geological terrane correlations across the southern Arabian Shield also retain documented uncertainties and must not be inferred solely from geographic adjacency.

Apply the following comparison design:

| Saudi comparison area | Yemen comparison target | Initial status | Required evidence before a representativeness claim |
|---|---|---|---|
| Asir western highlands / Sarawat escarpment | Yemen western highlands / Sarawat escarpment | Priority regional analogue candidate | Comparable elevation and slope distributions, land-cover composition, lithology/geomorphic setting, spatial support and independent source coverage |
| Asir western escarpment and foothills | Yemen western escarpment and foothills | Priority regional analogue candidate | Separate escarpment from foothill strata; quantify relief, slope, drainage dissection and surface cover |
| Najran western mountainous belt | Adjacent northern Yemeni highland strata, where geographically and geomorphically appropriate | Conditional analogue candidate | Demonstrate continuity and comparable terrain distributions using actual coverage on both sides of the border |
| Najran basin, Wadi Najran and eastern plains | Yemeni interior basins or wadi/plain strata only where independently shown comparable | Separate basin/wadi comparison; not a highland proxy | Compare basin position, alluvial setting, slope, elevation, drainage and land cover |
| Makkah metropolitan study | Yemen urban/urban-adjacent terrain only where task and terrain conditions match | Separate urban/metropolitan case study | Original control-point data and point-level terrain characterization remain required; no transfer of its reported accuracy |

The Saudi national 5 m DEM discussed in the Makkah publication remains a **Makkah study product/evidence item** unless an exact, independently documented product release is obtained that demonstrates coverage of Asir or Najran. Do not describe it as an Asir/Najran DEM, a Saudi-wide 5 m coverage, or a satellite acquisition merely because it is called a national DEM in the paper. For any Saudi product proposed for cross-border comparison, record the exact product name, producer, release/version, acquisition or compilation method, coverage polygon, resolution, DSM/DTM semantics, vertical datum, license, checksum and access date. Coverage must be verified from the actual file or authoritative coverage metadata.

The current scientific decision is therefore:

- Include Asir/Sarawat and selected Najran terrain as **priority Saudi regional comparison areas** in the study design.
- Treat regional physiographic continuity as the rationale for comparison, not as a completed representativeness result.
- Keep each terrain stratum separate; do not use Najran's basin/plains to represent mountain terrain or vice versa.
- Mark each Saudi–Yemen stratum pair as unquantified until the required matched terrain data are available and analyzed.
- Do not transfer the Makkah study's reported 5 m DEM accuracy statistics to Asir, Najran or Yemen.
- Do not issue a DEM product ranking until the previously defined product-file, regional-coverage and independent-reference gates pass for the relevant region and terrain class.

The USGS regional synthesis supports the broad physiographic continuity of the western highlands and Great Escarpment into Yemen. It does not establish quantitative terrain equivalence or DEM accuracy transfer. Published work on the southern Arabian Shield also notes that detailed terrane correlation near the Saudi–Yemen border remains uncertain where critical field and geochronological data are sparse.

### 42.6 Separate actual product coverage from proposed analogue geography

Every Saudi comparison record must distinguish two non-interchangeable geographic concepts:

- `actual_coverage`: the geographic footprint demonstrably covered by the exact product file/release being assessed. Record the coverage polygon or authoritative footprint identifier, source of the footprint, spatial resolution, tile identifiers, coverage-verification method, verification date and evidence reference. A study-area boundary or a regional name is not proof that a product file covers that area.
- `analogue_region`: a proposed geographic area selected for geomorphological comparison (for example, Asir western highlands, Sarawat escarpment, Najran western mountains, Najran basin/Wadi Najran/eastern plains, or the Makkah metropolitan study area). Record the rationale and the paired Yemen target stratum separately. This field expresses a comparison hypothesis, not product coverage.

For the currently cited Makkah study, the documented study footprint remains the Makkah metropolitan area described in Section 42.1. It must not be expanded to Asir or Najran without an exact product release and authoritative coverage evidence. If the product footprint is not independently available, set `actual_coverage_status = unverified`; do not infer coverage from the product's “national” label or from the study's regional context.

### 42.7 Measurable test of each Saudi–Yemen analogue pair

Treat each proposed Saudi–Yemen pair as a testable geomorphological hypothesis. Before interpreting a pair as representative, freeze the data sources, dates, spatial support, class definitions and comparison statistics for both sides. At minimum, evaluate:

- Elevation distribution: declared range, quantiles and elevation-class proportions.
- Slope distribution: slope algorithm, input surface/resolution, neighborhood/support, class proportions and distributional differences.
- Drainage dissection: drainage-density definition and units, flow-accumulation threshold, channel/extraction method, contributing-area basis and uncertainty. Do not compare drainage-density values generated with materially different extraction settings as if equivalent.
- Land cover: class scheme, observation date, spatial resolution and class proportions, with unknown/mixed classes retained.
- Where the task requires it, add local relief, aspect, lithology/geomorphic setting, basin position, aridity or other justified covariates; declare these before analysis rather than selecting them after seeing a favorable match.

Keep the following strata separate in the analysis: Asir western highlands; Asir escarpment and foothills; Najran western mountainous belt; Najran basin/Wadi Najran/eastern plains; and the Makkah metropolitan study. Pair each only with a named Yemen target stratum supported by geographic and geomorphic rationale. In particular, Najran basin and eastern plains are a separate basin/wadi/plain comparison and must not stand in for the western mountain belt.

Report the paired distributions, sample sizes, missingness, spatial support, dates and uncertainty. Use named distributional comparison statistics and any task-specific equivalence margins fixed before examining DEM residuals. Visual similarity, geographic proximity or continuity of a mountain chain may justify testing a pair, but cannot by themselves establish quantitative representativeness. If the required matched data are unavailable, retain `representativeness_status = unquantified`; this is absence of evidence, not evidence of unsuitability.

## 43. Implementation binding: DEM readiness contract v1

The typed implementation in `src/geologia/dem_readiness/` binds the metadata and disposition rules in Sections 40.5 and 41.4 to a versioned software contract. Its mandatory product context is scoped to one exact product release and requires: `product_version`, `spec_source`, `spec_date`, `metric_type`, `vertical_datum`, `surface_type`, `actual_coverage`, `coverage_status`, `spatial_resolution_x`, `spatial_resolution_y` and `validation_status`.

Each field must either contain a non-empty value or be explicitly marked `not_available` with a reason, reviewer and timezone-aware timestamp. An unavailable critical field blocks `ready_for_declared_use`. It may support `conditional_limited_use` only when a field-specific exception records why the declared narrow task does not depend on it or identifies compensating controls, evidence, reviewer and timestamp. Otherwise, absent or unresolved mandatory information yields `not_evaluable`; it is not proof that the product failed its accuracy requirements.

The evaluator applies this precedence: proven mandatory failure → `not_ready_for_declared_use`; otherwise material unresolved/missing evidence → `not_evaluable`; otherwise documented accepted restrictions or valid scope exceptions → `conditional_limited_use`; otherwise complete independently reviewed evidence → `ready_for_declared_use`. The only validation status that can support a readiness pass is `independently_reviewed`; `planned`, `coverage_checked`, `reference_ready` and `not_assessed` remain `not_assessed`, while `analyzed` without independent review remains `not_evaluable`. An unavailable validation status cannot be excepted. All applicable reason codes are retained independently of the primary disposition.

Coverage sufficiency logic must consume `actual_coverage` and `coverage_status` only. Analogue representativeness logic must consume `analogue_region`, `yemen_target_stratum` and `representativeness_status`; an analogue region is not product coverage.

The immutable implementation constants mirror the operational thresholds already frozen in Sections 13, 17 and 20: 30/50 observations per primary cell; 20/40 valid independent locations per km²; 20/30 occupied 5 km blocks; 60%/75% eligible-block occupancy; maximum 50% of observations in one block; 70% of confirmatory observations within five years of the DEM epoch; 5 km primary blocks with 2.5/10 km sensitivity; and 2,000 spatial block bootstrap replicates. These are screening rules, not universal standards or power guarantees. Changes require a dated protocol amendment before coverage/residual inspection and a separately reviewed implementation update.

The software contract validates metadata and applies deterministic decision bookkeeping only. It does not itself verify raster coverage, datum correctness, source independence, licensing, representativeness or DEM accuracy.
