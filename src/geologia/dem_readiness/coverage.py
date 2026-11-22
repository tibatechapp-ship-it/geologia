"""Deterministic evaluation of the pre-registered DEM reference-coverage gates.

This module evaluates supplied measurements only. It does not derive point
density, spatial blocks, dates, or coverage from geospatial files.
"""

from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import Availability, EvidenceValue, ReasonCode
from .thresholds import FROZEN_V1_THRESHOLDS


NonEmpty = Annotated[str, Field(min_length=1)]


class CoverageOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUABLE = "not_evaluable"


class CoverageLevel(StrEnum):
    EXPLORATORY = "exploratory"
    CONFIRMATORY = "confirmatory"


class PrecisionStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_ASSESSED = "not_assessed"


class SourceIndependenceStatus(StrEnum):
    INDEPENDENT = "independent"
    DEPENDENT = "dependent"
    CONDITIONAL = "conditional"
    UNRESOLVED = "unresolved"


class CoverageMetric(BaseModel):
    """Measured numeric value or an attributable declaration of missingness."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float | None = None
    available: bool
    missing_reason: str | None = None
    reviewer: str | None = None
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def validate_measurement(self) -> "CoverageMetric":
        if self.available:
            if self.value is None or not isfinite(self.value) or self.value < 0:
                raise ValueError("available coverage metric must be finite and non-negative")
            if self.missing_reason or self.reviewer or self.recorded_at:
                raise ValueError("missingness metadata is invalid for an available metric")
            return self
        if self.value is not None:
            raise ValueError("unavailable coverage metric must not contain a value")
        if not self.missing_reason or not self.reviewer:
            raise ValueError("unavailable coverage metric requires reason and reviewer")
        if self.recorded_at is None or self.recorded_at.tzinfo is None:
            raise ValueError("unavailable coverage metric requires timezone-aware recorded_at")
        return self


class CoverageEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observations_per_primary_cell: CoverageMetric
    valid_independent_locations_per_km2: CoverageMetric
    occupied_independent_blocks: CoverageMetric
    eligible_blocks_occupancy_fraction: CoverageMetric
    maximum_observation_fraction_in_one_block: CoverageMetric
    observations_0_3_years: CoverageMetric
    observations_3_5_years: CoverageMetric
    observations_5_10_years: CoverageMetric
    observations_over_10_years: CoverageMetric
    precision_status: PrecisionStatus
    precision_evidence_reference: str | None = None
    precision_reviewer: str | None = None
    precision_recorded_at: datetime | None = None

    @model_validator(mode="after")
    def validate_metric_ranges_and_precision(self) -> "CoverageEvidence":
        for name in (
            "eligible_blocks_occupancy_fraction",
            "maximum_observation_fraction_in_one_block",
        ):
            metric = getattr(self, name)
            if metric.available and metric.value is not None and metric.value > 1:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in (
            "observations_per_primary_cell",
            "occupied_independent_blocks",
            "observations_0_3_years",
            "observations_3_5_years",
            "observations_5_10_years",
            "observations_over_10_years",
        ):
            metric = getattr(self, name)
            if metric.available and metric.value is not None and not metric.value.is_integer():
                raise ValueError(f"{name} must be a whole-number count")
        if self.precision_status is PrecisionStatus.NOT_ASSESSED:
            if self.precision_evidence_reference or self.precision_reviewer or self.precision_recorded_at:
                raise ValueError("not_assessed precision must not claim assessment evidence")
        else:
            if not self.precision_evidence_reference or not self.precision_reviewer:
                raise ValueError("assessed precision requires evidence reference and reviewer")
            if self.precision_recorded_at is None or self.precision_recorded_at.tzinfo is None:
                raise ValueError("assessed precision requires timezone-aware recorded_at")
        return self

    @property
    def temporal_bin_total(self) -> float | None:
        bins = (
            self.observations_0_3_years,
            self.observations_3_5_years,
            self.observations_5_10_years,
            self.observations_over_10_years,
        )
        if not all(item.available and item.value is not None for item in bins):
            return None
        return sum(item.value or 0 for item in bins)

    @property
    def temporal_match_fraction_within_5_years(self) -> float | None:
        total = self.temporal_bin_total
        if total is None:
            return None
        within_five = (self.observations_0_3_years.value or 0) + (
            self.observations_3_5_years.value or 0
        )
        return within_five / total if total else 0.0


class CoverageRecord(BaseModel):
    """Coverage evidence for one exact product/area/reference/stratum tuple."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_version_id: NonEmpty
    pilot_area_id: NonEmpty
    reference_source_id: NonEmpty
    primary_stratum_id: NonEmpty
    product_epoch: NonEmpty
    equal_area_crs: NonEmpty
    reference_coverage_geometry_reference: EvidenceValue
    coverage_map_reference: EvidenceValue
    coverage_verification_method: EvidenceValue
    coverage_verified_at: datetime | None = None
    source_independence_status: SourceIndependenceStatus
    source_independence_rationale: NonEmpty
    source_independence_evidence_reference: str | None = None
    source_independence_reviewer: NonEmpty
    source_independence_recorded_at: datetime
    density_grid_width_km: float = Field(default=1.0, gt=0)
    spatial_block_width_km: float = Field(default=5.0, gt=0)
    evidence: CoverageEvidence

    @model_validator(mode="after")
    def validate_coverage_record(self) -> "CoverageRecord":
        if self.density_grid_width_km != FROZEN_V1_THRESHOLDS.section_17.density_grid_width_km:
            raise ValueError("density grid width must match frozen protocol v1")
        if self.spatial_block_width_km != FROZEN_V1_THRESHOLDS.section_17.spatial_block_width_km:
            raise ValueError("spatial block width must match frozen protocol v1")
        if self.source_independence_recorded_at.tzinfo is None:
            raise ValueError("source_independence_recorded_at must be timezone-aware")
        coverage_fields = (
            self.reference_coverage_geometry_reference,
            self.coverage_map_reference,
            self.coverage_verification_method,
        )
        if all(item.availability is Availability.AVAILABLE for item in coverage_fields):
            if self.coverage_verified_at is None or self.coverage_verified_at.tzinfo is None:
                raise ValueError("verified reference coverage requires timezone-aware coverage_verified_at")
        elif self.coverage_verified_at is not None and self.coverage_verified_at.tzinfo is None:
            raise ValueError("coverage_verified_at must be timezone-aware when supplied")
        if (
            self.source_independence_status
            in {SourceIndependenceStatus.INDEPENDENT, SourceIndependenceStatus.DEPENDENT}
            and not self.source_independence_evidence_reference
        ):
            raise ValueError("independence decision requires evidence_reference")
        return self


class GateCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: NonEmpty
    observed: float | None
    comparison: str
    threshold: float
    outcome: CoverageOutcome
    reason_code: ReasonCode | None = None


class CoverageGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: CoverageLevel
    outcome: CoverageOutcome
    checks: tuple[GateCheck, ...]
    reason_codes: tuple[ReasonCode, ...]


class CoverageAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record: CoverageRecord
    exploratory: CoverageGateResult
    confirmatory: CoverageGateResult


def _evaluate_gate(
    level: CoverageLevel,
    checks: list[GateCheck],
) -> CoverageGateResult:
    reasons = tuple(dict.fromkeys(
        check.reason_code for check in checks if check.reason_code is not None
    ))
    if any(check.outcome is CoverageOutcome.FAIL for check in checks):
        outcome = CoverageOutcome.FAIL
    elif any(check.outcome is CoverageOutcome.NOT_EVALUABLE for check in checks):
        outcome = CoverageOutcome.NOT_EVALUABLE
    else:
        outcome = CoverageOutcome.PASS
    return CoverageGateResult(
        level=level,
        outcome=outcome,
        checks=tuple(checks),
        reason_codes=reasons,
    )


def _minimum_check(
    metric_name: str,
    metric: CoverageMetric,
    threshold: float,
    reason: ReasonCode,
) -> GateCheck:
    if not metric.available:
        return GateCheck(
            metric=metric_name, observed=None, comparison="at_least",
            threshold=threshold, outcome=CoverageOutcome.NOT_EVALUABLE,
            reason_code=ReasonCode.UNRESOLVED,
        )
    passed = metric.value is not None and metric.value >= threshold
    return GateCheck(
        metric=metric_name, observed=metric.value, comparison="at_least",
        threshold=threshold,
        outcome=CoverageOutcome.PASS if passed else CoverageOutcome.FAIL,
        reason_code=None if passed else reason,
    )


