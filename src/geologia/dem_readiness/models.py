"""Typed, auditable data contracts for DEM product readiness.

These models validate metadata completeness and decision inputs. They do not
perform geospatial validation or establish scientific accuracy.
"""

import math
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


NonEmpty = Annotated[str, Field(min_length=1)]


def _is_timezone_aware(value: datetime) -> bool:
    """Reject tzinfo objects that do not provide a usable UTC offset."""
    return value.tzinfo is not None and value.utcoffset() is not None


class Availability(StrEnum):
    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"


class ValidationStatus(StrEnum):
    PLANNED = "planned"
    COVERAGE_CHECKED = "coverage_checked"
    REFERENCE_READY = "reference_ready"
    ANALYZED = "analyzed"
    INDEPENDENTLY_REVIEWED = "independently_reviewed"
    NOT_ASSESSED = "not_assessed"


class RepresentativenessStatus(StrEnum):
    UNQUANTIFIED = "unquantified"
    ASSESSED = "assessed"
    NOT_APPLICABLE = "not_applicable"


class ReadinessDisposition(StrEnum):
    READY = "ready_for_declared_use"
    CONDITIONAL = "conditional_limited_use"
    NOT_READY = "not_ready_for_declared_use"
    NOT_EVALUABLE = "not_evaluable"
    NOT_ASSESSED = "not_assessed"


class ReasonCode(StrEnum):
    GEOGRAPHIC_COVERAGE_MISSING = "geographic_coverage_missing"
    ACCURACY_REQUIREMENT_NOT_MET = "accuracy_requirement_not_met"
    LICENSE_INCOMPATIBLE = "license_incompatible"
    TECHNICAL_FORMAT_INCOMPATIBLE = "technical_format_incompatible"
    SOURCE_DEPENDENCE_CONFLICT = "source_dependence_conflict"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    METADATA_INSUFFICIENT = "metadata_insufficient"
    ACCESS_UNAVAILABLE = "access_unavailable"
    NOT_ASSESSED = "not_assessed"
    UNRESOLVED = "unresolved"
    NO_REFERENCE_DATA = "no_reference_data"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    SPATIALLY_CLUSTERED = "spatially_clustered"
    DATUM_UNDOCUMENTED = "datum_undocumented"
    REFERENCE_CONFLICT = "reference_conflict"
    PRECISION_INADEQUATE = "precision_inadequate"
    SOURCE_QUALITY_FAILED = "source_quality_failed"
    ENVIRONMENT_OMITTED = "environment_omitted"


class EvidenceValue(BaseModel):
    """A value or an explicit, attributable declaration that it is unavailable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    availability: Availability
    value: str | float | None = None
    reason: str | None = None
    reviewer: str | None = None
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def validate_availability_record(self) -> "EvidenceValue":
        if self.availability is Availability.AVAILABLE:
            if self.value is None or (isinstance(self.value, str) and not self.value.strip()):
                raise ValueError("available evidence must contain a non-empty value")
            if self.reason or self.reviewer or self.recorded_at:
                raise ValueError("unavailability metadata is only valid for not_available")
            return self

        if self.value is not None:
            raise ValueError("not_available evidence must not contain a value")
        if not self.reason or not self.reason.strip():
            raise ValueError("not_available evidence requires a documented reason")
        if not self.reviewer or not self.reviewer.strip():
            raise ValueError("not_available evidence requires a reviewer")
        if self.recorded_at is None or not _is_timezone_aware(self.recorded_at):
            raise ValueError("not_available evidence requires a timezone-aware recorded_at")
        return self


class MandatoryProductContext(BaseModel):
    """Mandatory provenance and product fields for one exact product release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_version: EvidenceValue
    spec_source: EvidenceValue
    spec_date: EvidenceValue
    metric_type: EvidenceValue
    vertical_datum: EvidenceValue
    surface_type: EvidenceValue
    actual_coverage: EvidenceValue
    coverage_status: EvidenceValue
    spatial_resolution_x: EvidenceValue
    spatial_resolution_y: EvidenceValue
    validation_status: EvidenceValue

    @model_validator(mode="after")
    def validate_validation_status(self) -> "MandatoryProductContext":
        status = self.validation_status
        if status.availability is Availability.AVAILABLE:
            allowed = {item.value for item in ValidationStatus}
            if not isinstance(status.value, str) or status.value not in allowed:
                raise ValueError(f"validation_status must be one of: {', '.join(sorted(allowed))}")
        return self

    def unavailable_fields(self) -> list[str]:
        return [
            name
            for name in type(self).model_fields
            if getattr(self, name).availability is Availability.NOT_AVAILABLE
        ]


