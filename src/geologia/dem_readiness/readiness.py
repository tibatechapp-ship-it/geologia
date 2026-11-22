"""Deterministic readiness decision rules; no scientific result is inferred."""

from .models import (
    Availability,
    ReadinessAssessment,
    ReadinessDisposition,
    ReadinessInput,
)
from .reason_codes import all_reason_codes


DECISION_RULE_VERSION = "dem-readiness-v1"


def assess_readiness(data: ReadinessInput) -> ReadinessAssessment:
    """Assess a product/version × area × task tuple using explicit precedence.

    Precedence:
    1. A proven mandatory requirement failure means not_ready.
    2. Otherwise, material unresolved evidence or unexcepted missing mandatory
       fields means not_evaluable.
    3. Otherwise, documented accepted restrictions/exceptions mean conditional.
    4. Only a complete, assessed record with no restrictions can be ready.
    5. Explicit not_assessed validation status remains not_assessed.
    """
    codes = all_reason_codes(data)
    missing = tuple(data.context.unavailable_fields())
    exceptions = {item.field_name: item for item in data.scope_exceptions}
    excepted = tuple(name for name in missing if name in exceptions)
    unexcepted = tuple(name for name in missing if name not in exceptions)

    if data.mandatory_failures:
        disposition = ReadinessDisposition.NOT_READY
        explanation = (
            "At least one mandatory requirement is demonstrably not met. "
            "All recorded reasons are retained; secondary reasons are not hidden."
        )
        blocking = ()
    elif data.unresolved_items or unexcepted:
        disposition = ReadinessDisposition.NOT_EVALUABLE
        explanation = (
            "No mandatory failure is proven, but unresolved evidence or missing "
            "mandatory context prevents a defensible readiness decision."
        )
        blocking = unexcepted
        if data.unresolved_items:
            codes = tuple(dict.fromkeys((*codes,)))
    elif (
        data.context.validation_status.value == "not_assessed"
        or any(record.code.value == "not_assessed" for record in data.unresolved_items)
    ):
        disposition = ReadinessDisposition.NOT_ASSESSED
        explanation = "The validation has not been performed; no readiness claim is made."
        blocking = ()
    elif data.accepted_restrictions or excepted:
        disposition = ReadinessDisposition.CONDITIONAL
        explanation = (
            "Use is limited to the declared scope by documented, accepted restrictions. "
            "Every unavailable field is covered by an explicit evidence-backed scope exception."
        )
        blocking = ()
    else:
        disposition = ReadinessDisposition.READY
        explanation = (
            "All mandatory context is available and no recorded mandatory failure, "
            "unresolved item or accepted restriction blocks this declared use."
        )
        blocking = ()

    return ReadinessAssessment(
        disposition=disposition,
        declared_use=data.declared_use,
        reason_codes=codes,
        blocking_fields=blocking,
        applied_scope_exceptions=excepted,
        decision_rule_version=DECISION_RULE_VERSION,
        explanation=explanation,
    )