def _maximum_check(
    metric_name: str,
    metric: CoverageMetric,
    threshold: float,
    reason: ReasonCode,
) -> GateCheck:
    if not metric.available:
        return GateCheck(
            metric=metric_name, observed=None, comparison="at_most",
            threshold=threshold, outcome=CoverageOutcome.NOT_EVALUABLE,
            reason_code=ReasonCode.UNRESOLVED,
        )
    passed = metric.value is not None and metric.value <= threshold
    return GateCheck(
        metric=metric_name, observed=metric.value, comparison="at_most",
        threshold=threshold,
        outcome=CoverageOutcome.PASS if passed else CoverageOutcome.FAIL,
        reason_code=None if passed else reason,
    )


def _coverage_documentation_checks(record: CoverageRecord) -> list[GateCheck]:
    fields = {
        "reference_coverage_geometry": record.reference_coverage_geometry_reference,
        "coverage_map": record.coverage_map_reference,
        "coverage_verification_method": record.coverage_verification_method,
    }
    return [
        GateCheck(
            metric=name,
            observed=None,
            comparison="must_be_available",
            threshold=1.0,
            outcome=(
                CoverageOutcome.PASS
                if item.availability is Availability.AVAILABLE
                else CoverageOutcome.NOT_EVALUABLE
            ),
            reason_code=(
                None
                if item.availability is Availability.AVAILABLE
                else ReasonCode.UNRESOLVED
            ),
        )
        for name, item in fields.items()
    ]


def _independence_check(record: CoverageRecord) -> GateCheck:
    status = record.source_independence_status
    if status is SourceIndependenceStatus.INDEPENDENT:
        outcome = CoverageOutcome.PASS
        reason = None
    elif status is SourceIndependenceStatus.DEPENDENT:
        outcome = CoverageOutcome.FAIL
        reason = ReasonCode.SOURCE_DEPENDENCE_CONFLICT
    else:
        outcome = CoverageOutcome.NOT_EVALUABLE
        reason = ReasonCode.UNRESOLVED
    return GateCheck(
        metric="source_independence",
        observed=None,
        comparison="must_be_independent",
        threshold=1.0,
        outcome=outcome,
        reason_code=reason,
    )


