"""Evidence-based DEM readiness contracts for declared use profiles."""

from .models import (
    Availability,
    DeclaredUseContext,
    EvidenceValue,
    MandatoryProductContext,
    ReadinessAssessment,
    ReadinessDisposition,
    ReadinessInput,
    ReasonCode,
    ReasonRecord,
    ScopeException,
    ValidationStatus,
)
from .readiness import assess_readiness
from .coverage import (
    CoverageAssessment,
    CoverageEvidence,
    CoverageMetric,
    CoverageOutcome,
    CoverageRecord,
    PrecisionStatus,
    SourceIndependenceStatus,
    evaluate_coverage,
)
from .report import (
    AnalogueComparisonRecord,
    DEMReadinessReport,
    RepresentativenessStatus,
    build_readiness_report,
)from .thresholds import FROZEN_V1_THRESHOLDS

__all__ = [
    "Availability",
    "AnalogueComparisonRecord",
    "CoverageAssessment",
    "CoverageEvidence",
    "CoverageMetric",
    "CoverageOutcome",
    "CoverageRecord",
    "DEMReadinessReport",
    "DeclaredUseContext",
    "EvidenceValue",
    "FROZEN_V1_THRESHOLDS",
    "MandatoryProductContext",
    "ReadinessAssessment",
    "ReadinessDisposition",
    "ReadinessInput",
    "RepresentativenessStatus",
    "ReasonCode",
    "ReasonRecord",
    "ScopeException",
    "SourceIndependenceStatus",
    "PrecisionStatus",
    "ValidationStatus",
    "assess_readiness",
    "build_readiness_report",
    "evaluate_coverage",
]
