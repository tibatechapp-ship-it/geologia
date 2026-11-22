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
