from datetime import UTC, datetime

from geologia.dem_readiness.models import (
    Availability,
    DeclaredUseContext,
    EvidenceValue,
    IndependentReviewEvidence,
    MandatoryProductContext,
    ReadinessDisposition,
    ReadinessInput,
    ReasonCode,
    ReasonRecord,
    ScopeException,
)
from geologia.dem_readiness.readiness import assess_readiness


NOW = datetime(2026, 11, 22, tzinfo=UTC)


def evidence(value):
    return EvidenceValue(availability=Availability.AVAILABLE, value=value)


def context(**overrides):
    values = {
        name: evidence(
            "independently_reviewed"
            if name == "validation_status"
            else "release-1"
            if name == "product_version"
            else "verified"
        )
        for name in MandatoryProductContext.model_fields
    }
    values.update(overrides)
    return MandatoryProductContext(**values)


def use():
    return DeclaredUseContext(
        product_name="Example DEM",
        product_version_id="release-1",
        pilot_area_id="pilot-north",
        task_profile_id="regional-reconnaissance-v1",
        intended_user="geological researcher",
        declared_scale="regional reconnaissance",
    )


def review():
    return IndependentReviewEvidence(
        product_version_id="release-1",
        pilot_area_id="pilot-north",
        task_profile_id="regional-reconnaissance-v1",
        reviewer="independent-reviewer-2",
        evidence_reference="evidence://independent-review/1",
        reviewed_at=NOW,
    )


def reason(code, stage="coverage"):
    return ReasonRecord(
        code=code,
        stage=stage,
        detail=f"Evidence establishes {code.value}.",
        evidence_reference="evidence://record/1",
        reviewer="reviewer-1",
        recorded_at=NOW,
    )


def test_complete_context_can_be_ready():
    result = assess_readiness(ReadinessInput(context=context(), declared_use=use(), independent_review=review()))
    assert result.disposition is ReadinessDisposition.READY


def test_proven_mandatory_failure_has_highest_precedence():
    result = assess_readiness(
        ReadinessInput(
            context=context(),
            declared_use=use(),
            mandatory_failures=(reason(ReasonCode.LICENSE_INCOMPATIBLE),),
            unresolved_items=(reason(ReasonCode.UNRESOLVED),),
        )
    )
    assert result.disposition is ReadinessDisposition.NOT_READY
    assert set(result.reason_codes) == {
        ReasonCode.LICENSE_INCOMPATIBLE,
        ReasonCode.UNRESOLVED,
    }


def test_missing_critical_metadata_without_exception_is_not_evaluable():
    missing = EvidenceValue(
        availability=Availability.NOT_AVAILABLE,
        reason="Provider metadata does not state the vertical datum.",
        reviewer="reviewer-1",
        recorded_at=NOW,
    )
    result = assess_readiness(
        ReadinessInput(
            context=context(vertical_datum=missing),
            declared_use=use(),
        )
    )
    assert result.disposition is ReadinessDisposition.NOT_EVALUABLE
    assert result.blocking_fields == ("vertical_datum",)


def test_scope_exception_allows_only_conditional_limited_use():
    missing = EvidenceValue(
        availability=Availability.NOT_AVAILABLE,
        reason="No vertical datum is supplied for this product release.",
        reviewer="reviewer-1",
        recorded_at=NOW,
    )
    exception = ScopeException(
        field_name="vertical_datum",
        rationale=(
            "This declared task uses only relative terrain visualization and does not "
            "compare absolute elevations."
        ),
        evidence_reference="evidence://task-profile/relative-only",
        reviewer="reviewer-1",
        recorded_at=NOW,
        compensating_controls=("Suppress absolute-height outputs", "Label datum as unknown"),
    )
    result = assess_readiness(
        ReadinessInput(
            context=context(vertical_datum=missing),
            declared_use=use(),
            scope_exceptions=(exception,),
            independent_review=review(),
        )
    )
    assert result.disposition is ReadinessDisposition.CONDITIONAL
    assert result.applied_scope_exceptions == ("vertical_datum",)


def test_restriction_is_conditional_not_ready():
    result = assess_readiness(
        ReadinessInput(
            context=context(),
            declared_use=use(),
            accepted_restrictions=(reason(ReasonCode.TEMPORAL_MISMATCH),),
            independent_review=review(),
        )
    )
    assert result.disposition is ReadinessDisposition.CONDITIONAL


