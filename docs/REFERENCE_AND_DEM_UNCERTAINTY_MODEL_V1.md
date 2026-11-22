# Reference and DEM uncertainty model v1

## Status and scope

This document specifies the next uncertainty-reporting layer for the file-backed DEM/reference residual engine. It is a design contract for implementation and review, not a validation result, an accuracy guarantee, or a change to the frozen Yemen sampling thresholds.

The engine currently accepts a per-reference-point `uncertainty_m` value, preserves it in residual records, and reports descriptive residual metrics. That numeric field alone does **not** identify its statistical meaning (standard uncertainty, expanded uncertainty, confidence interval half-width, or another quantity). Until the uncertainty semantics and provenance are explicit, it must not be used to correct DEM error metrics or claim uncertainty-adjusted accuracy.

## 1. Separate uncertainty sources

Every future report must distinguish at least:

1. **Observed residual variation**: dispersion of `DEM elevation − reference elevation` at valid sampled points.
2. **Reference measurement uncertainty**: uncertainty attached to surveyed/reference elevations, including its stated confidence convention and spatial dependence.
3. **DEM product uncertainty**: only a separately supported estimate for the exact product release, area, task profile and conditions. It is not inferred by subtracting reference uncertainty from RMSE.
4. **Spatial sampling uncertainty**: uncertainty in estimated metrics due to the selected sample and spatial clustering. It must be estimated using the protocol's spatial-block design, not an iid point bootstrap.
5. **Model/processing uncertainty**: uncertainty introduced by datum transformation, interpolation, filtering or other processing. The current engine applies no vertical transformation and uses nearest containing raster cell; no transformation uncertainty may be implied unless a documented operation is actually applied.

These components are not interchangeable and must not be collapsed into one number without an explicit, reviewed model.

## 2. Reference uncertainty record

A future typed reference-observation schema must carry, or link to a dataset-level record carrying:

- uncertainty value and unit;
- uncertainty kind: `standard_uncertainty_1sigma`, `expanded_uncertainty`, `confidence_interval_half_width`, or `unknown`;
- for expanded uncertainty, the coverage factor and stated confidence/coverage convention;
- method and source/evidence reference;
- whether the uncertainty is point-specific or shared/systematic;
- any known covariance, correlation length, common datum/network component, or explicit `dependence_not_characterized`;
- reviewer and timezone-aware review timestamp where the value is interpreted or converted.

Unknown or ambiguous uncertainty remains unknown. Do not silently treat a confidence interval half-width or expanded uncertainty as one standard deviation. Unit conversion is allowed only when the source unit and conversion are explicit and deterministic.

## 3. Initial report behavior

Before a reviewed uncertainty model is implemented, the report may provide descriptive summaries of supplied reference uncertainty values (count, missing/unknown count, minimum, median, maximum, and stratified summaries) only if their semantic kind is uniform and verified.

The report must label these as **reference uncertainty metadata**, not DEM accuracy or total uncertainty. If the uncertainty kind is mixed or unknown, retain the raw values and report `reference_uncertainty_summary_status = not_evaluable`; do not combine them statistically.

The existing residual metrics remain observed residual metrics. Their names, units, and interpretation must not change.

## 4. Variance decomposition: strict assumptions

For a simplified scalar model,

`r_i = e_{DEM,i} - e_{ref,i}`

and, only when both error components are zero-mean (or separately centered), mutually independent, expressed in the same vertical units and defined over compatible spatial support:

`Var(r) = Var(e_DEM) + Var(e_ref)`

If covariance is nonzero:

`Var(r) = Var(e_DEM) + Var(e_ref) - 2 Cov(e_DEM, e_ref)`

Therefore:

- Never estimate DEM variance as `Var(residual) − Var(reference uncertainty)` unless the independence, centering, distribution, support and uncertainty semantics assumptions are established and documented for the exact assessment.
- A negative result from such subtraction is not clipped to zero and presented as a valid estimate; it indicates incompatible assumptions/evidence or sampling uncertainty.
- Reference systematic bias, vertical-datum error, shared control-network error and spatial correlation cannot be removed by treating all point uncertainties as independent random noise.
- RMSE is not a variance component and must not be corrected by subtracting an uncertainty magnitude.

## 5. Spatial sampling uncertainty

Confidence intervals for residual metrics must use the predeclared spatial blocks and frozen protocol settings. The implementation must:

- resample spatial blocks, not individual points as if independent;
- preserve terrain-stratum reporting and disclose strata/blocks that cannot be resampled;
- use the protocol's declared bootstrap replicate count and sensitivity block sizes;
- record the random seed or deterministic resampling specification, algorithm/version, block size, valid blocks, replicate count and percentile/interval method;
- report an interval only when the design supports it; otherwise return `not_evaluable` with a reason code.

A bootstrap interval describes sampling variability under its resampling design. It does not include reference systematic uncertainty or establish source independence.

## 6. Reference uncertainty propagation

