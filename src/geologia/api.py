"""GEOLOGIA REST API: project workspace, safe dataset storage, and plan records."""
import argparse
import math
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

from geologia.dem_readiness.accuracy import (
    AccuracyRequirement,
    DEMAccuracyMetadata,
    compute_dem_reference_residuals,
)
from geologia.dem_readiness.models import (
    AccuracyAssessmentEvidence,
    DeclaredUseContext,
    ElevationUncertainty,
    IndependentReviewEvidence,
    MandatoryProductContext,
    ReadinessInput,
    ReasonRecord,
    ScopeException,
)
from geologia.dem_readiness.readiness import assess_readiness
from geologia.dem_readiness.coverage import (
    CoverageAssessmentRequest,
    CoverageAssessmentSubmission,
    evaluate_coverage_sufficiency,
)
from geologia.dem_readiness.manifest import DEMTileManifest
from geologia.dem_readiness.thresholds import FROZEN_V1_THRESHOLDS
from geologia import __version__
from geologia import knowledge, store
from geologia.planner import agent_status, build_plan
from geologia.registry import get_engine, list_engines
from geologia.vector import inspect_csv, inspect_geojson
from geologia.validation import validate_csv_file, validate_geojson_payload

@asynccontextmanager
async def lifespan(_: FastAPI):
    store.initialize()
    knowledge.initialize()
    yield


app = FastAPI(
    title="GEOLOGIA API",
    version=__version__,
    description="Bilingual geoscience workspace. Plans and stored datasets; no engine execution.",
    lifespan=lifespan,
)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_FORMATS = {".geojson", ".json", ".gpkg", ".tif", ".tiff", ".hgt", ".csv", ".las"}
def _dataset_content_matches(item: dict, path: Path) -> bool:
    """Verify stored bytes against the upload-time size and SHA-256 before reading them."""
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                size += len(chunk)
                if size > item["size_bytes"]:
                    return False
                digest.update(chunk)
    except OSError:
        return False
    return size == item["size_bytes"] and digest.hexdigest() == item["sha256"]


def _dataset_dependency_matches(
    project_id: str,
    dataset_id: str | None,
    expected_sha256: str | None,
    *,
    roles: tuple[str, ...],
    formats: tuple[str, ...],
) -> bool:
    """Verify a persisted assessment input still matches its upload record and bytes."""
    if not dataset_id or not expected_sha256:
        return False
    item = store.get_dataset(dataset_id)
    if (
        item is None
        or item["project_id"] != project_id
        or item["data_role"] not in roles
        or item["format"] not in formats
        or item["sha256"] != expected_sha256
    ):
        return False
    content_path = store.get_dataset_content_path(dataset_id)
    return content_path is not None and _dataset_content_matches(
        item, Path(content_path)
    )


ALLOWED_DATA_ROLES = {
    "dem", "geology_map", "recharge_estimate", "water_levels_timeseries", "well_logs",
    "structural_orientations", "contacts", "waveforms_or_catalog", "station_metadata",
    "geochemistry_samples", "geophysics_surveys", "aoi_boundary", "data_layers",
    "crs_definition", "imagery", "ground_control_points",
    "reference_elevation_observations", "dem_tile_manifest",
    "reference_uncertainty_sidecar",
}


class ProjectInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str = Field("", max_length=2000)
    language: Literal["ar", "en"] = "ar"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("project name must contain at least two non-space characters")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


