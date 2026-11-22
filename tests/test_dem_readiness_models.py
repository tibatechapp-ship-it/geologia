from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from geologia.dem_readiness.models import (
    Availability,
    EvidenceValue,
    MandatoryProductContext,
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