Monte Carlo propagation may be added only after uncertainty distributions and dependence structure are supplied by evidence. The model must document:

- the distribution and parameters for each uncertainty component;
- whether values are standard or expanded uncertainty and how conversion was justified;
- shared/systematic components sampled once per replicate rather than independently per point;
- spatial covariance or a justified approximation;
- the statistic being propagated and the output interval convention;
- reproducible seed, implementation version and convergence diagnostics.

If dependence is not characterized, the engine must not assume independent point errors. It may report sensitivity scenarios clearly labeled as scenarios, not primary corrected results.

## 7. Required output separation

The eventual report schema should keep separate fields, for example:

- `observed_residual_metrics` (existing metrics);
- `reference_uncertainty_summary`;
- `spatial_sampling_interval`;
- `reference_uncertainty_propagation`;
- `dem_error_estimate` (absent unless the decomposition gate passes);
- `uncertainty_model_status` and reason codes.

No field may imply that a DEM-specific uncertainty estimate was obtained when only residuals or reference uncertainties were available.

## 8. Acceptance gates for implementation

Implementation must include tests for:

- ambiguous/mixed uncertainty kinds blocking statistical combination;
- expanded uncertainty requiring a coverage factor and declared convention;
- non-finite, negative or unit-incompatible values rejected;
- shared systematic uncertainty not treated as independent per point;
- dependent reference sources blocking confirmatory decomposition;
- block bootstrap not resampling points iid;
- deterministic report metadata and reproducibility;
- missing covariance/dependence producing `not_evaluable` or explicitly labeled sensitivity analysis;
- readiness remaining `not_assessed` regardless of synthetic test success.

## Scientific boundary

This model does not create a universal DEM accuracy threshold, validate any Yemen DEM, establish independence of a reference source, or change GEOLOGIA's readiness disposition. All results remain scoped to the exact product version × pilot area × task profile × data and reference conditions.


## Implemented typed sidecar contract

The optional `reference_uncertainty_sidecar_path` must be supplied together with `reference_uncertainty_sidecar_sha256`. The sidecar is limited to 10 MiB, its exact bytes are SHA-256 checked, and its `reference_dataset_sha256` must match the reference CSV. The `records` object must contain exactly the CSV point IDs—no missing or extra points.

```json
{
  "schema": "geologia.reference-uncertainty.v1",
  "reference_dataset_sha256": "<SHA-256 of reference CSV>",
  "records": {
    "point-001": {
      "kind": "standard_uncertainty",
      "value": 0.15,
      "unit": "m",
      "source_reference": "survey-method://source",
      "method": "documented-method",
      "scope": "point_specific",
      "dependence": "unknown",
      "reviewer": "reviewer-id",
      "recorded_at": "2026-11-22T00:00:00+00:00"
    }
  }
}
```

Each record is validated by the `ElevationUncertainty` contract. Expanded uncertainty requires coverage factor and convention; confidence interval half-width requires confidence level and interval convention; unknown records require a reason and cannot carry a typed numeric value. Correlation declarations require evidence. The sidecar hash and typed records are included in the report. Values are preserved as metadata only: this feature does not convert uncertainty, aggregate mixed semantics, propagate uncertainty, or modify residual metrics. The legacy CSV `uncertainty_m` remains required for compatibility and remains explicitly untyped when no sidecar is supplied.


## Descriptive summary gate

The report emits `reference_uncertainty_summary` separately from observed residual metrics. Without a sidecar, it returns `not_evaluable` because the legacy CSV uncertainty semantics are unknown. With a sidecar, a descriptive minimum/median/maximum is emitted only when every record is known and all records share one uncertainty kind, unit, and scope. Expanded uncertainty additionally requires identical coverage factor/convention; confidence-interval half-widths require identical confidence level/interval convention. The summary also reports counts by dependence status.

Mixed kinds, mixed units or scopes, incompatible coverage/confidence conventions, or any unknown record return `not_evaluable` with a reason code. The descriptive summary is a distribution of declared metadata values—not a combined uncertainty, confidence interval, uncertainty propagation, or DEM accuracy estimate. It does not change the residual metrics or readiness disposition.


## API dataset workflow

The API accepts the sidecar as a JSON dataset uploaded with `X-Data-Role: reference_uncertainty_sidecar`. Upload validation checks the schema, SHA-256-shaped reference binding, non-empty point records, and every record against `ElevationUncertainty`. The DEM accuracy request may then include `reference_uncertainty_sidecar_dataset_id`. The API verifies upload-time byte integrity, binds the dataset ID and hash into the assessment record, and rechecks the sidecar bytes before reusing that accuracy assessment in a readiness request. The sidecar must reference the exact uploaded reference CSV SHA-256; the engine separately requires an exact match between sidecar point IDs and CSV point IDs.

Legacy requests that omit the sidecar dataset ID remain supported and continue to report uncertainty semantics as unknown.
