"""Reason-code aggregation and readiness precedence helpers."""

from .models import ReadinessInput, ReasonCode


def all_reason_codes(data: ReadinessInput) -> tuple[ReasonCode, ...]:
    """Return every recorded reason once, preserving first-seen order."""
    records = (
        *data.mandatory_failures,
        *data.unresolved_items,
        *data.accepted_restrictions,
    )
    return tuple(dict.fromkeys(record.code for record in records))
