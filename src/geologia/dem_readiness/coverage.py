"""Coverage sufficiency assessment for the pre-registered Yemen DEM protocol.

This module evaluates reference coverage only. It does not calculate DEM
accuracy, validate source independence, or infer terrain representativeness.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import Availability, EvidenceValue, ReasonCode
from .thresholds import FROZEN_V1_THRESHOLDS


NonEmpty = Annotated[str, Field(min_length=1)]


def _is_timezone_aware(value: datetime) -> bool:
    """Require a timezone object with a usable UTC offset."""
    return value.tzinfo is not None and value.utcoffset() is not None


CellCounts = dict[NonEmpty, Annotated[int, Field(ge=0)]]


class CoveragePhase(StrEnum):
    EXPLORATORY = "exploratory"
    CONFIRMATORY = "confirmatory"


class CoverageStatus(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    NOT_AVAILABLE = "not_available"
    NOT_ASSESSED = "not_assessed"


class CoverageDecisionStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    NOT_EVALUABLE = "not_evaluable"
    NOT_ASSESSED = "not_assessed"


class CoverageGateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"


class CoverageGateCode(StrEnum):
    SPATIAL_DENSITY = "spatial_density"
    OCCUPIED_BLOCK_COUNT = "occupied_block_count"
    ELIGIBLE_BLOCK_FRACTION = "eligible_block_fraction"
    BLOCK_CONCENTRATION = "block_concentration"
    PRIMARY_CELL_SAMPLE = "primary_cell_sample"
    TEMPORAL_MATCH = "temporal_match"


class CoverageUnitContext(BaseModel):
    """Exact reporting unit: product release × area × reference × stratum × task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_dataset_id: NonEmpty
    product_dataset_sha256: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
    reference_dataset_id: NonEmpty
    reference_dataset_sha256: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
    aoi_dataset_id: NonEmpty
    aoi_dataset_sha256: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
    product_version_id: NonEmpty
    pilot_area_id: NonEmpty
    reference_source_id: NonEmpty
    primary_stratum_id: NonEmpty
    task_profile_id: NonEmpty


class CoverageMetrics(BaseModel):
    """Precomputed counts from the exact registered polygon and reference source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    valid_independent_locations: int | None = Field(default=None, ge=0)
    polygon_area_km2: float | None = Field(default=None, gt=0)
    occupied_1km_cells: int | None = Field(default=None, ge=0)
    eligible_1km_cells: int | None = Field(default=None, gt=0)
    occupied_5km_blocks: int | None = Field(default=None, ge=0)
    eligible_5km_blocks: int | None = Field(default=None, gt=0)
    max_block_observation_fraction: float | None = Field(default=None, ge=0, le=1)
    primary_cell_observation_counts: CellCounts = Field(default_factory=dict)
    temporal_match_fraction: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_spatial_counts(self) -> "CoverageMetrics":
        if (
            self.occupied_1km_cells is not None
            and self.eligible_1km_cells is not None
            and self.occupied_1km_cells > self.eligible_1km_cells
        ):
            raise ValueError("occupied_1km_cells cannot exceed eligible_1km_cells")
        if (
            self.occupied_5km_blocks is not None
            and self.eligible_5km_blocks is not None
            and self.occupied_5km_blocks > self.eligible_5km_blocks
        ):
            raise ValueError("occupied_5km_blocks cannot exceed eligible_5km_blocks")
        if (
            self.valid_independent_locations is not None
            and self.primary_cell_observation_counts
            and sum(self.primary_cell_observation_counts.values())
            > self.valid_independent_locations
        ):
            raise ValueError(
                "primary-cell counts cannot exceed total valid independent locations"
            )
        return self


class CoverageGate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: CoverageGateCode
    status: CoverageGateStatus
    unit: str
    observed_value: float | int | None = None
    threshold_value: float | int | None = None
    scope: str
    explanation: NonEmpty


class CoverageEvidenceAttestation(BaseModel):
    """Caller-attributed provenance for footprint verification and computed metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coverage_footprint_reference: NonEmpty
    coverage_verification_method: NonEmpty
    coverage_reviewer: NonEmpty
    coverage_verified_at: datetime
    metrics_source_reference: NonEmpty
    metrics_computation_method: NonEmpty
    metrics_computed_by: NonEmpty
    metrics_computed_at: datetime
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
    analysis_code_commit: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{7,40}$")]

    @model_validator(mode="after")
    def validate_timestamps(self) -> "CoverageEvidenceAttestation":
        if not _is_timezone_aware(self.coverage_verified_at):
            raise ValueError("coverage_verified_at must be timezone-aware")
        if not _is_timezone_aware(self.metrics_computed_at):
            raise ValueError("metrics_computed_at must be timezone-aware")
        return self


class CoverageAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: CoverageUnitContext
    phase: CoveragePhase
    actual_coverage: EvidenceValue
    coverage_status: CoverageStatus
    metrics: CoverageMetrics
    evidence: CoverageEvidenceAttestation | None = None

    @model_validator(mode="after")
    def require_attestation_for_verified_coverage(self) -> "CoverageAssessmentRequest":
        if self.coverage_status is CoverageStatus.VERIFIED:
            if self.actual_coverage.availability is not Availability.AVAILABLE:
                raise ValueError("verified coverage requires available actual_coverage evidence")
            if self.evidence is None:
                raise ValueError("verified coverage requires a complete evidence attestation")
        if self.evidence is not None:
            if self.evidence.source_sha256 != self.context.reference_dataset_sha256:
                raise ValueError(
                    "metrics source_sha256 must match the exact reference dataset checksum"
                )
            if self.actual_coverage.value != self.evidence.coverage_footprint_reference:
                raise ValueError(
                    "actual_coverage must match the attested coverage footprint reference"
                )
        return self


class CoverageAssessmentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    created_by: NonEmpty
    request: CoverageAssessmentRequest


class CoverageAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: CoverageUnitContext
    phase: CoveragePhase
    status: CoverageDecisionStatus
    actual_coverage: EvidenceValue
    coverage_status: CoverageStatus
    evidence: CoverageEvidenceAttestation | None = None
    valid_independent_locations_per_km2: float | None = None
    occupied_1km_cell_fraction: float | None = None
    gates: tuple[CoverageGate, ...]
    reason_codes: tuple[ReasonCode, ...]
    protocol_version: str = "1"
    threshold_freeze_date: str = FROZEN_V1_THRESHOLDS.implementation_freeze_date
    interpretation: NonEmpty


def _gate(
    *,
    code: CoverageGateCode,
    observed: float | int | None,
    threshold: float | int,
    unit: str,
    scope: str,
    explanation: str,
    comparator: str = "minimum",
) -> CoverageGate:
    if observed is None:
        status = CoverageGateStatus.NOT_ASSESSED
    elif comparator == "maximum":
        status = (
            CoverageGateStatus.PASS
            if observed <= threshold
            else CoverageGateStatus.FAIL
        )
    else:
        status = (
            CoverageGateStatus.PASS
            if observed >= threshold
            else CoverageGateStatus.FAIL
        )
    return CoverageGate(
        code=code,
        status=status,
        unit=unit,
        observed_value=observed,
        threshold_value=threshold,
        scope=scope,
        explanation=explanation,
    )


