from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from geologia.dem_readiness.coverage import (
    CoverageAssessment,
    CoverageEvidence,
    CoverageMetric,
    CoverageRecord,
    PrecisionStatus,
    evaluate_coverage,
)
from geologia.dem_readiness.models import (
    Availability,
    DeclaredUseContext,
    EvidenceValue,
    MandatoryProductContext,
    ReadinessInput,
)
from geologia.dem_readiness.report import (
    AnalogueComparisonRecord,
    DEMReadinessReport,
    RepresentativenessStatus,
    build_readiness_report,
)


NOW = datetime(2026, 11, 22, tzinfo=UTC)


def available(value):
    return EvidenceValue(availability=Availability.AVAILABLE, value=value)


def readiness_input():
    context = MandatoryProductContext(
        **{
            name: available(
                "independently_reviewed" if name == "validation_status" else "verified"
            )
            for name in MandatoryProductContext.model_fields
        }
    )
    declared = DeclaredUseContext(
        product_name="Example DEM",
        product_version_id="release-1",
        pilot_area_id="pilot-1",
        task_profile_id="regional-reconnaissance-v1",
        intended_user="geological researcher",
        declared_scale="regional reconnaissance",
    )
    return ReadinessInput(context=context, declared_use=declared)


def coverage_assessment():
    m = lambda value: CoverageMetric(value=value, available=True)
    evidence = CoverageEvidence(
        observations_per_primary_cell=m(50),
        valid_independent_locations_per_km2=m(40),
        occupied_independent_blocks=m(30),
        eligible_blocks_occupancy_fraction=m(0.75),
        maximum_observation_fraction_in_one_block=m(0.5),
        temporal_match_fraction_within_5_years=m(0.7),
        precision_status=PrecisionStatus.PASSED,
        precision_evidence_reference="evidence://precision/1",
        precision_reviewer="reviewer-1",
        precision_recorded_at=NOW,
    )
    record = CoverageRecord(
        product_version_id="release-1",
        pilot_area_id="pilot-1",
        reference_source_id="reference-1",
        primary_stratum_id="steep-highlands",
        product_epoch="2024",
        equal_area_crs="EPSG:6933",
        evidence=evidence,
    )
    return evaluate_coverage(record)


def test_report_keeps_actual_coverage_and_analogue_hypothesis_separate():
    analogue = AnalogueComparisonRecord(
        analogue_region="Asir western highlands",
        yemen_target_stratum="western-highlands",
        representativeness_status=RepresentativenessStatus.UNQUANTIFIED,
        rationale="Physiographic continuity motivates a comparison, but matched data are not yet available.",
        reviewer="reviewer-1",
        recorded_at=NOW,
    )
    report = build_readiness_report(
        report_id="report-001",
        generated_at=NOW,
        readiness_input=readiness_input(),
        coverage_assessments=(coverage_assessment(),),
        analogue_comparisons=(analogue,),
    )
    payload = report.model_dump(mode="json")
    assert payload["accuracy_claim_status"] == "not_generated_by_readiness_report"
    assert payload["ranking_status"] == "not_generated"
    assert payload["coverage_assessments"][0]["confirmatory"]["outcome"] == "pass"
    assert payload["analogue_comparisons"][0]["representativeness_status"] == "unquantified"


def test_report_rejects_coverage_for_another_area_or_product_version():
    assessment = coverage_assessment()
    wrong_record = assessment.record.model_copy(update={"pilot_area_id": "different-area"})
    wrong_assessment = assessment.model_copy(update={"record": wrong_record})
    with pytest.raises(ValidationError):
        DEMReadinessReport(
            report_id="report-002",
            generated_at=NOW,
            declared_use=readiness_input().declared_use,
            readiness_input=readiness_input(),
            readiness_assessment=build_readiness_report(
                report_id="inner",
                generated_at=NOW,
                readiness_input=readiness_input(),
            ).readiness_assessment,
            coverage_assessments=(wrong_assessment,),
        )


def test_quantified_analogue_status_requires_evidence_reference():
    with pytest.raises(ValidationError):
        AnalogueComparisonRecord(
            analogue_region="Asir",
            yemen_target_stratum="western-highlands",
            representativeness_status=RepresentativenessStatus.QUANTITATIVELY_SUPPORTED,
            rationale="Matched independent terrain distributions support this limited comparison.",
            reviewer="reviewer-1",
            recorded_at=NOW,
        )
