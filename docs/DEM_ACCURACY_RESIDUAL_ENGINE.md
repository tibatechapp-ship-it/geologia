# DEM/reference residual computation

The optional file-backed accuracy engine samples DEM raster tiles at reference observation points and calculates direct residual metrics. It is a computation primitive, not a complete readiness decision.

## Reference CSV

Required columns:

`point_id,x,y,elevation_m,terrain_stratum,uncertainty_m`

- `x,y` are in the declared `reference_horizontal_crs`.
- `elevation_m` and `uncertainty_m` are metres.
- Point IDs must be unique; values must be finite; uncertainty must be non-negative.
- Maximum 100,000 observations and 100 MiB reference file.

## Mandatory metadata gates

The input must declare the DEM and reference vertical datums, units, DSM/DTM surface types and epochs, horizontal CRS, metadata references, source/release, and an attributable independence review record. For a confirmatory accuracy disposition, the caller must also supply the typed `DeclaredUseContext` and `IndependentReviewEvidence` from the readiness contract. The review must match the exact product version, pilot area and task profile, and its reviewer, evidence reference and timestamp must match the supplied review metadata. Missing or mismatched review evidence leaves computed metrics descriptive-only and accuracy `not_evaluable`.

The v1 engine refuses to compute residuals when vertical datums, surface types, units or epochs are incompatible. It does not apply a geoid or vertical transformation. Reference points are transformed horizontally to the DEM CRS.

## Sampling and metrics

- Sample the containing raster cell; no interpolation.
- Nodata points are excluded and counted by reason.
- Overlapping valid tiles are compared; a value conflict beyond a numerical equality tolerance excludes that point.
- Residual sign is **DEM minus reference**.
- Direct metrics: bias, MAE, RMSE, sample residual standard deviation, median, NMAD and empirical LE90.
- Empirical LE90 is calculated directly by nearest-rank on absolute residuals; no LE90-to-RMSE conversion is used.
- Metrics are also reported by terrain stratum.

A task-specific `AccuracyRequirement` must carry a metric, maximum value, minimum sample count, requirement reference, approver and timezone-aware freeze timestamp. No universal accuracy threshold is supplied.

## Interpretation

- `accuracy_requirement_met_for_declared_use` means only that the selected metric met the frozen requirement for this declared scope.
- `accuracy_requirement_not_met` is a measured failure of that requirement.
- Unresolved/dependent references produce descriptive-only metrics and `not_evaluable` for accuracy claims.
- Conditional independence remains `conditional_limited_use`.
- Every output keeps `readiness_disposition=not_assessed`; coverage, provenance, scientific review and task-specific readiness remain separate gates.

This engine does not authenticate reviewer identity, independently verify reference-source independence, or prove that the supplied metadata references are correct. Input binding is enforced as follows: the caller supplies the typed `DEMTileManifest`; GEOLOGIA hashes its model JSON using the `canonical-json-v1` serialization (UTF-8, sorted keys, compact separators, non-ASCII preserved, non-finite numbers rejected), and verifies the supplied manifest SHA-256. It independently computes the same canonical hash over the exact AOI payload passed to the assessment and verifies the AOI SHA-256. The manifest product version must match the assessment metadata, and its tile SHA-256 membership must match the freshly hashed DEM files. The report marks these bindings as verified. This binds the assessed payloads and tile bytes; it does not authenticate the publisher, prove the truth of external metadata, or establish reference-source independence. The canonicalization scheme is GEOLOGIA-specific and must be versioned if serialization rules change.
