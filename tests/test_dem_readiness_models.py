from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from geologia.dem_readiness.models import (
    Availability,
    EvidenceValue,
    MandatoryProductContext,
    AnalogueRepresentativenessContext,
    RepresentativenessStatus,
)


def test_not_available_requires_reason_reviewer_and_timezone():
    with pytest.raises(ValidationError):
        EvidenceValue(availability=Availability.NOT_AVAILABLE)


def test_available_value_rejects_blank_string():
    with pytest.raises(ValidationError):
        EvidenceValue(availability=Availability.AVAILABLE, value="  ")


def test_not_available_record_is_auditable():
    value = EvidenceValue(
        availability=Availability.NOT_AVAILABLE,
        reason="The provider has not published the vertical datum.",
        reviewer="reviewer-1",
        recorded_at=datetime(2026, 11, 22, tzinfo=UTC),
    )
    assert value.value is None
    assert value.availability is Availability.NOT_AVAILABLE


def test_mandatory_context_lists_every_unavailable_field():
    fields = {
        name: EvidenceValue(
            availability=Availability.NOT_AVAILABLE,
            reason=f"{name} has not been verified.",
            reviewer="reviewer-1",
            recorded_at=datetime(2026, 11, 22, tzinfo=UTC),
        )
        for name in MandatoryProductContext.model_fields
    }
    context = MandatoryProductContext(**fields)
    assert set(context.unavailable_fields()) == set(MandatoryProductContext.model_fields)


def test_validation_status_rejects_unknown_values():
    fields = {
        name: EvidenceValue(availability=Availability.AVAILABLE, value="verified")
        for name in MandatoryProductContext.model_fields
    }
    fields["validation_status"] = EvidenceValue(
        availability=Availability.AVAILABLE,
        value="probably_ready",
    )
    with pytest.raises(ValidationError):
        MandatoryProductContext(**fields)


def test_analogue_pair_is_separate_from_product_coverage():
    analogue = AnalogueRepresentativenessContext(
        analogue_region="Asir western highlands",
        yemen_target_stratum="Yemen western highlands",
        representativeness_status=RepresentativenessStatus.UNQUANTIFIED,
        limitations=("Matched slope and land-cover distributions are not yet available.",),
    )
    assert analogue.representativeness_status is RepresentativenessStatus.UNQUANTIFIED
    assert not hasattr(analogue, "actual_coverage")


def test_assessed_analogue_requires_attributable_evidence():
    with pytest.raises(ValidationError):
        AnalogueRepresentativenessContext(
            analogue_region="Najran western mountain belt",
            yemen_target_stratum="Northern Yemen highlands",
            representativeness_status=RepresentativenessStatus.ASSESSED,
        )


def test_reason_record_requires_evidence_reference():
    from geologia.dem_readiness.models import ReasonCode, ReasonRecord

    with pytest.raises(ValidationError):
        ReasonRecord(
            code=ReasonCode.UNRESOLVED,
            stage="metadata",
            detail="The provider documentation is contradictory.",
            reviewer="reviewer-1",
            recorded_at=datetime(2026, 11, 22, tzinfo=UTC),
        )


from geologia.dem_readiness.models import (
    DependenceStatus,
    ElevationUncertainty,
    UncertaintyKind,
    UncertaintyScope,
)


def _uncertainty(**overrides):
    data = {
        "kind": UncertaintyKind.STANDARD,
        "value": 0.25,
        "unit": "m",
        "source_reference": "dataset:survey-2026",
        "method": "documented instrument standard uncertainty",
        "scope": UncertaintyScope.POINT_SPECIFIC,
        "dependence": DependenceStatus.UNKNOWN,
        "reviewer": "reviewer-1",
        "recorded_at": datetime(2026, 11, 22, tzinfo=UTC),
    }
    data.update(overrides)
    return ElevationUncertainty(**data)


def test_standard_uncertainty_preserves_semantics_and_unit():
    item = _uncertainty()
    assert item.kind is UncertaintyKind.STANDARD
    assert item.value == 0.25
    assert item.unit == "m"


def test_expanded_uncertainty_requires_coverage_factor_and_convention():
    with pytest.raises(ValidationError):
        _uncertainty(
            kind=UncertaintyKind.EXPANDED,
            coverage_factor=None,
            coverage_convention=None,
        )


def test_expanded_uncertainty_requires_explicit_coverage_metadata():
    item = _uncertainty(
        kind=UncertaintyKind.EXPANDED,
        coverage_factor=2.0,
        coverage_convention="k=2; stated convention in source report",
    )
    assert item.coverage_factor == 2.0


def test_confidence_interval_requires_level_and_interval_convention():
    with pytest.raises(ValidationError):
        _uncertainty(
            kind=UncertaintyKind.CONFIDENCE_INTERVAL_HALF_WIDTH,
            confidence_level=None,
            interval_convention=None,
        )


def test_unknown_uncertainty_cannot_be_given_numeric_value():
    with pytest.raises(ValidationError):
        _uncertainty(
            kind=UncertaintyKind.UNKNOWN,
            value=0.2,
            source_reference=None,
            method=None,
            unknown_reason="Provider does not define uncertainty semantics.",
        )


def test_unknown_uncertainty_requires_reason_and_no_numeric_value():
    item = _uncertainty(
        kind=UncertaintyKind.UNKNOWN,
        value=None,
        source_reference=None,
        method=None,
        unknown_reason="Provider field uncertainty_m is not defined.",
    )
    assert item.value is None
    assert item.kind is UncertaintyKind.UNKNOWN


@pytest.mark.parametrize("value", [-0.01, float("inf"), float("nan")])
def test_uncertainty_rejects_negative_or_non_finite_values(value):
    with pytest.raises(ValidationError):
        _uncertainty(value=value)


def test_correlated_uncertainty_requires_evidence_reference():
    with pytest.raises(ValidationError):
        _uncertainty(dependence=DependenceStatus.CORRELATED)


def test_correlated_uncertainty_records_dependence_evidence():
    item = _uncertainty(
        dependence=DependenceStatus.CORRELATED,
        dependence_evidence_reference="study:covariance-model-1",
    )
    assert item.dependence is DependenceStatus.CORRELATED


def test_uncertainty_requires_timezone_aware_recorded_at():
    with pytest.raises(ValidationError):
        _uncertainty(recorded_at=datetime(2026, 11, 22))
