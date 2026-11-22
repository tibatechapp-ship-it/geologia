from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from geologia.dem_readiness.coverage import (
    CoverageDecisionStatus,
    CoverageMetrics,
    CoveragePhase,
    CoverageStatus,
    evaluate_coverage_sufficiency,
)
from geologia.dem_readiness.models import Availability, EvidenceValue, ReasonCode


def verified_coverage():
    return EvidenceValue(
        availability=Availability.AVAILABLE,
        value="coverage://product-release/pilot-polygon-v1",
    )


def exploratory_metrics():
    return CoverageMetrics(
        valid_independent_locations=60,
        polygon_area_km2=3.0,
        occupied_5km_blocks=20,
        eligible_5km_blocks=30,
        max_block_observation_fraction=0.50,
        primary_cell_observation_counts={"steep_bare": 30, "moderate_bare": 30},
    )


def confirmatory_metrics():
    return CoverageMetrics(
        valid_independent_locations=120,
        polygon_area_km2=3.0,
        occupied_5km_blocks=30,
        eligible_5km_blocks=40,
        max_block_observation_fraction=0.50,
        primary_cell_observation_counts={"steep_bare": 50, "moderate_bare": 70},
        temporal_match_fraction=0.70,
    )


def test_exploratory_coverage_passes_all_frozen_gates():
    result = evaluate_coverage_sufficiency(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.VERIFIED,
        metrics=exploratory_metrics(),
        phase=CoveragePhase.EXPLORATORY,
    )
    assert result.status is CoverageDecisionStatus.SUFFICIENT
    assert result.valid_independent_locations_per_km2 == 20
    assert all(gate.status.value in {"pass", "not_applicable"} for gate in result.gates)


def test_confirmatory_coverage_passes_at_frozen_boundaries():
    result = evaluate_coverage_sufficiency(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.VERIFIED,
        metrics=confirmatory_metrics(),
        phase=CoveragePhase.CONFIRMATORY,
    )
    assert result.status is CoverageDecisionStatus.SUFFICIENT
    assert result.valid_independent_locations_per_km2 == 40


def test_low_density_is_insufficient_reference_coverage_not_dem_failure():
    metrics = exploratory_metrics().model_copy(update={"valid_independent_locations": 30})
    result = evaluate_coverage_sufficiency(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.VERIFIED,
        metrics=metrics,
        phase=CoveragePhase.EXPLORATORY,
    )
    assert result.status is CoverageDecisionStatus.INSUFFICIENT
    assert ReasonCode.INSUFFICIENT_SAMPLE in result.reason_codes
    assert "not evidence that the DEM itself is inaccurate" in result.interpretation


def test_unverified_actual_coverage_cannot_be_replaced_by_analogue_geography():
    result = evaluate_coverage_sufficiency(
        actual_coverage=EvidenceValue(
            availability=Availability.NOT_AVAILABLE,
            reason="No exact product footprint has been obtained.",
            reviewer="reviewer-1",
            recorded_at=datetime(2026, 11, 22, tzinfo=UTC),
        ),
        coverage_status=CoverageStatus.UNVERIFIED,
        metrics=confirmatory_metrics(),
        phase=CoveragePhase.CONFIRMATORY,
    )
    assert result.status is CoverageDecisionStatus.NOT_EVALUABLE
    assert ReasonCode.METADATA_INSUFFICIENT in result.reason_codes


def test_missing_confirmatory_temporal_metric_prevents_sufficiency_pass():
    metrics = confirmatory_metrics().model_copy(update={"temporal_match_fraction": None})
    result = evaluate_coverage_sufficiency(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.VERIFIED,
        metrics=metrics,
        phase=CoveragePhase.CONFIRMATORY,
    )
    assert result.status is CoverageDecisionStatus.NOT_EVALUABLE
    assert ReasonCode.NOT_ASSESSED in result.reason_codes


def test_block_concentration_failure_is_spatially_clustered():
    metrics = exploratory_metrics().model_copy(
        update={"max_block_observation_fraction": 0.60}
    )
    result = evaluate_coverage_sufficiency(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.VERIFIED,
        metrics=metrics,
        phase=CoveragePhase.EXPLORATORY,
    )
    assert result.status is CoverageDecisionStatus.INSUFFICIENT
    assert ReasonCode.SPATIALLY_CLUSTERED in result.reason_codes


def test_occupied_blocks_cannot_exceed_eligible_blocks():
    with pytest.raises(ValidationError):
        CoverageMetrics(occupied_5km_blocks=10, eligible_5km_blocks=5)
