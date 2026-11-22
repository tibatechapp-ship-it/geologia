from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from geologia.dem_readiness.coverage import (
    CoverageDecisionStatus,
    CoverageAssessmentRequest,
    CoverageEvidenceAttestation,
    CoverageMetrics,
    CoveragePhase,
    CoverageUnitContext,
    CoverageStatus,
    evaluate_coverage_sufficiency,
)
from geologia.dem_readiness.models import Availability, EvidenceValue, ReasonCode


def unit_context():
    return CoverageUnitContext(
        product_dataset_id="dataset-dem-1",
        product_dataset_sha256="b" * 64,
        reference_dataset_id="dataset-reference-1",
        reference_dataset_sha256="a" * 64,
        aoi_dataset_id="dataset-aoi-1",
        aoi_dataset_sha256="c" * 64,
        product_version_id="copernicus-glo30-release-x",
        pilot_area_id="yemen-pilot-west-01",
        reference_source_id="icesat2-atl08-release-x",
        primary_stratum_id="steep-bare",
        task_profile_id="regional-reconnaissance-v1",
    )


def evidence_attestation():
    return CoverageEvidenceAttestation(
        coverage_footprint_reference="coverage://product-release/pilot-polygon-v1",
        coverage_verification_method="Raster footprint intersected with registered AOI.",
        coverage_reviewer="reviewer-1",
        coverage_verified_at=datetime(2026, 11, 22, tzinfo=UTC),
        metrics_source_reference="evidence://reference-observations/1",
        metrics_computation_method="Frozen equal-area 1 km and 5 km grid count script.",
        metrics_computed_by="analyst-1",
        metrics_computed_at=datetime(2026, 11, 22, tzinfo=UTC),
        source_sha256="a" * 64,
        analysis_code_commit="a1b2c3d4",
    )


def assess_coverage(*, actual_coverage, coverage_status, metrics, phase):
    request = CoverageAssessmentRequest(
        context=unit_context(),
        actual_coverage=actual_coverage,
        coverage_status=coverage_status,
        metrics=metrics,
        phase=phase,
        evidence=evidence_attestation()
        if coverage_status is CoverageStatus.VERIFIED
        else None,
    )
    return evaluate_coverage_sufficiency(request)


def verified_coverage():
    return EvidenceValue(
        availability=Availability.AVAILABLE,
        value="coverage://product-release/pilot-polygon-v1",
    )


def exploratory_metrics():
    return CoverageMetrics(
        valid_independent_locations=60,
        polygon_area_km2=3.0,
        occupied_1km_cells=40,
        eligible_1km_cells=60,
        occupied_5km_blocks=20,
        eligible_5km_blocks=30,
        max_block_observation_fraction=0.50,
        primary_cell_observation_counts={"steep_bare": 30, "moderate_bare": 30},
    )


def confirmatory_metrics():
    return CoverageMetrics(
        valid_independent_locations=120,
        polygon_area_km2=3.0,
        occupied_1km_cells=60,
        eligible_1km_cells=80,
        occupied_5km_blocks=30,
        eligible_5km_blocks=40,
        max_block_observation_fraction=0.50,
        primary_cell_observation_counts={"steep_bare": 50, "moderate_bare": 70},
        temporal_match_fraction=0.70,
    )


def test_exploratory_coverage_passes_all_frozen_gates():
    result = assess_coverage(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.VERIFIED,
        metrics=exploratory_metrics(),
        phase=CoveragePhase.EXPLORATORY,
    )
    assert result.status is CoverageDecisionStatus.SUFFICIENT
    assert result.valid_independent_locations_per_km2 == 20
    assert result.occupied_1km_cell_fraction == pytest.approx(2 / 3)
    assert all(gate.status.value in {"pass", "not_applicable"} for gate in result.gates)


def test_confirmatory_coverage_passes_at_frozen_boundaries():
    result = assess_coverage(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.VERIFIED,
        metrics=confirmatory_metrics(),
        phase=CoveragePhase.CONFIRMATORY,
    )
    assert result.status is CoverageDecisionStatus.SUFFICIENT
    assert result.valid_independent_locations_per_km2 == 40


def test_low_density_is_insufficient_reference_coverage_not_dem_failure():
    metrics = exploratory_metrics().model_copy(update={"polygon_area_km2": 6.0})
    result = assess_coverage(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.VERIFIED,
        metrics=metrics,
        phase=CoveragePhase.EXPLORATORY,
    )
    assert result.status is CoverageDecisionStatus.INSUFFICIENT
    assert ReasonCode.INSUFFICIENT_SAMPLE in result.reason_codes
    assert "not evidence that the DEM itself is inaccurate" in result.interpretation


def test_unverified_actual_coverage_cannot_be_replaced_by_analogue_geography():
    result = assess_coverage(
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
    result = assess_coverage(
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
    result = assess_coverage(
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


def test_not_assessed_coverage_status_does_not_run_sufficiency_gates():
    result = assess_coverage(
        actual_coverage=verified_coverage(),
        coverage_status=CoverageStatus.NOT_ASSESSED,
        metrics=confirmatory_metrics(),
        phase=CoveragePhase.CONFIRMATORY,
    )
    assert result.status is CoverageDecisionStatus.NOT_ASSESSED
    assert result.gates == ()


def test_verified_coverage_requires_explicit_evidence_attestation():
    with pytest.raises(ValidationError):
        CoverageAssessmentRequest(
            context=unit_context(),
            phase=CoveragePhase.EXPLORATORY,
            actual_coverage=verified_coverage(),
            coverage_status=CoverageStatus.VERIFIED,
            metrics=exploratory_metrics(),
        )


def test_metrics_attestation_checksum_must_match_reference_dataset():
    with pytest.raises(ValidationError):
        CoverageAssessmentRequest(
            context=unit_context(),
            phase=CoveragePhase.EXPLORATORY,
            actual_coverage=verified_coverage(),
            coverage_status=CoverageStatus.VERIFIED,
            metrics=exploratory_metrics(),
            evidence=evidence_attestation().model_copy(
                update={"source_sha256": "c" * 64}
            ),
        )
