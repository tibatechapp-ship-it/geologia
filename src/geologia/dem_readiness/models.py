"""Typed, auditable data contracts for DEM product readiness.

These models validate metadata completeness and decision inputs. They do not
perform geospatial validation or establish scientific accuracy.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


NonEmpty = Annotated[str, Field(min_length=1)]


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
        if self.recorded_at is None or self.recorded_at.tzinfo is None:
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
            for name in self.model_fields
            if getattr(self, name).availability is Availability.NOT_AVAILABLE
        ]


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
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
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
        if self.recorded_at.tzinfo is None:
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
        if self.recorded_at.tzinfo is None:
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
        if self.independent_review is not None:
            if self.context.validation_status.value != ValidationStatus.INDEPENDENTLY_REVIEWED.value:
                raise ValueError("independent review evidence requires independently_reviewed status")
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
                raise ValueError("independent review evidence must match the exact declared use")
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