def evaluate_coverage(record: CoverageRecord) -> CoverageAssessment:
    """Evaluate exploratory and confirmatory gates against frozen protocol v1."""
    section13 = FROZEN_V1_THRESHOLDS.section_13
    section17 = FROZEN_V1_THRESHOLDS.section_17
    evidence = record.evidence

    independence_check = _independence_check(record)
    documentation_checks = _coverage_documentation_checks(record)
    exploratory_checks = [
        *documentation_checks,
        independence_check,
        _minimum_check(
            "observations_per_primary_cell",
            evidence.observations_per_primary_cell,
            section13.exploratory_observations_per_primary_cell,
            ReasonCode.INSUFFICIENT_SAMPLE,
        ),
        _minimum_check(
            "valid_independent_locations_per_km2",
            evidence.valid_independent_locations_per_km2,
            section17.exploratory_valid_locations_per_km2,
            ReasonCode.INSUFFICIENT_SAMPLE,
        ),
        _minimum_check(
            "occupied_independent_blocks",
            evidence.occupied_independent_blocks,
            section17.exploratory_occupied_blocks,
            ReasonCode.SPATIALLY_CLUSTERED,
        ),
        _minimum_check(
            "eligible_blocks_occupancy_fraction",
            evidence.eligible_blocks_occupancy_fraction,
            section17.exploratory_eligible_blocks_fraction,
            ReasonCode.SPATIALLY_CLUSTERED,
        ),
        _maximum_check(
            "maximum_observation_fraction_in_one_block",
            evidence.maximum_observation_fraction_in_one_block,
            section17.maximum_observation_fraction_in_one_block,
            ReasonCode.SPATIALLY_CLUSTERED,
        ),
    ]

    confirmatory_checks = [
        *documentation_checks,
        independence_check,
        _minimum_check(
            "observations_per_primary_cell",
            evidence.observations_per_primary_cell,
            section13.confirmatory_observations_per_primary_cell,
            ReasonCode.INSUFFICIENT_SAMPLE,
        ),
        _minimum_check(
            "valid_independent_locations_per_km2",
            evidence.valid_independent_locations_per_km2,
            section17.confirmatory_valid_locations_per_km2,
            ReasonCode.INSUFFICIENT_SAMPLE,
        ),
        _minimum_check(
            "occupied_independent_blocks",
            evidence.occupied_independent_blocks,
            section17.confirmatory_occupied_blocks,
            ReasonCode.SPATIALLY_CLUSTERED,
        ),
        _minimum_check(
            "eligible_blocks_occupancy_fraction",
            evidence.eligible_blocks_occupancy_fraction,
            section17.confirmatory_eligible_blocks_fraction,
            ReasonCode.SPATIALLY_CLUSTERED,
        ),
        _maximum_check(
            "maximum_observation_fraction_in_one_block",
            evidence.maximum_observation_fraction_in_one_block,
            section17.maximum_observation_fraction_in_one_block,
            ReasonCode.SPATIALLY_CLUSTERED,
        ),
        (
            GateCheck(
                metric="temporal_match_fraction_within_5_years",
                observed=None,
                comparison="at_least",
                threshold=section17.confirmatory_temporal_match_fraction,
                outcome=CoverageOutcome.NOT_EVALUABLE,
                reason_code=ReasonCode.UNRESOLVED,
            )
            if evidence.temporal_match_fraction_within_5_years is None
            else GateCheck(
                metric="temporal_match_fraction_within_5_years",
                observed=evidence.temporal_match_fraction_within_5_years,
                comparison="at_least",
                threshold=section17.confirmatory_temporal_match_fraction,
                outcome=(
                    CoverageOutcome.FAIL
                    if evidence.temporal_bin_total == 0
                    or evidence.temporal_match_fraction_within_5_years
                    < section17.confirmatory_temporal_match_fraction
                    else CoverageOutcome.PASS
                ),
                reason_code=(
                    ReasonCode.NO_REFERENCE_DATA
                    if evidence.temporal_bin_total == 0
                    else (
                        ReasonCode.TEMPORAL_MISMATCH
                        if evidence.temporal_match_fraction_within_5_years
                        < section17.confirmatory_temporal_match_fraction
                        else None
                    )
                ),
            )
        ),
    ]

    if evidence.precision_status is PrecisionStatus.FAILED:
        precision_outcome = CoverageOutcome.FAIL
        precision_reason = ReasonCode.PRECISION_INADEQUATE
    elif evidence.precision_status is PrecisionStatus.NOT_ASSESSED:
        precision_outcome = CoverageOutcome.NOT_EVALUABLE
        precision_reason = ReasonCode.NOT_ASSESSED
    else:
        precision_outcome = CoverageOutcome.PASS
        precision_reason = None

    confirmatory_checks.append(
        GateCheck(
            metric="precision_assessment",
            observed=None,
            comparison="must_be_passed",
            threshold=1.0,
            outcome=precision_outcome,
            reason_code=precision_reason,
        )
    )

    return CoverageAssessment(
        record=record,
        exploratory=_evaluate_gate(CoverageLevel.EXPLORATORY, exploratory_checks),
        confirmatory=_evaluate_gate(CoverageLevel.CONFIRMATORY, confirmatory_checks),
    )