def test_unresolved_evidence_is_not_evidence_of_failure():
    result = assess_readiness(
        ReadinessInput(
            context=context(),
            declared_use=use(),
            unresolved_items=(reason(ReasonCode.UNRESOLVED),),
        )
    )
    assert result.disposition is ReadinessDisposition.NOT_EVALUABLE
    assert ReasonCode.UNRESOLVED in result.reason_codes


def test_not_assessed_status_is_not_a_pass():
    result = assess_readiness(
        ReadinessInput(
            context=context(validation_status=evidence("not_assessed")),
            declared_use=use(),
        )
    )
    assert result.disposition is ReadinessDisposition.NOT_ASSESSED


def test_analyzed_without_independent_review_is_not_evaluable():
    result = assess_readiness(
        ReadinessInput(
            context=context(validation_status=evidence("analyzed")),
            declared_use=use(),
        )
    )
    assert result.disposition is ReadinessDisposition.NOT_EVALUABLE
    assert ReasonCode.UNRESOLVED in result.reason_codes


def test_validation_status_cannot_be_bypassed_by_scope_exception():
    missing = EvidenceValue(
        availability=Availability.NOT_AVAILABLE,
        reason="No validation workflow status is recorded.",
        reviewer="reviewer-1",
        recorded_at=NOW,
    )
    exception = ScopeException(
        field_name="validation_status",
        rationale="The declared task is a simple visualization only.",
        evidence_reference="evidence://task-profile/view-only",
        reviewer="reviewer-1",
        recorded_at=NOW,
        compensating_controls=("Suppress all readiness labels",),
    )
    result = assess_readiness(
        ReadinessInput(
            context=context(validation_status=missing),
            declared_use=use(),
            scope_exceptions=(exception,),
        )
    )
    assert result.disposition is ReadinessDisposition.NOT_EVALUABLE
    assert "validation_status" in result.blocking_fields



def test_scope_exception_cannot_reference_unknown_field():
    import pytest
    from pydantic import ValidationError

    exception = ScopeException(
        field_name="analogue_region",
        rationale="This is not part of the product mandatory context contract.",
        evidence_reference="evidence://invalid-field",
        reviewer="reviewer-1",
        recorded_at=NOW,
        compensating_controls=("No coverage claim is made",),
    )
    with pytest.raises(ValidationError):
        ReadinessInput(
            context=context(),
            declared_use=use(),
            scope_exceptions=(exception,),
        )


def test_scope_exception_cannot_be_attached_to_available_field():
    import pytest
    from pydantic import ValidationError

    exception = ScopeException(
        field_name="vertical_datum",
        rationale="This field is already available and needs no exception.",
        evidence_reference="evidence://available-field",
        reviewer="reviewer-1",
        recorded_at=NOW,
        compensating_controls=("No additional control",),
    )
    with pytest.raises(ValidationError):
        ReadinessInput(
            context=context(),
            declared_use=use(),
            scope_exceptions=(exception,),
        )


def test_duplicate_scope_exceptions_for_same_field_are_rejected():
    import pytest
    from pydantic import ValidationError

    exception = ScopeException(
        field_name="vertical_datum",
        rationale="This declared task avoids absolute elevation comparisons.",
        evidence_reference="evidence://task-profile/relative-only",
        reviewer="reviewer-1",
        recorded_at=NOW,
        compensating_controls=("Suppress absolute-height outputs",),
    )
    missing = EvidenceValue(
        availability=Availability.NOT_AVAILABLE,
        reason="Datum not published.",
        reviewer="reviewer-1",
        recorded_at=NOW,
    )
    with pytest.raises(ValidationError):
        ReadinessInput(
            context=context(vertical_datum=missing),
            declared_use=use(),
            scope_exceptions=(exception, exception),
        )


def test_not_assessed_reason_code_is_not_misclassified_as_unresolved():
    result = assess_readiness(
        ReadinessInput(
            context=context(validation_status=evidence("not_assessed")),
            declared_use=use(),
            unresolved_items=(reason(ReasonCode.NOT_ASSESSED),),
        )
    )
    assert result.disposition is ReadinessDisposition.NOT_ASSESSED
