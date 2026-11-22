from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from geologia.dem_readiness.coverage import (
    CoverageEvidence,
    CoverageMetric,
    CoverageOutcome,
    CoverageRecord,
    PrecisionStatus,
    evaluate_coverage,
)
from geologia.dem_readiness.models import ReasonCode


NOW = datetime(2026, 11, 22, tzinfo=UTC)


def metric(value):
    return CoverageMetric(value=value, available=True)


def coverage_record(**overrides):
    values = {
        "observations_per_primary_cell": metric(50),
        "valid_independent_locations_per_km2": metric(40),
        "occupied_independent_blocks": metric(30),
        "eligible_blocks_occupancy_fraction": metric(0.75),
        "maximum_observation_fraction_in_one_block": metric(0.50),
        "temporal_match_fraction_within_5_years": metric(0.70),
        "precision_status": PrecisionStatus.PASSED,
        "precision_evidence_reference": "evidence://precision/1",
        "precision_reviewer": "reviewer-1",
        "precision_recorded_at": NOW,
    }
    values.update(overrides)
    return CoverageRecord(
        product_version_id="release-1",
        pilot_area_id="pilot-1",
        reference_source_id="reference-1",
        primary_stratum_id="steep-highlands",
        product_epoch="2024",
        equal_area_crs="EPSG:6933",
        evidence=CoverageEvidence(**values),
    )


def test_frozen_thresholds_pass_both_coverage_gates():
    result = evaluate_coverage(coverage_record())
    assert result.exploratory.outcome is CoverageOutcome.PASS
    assert result.confirmatory.outcome is CoverageOutcome.PASS


def test_exploratory_can_pass_when_confirmatory_fails():
    result = evaluate_coverage(
        coverage_record(
            observations_per_primary_cell=metric(35),
            valid_independent_locations_per_km2=metric(25),
            occupied_independent_blocks=metric(22),
            eligible_blocks_occupancy_fraction=metric(0.65),
            temporal_match_fraction_within_5_years=metric(0.40),
        )
    )
    assert result.exploratory.outcome is CoverageOutcome.PASS
    assert result.confirmatory.outcome is CoverageOutcome.FAIL
    assert ReasonCode.INSUFFICIENT_SAMPLE in result.confirmatory.reason_codes
    assert ReasonCode.TEMPORAL_MISMATCH in result.confirmatory.reason_codes


def test_known_failure_is_not_hidden_by_missing_metric():
    missing = CoverageMetric(
        available=False,
        missing_reason="Reference track inventory is not complete.",
        reviewer="reviewer-1",
        recorded_at=NOW,
    )
    result = evaluate_coverage(
        coverage_record(
            valid_independent_locations_per_km2=metric(5),
            temporal_match_fraction_within_5_years=missing,
        )
    )
    assert result.confirmatory.outcome is CoverageOutcome.FAIL
    assert ReasonCode.INSUFFICIENT_SAMPLE in result.confirmatory.reason_codes
    assert ReasonCode.UNRESOLVED in result.confirmatory.reason_codes


def test_missing_metric_requires_auditable_reason():
    with pytest.raises(ValidationError):
        CoverageMetric(available=False)


def test_fraction_metric_rejects_values_above_one():
    with pytest.raises(ValidationError):
        CoverageEvidence(
            observations_per_primary_cell=metric(50),
            valid_independent_locations_per_km2=metric(40),
            occupied_independent_blocks=metric(30),
            eligible_blocks_occupancy_fraction=metric(1.2),
            maximum_observation_fraction_in_one_block=metric(0.5),
            temporal_match_fraction_within_5_years=metric(0.7),
            precision_status=PrecisionStatus.NOT_ASSESSED,
        )
