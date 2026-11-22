"""Coverage sufficiency assessment for the pre-registered Yemen DEM protocol.

This module evaluates reference coverage only. It does not calculate DEM
accuracy, validate source independence, or infer terrain representativeness.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import Availability, EvidenceValue, ReasonCode
from .thresholds import FROZEN_V1_THRESHOLDS


NonEmpty = Annotated[str, Field(min_length=1)]
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


class CoverageMetrics(BaseModel):
    """Precomputed counts from the exact registered polygon and reference source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    valid_independent_locations: int | None = Field(default=None, ge=0)
    polygon_area_km2: float | None = Field(default=None, gt=0)
    occupied_5km_blocks: int | None = Field(default=None, ge=0)
    eligible_5km_blocks: int | None = Field(default=None, gt=0)
    max_block_observation_fraction: float | None = Field(default=None, ge=0, le=1)
    primary_cell_observation_counts: CellCounts = Field(default_factory=dict)
    temporal_match_fraction: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_spatial_counts(self) -> "CoverageMetrics":
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


class CoverageAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: CoveragePhase
    status: CoverageDecisionStatus
    actual_coverage: EvidenceValue
    coverage_status: CoverageStatus
    valid_independent_locations_per_km2: float | None = None
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
    *,
    actual_coverage: EvidenceValue,
    coverage_status: CoverageStatus,
    metrics: CoverageMetrics,
    phase: CoveragePhase,
) -> CoverageAssessment:
    """Evaluate frozen spatial/temporal screening gates for one coverage unit.

    Inputs are the exact product-footprint evidence, its verification status,
    and measurements computed inside the registered polygon. Analogue-region
    labels and Saudi–Yemen representativeness records are deliberately absent.
    """
    if coverage_status is CoverageStatus.NOT_ASSESSED:
        return CoverageAssessment(
            phase=phase,
            status=CoverageDecisionStatus.NOT_ASSESSED,
            actual_coverage=actual_coverage,
            coverage_status=coverage_status,
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
            phase=phase,
            status=CoverageDecisionStatus.NOT_EVALUABLE,
            actual_coverage=actual_coverage,
            coverage_status=coverage_status,
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
            explanation="Occupied share of all eligible blocks, without post-hoc boundary trimming.",
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
            "All applicable frozen coverage screening gates passed for this exact "
            "product footprint, polygon, phase and reference source. This does not "
            "establish datum readiness, source independence or DEM accuracy."
        )

    return CoverageAssessment(
        phase=phase,
        status=status,
        actual_coverage=actual_coverage,
        coverage_status=coverage_status,
        valid_independent_locations_per_km2=density,
        gates=tuple(gates),
        reason_codes=tuple(dict.fromkeys(reasons)),
        interpretation=interpretation,
    )
