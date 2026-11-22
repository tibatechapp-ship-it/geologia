# DEM readiness contract v1

**Implementation freeze date:** 2026-11-22  
**Protocol source:** `docs/YEMEN_DEM_VALIDATION_PROTOCOL.md`, Sections 13, 17 and 20, plus Sections 40.5 and 41.4.  
**Scope:** typed provenance and readiness decisions for one exact product/version × pilot area × declared task profile.

This contract implements decision bookkeeping. It does **not** read DEM rasters, validate vertical accuracy, prove source independence, calculate coverage, or certify scientific suitability.

## 1. Decision precedence

The evaluator applies this order:

1. **`not_ready_for_declared_use`** only when at least one mandatory requirement is demonstrably not met by applicable evidence.
2. **`not_evaluable`** when no mandatory failure is proven, but unresolved evidence or missing mandatory context prevents a defensible decision.
3. **`conditional_limited_use`** only for known, accepted restrictions in the declared narrow task, or for a missing field covered by an explicit evidence-backed scope exception.
4. **`ready_for_declared_use`** only when mandatory context is complete, validation is assessed, and no mandatory failure, unresolved item or accepted restriction remains.
5. **`not_assessed`** is retained for work that has not been evaluated; it is never a pass.

A readiness pass requires `validation_status = independently_reviewed`. The statuses `planned`, `coverage_checked`, `reference_ready` and `not_assessed` remain `not_assessed`; `analyzed` without independent review remains `not_evaluable`. An unavailable `validation_status` cannot be bypassed through a scope exception.

A missing field is not automatically a proven failure. A missing field also cannot be bypassed by calling the result “conditional”: the exception must identify the field, explain why the declared task does not depend on it or document compensating controls, cite evidence, and name a reviewer and timestamp.

## 2. Mandatory context schema

Each field is an `EvidenceValue`:

- `availability = available`: a non-empty `value` is required.
- `availability = not_available`: `value` must be absent and a reason, reviewer, and timezone-aware `recorded_at` are mandatory.

Required fields:

| Field | Meaning |
|---|---|
| `product_version` | Exact product release/version, not only a product family |
| `spec_source` | Specification/metadata source reference |
| `spec_date` | Specification publication/access date as declared |
| `metric_type` | Exact metric and definition, or provider statement |
| `vertical_datum` | Native vertical datum/reference |
| `surface_type` | DSM, DTM, or explicitly unresolved semantics |
| `actual_coverage` | Verified footprint or authoritative footprint identifier |
| `coverage_status` | Coverage verification state |
| `spatial_resolution_x`, `spatial_resolution_y` | Resolution by axis with units |
| `validation_status` | Whether validation is planned, checked, analyzed, reviewed, or not assessed |

Coverage sufficiency must consume `actual_coverage` and `coverage_status` only. The separate `AnalogueRepresentativenessContext` records `analogue_region`, `yemen_target_stratum`, and `representativeness_status`; it is intentionally not part of the coverage input and cannot substitute for actual product coverage. An `assessed` analogue record requires an evidence reference, reviewer and timezone-aware timestamp. An `unquantified` record must state its limitations.

The contract requires exact provenance values or explicit, attributable unavailability. It does not silently fill metadata from product-family assumptions.

## 3. Reason codes and preservation

Reason codes are separate from disposition. Multiple codes may coexist on one assessment. Every reason record requires a stage, detailed explanation, evidence reference, reviewer and timezone-aware timestamp. The evaluator preserves all recorded codes in first-seen order; a primary status must not erase secondary reasons.

- `not_ready_for_declared_use`: proven mandatory failure.
- `not_evaluable`: unresolved or missing evidence blocks a decision, without proving product failure.
- `unresolved`: evidence is conflicting or insufficient for a defensible decision and must remain visible.
- `not_assessed`: screening/validation has not been completed.

The typed code list includes the candidate-exclusion reasons in Section 40.5 and the non-evaluable reasons in Section 22.

## 4. Frozen protocol v1 screening thresholds

The immutable Python constants mirror the already registered operational thresholds:

| Protocol section | Gate | Exploratory | Confirmatory |
|---|---|---:|---:|
| 13 | Independent observations per primary cell | 30 | 50 |
| 17 | Valid independent locations per km² | 20 | 40 |
| 17 | Occupied independent 5 km blocks | 20 | 30 |
| 17 | Eligible blocks occupied | 60% | 75% |
| 17 | Maximum share in any one block | 50% | 50% |
| 17 | Observations within 5 years of DEM epoch | — | 70% |
| 20 | Primary block width | 5 km | 5 km |
| 20 | Sensitivity widths | 2.5 km and 10 km | 2.5 km and 10 km |
| 20 | Spatial block bootstrap replicates | 2,000 | 2,000 |

These are operational screens, not universal standards and not guarantees of statistical power. The Section 13 floors do not replace the precision/power assessment. Section 17's density gate does not override independent-block, reference-quality, temporal or per-stratum requirements. Threshold changes require a dated protocol amendment before coverage or residual inspection; implementation constants must then be changed in a separately reviewed release.

## 5. Explicitly out of scope

This first implementation does not infer that a product has geographic coverage from a named analogue region, calculate coverage from raster files, determine DSM/DTM from pixels, validate licenses, resolve source lineage, or calculate accuracy. Those are evidence-producing workflows that must populate this contract with attributable records before readiness can be assessed.