def evaluate_coverage_sufficiency(
    request: CoverageAssessmentRequest,
) -> CoverageAssessment:
    """Evaluate frozen spatial/temporal screening gates for one coverage unit.

    Inputs are the exact product-footprint evidence, its verification status,
    and measurements computed inside the registered polygon. Analogue-region
    labels and Saudi–Yemen representativeness records are deliberately absent.
    """
    context = request.context
    phase = request.phase
    actual_coverage = request.actual_coverage
    coverage_status = request.coverage_status
    metrics = request.metrics

    if coverage_status is CoverageStatus.NOT_ASSESSED:
        return CoverageAssessment(
            context=context,
            phase=phase,
            status=CoverageDecisionStatus.NOT_ASSESSED,
            actual_coverage=actual_coverage,
            coverage_status=coverage_status,
            evidence=request.evidence,
            gates=(),
            reason_codes=(ReasonCode.NOT_ASSESSED,),
            interpretation=(
                "Product coverage has not been assessed. No coverage sufficiency "
                "or product-readiness conclusion is available."
            ),
        )

    if (
        actual_coverage.availability is not Availability.AVAILABLE
        or coverage_status is not CoverageStatus.VERIFIED
        or not isinstance(actual_coverage.value, str)
    ):
        return CoverageAssessment(
            context=context,
            phase=phase,
            status=CoverageDecisionStatus.NOT_EVALUABLE,
            actual_coverage=actual_coverage,
            coverage_status=coverage_status,
            evidence=request.evidence,
            gates=(),
            reason_codes=(ReasonCode.METADATA_INSUFFICIENT,),
            interpretation=(
                "The exact product footprint is unavailable, partial or unverified. "
                "Coverage sufficiency cannot be inferred from an analogue region."
            ),
        )

    thresholds = FROZEN_V1_THRESHOLDS
    section13 = thresholds.section_13
    section17 = thresholds.section_17
    if phase is CoveragePhase.EXPLORATORY:
        density_floor = section17.exploratory_valid_locations_per_km2
        block_floor = section17.exploratory_occupied_blocks
        fraction_floor = section17.exploratory_eligible_blocks_fraction
        cell_floor = section13.exploratory_observations_per_primary_cell
    else:
        density_floor = section17.confirmatory_valid_locations_per_km2
        block_floor = section17.confirmatory_occupied_blocks
        fraction_floor = section17.confirmatory_eligible_blocks_fraction
        cell_floor = section13.confirmatory_observations_per_primary_cell

    density = None
    if metrics.valid_independent_locations is not None and metrics.polygon_area_km2 is not None:
        density = metrics.valid_independent_locations / metrics.polygon_area_km2

    occupied_1km_fraction = (
        metrics.occupied_1km_cells / metrics.eligible_1km_cells
        if metrics.occupied_1km_cells is not None
        and metrics.eligible_1km_cells is not None
        else None
    )

    gates: list[CoverageGate] = [
        _gate(
            code=CoverageGateCode.SPATIAL_DENSITY,
            observed=density,
            threshold=density_floor,
            unit="valid independent locations/km²",
            scope="registered polygon and reference source",
            explanation="Independent-location density against the frozen phase floor.",
        ),
        _gate(
            code=CoverageGateCode.OCCUPIED_BLOCK_COUNT,
            observed=metrics.occupied_5km_blocks,
            threshold=block_floor,
            unit="occupied 5 km blocks",
            scope="registered equal-area 5 km grid",
            explanation="Occupied independent spatial blocks against the frozen phase floor.",
        ),
        _gate(
            code=CoverageGateCode.ELIGIBLE_BLOCK_FRACTION,
            observed=(
                metrics.occupied_5km_blocks / metrics.eligible_5km_blocks
                if metrics.occupied_5km_blocks is not None
                and metrics.eligible_5km_blocks is not None
                else None
            ),
            threshold=fraction_floor,
            unit="fraction of pre-defined eligible blocks",
            scope="full pre-registered polygon denominator",
            explanation=(
                "Occupied share of all eligible blocks, "
                "without post-hoc boundary trimming."
            ),
        ),
        _gate(
            code=CoverageGateCode.BLOCK_CONCENTRATION,
            observed=metrics.max_block_observation_fraction,
            threshold=section17.maximum_observation_fraction_in_one_block,
            unit="maximum observation share",
            scope="largest single pre-defined 5 km block",
            explanation="Maximum allowed share of valid observations in one block.",
            comparator="maximum",
        ),
    ]

    if metrics.primary_cell_observation_counts:
        for cell_id, count in sorted(metrics.primary_cell_observation_counts.items()):
            gates.append(
                _gate(
                    code=CoverageGateCode.PRIMARY_CELL_SAMPLE,
                    observed=count,
                    threshold=cell_floor,
                    unit="valid independent observations",
                    scope=f"primary stratum: {cell_id}",
                    explanation="Per-primary-cell sample floor from protocol Section 13.",
                )
            )
    else:
        gates.append(
            CoverageGate(
                code=CoverageGateCode.PRIMARY_CELL_SAMPLE,
                status=CoverageGateStatus.NOT_ASSESSED,
                unit="valid independent observations",
                observed_value=None,
                threshold_value=cell_floor,
                scope="all registered primary strata",
                explanation="No per-primary-cell observation counts were supplied.",
            )
        )

    if phase is CoveragePhase.CONFIRMATORY:
        gates.append(
            _gate(
                code=CoverageGateCode.TEMPORAL_MATCH,
                observed=metrics.temporal_match_fraction,
                threshold=section17.confirmatory_temporal_match_fraction,
                unit="fraction within five years of DEM epoch",
                scope="this exact DEM epoch, polygon and primary stratum",
                explanation="Confirmatory temporal-match gate from protocol Section 17.",
            )
        )
    else:
        gates.append(
            CoverageGate(
                code=CoverageGateCode.TEMPORAL_MATCH,
                status=CoverageGateStatus.NOT_APPLICABLE,
                unit="fraction within five years of DEM epoch",
                observed_value=metrics.temporal_match_fraction,
                threshold_value=None,
                scope="exploratory screening",
                explanation="The five-year / 70% gate is confirmatory only.",
            )
        )

    failed = [gate for gate in gates if gate.status is CoverageGateStatus.FAIL]
    unassessed = [
        gate for gate in gates if gate.status is CoverageGateStatus.NOT_ASSESSED
    ]
    reasons: list[ReasonCode] = []
    for gate in failed:
        if gate.code in {
            CoverageGateCode.SPATIAL_DENSITY,
            CoverageGateCode.OCCUPIED_BLOCK_COUNT,
            CoverageGateCode.PRIMARY_CELL_SAMPLE,
        }:
            reasons.append(ReasonCode.INSUFFICIENT_SAMPLE)
        elif gate.code is CoverageGateCode.BLOCK_CONCENTRATION:
            reasons.append(ReasonCode.SPATIALLY_CLUSTERED)
        elif gate.code is CoverageGateCode.ELIGIBLE_BLOCK_FRACTION:
            reasons.append(ReasonCode.SPATIALLY_CLUSTERED)
        elif gate.code is CoverageGateCode.TEMPORAL_MATCH:
            reasons.append(ReasonCode.TEMPORAL_MISMATCH)
    if unassessed:
        reasons.append(ReasonCode.NOT_ASSESSED)

    if failed:
        status = CoverageDecisionStatus.INSUFFICIENT
        interpretation = (
            "At least one frozen coverage gate failed. This is a reference-coverage "
            "limitation, not evidence that the DEM itself is inaccurate."
        )
    elif unassessed:
        status = CoverageDecisionStatus.NOT_EVALUABLE
        interpretation = (
            "The exact product footprint is verified, but one or more required "
            "coverage measurements are missing. No sufficiency pass is assigned."
        )
    else:
        status = CoverageDecisionStatus.SUFFICIENT
        interpretation = (
            "All applicable frozen coverage screening gates passed for the supplied "
            "and attested product footprint, polygon, phase and reference source. "
            "This is an input-screening result, not independent verification; it does "
            "not establish datum readiness, source independence or DEM accuracy."
        )

    return CoverageAssessment(
        context=context,
        phase=phase,
        status=status,
        actual_coverage=actual_coverage,
        coverage_status=coverage_status,
        evidence=request.evidence,
        valid_independent_locations_per_km2=density,
        occupied_1km_cell_fraction=occupied_1km_fraction,
        gates=tuple(gates),
        reason_codes=tuple(dict.fromkeys(reasons)),
        interpretation=interpretation,
    )
