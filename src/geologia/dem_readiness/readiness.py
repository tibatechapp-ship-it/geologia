"""Deterministic readiness decision rules; no scientific result is inferred."""

from .models import (
    ReadinessAssessment,
    ReadinessDisposition,
    ReadinessInput,
    ReasonCode,
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
    if missing:
        codes = tuple(dict.fromkeys((*codes, ReasonCode.METADATA_INSUFFICIENT)))
    exceptions = {item.field_name: item for item in data.scope_exceptions}
    excepted = tuple(name for name in missing if name in exceptions)
    unexcepted = tuple(
        name for name in missing
        if name not in exceptions or name == "validation_status"
    )

    if data.mandatory_failures:
        disposition = ReadinessDisposition.NOT_READY
        explanation = (
            "At least one mandatory requirement is demonstrably not met. "
            "All recorded reasons are retained; secondary reasons are not hidden."
        )
        blocking = ()
    elif unexcepted or any(
        item.code is not ReasonCode.NOT_ASSESSED for item in data.unresolved_items
    ):
        disposition = ReadinessDisposition.NOT_EVALUABLE
        explanation = (
            "No mandatory failure is proven, but unresolved evidence or missing "
            "mandatory context prevents a defensible readiness decision."
        )
        blocking = unexcepted
    elif any(item.code is ReasonCode.NOT_ASSESSED for item in data.unresolved_items):
        codes = tuple(dict.fromkeys((*codes, ReasonCode.NOT_ASSESSED)))
        disposition = ReadinessDisposition.NOT_ASSESSED
        explanation = (
            "The relevant validation work has not been performed; "
            "no readiness claim is made."
        )
        blocking = ()
    elif data.context.validation_status.value in {
        "planned", "coverage_checked", "reference_ready", "not_assessed"
    }:
        codes = tuple(dict.fromkeys((*codes, ReasonCode.NOT_ASSESSED)))
        disposition = ReadinessDisposition.NOT_ASSESSED
        explanation = (
            "The validation has not reached independent review; no readiness claim is made."
        )
        blocking = ()
    elif data.context.validation_status.value == "analyzed":
        codes = tuple(dict.fromkeys((*codes, ReasonCode.UNRESOLVED)))
        disposition = ReadinessDisposition.NOT_EVALUABLE
        explanation = (
            "Analysis exists, but the required independent review is not recorded."
        )
        blocking = ("validation_status",)
    elif (
        data.context.validation_status.value == "independently_reviewed"
        and data.independent_review is None
    ):
        codes = tuple(dict.fromkeys((*codes, ReasonCode.UNRESOLVED)))
        disposition = ReadinessDisposition.NOT_EVALUABLE
        explanation = (
            "The status claims independent review, but no attributable review record "
            "bound to this exact product, area and task is supplied."
        )
        blocking = ("independent_review",)
    elif (
        data.context.validation_status.value == "independently_reviewed"
        and data.independent_review is not None
        and data.accuracy_assessment is None
    ):
        codes = tuple(dict.fromkeys((*codes, ReasonCode.NOT_ASSESSED)))
        disposition = ReadinessDisposition.NOT_EVALUABLE
        explanation = (
            "Independent review is recorded, but no persisted, exact-scope accuracy "
            "assessment is supplied; readiness cannot be established."
        )
        blocking = ("accuracy_assessment",)
    elif (
        data.accuracy_assessment is not None
        and data.accuracy_assessment.accuracy_disposition
        == "accuracy_requirement_not_met"
    ):
        codes = tuple(dict.fromkeys((*codes, ReasonCode.ACCURACY_REQUIREMENT_NOT_MET)))
        disposition = ReadinessDisposition.NOT_READY
        explanation = (
            "The declared task's frozen accuracy requirement was not met by the "
            "bound primary assessment."
        )
        blocking = ("accuracy_assessment",)
    elif (
        data.accuracy_assessment is not None
        and data.accuracy_assessment.accuracy_disposition == "not_evaluable"
    ):
        codes = tuple(dict.fromkeys((*codes, ReasonCode.UNRESOLVED)))
        disposition = ReadinessDisposition.NOT_EVALUABLE
        explanation = (
            "The bound accuracy assessment is not evaluable for the declared use."
        )
        blocking = ("accuracy_assessment",)
    elif (
        data.accuracy_assessment is not None
        and data.accuracy_assessment.accuracy_disposition == "not_assessed"
    ):
        codes = tuple(dict.fromkeys((*codes, ReasonCode.NOT_ASSESSED)))
        disposition = ReadinessDisposition.NOT_ASSESSED
        explanation = "The bound accuracy assessment has not been completed."
        blocking = ("accuracy_assessment",)
    elif (
        data.accuracy_assessment is not None
        and data.accuracy_assessment.accuracy_disposition == "conditional_limited_use"
    ):
        codes = tuple(dict.fromkeys((*codes, ReasonCode.SOURCE_DEPENDENCE_CONFLICT)))
        disposition = ReadinessDisposition.CONDITIONAL
        explanation = (
            "Accuracy evidence is conditional and cannot support unrestricted "
            "readiness for the declared use."
        )
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