class AnalogueRepresentativenessContext(BaseModel):
    """Comparison hypothesis metadata; never evidence of product-file coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analogue_region: NonEmpty
    yemen_target_stratum: NonEmpty
    representativeness_status: RepresentativenessStatus
    evidence_reference: str | None = None
    reviewer: str | None = None
    recorded_at: datetime | None = None
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_assessment_evidence(self) -> "AnalogueRepresentativenessContext":
        if self.representativeness_status is RepresentativenessStatus.ASSESSED:
            if not self.evidence_reference or not self.reviewer or self.recorded_at is None:
                raise ValueError(
                    "assessed representativeness requires evidence, reviewer and timestamp"
                )
            if not _is_timezone_aware(self.recorded_at):
                raise ValueError("recorded_at must be timezone-aware")
        elif self.representativeness_status is RepresentativenessStatus.UNQUANTIFIED:
            if not self.limitations:
                raise ValueError("unquantified representativeness requires a limitation")
        return self


class DeclaredUseContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_name: NonEmpty
    product_version_id: NonEmpty
    pilot_area_id: NonEmpty
    task_profile_id: NonEmpty
    intended_user: NonEmpty
    declared_scale: NonEmpty


class IndependentReviewEvidence(BaseModel):
    """Attributable review bound to the exact declared product, area and task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_version_id: NonEmpty
    pilot_area_id: NonEmpty
    task_profile_id: NonEmpty
    reviewer: NonEmpty
    evidence_reference: NonEmpty
    reviewed_at: datetime

    @model_validator(mode="after")
    def require_timezone(self) -> "IndependentReviewEvidence":
        if not _is_timezone_aware(self.reviewed_at):
            raise ValueError("reviewed_at must be timezone-aware")
        return self


class AccuracyAssessmentEvidence(BaseModel):
    """Exact reference to a persisted accuracy assessment for one declared use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_id: NonEmpty
    record_hash: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
    assessment_sha256: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
    product_version_id: NonEmpty
    pilot_area_id: NonEmpty
    task_profile_id: NonEmpty
    accuracy_disposition: Literal[
        "accuracy_requirement_met_for_declared_use",
        "accuracy_requirement_not_met",
        "conditional_limited_use",
        "not_evaluable",
        "not_assessed",
    ]
    metrics_scope: Literal[
        "primary_confirmatory",
        "conditional_limited_use",
        "descriptive_only",
    ]
    independence_status: Literal[
        "independent_confirmed",
        "conditional_limited_use",
        "unresolved",
        "dependent",
    ]
    coverage_footprint_reference: NonEmpty
    evidence_reference: NonEmpty
    assessed_at: datetime

    @model_validator(mode="after")
    def validate_accuracy_evidence(self) -> "AccuracyAssessmentEvidence":
        for name in self.model_fields:
            value = getattr(self, name)
            if isinstance(value, str) and not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.assessed_at.tzinfo is None or self.assessed_at.utcoffset() is None:
            raise ValueError("assessed_at must have a valid UTC offset")
        if self.accuracy_disposition == "accuracy_requirement_met_for_declared_use":
            if (
                self.metrics_scope != "primary_confirmatory"
                or self.independence_status != "independent_confirmed"
            ):
                raise ValueError(
                    "a met accuracy requirement must be primary and independently confirmed"
                )
        if self.accuracy_disposition == "conditional_limited_use":
            if self.metrics_scope != "conditional_limited_use":
                raise ValueError(
                    "conditional accuracy evidence must use conditional_limited_use scope"
                )
        return self


class ReasonRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ReasonCode
    stage: NonEmpty
    detail: NonEmpty
    evidence_reference: NonEmpty
    reviewer: NonEmpty
    recorded_at: datetime

    @model_validator(mode="after")
    def require_timezone(self) -> "ReasonRecord":
        if not _is_timezone_aware(self.recorded_at):
            raise ValueError("recorded_at must be timezone-aware")
        return self


class ScopeException(BaseModel):
    """Evidence that a missing field does not invalidate a narrowly bounded task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: NonEmpty
    rationale: NonEmpty
    evidence_reference: NonEmpty
    reviewer: NonEmpty
    recorded_at: datetime
    compensating_controls: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_exception(self) -> "ScopeException":
        if not _is_timezone_aware(self.recorded_at):
            raise ValueError("recorded_at must be timezone-aware")
        if not self.compensating_controls and len(self.rationale.strip()) < 20:
            raise ValueError(
                "scope exception needs substantive rationale or documented compensating controls"
            )
        return self


class ReadinessInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: MandatoryProductContext
    declared_use: DeclaredUseContext
    mandatory_failures: tuple[ReasonRecord, ...] = ()
    unresolved_items: tuple[ReasonRecord, ...] = ()
    accepted_restrictions: tuple[ReasonRecord, ...] = ()
    scope_exceptions: tuple[ScopeException, ...] = ()
    independent_review: IndependentReviewEvidence | None = None
    accuracy_assessment: AccuracyAssessmentEvidence | None = None

    @model_validator(mode="after")
    def validate_scope_exceptions(self) -> "ReadinessInput":
        known_fields = set(MandatoryProductContext.model_fields)
        exception_fields = [item.field_name for item in self.scope_exceptions]
        if len(exception_fields) != len(set(exception_fields)):
            raise ValueError("only one scope exception may be recorded per field")
        unknown = sorted(set(exception_fields) - known_fields)
        if unknown:
            raise ValueError(f"scope exceptions reference unknown fields: {', '.join(unknown)}")
        available = sorted(
            name
            for name in exception_fields
            if getattr(self.context, name).availability is Availability.AVAILABLE
        )
        if available:
            raise ValueError(
                "scope exceptions may only apply to not_available fields: "
                + ", ".join(available)
            )
        if self.accuracy_assessment is not None:
            assessment = self.accuracy_assessment
            expected = (
                self.declared_use.product_version_id,
                self.declared_use.pilot_area_id,
                self.declared_use.task_profile_id,
            )
            actual = (
                assessment.product_version_id,
                assessment.pilot_area_id,
                assessment.task_profile_id,
            )
            if actual != expected:
                raise ValueError(
                    "accuracy assessment must match the exact declared product, area and task"
                )
            product_version = self.context.product_version
            if (
                product_version.availability is Availability.AVAILABLE
                and product_version.value != assessment.product_version_id
            ):
                raise ValueError(
                    "accuracy assessment product version must match mandatory context"
                )
        if self.independent_review is not None:
            if (
                self.context.validation_status.value
                != ValidationStatus.INDEPENDENTLY_REVIEWED.value
            ):
                raise ValueError(
                    "independent review evidence requires independently_reviewed status"
                )
            review = self.independent_review
            expected = (
                self.declared_use.product_version_id,
                self.declared_use.pilot_area_id,
                self.declared_use.task_profile_id,
            )
            actual = (
                review.product_version_id,
                review.pilot_area_id,
                review.task_profile_id,
            )
            if actual != expected:
                raise ValueError(
                    "independent review evidence must match the exact declared use"
                )
            product_version = self.context.product_version
            if (
                product_version.availability is Availability.AVAILABLE
                and product_version.value != self.declared_use.product_version_id
            ):
                raise ValueError(
                    "declared product version must match the mandatory product context"
                )
        return self


class ReadinessAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    disposition: ReadinessDisposition
    declared_use: DeclaredUseContext
    reason_codes: tuple[ReasonCode, ...]
    blocking_fields: tuple[str, ...] = ()
    applied_scope_exceptions: tuple[str, ...] = ()
    decision_rule_version: NonEmpty
    explanation: NonEmpty


class UncertaintyKind(StrEnum):
    """Semantic interpretation of an uncertainty magnitude; not interchangeable."""

    STANDARD = "standard_uncertainty"
    EXPANDED = "expanded_uncertainty"
    CONFIDENCE_INTERVAL_HALF_WIDTH = "confidence_interval_half_width"
    UNKNOWN = "unknown"