class JobInput(BaseModel):
    request: str = Field(..., min_length=3, max_length=2000)
    language: Literal["ar", "en"] = "ar"

    @field_validator("request")
    @classmethod
    def normalize_request(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("request must contain at least three non-space characters")
        return value


class ReprojectInput(BaseModel):
    target_crs: str = Field(..., min_length=1, max_length=200)


class CoverageInspectionInput(BaseModel):
    aoi_dataset_id: str = Field(..., min_length=1, max_length=64)
    aoi_crs: str = Field(..., min_length=1, max_length=200)


class DEMTileCollectionCoverageInput(BaseModel):
    dem_dataset_ids: list[str] = Field(..., min_length=1, max_length=256)
    aoi_dataset_id: str = Field(..., min_length=1, max_length=64)
    aoi_crs: str = Field(..., min_length=1, max_length=200)

    @field_validator("dem_dataset_ids")
    @classmethod
    def validate_unique_dem_dataset_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 64 for value in normalized):
            raise ValueError("DEM dataset IDs must be non-empty and at most 64 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("DEM dataset IDs must be unique")
        return normalized


class DEMAccuracyAssessmentInput(BaseModel):
    product_manifest_dataset_id: str = Field(..., min_length=1, max_length=64)
    reference_dataset_id: str = Field(..., min_length=1, max_length=64)
    reference_uncertainty_sidecar_dataset_id: str | None = Field(default=None, max_length=64)
    aoi_dataset_id: str = Field(..., min_length=1, max_length=64)
    metadata: DEMAccuracyMetadata
    declared_use: DeclaredUseContext
    independent_review: IndependentReviewEvidence
    coverage_footprint_reference: str = Field(..., min_length=1, max_length=1024)
    requirement: AccuracyRequirement | None = None
    created_by: str = Field(..., min_length=1, max_length=128)

    @field_validator("created_by")
    @classmethod
    def nonblank_creator(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("created_by must be non-empty")
        return normalized


class DEMReadinessAssessmentInput(BaseModel):
    product_manifest_dataset_id: str = Field(..., min_length=1, max_length=64)
    declared_use: DeclaredUseContext
    context: MandatoryProductContext
    accuracy_assessment_id: str | None = Field(default=None, max_length=64)
    independent_review: IndependentReviewEvidence | None = None
    mandatory_failures: tuple[ReasonRecord, ...] = ()
    unresolved_items: tuple[ReasonRecord, ...] = ()
    accepted_restrictions: tuple[ReasonRecord, ...] = ()
    scope_exceptions: tuple[ScopeException, ...] = ()
    created_by: str = Field(..., min_length=1, max_length=128)

    @field_validator("created_by")
    @classmethod
    def nonblank_creator(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("created_by must be non-empty")
        return normalized


class ClaimInput(BaseModel):
    statement: str = Field(..., min_length=8, max_length=2000)
    created_by: str = Field(..., min_length=1, max_length=200)


class ClaimEvidenceInput(BaseModel):
    chunk_id: str = Field(..., min_length=1, max_length=64)
    relation: Literal["supports", "contradicts", "contextualizes", "unclear"]
    rationale: str = Field(..., min_length=1, max_length=2000)
    recorded_by: str = Field(..., min_length=1, max_length=200)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON numeric value must be finite")
    return parsed


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


MAX_JSON_DEPTH = 256
MAX_JSON_NODES = 1_000_000


def _check_json_limits(value: object) -> None:
    """Iteratively bound nested containers and total JSON values without recursive walking."""
    stack = [(iter((value,)), 0)]
    nodes = 0
    while stack:
        iterator, depth = stack[-1]
        try:
            child = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ValueError("JSON item count exceeds the supported limit")
        if isinstance(child, dict):
            next_depth = depth + 1
            if next_depth > MAX_JSON_DEPTH:
                raise ValueError("JSON nesting exceeds the supported depth")
            stack.append((iter(child.values()), next_depth))
        elif isinstance(child, list):
            next_depth = depth + 1
            if next_depth > MAX_JSON_DEPTH:
                raise ValueError("JSON nesting exceeds the supported depth")
            stack.append((iter(child), next_depth))


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
            parse_float=_finite_json_float,
            object_pairs_hook=_unique_json_object,
        )
        _check_json_limits(payload)
        return payload
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds the supported depth") from exc


def _geojson_summary(path: Path) -> dict:
    try:
        payload = _read_json(path)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
        ) from exc
    try:
        metrics = inspect_geojson(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid GeoJSON: {exc}") from exc
    return {"validation": "structural_only", "feature_count": metrics["feature_count"]}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "geologia", "version": __version__,
            "engines_integrated": 0, "execution_enabled": False}

@app.get("/api/v1/dem/coverage-thresholds")
def dem_coverage_thresholds() -> dict:
    """Expose immutable protocol v1 screening thresholds; not DEM accuracy limits."""
    return FROZEN_V1_THRESHOLDS.model_dump(mode="json")


@app.post("/api/v1/dem/coverage-assessments")
def dem_coverage_assessment(body: CoverageAssessmentRequest) -> dict:
    """Preview caller-supplied reference coverage metrics; no files are inspected or stored."""
    return evaluate_coverage_sufficiency(body).model_dump(mode="json")


@app.post(
    "/api/v1/projects/{project_id}/dem/readiness-assessments",
    status_code=201,
)
def project_dem_readiness_assessment_save(
    project_id: str,
    body: DEMReadinessAssessmentInput,
) -> dict:
    """Evaluate readiness using verified persisted accuracy evidence and save the decision."""
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    manifest_dataset = store.get_dataset(body.product_manifest_dataset_id)
    if (
        manifest_dataset is None
        or manifest_dataset["project_id"] != project_id
        or manifest_dataset["data_role"] != "dem_tile_manifest"
        or manifest_dataset["format"] != "json"
    ):
        raise HTTPException(status_code=404, detail="DEM product manifest not found")
    manifest_path = store.get_dataset_content_path(manifest_dataset["id"])
    if manifest_path is None or not _dataset_content_matches(
        manifest_dataset, Path(manifest_path)
    ):
        raise HTTPException(
            status_code=409, detail="DEM product manifest failed integrity verification"
        )
    try:
        manifest = DEMTileManifest.model_validate(_read_json(Path(manifest_path)))
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="DEM product manifest is invalid") from exc
    if manifest.product_version_id != body.declared_use.product_version_id:
        raise HTTPException(
            status_code=409,
            detail="manifest product version does not match the declared use",
        )
    product_version = body.context.product_version
    if (
        product_version.availability.value != "available"
        or product_version.value != manifest.product_version_id
    ):
        raise HTTPException(
            status_code=409,
            detail="readiness context must identify the exact manifest product version",
        )

    review = body.independent_review
    accuracy_evidence = None
    accuracy_record = None
    if body.accuracy_assessment_id is not None:
        chain = store.verify_accuracy_assessment_chain(project_id)
        if not chain["valid"]:
            raise HTTPException(
                status_code=409, detail="project accuracy assessment chain is invalid"
            )
        accuracy_record = store.get_accuracy_assessment(body.accuracy_assessment_id)
        if accuracy_record is None or accuracy_record["project_id"] != project_id:
            raise HTTPException(status_code=404, detail="accuracy assessment not found")
        accuracy_report = accuracy_record["assessment"]
        accuracy_request = accuracy_record["request"]
        if accuracy_report.get("dem_tiles") is None or [
            item.get("sha256") for item in accuracy_report.get("dem_tiles", [])
        ] != list(manifest.tile_dataset_sha256s):
            raise HTTPException(
                status_code=409,
                detail="accuracy record tile checksums do not match the current manifest",
            )
        for tile_id, tile_sha256 in zip(
            manifest.tile_dataset_ids, manifest.tile_dataset_sha256s, strict=True
        ):
            tile = store.get_dataset(tile_id)
            tile_path = store.get_dataset_content_path(tile_id) if tile else None
            if (
                tile is None
                or tile["project_id"] != project_id
                or tile["data_role"] != "dem"
                or tile["sha256"] != tile_sha256
                or tile_path is None
                or not _dataset_content_matches(tile, Path(tile_path))
            ):
                raise HTTPException(
                    status_code=409,
                    detail="DEM tile content changed after the accuracy assessment",
                )
        reference_id = accuracy_report.get("reference_dataset_id")
        reference_dataset = store.get_dataset(reference_id) if reference_id else None
        reference_path = (
            store.get_dataset_content_path(reference_id) if reference_dataset else None
        )
        if (
            reference_dataset is None
            or reference_dataset["project_id"] != project_id
            or reference_dataset["data_role"] != "reference_elevation_observations"
            or reference_dataset["sha256"] != accuracy_report.get("reference_dataset_sha256")
            or reference_path is None
            or not _dataset_content_matches(
                reference_dataset, Path(reference_path)
            )
        ):
            raise HTTPException(
                status_code=409,
                detail="reference dataset content changed after the accuracy assessment",
            )
        aoi_id = accuracy_report.get("aoi_dataset_id")
        aoi_dataset = store.get_dataset(aoi_id) if aoi_id else None
        aoi_path = store.get_dataset_content_path(aoi_id) if aoi_dataset else None
        if (
            aoi_dataset is None
            or aoi_dataset["project_id"] != project_id
            or aoi_dataset["data_role"] != "aoi_boundary"
            or aoi_dataset["sha256"] != accuracy_report.get("aoi_dataset_file_sha256")
            or aoi_path is None
            or not _dataset_content_matches(aoi_dataset, Path(aoi_path))
        ):
            raise HTTPException(
                status_code=409,
                detail="AOI dataset content changed after the accuracy assessment",
            )
        uncertainty_sidecar_id = accuracy_report.get(
            "reference_uncertainty_sidecar_dataset_id"
        )
        if uncertainty_sidecar_id is not None:
            sidecar_dataset = store.get_dataset(uncertainty_sidecar_id)
            sidecar_path = store.get_dataset_content_path(uncertainty_sidecar_id)
            if (
                accuracy_request.get("reference_uncertainty_sidecar_dataset_id")
                != uncertainty_sidecar_id
                or sidecar_dataset is None
                or sidecar_dataset["project_id"] != project_id
                or sidecar_dataset["data_role"] != "reference_uncertainty_sidecar"
                or sidecar_dataset["format"] != "json"
                or sidecar_dataset["sha256"]
                != accuracy_report.get("reference_uncertainty_sidecar_dataset_sha256")
                or sidecar_dataset["sha256"]
                != accuracy_report.get("reference_uncertainty_sidecar_sha256")
                or sidecar_path is None
                or not _dataset_content_matches(
                    sidecar_dataset, Path(sidecar_path)
                )
            ):
                raise HTTPException(
                    status_code=409,
                    detail="reference uncertainty sidecar changed after accuracy assessment",
                )
        try:
            aoi_payload = _read_json(Path(aoi_path))
            canonical_manifest = json.dumps(
                manifest.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            canonical_aoi = json.dumps(
                aoi_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail="accuracy source JSON is invalid") from exc
        if (
            hashlib.sha256(canonical_manifest.encode("utf-8")).hexdigest()
            != accuracy_report.get("product_manifest_sha256")
            or hashlib.sha256(canonical_aoi.encode("utf-8")).hexdigest()
            != accuracy_report.get("aoi_dataset_sha256")
        ):
            raise HTTPException(
                status_code=409,
                detail="canonical manifest or AOI hash no longer matches accuracy evidence",
            )
        coverage = store.get_dataset_coverage_inspection(aoi_id)
        if (
            coverage is None
            or coverage.get("format") != "dem_tile_collection_coverage_inspection"
            or coverage.get("project_id") != project_id
            or coverage.get("product_dataset_ids") != list(manifest.tile_dataset_ids)
            or coverage.get("product_dataset_sha256s")
            != list(manifest.tile_dataset_sha256s)
            or coverage.get("aoi_dataset_id") != aoi_id
            or coverage.get("aoi_dataset_sha256") != aoi_dataset["sha256"]
            or coverage.get("aoi_crs")
            != accuracy_request.get("metadata", {}).get("aoi_crs")
            or coverage.get("coverage_footprint_reference")
            != accuracy_report.get("coverage_footprint_reference")
            or coverage.get("aoi_fully_within_raster_extent") is not True
            or coverage.get("all_aoi_pixel_centres_valid") is not True
        ):
            raise HTTPException(
                status_code=409,
                detail="coverage inspection no longer matches the accuracy evidence",
            )
        if (
            accuracy_report.get("product_manifest_dataset_id")
            != manifest_dataset["id"]
            or accuracy_report.get("product_manifest_dataset_sha256")
            != manifest_dataset["sha256"]
            or accuracy_report.get("product_version_id")
            != manifest.product_version_id
            or accuracy_report.get("declared_use")
            != body.declared_use.model_dump(mode="json")
        ):
            raise HTTPException(
                status_code=409,
                detail="accuracy assessment does not match this manifest and declared use",
            )
        try:
            persisted_review = IndependentReviewEvidence.model_validate(
                accuracy_report["independent_review"]
            )
        except (KeyError, ValidationError) as exc:
            raise HTTPException(
                status_code=409, detail="accuracy record has no valid review evidence"
            ) from exc
        if review is not None and review != persisted_review:
            raise HTTPException(
                status_code=409,
                detail="submitted independent review differs from the persisted accuracy review",
            )
        review = persisted_review
        try:
            assessed_at = datetime.fromisoformat(accuracy_record["created_at"])
            accuracy_evidence = AccuracyAssessmentEvidence(
                assessment_id=accuracy_record["id"],
                record_hash=accuracy_record["record_hash"],
                assessment_sha256=accuracy_record["assessment_sha256"],
                product_version_id=accuracy_report["product_version_id"],
                pilot_area_id=body.declared_use.pilot_area_id,
                task_profile_id=body.declared_use.task_profile_id,
                accuracy_disposition=accuracy_report["accuracy_disposition"],
                metrics_scope=accuracy_report["metrics_scope"],
                independence_status=accuracy_report["independence_status"],
                coverage_footprint_reference=accuracy_report[
                    "coverage_footprint_reference"
                ],
                evidence_reference=(
                    f"accuracy-assessment://{accuracy_record['id']}"
                    f"#{accuracy_record['record_hash']}"
                ),
                assessed_at=assessed_at,
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=409, detail="persisted accuracy evidence is malformed"
            ) from exc

    readiness_input = ReadinessInput(
        context=body.context,
        declared_use=body.declared_use,
        mandatory_failures=body.mandatory_failures,
        unresolved_items=body.unresolved_items,
        accepted_restrictions=body.accepted_restrictions,
        scope_exceptions=body.scope_exceptions,
        independent_review=review,
        accuracy_assessment=accuracy_evidence,
    )
    assessment = assess_readiness(readiness_input)
    report = assessment.model_dump(mode="json")
    report.update({
        "product_manifest_dataset_id": manifest_dataset["id"],
        "product_manifest_dataset_sha256": manifest_dataset["sha256"],
        "accuracy_assessment_id": (
            accuracy_record["id"] if accuracy_record is not None else None
        ),
        "accuracy_assessment_record_hash": (
            accuracy_record["record_hash"] if accuracy_record is not None else None
        ),
        "accuracy_assessment_payload_sha256": (
            accuracy_record["assessment_sha256"]
            if accuracy_record is not None
            else None
        ),
    })
    return store.save_readiness_assessment(
        project_id,
        body.model_dump(mode="json"),
        report,
        body.created_by,
    )


@app.get("/api/v1/projects/{project_id}/dem/readiness-assessments")
def project_dem_readiness_assessment_list(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return store.list_readiness_assessments(project_id, limit=limit, offset=offset)


@app.get("/api/v1/projects/{project_id}/dem/readiness-assessments/chain")
def project_dem_readiness_assessment_chain(project_id: str) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return store.verify_readiness_assessment_chain(project_id)


@app.get("/api/v1/projects/{project_id}/dem/readiness-assessments/{assessment_id}")
def project_dem_readiness_assessment_get(
    project_id: str,
    assessment_id: str,
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    record = store.get_readiness_assessment(assessment_id)
    if record is None or record["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="readiness assessment not found")
    return record


@app.post(
    "/api/v1/projects/{project_id}/dem/accuracy-assessments",
    status_code=201,
)
def project_dem_accuracy_assessment_save(
    project_id: str,
    body: DEMAccuracyAssessmentInput,
) -> dict:
    """Compute and persist DEM/reference residuals bound to a product manifest and review."""
    from geologia.formats import FormatDependencyError, FormatValidationError

    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    manifest_dataset = store.get_dataset(body.product_manifest_dataset_id)
    reference = store.get_dataset(body.reference_dataset_id)
    aoi = store.get_dataset(body.aoi_dataset_id)
    if (
        manifest_dataset is None
        or manifest_dataset["project_id"] != project_id
        or manifest_dataset["data_role"] != "dem_tile_manifest"
        or manifest_dataset["format"] != "json"
    ):
        raise HTTPException(status_code=404, detail="DEM product manifest not found")
    if (
        reference is None
        or reference["project_id"] != project_id
        or reference["data_role"] != "reference_elevation_observations"
        or reference["format"] != "csv"
    ):
        raise HTTPException(status_code=404, detail="reference observation dataset not found")
    if (
        aoi is None
        or aoi["project_id"] != project_id
        or aoi["data_role"] != "aoi_boundary"
        or aoi["format"] not in {"geojson", "json"}
    ):
        raise HTTPException(status_code=404, detail="AOI dataset not found")

    uncertainty_sidecar = None
    uncertainty_sidecar_path = None
    if body.reference_uncertainty_sidecar_dataset_id is not None:
        uncertainty_sidecar = store.get_dataset(
            body.reference_uncertainty_sidecar_dataset_id
        )
        if (
            uncertainty_sidecar is None
            or uncertainty_sidecar["project_id"] != project_id
            or uncertainty_sidecar["data_role"] != "reference_uncertainty_sidecar"
            or uncertainty_sidecar["format"] != "json"
        ):
            raise HTTPException(
                status_code=404,
                detail="typed reference uncertainty sidecar dataset not found",
            )
        uncertainty_sidecar_path = store.get_dataset_content_path(
            uncertainty_sidecar["id"]
        )
        if (
            uncertainty_sidecar_path is None
            or not _dataset_content_matches(
                uncertainty_sidecar, Path(uncertainty_sidecar_path)
            )
        ):
            raise HTTPException(
                status_code=409,
                detail="reference uncertainty sidecar failed integrity verification",
            )

    assessment_datasets = [manifest_dataset, reference, aoi]
    if uncertainty_sidecar is not None:
        assessment_datasets.append(uncertainty_sidecar)
    for item in assessment_datasets:
        content_path = store.get_dataset_content_path(item["id"])
        if content_path is None or not _dataset_content_matches(item, Path(content_path)):
            raise HTTPException(
                status_code=409,
                detail="accuracy input dataset failed integrity verification",
            )

    try:
        manifest = DEMTileManifest.model_validate(
            _read_json(Path(store.get_dataset_content_path(manifest_dataset["id"])))
        )
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="DEM tile manifest is invalid") from exc

    metadata = body.metadata
    declared_use = body.declared_use
    review = body.independent_review
    if (
        manifest.product_version_id != metadata.product_version_id
        or manifest.product_version_id != declared_use.product_version_id
        or metadata.product_version_id != review.product_version_id
        or declared_use.pilot_area_id != review.pilot_area_id
        or declared_use.task_profile_id != review.task_profile_id
        or review.reviewer != metadata.independence_reviewer
        or review.evidence_reference != metadata.independence_evidence_reference
        or review.reviewed_at != metadata.independence_reviewed_at
    ):
        raise HTTPException(
            status_code=409,
            detail="manifest, metadata, declared use and independent review must match exactly",
        )
    now = datetime.now(timezone.utc)
    if review.reviewed_at.astimezone(timezone.utc) > now:
        raise HTTPException(
            status_code=409, detail="independent review timestamp is in the future"
        )
    if body.requirement is not None:
        if body.requirement.frozen_at.astimezone(timezone.utc) > now:
            raise HTTPException(
                status_code=409,
                detail="accuracy requirement freeze timestamp is in the future",
            )

    dem_paths = []
    for tile_id, tile_sha256 in zip(
        manifest.tile_dataset_ids, manifest.tile_dataset_sha256s, strict=True
    ):
        tile = store.get_dataset(tile_id)
        if (
            tile is None
            or tile["project_id"] != project_id
            or tile["data_role"] != "dem"
            or tile["format"] not in {"tif", "tiff", "hgt"}
            or tile["sha256"] != tile_sha256
        ):
            raise HTTPException(
                status_code=409,
                detail="manifest tile membership or checksum does not match project datasets",
            )
        tile_path = store.get_dataset_content_path(tile_id)
        if tile_path is None or not _dataset_content_matches(tile, Path(tile_path)):
            raise HTTPException(
                status_code=409, detail="DEM tile failed integrity verification"
            )
        dem_paths.append(Path(tile_path))

    coverage = store.get_dataset_coverage_inspection(aoi["id"])
    if (
        coverage is None
        or coverage.get("format") != "dem_tile_collection_coverage_inspection"
        or coverage.get("inspection_status") != "measured"
        or coverage.get("project_id") != project_id
        or coverage.get("product_dataset_ids") != list(manifest.tile_dataset_ids)
        or coverage.get("product_dataset_sha256s") != list(manifest.tile_dataset_sha256s)
        or coverage.get("aoi_dataset_id") != aoi["id"]
        or coverage.get("aoi_dataset_sha256") != aoi["sha256"]
        or coverage.get("aoi_crs") != metadata.aoi_crs
        or coverage.get("coverage_footprint_reference")
        != body.coverage_footprint_reference
        or coverage.get("aoi_fully_within_raster_extent") is not True
        or coverage.get("all_aoi_pixel_centres_valid") is not True
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "accuracy assessment requires full persisted coverage for "
                "the exact manifest and AOI"
            ),
        )

    reference_path = store.get_dataset_content_path(reference["id"])
    aoi_path = store.get_dataset_content_path(aoi["id"])
    try:
        aoi_payload = _read_json(Path(aoi_path))
        canonical_manifest = json.dumps(
            manifest.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        canonical_aoi = json.dumps(
            aoi_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        canonical_manifest_sha256 = hashlib.sha256(
            canonical_manifest.encode("utf-8")
        ).hexdigest()
        canonical_aoi_sha256 = hashlib.sha256(
            canonical_aoi.encode("utf-8")
        ).hexdigest()
        report = compute_dem_reference_residuals(
            dem_paths,
            Path(reference_path),
            aoi_payload,
            metadata=metadata,
            product_manifest_sha256=canonical_manifest_sha256,
            reference_dataset_sha256=reference["sha256"],
            aoi_dataset_sha256=canonical_aoi_sha256,
            product_manifest=manifest,
            coverage_footprint_reference=body.coverage_footprint_reference,
            requirement=body.requirement,
            declared_use=declared_use,
            independent_review=review,
            reference_uncertainty_sidecar_path=(
                Path(uncertainty_sidecar_path)
                if uncertainty_sidecar_path is not None
                else None
            ),
            reference_uncertainty_sidecar_sha256=(
                uncertainty_sidecar["sha256"]
                if uncertainty_sidecar is not None
                else None
            ),
        )
    except FormatDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FormatValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="AOI or manifest JSON is invalid") from exc

    report.update({
        "project_id": project_id,
        "product_manifest_dataset_id": manifest_dataset["id"],
        "product_manifest_dataset_sha256": manifest_dataset["sha256"],
        "aoi_dataset_file_sha256": aoi["sha256"],
        "reference_dataset_id": reference["id"],
        "reference_uncertainty_sidecar_dataset_id": (
            uncertainty_sidecar["id"] if uncertainty_sidecar is not None else None
        ),
        "reference_uncertainty_sidecar_dataset_sha256": (
            uncertainty_sidecar["sha256"]
            if uncertainty_sidecar is not None
            else None
        ),
        "aoi_dataset_id": aoi["id"],
        "declared_use": declared_use.model_dump(mode="json"),
        "independent_review": review.model_dump(mode="json"),
        "created_by": body.created_by.strip(),
    })
    record = store.save_accuracy_assessment(
        project_id,
        body.model_dump(mode="json"),
        report,
        body.created_by,
    )
    return record


@app.get("/api/v1/projects/{project_id}/dem/accuracy-assessments")
def project_dem_accuracy_assessment_list(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return store.list_accuracy_assessments(project_id, limit=limit, offset=offset)


@app.get("/api/v1/projects/{project_id}/dem/accuracy-assessments/chain")
def project_dem_accuracy_assessment_chain(project_id: str) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    result = store.verify_accuracy_assessment_chain(project_id)
    record_chain_valid = result["valid"]
    dependency_errors: list[dict[str, str]] = []
    offset = 0
    page_size = 200
    while True:
        page = store.list_accuracy_assessments(
            project_id, limit=page_size, offset=offset
        )
        records = page["assessments"]
        for record in records:
            request = record["request"]
            assessment = record["assessment"]
            dependencies = (
                (
                    "product_manifest_dataset",
                    "product_manifest_dataset_id",
                    "product_manifest_dataset_id",
                    "product_manifest_dataset_sha256",
                    ("dem_tile_manifest",),
                    ("json",),
                ),
                (
                    "reference_dataset",
                    "reference_dataset_id",
                    "reference_dataset_id",
                    "reference_dataset_sha256",
                    (
                        "ground_control_points",
                        "reference_elevation_observations",
                    ),
                    ("csv",),
                ),
                (
                    "aoi_dataset",
                    "aoi_dataset_id",
                    "aoi_dataset_id",
                    "aoi_dataset_file_sha256",
                    ("aoi_boundary",),
                    ("geojson", "json"),
                ),
            )
            for (
                label,
                request_id_key,
                assessment_id_key,
                expected_sha_key,
                roles,
                formats,
            ) in dependencies:
                dataset_id = assessment.get(assessment_id_key)
                expected_sha = assessment.get(expected_sha_key)
                if (
                    request.get(request_id_key) != dataset_id
                    or not _dataset_dependency_matches(
                        project_id,
                        dataset_id,
                        expected_sha,
                        roles=roles,
                        formats=formats,
                    )
                ):
                    dependency_errors.append(
                        {
                            "record_id": record["id"],
                            "code": f"{label}_integrity_mismatch",
                        }
                    )

            manifest_id = assessment.get("product_manifest_dataset_id")
            manifest_path = (
                store.get_dataset_content_path(manifest_id)
                if manifest_id is not None
                else None
            )
            if manifest_path is not None and _dataset_dependency_matches(
                project_id,
                manifest_id,
                assessment.get("product_manifest_dataset_sha256"),
                roles=("dem_tile_manifest",),
                formats=("json",),
            ):
                try:
                    manifest = DEMTileManifest.model_validate(
                        _read_json(Path(manifest_path))
                    )
                except (UnicodeDecodeError, ValueError, ValidationError):
                    dependency_errors.append(
                        {
                            "record_id": record["id"],
                            "code": "dem_tile_manifest_invalid",
                        }
                    )
                else:
                    for tile_id, tile_sha256 in zip(
                        manifest.tile_dataset_ids,
                        manifest.tile_dataset_sha256s,
                        strict=True,
                    ):
                        if not _dataset_dependency_matches(
                            project_id,
                            tile_id,
                            tile_sha256,
                            roles=("dem",),
                            formats=("tif", "tiff", "hgt"),
                        ):
                            dependency_errors.append(
                                {
                                    "record_id": record["id"],
                                    "code": "dem_tile_dataset_integrity_mismatch",
                                }
                            )
            else:
                dependency_errors.append(
                    {
                        "record_id": record["id"],
                        "code": "dem_tile_manifest_dependency_unavailable",
                    }
                )

            sidecar_id = assessment.get(
                "reference_uncertainty_sidecar_dataset_id"
            )
            if sidecar_id is not None and (
                request.get("reference_uncertainty_sidecar_dataset_id")
                != sidecar_id
                or not _dataset_dependency_matches(
                    project_id,
                    sidecar_id,
                    assessment.get(
                        "reference_uncertainty_sidecar_dataset_sha256"
                    ),
                    roles=("reference_uncertainty_sidecar",),
                    formats=("json",),
                )
                or assessment.get("reference_uncertainty_sidecar_sha256")
                != assessment.get(
                    "reference_uncertainty_sidecar_dataset_sha256"
                )
            ):
                dependency_errors.append(
                    {
                        "record_id": record["id"],
                        "code": "reference_uncertainty_sidecar_integrity_mismatch",
                    }
                )
        offset += len(records)
        if not records or offset >= page["count"]:
            break
    result["record_chain_valid"] = record_chain_valid
    result["dependency_integrity_valid"] = not dependency_errors
    result["dependency_errors"] = dependency_errors
    result["valid"] = record_chain_valid and not dependency_errors
    return result


@app.get("/api/v1/projects/{project_id}/dem/accuracy-assessments/{assessment_id}")
def project_dem_accuracy_assessment_get(
    project_id: str,
    assessment_id: str,
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    record = store.get_accuracy_assessment(assessment_id)
    if record is None or record["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="accuracy assessment not found")
    return record


@app.post("/api/v1/projects/{project_id}/dem/coverage-assessments", status_code=201)
def dem_coverage_assessment_save(
    project_id: str,
    body: CoverageAssessmentSubmission,
) -> dict:
    """Persist a caller-attributed coverage assessment in the project's hash chain."""
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")

    context = body.request.context
    product = store.get_dataset(context.product_dataset_id)
    reference = store.get_dataset(context.reference_dataset_id)
    aoi = store.get_dataset(context.aoi_dataset_id)
    if product is None or reference is None or aoi is None:
        raise HTTPException(status_code=404, detail="product, reference or AOI dataset not found")
    if (
        product["project_id"] != project_id
        or reference["project_id"] != project_id
        or aoi["project_id"] != project_id
    ):
        raise HTTPException(status_code=404, detail="product, reference or AOI dataset not found")
    if (
        product["sha256"] != context.product_dataset_sha256
        or reference["sha256"] != context.reference_dataset_sha256
    ):
        raise HTTPException(
            status_code=409,
            detail="request dataset checksums do not match the stored upload records",
        )
    if aoi["data_role"] != "aoi_boundary":
        raise HTTPException(status_code=422, detail="AOI dataset must have data_role=aoi_boundary")
    if aoi["sha256"] != context.aoi_dataset_sha256:
        raise HTTPException(status_code=409, detail="AOI dataset checksum does not match request")
    if product["data_role"] not in {"dem", "dem_tile_manifest"}:
        raise HTTPException(
            status_code=422,
            detail="product dataset must be a DEM tile or dem_tile_manifest",
        )
    if product["data_role"] == "dem_tile_manifest" and product["format"] != "json":
        raise HTTPException(status_code=422, detail="DEM tile manifest must be a JSON dataset")
    if reference["data_role"] not in {
        "ground_control_points",
        "reference_elevation_observations",
    }:
        raise HTTPException(
            status_code=422,
            detail=(
                "reference dataset must be ground_control_points or "
                "reference_elevation_observations"
            ),
        )

    for item in (product, reference, aoi):
        stored_path = store.get_dataset_content_path(item["id"])
        if stored_path is None or not _dataset_content_matches(item, Path(stored_path)):
            raise HTTPException(
                status_code=409,
                detail="DEM, reference or AOI dataset failed upload-time integrity verification",
            )

    evidence = body.request.evidence
    if evidence is None:
        raise HTTPException(
            status_code=409,
            detail="coverage assessment requires attributable evidence",
        )

    if product["data_role"] == "dem":
        inspection = store.get_dataset_coverage_inspection(product["id"])
        inspection_matches = (
            inspection is not None
            and inspection.get("inspection_status") == "measured"
            and inspection.get("product_dataset_sha256") == product["sha256"]
            and inspection.get("aoi_dataset_id") == aoi["id"]
            and inspection.get("aoi_dataset_sha256") == aoi["sha256"]
            and inspection.get("coverage_footprint_reference")
            == evidence.coverage_footprint_reference
        )
    else:
        manifest_path = store.get_dataset_content_path(product["id"])
        try:
            manifest_payload = _read_json(Path(manifest_path))
            manifest = DEMTileManifest.model_validate(manifest_payload)
        except (UnicodeDecodeError, ValueError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail="DEM tile manifest is invalid") from exc
        if manifest.product_version_id != context.product_version_id:
            raise HTTPException(
                status_code=409,
                detail="manifest product version does not match the declared product version",
            )
        tile_items = []
        for tile_id, tile_sha256 in zip(
            manifest.tile_dataset_ids, manifest.tile_dataset_sha256s, strict=True
        ):
            tile = store.get_dataset(tile_id)
            if (
                tile is None
                or tile["project_id"] != project_id
                or tile["data_role"] != "dem"
                or tile["format"] not in {"tif", "tiff", "hgt"}
                or tile["sha256"] != tile_sha256
            ):
                raise HTTPException(
                    status_code=409,
                    detail="manifest tile membership or checksum does not match project datasets",
                )
            tile_path = store.get_dataset_content_path(tile_id)
            if tile_path is None or not _dataset_content_matches(tile, Path(tile_path)):
                raise HTTPException(
                    status_code=409, detail="manifest DEM tile failed integrity verification"
                )
            tile_items.append(tile)

        inspection = store.get_dataset_coverage_inspection(aoi["id"])
        inspection_matches = (
            inspection is not None
            and inspection.get("format") == "dem_tile_collection_coverage_inspection"
            and inspection.get("inspection_status") == "measured"
            and inspection.get("project_id") == project_id
            and inspection.get("product_dataset_ids")
            == list(manifest.tile_dataset_ids)
            and inspection.get("product_dataset_sha256s")
            == list(manifest.tile_dataset_sha256s)
            and inspection.get("aoi_dataset_id") == aoi["id"]
            and inspection.get("aoi_dataset_sha256") == aoi["sha256"]
            and inspection.get("coverage_footprint_reference")
            == evidence.coverage_footprint_reference
        )

    if (
        not inspection_matches
        or (
            body.request.coverage_status.value == "verified"
            and not (
                inspection.get("aoi_fully_within_raster_extent") is True
                and inspection.get("all_aoi_pixel_centres_valid") is True
            )
        )
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "coverage assessment must cite a persisted inspection matching "
                "the exact product manifest, tile checksums and AOI"
            ),
        )

    assessment = evaluate_coverage_sufficiency(body.request)
    try:
        return store.save_coverage_assessment(
            project_id,
            body.request.model_dump(mode="json"),
            assessment.model_dump(mode="json"),
            body.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/projects/{project_id}/dem/coverage-assessments")
def dem_coverage_assessments_list(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return store.list_coverage_assessments(project_id, limit=limit, offset=offset)


@app.get("/api/v1/projects/{project_id}/dem/coverage-assessments/integrity")
def dem_coverage_assessments_integrity(project_id: str) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return store.verify_coverage_assessment_chain(project_id)


@app.get("/api/v1/projects/{project_id}/dem/coverage-assessments/{assessment_id}")
def dem_coverage_assessment_get(project_id: str, assessment_id: str) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    item = store.get_coverage_assessment(assessment_id)
    if item is None or item["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="coverage assessment not found")
    return item


@app.get("/api/v1/agent/status")
def agent_status_endpoint() -> dict:
    """Expose the model-independent local agent's declared capabilities."""
    return agent_status()


@app.get("/api/v1/knowledge/status")
def knowledge_status_endpoint() -> dict:
    """Return local knowledge index counts and active search backend."""
    return knowledge.status()


@app.get("/api/v1/knowledge/search")
def knowledge_search_endpoint(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    """Search only locally ingested, license-reviewed source text."""
    try:
        return knowledge.search(q, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



@app.post("/api/v1/knowledge/claims", status_code=201)
def knowledge_claim_create(body: ClaimInput) -> dict:
    """Record a claim to organize evidence; this does not validate the claim."""
    try:
        return knowledge.create_claim(body.statement, body.created_by)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/knowledge/claims")
def knowledge_claims_list(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """List recorded claims and evidence counts, not scientific conclusions."""
    try:
        return knowledge.list_claims(limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/knowledge/claims/{claim_id}")
def knowledge_claim_get(claim_id: str) -> dict:
    item = knowledge.get_claim(claim_id)
    if item is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return item


@app.post("/api/v1/knowledge/claims/{claim_id}/evidence", status_code=201)
def knowledge_claim_evidence_add(
    claim_id: str, body: ClaimEvidenceInput
) -> dict:
    """Record a human-labelled relation to an exact indexed evidence chunk."""
    try:
        return knowledge.annotate_claim_evidence(
            claim_id,
            body.chunk_id,
            body.relation,
            body.rationale,
            body.recorded_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/engines")
def engines(domain: str | None = None) -> dict:
    items = list_engines(domain)
    return {"count": len(items), "engines": items}


@app.get("/api/v1/engines/{engine_id}")
def engine_detail(engine_id: str) -> dict:
    card = get_engine(engine_id)
    if card is None:
        raise HTTPException(status_code=404, detail="engine not found")
    return card


@app.get("/api/v1/projects")
def projects_list() -> dict:
    items = store.list_projects()
    return {"count": len(items), "projects": items}


@app.post("/api/v1/projects", status_code=201)
def projects_create(body: ProjectInput) -> dict:
    return store.create_project(body.name.strip(), body.description.strip(), body.language)


@app.get("/api/v1/projects/{project_id}")
def projects_get(project_id: str) -> dict:
    item = store.get_project(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="project not found")
    return item


@app.post("/api/v1/projects/{project_id}/datasets", status_code=201)
async def dataset_upload(
    project_id: str,
    request: Request,
    dataset_name: str = Header(..., alias="X-Dataset-Name", min_length=2, max_length=120),
    filename: str = Header(..., alias="X-Filename", min_length=1, max_length=255),
    crs: str | None = Header(None, alias="X-CRS", max_length=100),
    data_role: str | None = Header(None, alias="X-Data-Role", max_length=80),
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    dataset_name = dataset_name.strip()
    if len(dataset_name) < 2:
        raise HTTPException(
            status_code=422,
            detail="dataset name must contain at least two non-space characters",
        )
    if data_role and data_role not in ALLOWED_DATA_ROLES:
        raise HTTPException(status_code=422, detail="unknown dataset data role")
    safe_name = Path(filename.replace("\\", "/")).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_FORMATS:
        raise HTTPException(status_code=415, detail="unsupported dataset format")
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="dataset exceeds upload limit")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid Content-Length") from exc

    storage = store.storage_path()
    temporary_path = None
    final_path = storage / f"{uuid4().hex}.blob"
    digest = hashlib.sha256()
    size = 0
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=storage, prefix=".upload-", delete=False
        ) as tmp:
            temporary_path = Path(tmp.name)
            async for chunk in request.stream():
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="dataset exceeds upload limit")
                digest.update(chunk)
                tmp.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="empty dataset")
        summary = {"validation": "stored_only"}
        effective_crs = crs.strip() if crs and crs.strip() else None
        if suffix in {".geojson", ".json"}:
            if data_role == "reference_uncertainty_sidecar":
                if suffix != ".json":
                    raise HTTPException(status_code=415, detail="uncertainty sidecar must be .json")
                try:
                    payload = _read_json(temporary_path)
                except (UnicodeDecodeError, ValueError) as exc:
                    raise HTTPException(
                        status_code=422,
                        detail="uncertainty sidecar JSON is invalid",
                    ) from exc
                if (
                    not isinstance(payload, dict)
                    or payload.get("schema") != "geologia.reference-uncertainty.v1"
                ):
                    raise HTTPException(
                        status_code=422,
                        detail="uncertainty sidecar schema is unsupported",
                    )
                reference_sha = payload.get("reference_dataset_sha256")
                records = payload.get("records")
                if (
                    not isinstance(reference_sha, str)
                    or len(reference_sha) != 64
                    or any(char not in "0123456789abcdefABCDEF" for char in reference_sha)
                    or not isinstance(records, dict)
                    or not records
                ):
                    raise HTTPException(
                        status_code=422,
                        detail="uncertainty sidecar header or records are invalid",
                    )
                try:
                    for point_id, record in records.items():
                        if not isinstance(point_id, str) or not point_id.strip():
                            raise ValueError("point_id must be a non-empty string")
                        ElevationUncertainty.model_validate(record)
                except (TypeError, ValueError, ValidationError) as exc:
                    raise HTTPException(
                        status_code=422,
                        detail="uncertainty sidecar contains an invalid typed record",
                    ) from exc
                summary = {
                    "validation": "typed_uncertainty_records_validated",
                    "schema": payload["schema"],
                    "reference_dataset_sha256": reference_sha.lower(),
                    "record_count": len(records),
                    "scientific_interpretation": False,
                }
            elif data_role == "dem_tile_manifest":
                try:
                    manifest = DEMTileManifest.model_validate(
                        _read_json(temporary_path)
                    )
                except (UnicodeDecodeError, ValueError, ValidationError) as exc:
                    raise HTTPException(
                        status_code=422, detail="DEM tile manifest JSON is invalid"
                    ) from exc
                summary = {
                    "validation": "manifest_structure_validated",
                    "schema": manifest.schema,
                    "product_version_id": manifest.product_version_id,
                    "tile_count": len(manifest.tile_dataset_ids),
                }
            else:
                summary = _geojson_summary(temporary_path)
                effective_crs = effective_crs or "EPSG:4326"
        os.replace(temporary_path, final_path)
        clean_filename = safe_name.replace("\\", "/").split("/")[-1]
        try:
            item = store.create_dataset(
                project_id, name=dataset_name, file_format=suffix.lstrip("."),
                original_filename=clean_filename, content_path=str(final_path),
                sha256=digest.hexdigest(), size_bytes=size, crs=effective_crs,
                data_role=data_role, summary=summary,
            )
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
        return item
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@app.get("/api/v1/projects/{project_id}/datasets")
def datasets_list(project_id: str) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    items = store.list_datasets(project_id)
    return {"count": len(items), "datasets": items}


@app.get("/api/v1/datasets/{dataset_id}")
def datasets_get(dataset_id: str) -> dict:
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return item


@app.get("/api/v1/crs/inspect")
def crs_inspection(crs: str) -> dict:
    """Validate and normalize a user-provided CRS definition."""
    from geologia.geospatial import inspect_crs

    try:
        return inspect_crs(crs)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/datasets/{dataset_id}/reproject", status_code=201)
def dataset_reproject(dataset_id: str, body: ReprojectInput) -> dict:
    """Create a new reprojected GeoJSON dataset; never overwrite the source."""
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if item["format"] not in {"geojson", "json"}:
        raise HTTPException(status_code=415, detail="reprojection supports GeoJSON only")
    content_path = store.get_dataset_content_path(dataset_id)
    if content_path is None or not Path(content_path).is_file():
        raise HTTPException(status_code=410, detail="dataset file is missing")
    if not _dataset_content_matches(item, Path(content_path)):
        raise HTTPException(
            status_code=409,
            detail="dataset integrity mismatch; stored bytes differ from the upload-time record",
        )
    try:
        payload = _read_json(Path(content_path))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
        ) from exc
    try:
        metrics = inspect_geojson(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid GeoJSON: {exc}") from exc
    source_crs = item["crs"] or "EPSG:4326"
    from geologia.geospatial import reproject_geojson

    try:
        transformed, info = reproject_geojson(payload, source_crs, body.target_crs)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    transformed_metrics = inspect_geojson(transformed)
    output_bytes = json.dumps(
        transformed, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if len(output_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="reprojected dataset exceeds storage limit")
    storage = store.storage_path()
    temporary_path = None
    final_path = storage / f"{uuid4().hex}.blob"
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=storage, prefix=".reproject-", delete=False
        ) as tmp:
            temporary_path = Path(tmp.name)
            tmp.write(output_bytes)
        os.replace(temporary_path, final_path)
        derived_name = f"{item['name']} [{info['target_crs']}]"
        derived_name = derived_name[:120]
        original_filename = Path(item["original_filename"]).stem[:180]
        original_filename += ".reprojected.geojson"
        summary = {
            "validation": "structural_only",
            "feature_count": metrics["feature_count"],
            "derived_from_dataset_id": dataset_id,
            "operation": "geojson_reprojection",
            "coordinate_count": metrics["coordinate_count"],
            "bbox_xy": transformed_metrics["bbox_xy"],
            "source_crs": info["source_crs"],
            "target_crs": info["target_crs"],
            "scientific_interpretation": False,
        }
        try:
            dataset = store.create_dataset(
                item["project_id"], name=derived_name, file_format="geojson",
                original_filename=original_filename, content_path=str(final_path),
                sha256=hashlib.sha256(output_bytes).hexdigest(),
                size_bytes=len(output_bytes), crs=info["target_crs"],
                data_role=item["data_role"], summary=summary,
            )
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
        return {
            "dataset": dataset,
            "operation": "geojson_reprojection",
            **info,
            "coordinate_count": metrics["coordinate_count"],
            "source_dataset_id": dataset_id,
            "source_dataset_modified": False,
        }
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@app.get("/api/v1/datasets/{dataset_id}/geojson")
def dataset_geojson(dataset_id: str) -> JSONResponse:
    """Return validated GeoJSON only; never expose the private storage path."""
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if item["format"] not in {"geojson", "json"}:
        raise HTTPException(status_code=415, detail="map view supports GeoJSON only")
    content_path = store.get_dataset_content_path(dataset_id)
    if content_path is None or not Path(content_path).is_file():
        raise HTTPException(status_code=410, detail="dataset file is missing")
    if not _dataset_content_matches(item, Path(content_path)):
        raise HTTPException(
            status_code=409,
            detail="dataset integrity mismatch; stored bytes differ from the upload-time record",
        )
    try:
        payload = _read_json(Path(content_path))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
        ) from exc
    try:
        inspect_geojson(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    declared_crs = item["crs"] or "EPSG:4326"
    if declared_crs.upper() not in {"EPSG:4326", "OGC:CRS84"}:
        from geologia.geospatial import reproject_geojson

        try:
            payload, _ = reproject_geojson(payload, declared_crs, "EPSG:4326")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JSONResponse(content=payload)


@app.post("/api/v1/datasets/{dataset_id}/inspect", status_code=200)
def dataset_inspect(dataset_id: str) -> dict:
    """Run bounded format-specific inspection; never claim scientific interpretation."""
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    content_path = store.get_dataset_content_path(dataset_id)
    if content_path is None or not Path(content_path).is_file():
        raise HTTPException(status_code=410, detail="dataset file is missing")
    if not _dataset_content_matches(item, Path(content_path)):
        raise HTTPException(
            status_code=409,
            detail="dataset integrity mismatch; stored bytes differ from the upload-time record",
        )

    file_format = item["format"]
    if file_format == "csv":
        try:
            report = inspect_csv(Path(content_path))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        operation = "csv_inspection"
    elif file_format in {"geojson", "json"}:
        try:
            payload = _read_json(Path(content_path))
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
            ) from exc
        try:
            report = inspect_geojson(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        operation = "geojson_inspection"
    elif file_format in {"gpkg", "tif", "tiff", "las"}:
        from geologia.formats import (
            FormatDependencyError,
            FormatValidationError,
            inspect_geopackage,
            inspect_geotiff,
            inspect_las,
        )

        inspectors = {
            "gpkg": inspect_geopackage,
            "tif": inspect_geotiff,
            "tiff": inspect_geotiff,
            "las": inspect_las,
        }
        try:
            report = inspectors[file_format](Path(content_path))
        except FormatDependencyError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except FormatValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        operation = f"{report['format']}_inspection"
    else:
        raise HTTPException(status_code=415, detail="inspection is not supported for this format")

    import importlib.metadata
    import sys

    parser_packages = {
        "gpkg": "pyogrio", "tif": "rasterio", "tiff": "rasterio",
        "las": "laspy", "geojson": "json", "json": "json", "csv": "csv",
    }
    package = parser_packages[file_format]
    try:
        parser_version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        parser_version = "stdlib"
    report["provenance"] = {
        "dataset_id": dataset_id,
        "source_sha256": item["sha256"],
        "original_filename": item["original_filename"],
        "format": file_format,
        "declared_crs": item["crs"],
        "inspected_at_utc": store.utc_now(),
        "geologia_version": __version__,
        "python_version": sys.version.split()[0],
        "parser": package,
        "parser_version": parser_version,
        "scientific_validation": False,
    }

    report.update({
        "dataset_id": dataset_id,
        "operation": operation,
        "scientific_interpretation": False,
    })
    store.save_dataset_inspection(dataset_id, report)
    return report



@app.post("/api/v1/datasets/{dataset_id}/coverage-inspection", status_code=200)
def dataset_coverage_inspect(
    dataset_id: str,
    body: CoverageInspectionInput,
) -> dict:
    """Measure raster extent and valid-data mask against a declared AOI polygon."""
    from geologia.formats import (
        FormatDependencyError,
        FormatValidationError,
        inspect_dem_aoi_coverage,
    )

    product = store.get_dataset(dataset_id)
    aoi = store.get_dataset(body.aoi_dataset_id)
    if product is None or aoi is None:
        raise HTTPException(status_code=404, detail="DEM or AOI dataset not found")
    if product["project_id"] != aoi["project_id"]:
        raise HTTPException(status_code=404, detail="DEM or AOI dataset not found")
    if product["data_role"] != "dem":
        raise HTTPException(status_code=422, detail="dataset must have data_role=dem")
    if aoi["data_role"] != "aoi_boundary":
        raise HTTPException(status_code=422, detail="AOI dataset must have data_role=aoi_boundary")
    if product["format"] not in {"tif", "tiff"}:
        raise HTTPException(status_code=415, detail="coverage inspection requires a GeoTIFF DEM")
    if aoi["format"] not in {"geojson", "json"}:
        raise HTTPException(status_code=415, detail="AOI must be a GeoJSON dataset")

    dem_path = store.get_dataset_content_path(product["id"])
    aoi_path = store.get_dataset_content_path(aoi["id"])
    for item, path in ((product, dem_path), (aoi, aoi_path)):
        if path is None or not _dataset_content_matches(item, Path(path)):
            raise HTTPException(
                status_code=409,
                detail="DEM or AOI dataset failed upload-time integrity verification",
            )

    try:
        payload = _read_json(Path(aoi_path))
        inspect_geojson(payload)
        report = inspect_dem_aoi_coverage(Path(dem_path), payload, body.aoi_crs)
    except FormatDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FormatValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid AOI GeoJSON: {exc}") from exc

    report.update({
        "product_dataset_id": product["id"],
        "product_dataset_sha256": product["sha256"],
        "aoi_dataset_id": aoi["id"],
        "aoi_dataset_sha256": aoi["sha256"],
        "aoi_crs": body.aoi_crs,
        "inspected_at_utc": store.utc_now(),
    })
    canonical = json.dumps(
        report,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    report_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    report["inspection_sha256"] = report_sha256
    report["coverage_footprint_reference"] = (
        f"coverage-inspection:{product['id']}:{report_sha256}"
    )
    store.save_dataset_coverage_inspection(product["id"], report)
    return report


@app.post(
    "/api/v1/projects/{project_id}/dem/tile-collection-coverage-inspection",
    status_code=200,
)
def project_dem_tile_collection_coverage_inspect(
    project_id: str,
    body: DEMTileCollectionCoverageInput,
) -> dict:
    """Measure a bounded aligned DEM tile collection against one AOI and persist its report."""
    from geologia.formats import (
        FormatDependencyError,
        FormatValidationError,
        inspect_dem_tile_collection_coverage,
    )

    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    aoi = store.get_dataset(body.aoi_dataset_id)
    if (
        aoi is None
        or aoi["project_id"] != project_id
        or aoi["data_role"] != "aoi_boundary"
        or aoi["format"] not in {"geojson", "json"}
    ):
        raise HTTPException(status_code=404, detail="AOI dataset not found")
    aoi_path = store.get_dataset_content_path(aoi["id"])
    if aoi_path is None or not _dataset_content_matches(aoi, Path(aoi_path)):
        raise HTTPException(status_code=409, detail="AOI dataset failed integrity verification")

    products = []
    paths = []
    for dataset_id in body.dem_dataset_ids:
        item = store.get_dataset(dataset_id)
        if (
            item is None
            or item["project_id"] != project_id
            or item["data_role"] != "dem"
            or item["format"] not in {"tif", "tiff", "hgt"}
        ):
            raise HTTPException(status_code=404, detail="DEM tile dataset not found")
        content_path = store.get_dataset_content_path(item["id"])
        if content_path is None or not _dataset_content_matches(item, Path(content_path)):
            raise HTTPException(
                status_code=409, detail="DEM tile dataset failed integrity verification"
            )
        products.append(item)
        paths.append(Path(content_path))

    try:
        aoi_payload = _read_json(Path(aoi_path))
        inspect_geojson(aoi_payload)
        report = inspect_dem_tile_collection_coverage(
            paths, aoi_payload, body.aoi_crs
        )
    except FormatDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FormatValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid AOI GeoJSON: {exc}") from exc

    report.update({
        "project_id": project_id,
        "product_dataset_ids": [item["id"] for item in products],
        "product_dataset_sha256s": [item["sha256"] for item in products],
        "aoi_dataset_id": aoi["id"],
        "aoi_dataset_sha256": aoi["sha256"],
        "aoi_crs": body.aoi_crs,
        "inspected_at_utc": store.utc_now(),
        "geologia_version": __version__,
    })
    canonical = json.dumps(
        report,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    report_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    report["inspection_sha256"] = report_sha256
    report["coverage_footprint_reference"] = (
        f"coverage-inspection-mosaic:{project_id}:{report_sha256}"
    )
    # Attach the collection report to its AOI dataset; the report itself names every DEM tile.
    store.save_dataset_coverage_inspection(aoi["id"], report)
    return report


@app.get(
    "/api/v1/projects/{project_id}/dem/tile-collection-coverage-inspection/{aoi_dataset_id}"
)
def project_dem_tile_collection_coverage_inspection_get(
    project_id: str,
    aoi_dataset_id: str,
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    aoi = store.get_dataset(aoi_dataset_id)
    if aoi is None or aoi["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="AOI dataset not found")
    report = store.get_dataset_coverage_inspection(aoi_dataset_id)
    if report is None or report.get("format") != "dem_tile_collection_coverage_inspection":
        raise HTTPException(status_code=404, detail="tile collection coverage report not found")
    return report


@app.get("/api/v1/datasets/{dataset_id}/coverage-inspection")
def dataset_coverage_inspection_get(dataset_id: str) -> dict:
    if store.get_dataset(dataset_id) is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    report = store.get_dataset_coverage_inspection(dataset_id)
    if report is None:
        raise HTTPException(status_code=404, detail="coverage inspection not found")
    return report


@app.post("/api/v1/datasets/{dataset_id}/validate", status_code=200)
def dataset_validate(dataset_id: str) -> dict:
    """Run deterministic structural checks and supported versioned schema profiles."""
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    content_path = store.get_dataset_content_path(dataset_id)
    if content_path is None or not Path(content_path).is_file():
        raise HTTPException(status_code=410, detail="dataset file is missing")
    path = Path(content_path)
    digest = hashlib.sha256()
    actual_size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            actual_size += len(chunk)
            digest.update(chunk)
    if actual_size != item["size_bytes"] or digest.hexdigest() != item["sha256"]:
        report = {
            "validation_level": "integrity",
            "validation_status": "failed",
            "profile": None,
            "checks": [{"code": "dataset.integrity.sha256", "status": "failed"}],
            "errors": [{
                "code": "dataset.integrity.sha256_mismatch",
                "message": "Stored dataset bytes no longer match the recorded size and SHA-256.",
            }],
            "error_count": 1,
            "warnings": [],
            "warning_count": 0,
            "scientific_interpretation": False,
        }
        report["dataset_id"] = dataset_id
        report["source_sha256"] = item["sha256"]
        report["source_size_bytes"] = item["size_bytes"]
        report["validated_at"] = store.utc_now()
        store.save_dataset_validation(dataset_id, report)
        return report
    if item["format"] == "csv":
        report = validate_csv_file(path, item["data_role"])
    elif item["format"] in {"geojson", "json"}:
        try:
            payload = _read_json(path)
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
            ) from exc
        report = validate_geojson_payload(payload, item["data_role"])
    else:
        raise HTTPException(
            status_code=415,
            detail="validation profiles currently support CSV and GeoJSON only",
        )
    report["dataset_id"] = dataset_id
    report["source_sha256"] = item["sha256"]
    report["source_size_bytes"] = item["size_bytes"]
    report["validated_at"] = store.utc_now()
    store.save_dataset_validation(dataset_id, report)
    return report


@app.get("/api/v1/datasets/{dataset_id}/validation", status_code=200)
def dataset_validation_get(dataset_id: str) -> dict:
    """Read the latest persisted validation report without re-running checks."""
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    report = store.get_dataset_validation(dataset_id)
    if report is None:
        raise HTTPException(status_code=404, detail="dataset has not been validated")
    return report



@app.post("/api/v1/projects/{project_id}/jobs", status_code=201)
def jobs_create(project_id: str, body: JobInput) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    plan = build_plan(body.request, body.language)
    available = store.list_dataset_roles(project_id)
    if plan["needs_clarification"]:
        plan["data_readiness"] = {
            "available_inputs": available,
            "missing_inputs": [],
            "required_roles_present": None,
            "readiness_status": "not_assessed",
            "content_validation": "not_performed",
            "execution_allowed": False,
            "execution_blocked_reason": "Clarify the request before assessing required inputs.",
        }
    else:
        required = plan["required_inputs"]
        missing = sorted(set(required) - set(available))
        plan["data_readiness"] = {
            "available_inputs": available,
            "missing_inputs": missing,
            "required_roles_present": not missing,
            "readiness_status": "assessed",
            "content_validation": "not_performed",
            "execution_allowed": False,
            "execution_blocked_reason": "No scientific engine is integrated or certified.",
        }
    if plan["needs_clarification"]:
        plan["knowledge_retrieval"] = {
            "status": "deferred_until_clarification",
            "retrieval_method": "local_only",
            "model_used": False,
            "scientific_conclusion": False,
            "results": [],
        }
    else:
        retrieval = knowledge.search(body.request, limit=3)
        plan["knowledge_retrieval"] = {
            "status": (
                "local_references_found"
                if retrieval["count"]
                else "no_approved_local_sources"
            ),
            "retrieval_method": retrieval["retrieval_method"],
            "model_used": False,
            "scientific_conclusion": False,
            "evidence_summary": retrieval["evidence_summary"],
            "evidence_interpretation": (
                "local lexical retrieval only; not scientific confidence "
                "or a validated scientific conclusion"
            ),
            "results": retrieval["results"],
        }
    return store.create_job(project_id, body.request, body.language, plan)


@app.get("/api/v1/projects/{project_id}/jobs")
def jobs_list(project_id: str) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    items = store.list_jobs(project_id)
    return {"count": len(items), "jobs": items}


@app.get("/api/v1/jobs/{job_id}")
def jobs_get(job_id: str) -> dict:
    item = store.get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="job not found")
    return item

@app.get("/api/v1/jobs/{job_id}/events")
def jobs_events(job_id: str) -> dict:
    if store.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    events = store.list_job_events(job_id)
    return {"count": len(events), "events": events}


@app.post("/api/v1/jobs/{job_id}/cancel")
def jobs_cancel(job_id: str) -> dict:
    """Cancel a job or request cooperative cancellation from a running worker."""
    try:
        item = store.request_job_cancellation(job_id, actor="human")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job": item,
        "cancellation": (
            "requested" if item["status"] == "cancel_requested" else "confirmed"
        ),
        "execution_stopped": item["status"] == "cancelled",
    }

@app.get("/api/v1/datasets/{dataset_id}/provenance")
def dataset_provenance(dataset_id: str) -> dict:
    """Return event-chain status separately from current stored-file integrity."""
    report = store.get_dataset_provenance(dataset_id)
    if report is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    item = store.get_dataset(dataset_id)
    content_path = store.get_dataset_content_path(dataset_id)
    if content_path is None or not Path(content_path).is_file():
        content_integrity = "missing"
    elif item is not None and _dataset_content_matches(item, Path(content_path)):
        content_integrity = "verified"
    else:
        content_integrity = "failed"
    return {**report, "content_integrity": content_integrity}

def run() -> None:
    parser = argparse.ArgumentParser(description="Run GEOLOGIA API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error(
            "remote binding is disabled in this development server; "
            "use loopback until authentication and production controls are implemented"
        )
    uvicorn.run("geologia.api:app", host=args.host, port=args.port, reload=False)


app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")


if __name__ == "__main__":
    run()