class UncertaintyScope(StrEnum):
    POINT_SPECIFIC = "point_specific"
    SHARED_SYSTEMATIC = "shared_systematic"
    AREA_LEVEL = "area_level"


class DependenceStatus(StrEnum):
    UNKNOWN = "unknown"
    INDEPENDENCE_ASSUMED = "independence_assumed"
    INDEPENDENCE_SUPPORTED = "independence_supported"
    CORRELATED = "correlated"


class ElevationUncertainty(BaseModel):
    """Auditable uncertainty metadata; deliberately does not propagate values.

    Values remain in their declared unit and semantic kind. Conversion to
    standard uncertainty or combination with another source requires a separate
    explicit, documented operation with defensible distribution/dependence
    assumptions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: UncertaintyKind
    value: Annotated[float, Field(ge=0)] | None = None
    unit: Literal["m", "cm", "mm"] = "m"
    source_reference: NonEmpty | None = None
    method: NonEmpty | None = None
    scope: UncertaintyScope
    dependence: DependenceStatus = DependenceStatus.UNKNOWN
    coverage_factor: Annotated[float, Field(gt=0)] | None = None
    coverage_convention: NonEmpty | None = None
    confidence_level: Annotated[float, Field(gt=0, lt=1)] | None = None
    interval_convention: NonEmpty | None = None
    dependence_evidence_reference: NonEmpty | None = None
    unknown_reason: NonEmpty | None = None
    reviewer: NonEmpty
    recorded_at: datetime

    @model_validator(mode="after")
    def validate_uncertainty_semantics(self) -> "ElevationUncertainty":
        if not _is_timezone_aware(self.recorded_at):
            raise ValueError("recorded_at must be timezone-aware")

        if self.kind is UncertaintyKind.UNKNOWN:
            if self.value is not None:
                raise ValueError("unknown uncertainty must not carry a numeric value")
            if not self.unknown_reason:
                raise ValueError("unknown uncertainty requires a documented reason")
            if any(
                item is not None
                for item in (
                    self.source_reference,
                    self.method,
                    self.coverage_factor,
                    self.coverage_convention,
                    self.confidence_level,
                    self.interval_convention,
                )
            ):
                raise ValueError(
                    "unknown uncertainty cannot declare numeric interpretation metadata"
                )
        else:
            if self.value is None:
                raise ValueError("known uncertainty requires a numeric value")
            if not math.isfinite(self.value):
                raise ValueError("uncertainty value must be finite")
            if not self.source_reference or not self.method:
                raise ValueError("known uncertainty requires source_reference and method")
            if self.unknown_reason is not None:
                raise ValueError("known uncertainty must not carry unknown_reason")

        if self.kind is UncertaintyKind.EXPANDED:
            if self.coverage_factor is None or not self.coverage_convention:
                raise ValueError(
                    "expanded uncertainty requires coverage_factor and coverage_convention"
                )
        elif self.coverage_factor is not None or self.coverage_convention is not None:
            raise ValueError(
                "coverage factor/convention are only valid for expanded uncertainty"
            )

        if self.kind is UncertaintyKind.CONFIDENCE_INTERVAL_HALF_WIDTH:
            if self.confidence_level is None or not self.interval_convention:
                raise ValueError(
                    "confidence interval half-width requires confidence_level "
                    "and interval_convention"
                )
        elif self.confidence_level is not None or self.interval_convention is not None:
            raise ValueError(
                "confidence interval metadata is only valid for interval half-width"
            )

        if self.dependence is DependenceStatus.CORRELATED:
            if not self.dependence_evidence_reference:
                raise ValueError(
                    "correlated uncertainty requires dependence evidence reference"
                )
        elif self.dependence_evidence_reference is not None:
            raise ValueError(
                "dependence evidence reference is only valid when correlated"
            )

        if self.scope is UncertaintyScope.SHARED_SYSTEMATIC:
            if self.dependence is DependenceStatus.INDEPENDENCE_SUPPORTED:
                raise ValueError(
                    "shared systematic uncertainty cannot be marked independence_supported"
                )

        return self
