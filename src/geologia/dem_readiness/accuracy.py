"""File-backed DEM/reference residual computation with explicit scientific gates."""

import csv
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from geologia.dem_readiness.manifest import DEMTileManifest
from geologia.dem_readiness.models import (
    DeclaredUseContext,
    ElevationUncertainty,
    IndependentReviewEvidence,
)

NonEmpty = Annotated[str, Field(min_length=1)]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]

AccuracyMetric = Literal["rmse_m", "mae_m", "abs_bias_m", "empirical_le90_m"]
IndependenceStatus = Literal[
    "independent_confirmed",
    "conditional_limited_use",
    "unresolved",
    "dependent",
]
SurfaceType = Literal["DSM", "DTM"]


class DEMAccuracyMetadata(BaseModel):
    """Required provenance and compatibility metadata; never inferred from pixels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_version_id: NonEmpty
    dem_vertical_datum: NonEmpty
    reference_vertical_datum: NonEmpty
    dem_vertical_unit: NonEmpty
    reference_vertical_unit: NonEmpty
    dem_surface_type: SurfaceType
    reference_surface_type: SurfaceType
    dem_epoch: NonEmpty
    reference_epoch: NonEmpty
    reference_source_id: NonEmpty
    reference_release: NonEmpty
    reference_horizontal_crs: NonEmpty
    aoi_crs: NonEmpty
    dem_metadata_reference: NonEmpty
    reference_metadata_reference: NonEmpty
    independence_status: IndependenceStatus
    independence_evidence_reference: NonEmpty
    independence_reviewer: NonEmpty
    independence_reviewed_at: datetime

    @model_validator(mode="after")
    def require_timezone(self) -> "DEMAccuracyMetadata":
        for name in self.model_fields:
            value = getattr(self, name)
            if isinstance(value, str) and not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if (
            self.independence_reviewed_at.tzinfo is None
            or self.independence_reviewed_at.utcoffset() is None
        ):
            raise ValueError("independence_reviewed_at must have a valid UTC offset")
        return self


class AccuracyRequirement(BaseModel):
    """Task-specific, frozen accuracy requirement; no universal limit is supplied."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: AccuracyMetric
    maximum_value_m: float = Field(ge=0)
    minimum_valid_observations: int = Field(ge=1, le=100_000)
    requirement_reference: NonEmpty
    approved_by: NonEmpty
    frozen_at: datetime

    @field_validator("maximum_value_m")
    @classmethod
    def finite_limit(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("accuracy limit must be finite")
        return value

    @model_validator(mode="after")
    def require_timezone(self) -> "AccuracyRequirement":
        for name in self.model_fields:
            value = getattr(self, name)
            if isinstance(value, str) and not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.frozen_at.tzinfo is None or self.frozen_at.utcoffset() is None:
            raise ValueError("frozen_at must have a valid UTC offset")
        return self


MAX_REFERENCE_OBSERVATIONS = 100_000
MAX_REFERENCE_FILE_BYTES = 100 * 1024 * 1024
MAX_DEM_ACCURACY_TILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_DEM_ACCURACY_TILES = 256
OVERLAP_EQUALITY_TOLERANCE_M = 1e-6

MAX_REFERENCE_UNCERTAINTY_SIDECAR_BYTES = 10 * 1024 * 1024


def _load_reference_uncertainty_sidecar(
    path: Path,
    expected_sha256: str,
    reference_sha256: str,
    point_ids: set[str],
) -> tuple[str, dict[str, ElevationUncertainty]]:
    """Load hash-bound typed uncertainty records without propagating them."""
    size, digest = _sha256_file(path, MAX_REFERENCE_UNCERTAINTY_SIDECAR_BYTES)
    if digest.lower() != expected_sha256.lower():
        raise FormatValidationError(
            "reference uncertainty sidecar SHA-256 does not match its record"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FormatValidationError(
            "reference uncertainty sidecar is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != "geologia.reference-uncertainty.v1":
        raise FormatValidationError(
            "reference uncertainty sidecar schema is unsupported"
        )
    if payload.get("reference_dataset_sha256", "").lower() != reference_sha256.lower():
        raise FormatValidationError(
            "reference uncertainty sidecar is not bound to this reference CSV"
        )
    records = payload.get("records")
    if not isinstance(records, dict):
        raise FormatValidationError(
            "reference uncertainty sidecar records must be an object keyed by point_id"
        )
    if set(records) != point_ids:
        raise FormatValidationError(
            "reference uncertainty sidecar point IDs must exactly match the reference CSV"
        )
    parsed = {}
    for point_id, record in records.items():
        if not isinstance(record, dict):
            raise FormatValidationError(
                f"reference uncertainty record {point_id!r} must be an object"
            )
        try:
            parsed[point_id] = ElevationUncertainty.model_validate(record)
        except ValidationError as exc:
            raise FormatValidationError(
                f"reference uncertainty record {point_id!r} is invalid"
            ) from exc
    return digest, parsed

def _canonical_json_sha256(payload: object) -> str:
    """Hash deterministic UTF-8 JSON for the exact structured input payload."""
    import json

    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("payload cannot be canonicalized as finite JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path, maximum_bytes: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                total += len(chunk)
                if total > maximum_bytes:
                    raise ValueError("input file exceeds the accuracy-processing size limit")
                digest.update(chunk)
    except OSError as exc:
        raise ValueError("input file cannot be read") from exc
    if total == 0:
        raise ValueError("input file must be non-empty")
    return total, digest.hexdigest()


def _metrics(residuals: list[float]) -> dict[str, float | int | None]:
    count = len(residuals)
    if not count:
        return {
            "count": 0,
            "bias_m": None,
            "mae_m": None,
            "rmse_m": None,
            "residual_std_m": None,
            "median_residual_m": None,
            "nmad_m": None,
            "empirical_le90_m": None,
        }
    absolute = [abs(value) for value in residuals]
    bias = statistics.fmean(residuals)
    median = statistics.median(residuals)
    deviations = [abs(value - median) for value in residuals]
    sorted_absolute = sorted(absolute)
    nearest_rank_90 = max(1, math.ceil(0.90 * count))
    return {
        "count": count,
        "bias_m": bias,
        "mae_m": statistics.fmean(absolute),
        "rmse_m": math.sqrt(statistics.fmean(value * value for value in residuals)),
        "residual_std_m": statistics.stdev(residuals) if count > 1 else None,
        "median_residual_m": median,
        "nmad_m": 1.4826 * statistics.median(deviations),
        "empirical_le90_m": sorted_absolute[nearest_rank_90 - 1],
    }


def _not_evaluable_report(
    reason: str,
    *,
    metadata: DEMAccuracyMetadata,
    product_manifest_sha256: str,
    reference_dataset_sha256: str,
    aoi_dataset_sha256: str,
    coverage_footprint_reference: str,
) -> dict:
    return {
        "assessment_type": "dem_reference_residuals",
        "assessment_status": "not_evaluable",
        "accuracy_disposition": "not_evaluable",
        "reason_codes": [reason],
        "product_version_id": metadata.product_version_id,
        "product_manifest_sha256": product_manifest_sha256,
        "input_hash_scheme": "canonical-json-v1",
        "product_manifest_hash_binding": "verified_canonical_manifest",
        "reference_dataset_sha256": reference_dataset_sha256,
        "aoi_dataset_sha256": aoi_dataset_sha256,
        "aoi_hash_binding": "verified_canonical_aoi_payload",
        "coverage_footprint_reference": coverage_footprint_reference,
        "independence_status": metadata.independence_status,
        "metrics": None,
        "readiness_disposition": "not_assessed",
        "scientific_interpretation": False,
    }


def compute_dem_reference_residuals(
    dem_paths: list[Path],
    reference_csv_path: Path,
    aoi_payload: dict,
    *,
    metadata: DEMAccuracyMetadata,
    product_manifest_sha256: str,
    reference_dataset_sha256: str,
    aoi_dataset_sha256: str,
    product_manifest: DEMTileManifest,
    coverage_footprint_reference: str,
    requirement: AccuracyRequirement | None = None,
    declared_use: DeclaredUseContext | None = None,
    independent_review: IndependentReviewEvidence | None = None,
    reference_uncertainty_sidecar_path: Path | None = None,
    reference_uncertainty_sidecar_sha256: str | None = None,
) -> dict:
    """Sample aligned DEM tiles at reference points and calculate direct residual metrics.

    CSV columns: point_id,x,y,elevation_m,terrain_stratum,uncertainty_m.
    Optional typed uncertainty metadata is supplied in a separately hashed JSON sidecar.
    Residual convention: DEM elevation minus reference elevation.
    """
    from contextlib import ExitStack

    from geologia.formats import (
        FormatValidationError,
        _densify_geometry_for_crs,
        _polygonal_aoi,
        _dependency,
    )

    rasterio = _dependency("rasterio")
    pyproj = _dependency("pyproj")
    from rasterio.windows import Window
    from shapely.geometry import Point
    from shapely.ops import transform as transform_geometry

    if not dem_paths or len(dem_paths) > MAX_DEM_ACCURACY_TILES:
        raise FormatValidationError(
            f"accuracy assessment requires 1 to {MAX_DEM_ACCURACY_TILES} DEM tiles"
        )
    if len({Path(path).resolve() for path in dem_paths}) != len(dem_paths):
        raise FormatValidationError("accuracy assessment contains duplicate DEM paths")
    for value in (
        product_manifest_sha256,
        reference_dataset_sha256,
        aoi_dataset_sha256,
    ):
        if len(value) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in value
        ):
            raise FormatValidationError("accuracy input checksums must be SHA-256 values")
    try:
        canonical_manifest_sha = _canonical_json_sha256(
            product_manifest.model_dump(mode="json")
        )
        canonical_aoi_sha = _canonical_json_sha256(aoi_payload)
    except ValueError as exc:
        raise FormatValidationError(
            "manifest or AOI payload is not canonicalizable finite JSON"
        ) from exc
    if canonical_manifest_sha.lower() != product_manifest_sha256.lower():
        raise FormatValidationError(
            "product manifest SHA-256 does not match canonical manifest content"
        )
    if canonical_aoi_sha.lower() != aoi_dataset_sha256.lower():
        raise FormatValidationError(
            "AOI SHA-256 does not match canonical AOI content"
        )
    if product_manifest.product_version_id != metadata.product_version_id:
        raise FormatValidationError(
            "manifest product version does not match accuracy metadata"
        )
    if not coverage_footprint_reference.strip():
        raise FormatValidationError(
            "accuracy assessment requires a coverage footprint reference"
        )

    if metadata.dem_vertical_datum != metadata.reference_vertical_datum:
        return _not_evaluable_report(
            "vertical_datum_mismatch",
            metadata=metadata,
            product_manifest_sha256=product_manifest_sha256,
            reference_dataset_sha256=reference_dataset_sha256,
            aoi_dataset_sha256=aoi_dataset_sha256,
            coverage_footprint_reference=coverage_footprint_reference,
        )
    if (
        metadata.dem_vertical_unit.lower() != "m"
        or metadata.reference_vertical_unit.lower() != "m"
    ):
        return _not_evaluable_report(
            "technical_format_incompatible",
            metadata=metadata,
            product_manifest_sha256=product_manifest_sha256,
            reference_dataset_sha256=reference_dataset_sha256,
            aoi_dataset_sha256=aoi_dataset_sha256,
            coverage_footprint_reference=coverage_footprint_reference,
        )
    if metadata.dem_surface_type != metadata.reference_surface_type:
        return _not_evaluable_report(
            "surface_type_mismatch",
            metadata=metadata,
            product_manifest_sha256=product_manifest_sha256,
            reference_dataset_sha256=reference_dataset_sha256,
            aoi_dataset_sha256=aoi_dataset_sha256,
            coverage_footprint_reference=coverage_footprint_reference,
        )
    if metadata.dem_epoch != metadata.reference_epoch:
        return _not_evaluable_report(
            "temporal_mismatch",
            metadata=metadata,
            product_manifest_sha256=product_manifest_sha256,
            reference_dataset_sha256=reference_dataset_sha256,
            aoi_dataset_sha256=aoi_dataset_sha256,
            coverage_footprint_reference=coverage_footprint_reference,
        )

    reference_size, reference_sha = _sha256_file(
        Path(reference_csv_path), MAX_REFERENCE_FILE_BYTES
    )
    if reference_sha.lower() != reference_dataset_sha256.lower():
        raise FormatValidationError(
            "reference CSV SHA-256 does not match its dataset record"
        )
    tile_records = []
    total_dem_bytes = 0
    for path in dem_paths:
        size_bytes, digest = _sha256_file(Path(path), MAX_DEM_ACCURACY_TILE_BYTES)
        total_dem_bytes += size_bytes
        if total_dem_bytes > 50 * 1024 * 1024 * 1024:
            raise FormatValidationError("DEM tile collection exceeds the 50 GiB limit")
        tile_records.append({
            "filename": Path(path).name,
            "size_bytes": size_bytes,
            "sha256": digest,
        })

    manifest_tile_hashes = sorted(
        value.lower() for value in product_manifest.tile_dataset_sha256s
    )
    actual_tile_hashes = sorted(record["sha256"].lower() for record in tile_records)
    if manifest_tile_hashes != actual_tile_hashes:
        raise FormatValidationError(
            "manifest tile SHA-256 membership does not match the supplied DEM files"
        )

    try:
        reference_crs = pyproj.CRS.from_user_input(
            metadata.reference_horizontal_crs
        )
        aoi_source_crs = pyproj.CRS.from_user_input(metadata.aoi_crs)
        aoi = _polygonal_aoi(aoi_payload)
        if (
            aoi_source_crs.is_compound
            or aoi_source_crs.is_vertical
            or not (aoi_source_crs.is_geographic or aoi_source_crs.is_projected)
        ):
            raise FormatValidationError("AOI CRS must be horizontal")
    except Exception as exc:
        if isinstance(exc, FormatValidationError):
            raise
        raise FormatValidationError("reference/AOI CRS or geometry is invalid") from exc

    observations = []
    seen_ids = set()
    required_columns = {
        "point_id", "x", "y", "elevation_m", "terrain_stratum", "uncertainty_m"
    }
    try:
        with Path(reference_csv_path).open(
            "r", encoding="utf-8-sig", newline=""
        ) as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
                raise FormatValidationError(
                    "reference CSV must contain point_id,x,y,elevation_m,"
                    "terrain_stratum,uncertainty_m"
                )
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise FormatValidationError("reference CSV contains duplicate column names")
            for row_number, row in enumerate(reader, start=2):
                if len(observations) >= MAX_REFERENCE_OBSERVATIONS:
                    raise FormatValidationError(
                        "reference CSV exceeds the 100,000 observation limit"
                    )
                point_id = (row.get("point_id") or "").strip()
                stratum = (row.get("terrain_stratum") or "").strip()
                if not point_id or not stratum or point_id in seen_ids:
                    raise FormatValidationError(
                        f"reference row {row_number} has empty or duplicate point ID/stratum"
                    )
                seen_ids.add(point_id)
                try:
                    x, y, elevation, uncertainty = (
                        float(row["x"]),
                        float(row["y"]),
                        float(row["elevation_m"]),
                        float(row["uncertainty_m"]),
                    )
                except (TypeError, ValueError) as exc:
                    raise FormatValidationError(
                        f"reference row {row_number} contains a non-numeric value"
                    ) from exc
                if not all(
                    math.isfinite(value)
                    for value in (x, y, elevation, uncertainty)
                ):
                    raise FormatValidationError(
                        f"reference row {row_number} contains a non-finite value"
                    )
                if uncertainty < 0:
                    raise FormatValidationError(
                        f"reference row {row_number} has negative uncertainty"
                    )
                observations.append({
                    "point_id": point_id,
                    "x": x,
                    "y": y,
                    "reference_elevation_m": elevation,
                    "terrain_stratum": stratum,
                    "reference_uncertainty_m": uncertainty,
                    "reference_uncertainty_kind": "unknown",
                    "reference_uncertainty_semantics": "legacy_untyped_not_propagated",
                })
    except OSError as exc:
        raise FormatValidationError("reference CSV cannot be read") from exc
    if not observations:
        raise FormatValidationError("reference CSV contains no observations")

    if (reference_uncertainty_sidecar_path is None) != (
        reference_uncertainty_sidecar_sha256 is None
    ):
        raise FormatValidationError(
            "reference uncertainty sidecar path and SHA-256 must be supplied together"
        )
    uncertainty_sidecar_sha = None
    if reference_uncertainty_sidecar_path is not None:
        if len(reference_uncertainty_sidecar_sha256) != 64 or any(
            char not in "0123456789abcdefABCDEF"
            for char in reference_uncertainty_sidecar_sha256
        ):
            raise FormatValidationError(
                "reference uncertainty sidecar SHA-256 must be a SHA-256 value"
            )
        uncertainty_sidecar_sha, typed_uncertainties = _load_reference_uncertainty_sidecar(
            Path(reference_uncertainty_sidecar_path),
            reference_uncertainty_sidecar_sha256,
            reference_sha,
            seen_ids,
        )
        for observation in observations:
            uncertainty = typed_uncertainties[observation["point_id"]]
            observation["typed_reference_uncertainty"] = uncertainty.model_dump(
                mode="json"
            )
            observation["reference_uncertainty_kind"] = uncertainty.kind.value
            observation["reference_uncertainty_semantics"] = (
                "typed_metadata_not_propagated"
                if uncertainty.kind.value != "unknown"
                else "declared_unknown_not_propagated"
            )

    excluded: dict[str, int] = {}
    residual_records = []
    all_residuals = []
    residuals_by_stratum: dict[str, list[float]] = {}

    with ExitStack() as stack:
        datasets = []
        dem_crs = None
        reference_grid = None
        for path in dem_paths:
            try:
                dataset = stack.enter_context(rasterio.open(Path(path), "r"))
            except Exception as exc:
                raise FormatValidationError("DEM tile cannot be opened") from exc
            if (
                dataset.count < 1
                or dataset.crs is None
                or dataset.width * dataset.height > 100_000_000
            ):
                raise FormatValidationError(
                    "DEM tile must have a band, horizontal CRS and at most 100 million pixels"
                )
            tile_crs = pyproj.CRS.from_user_input(dataset.crs)
            if dem_crs is None:
                dem_crs = tile_crs
                reference_grid = dataset.transform
            elif not tile_crs.equals(dem_crs):
                raise FormatValidationError(
                    "DEM accuracy tiles must share one horizontal CRS"
                )
            if any(
                not math.isclose(left, right, rel_tol=0, abs_tol=1e-9)
                for left, right in zip(
                    (
                        dataset.transform.a, dataset.transform.b,
                        dataset.transform.d, dataset.transform.e,
                    ),
                    (
                        reference_grid.a, reference_grid.b,
                        reference_grid.d, reference_grid.e,
                    ),
                )
            ):
                raise FormatValidationError(
                    "DEM accuracy tiles must share grid orientation and resolution"
                )
            offset_col, offset_row = (~reference_grid) * (
                dataset.transform.c, dataset.transform.f
            )
            if (
                not math.isclose(offset_col, round(offset_col), abs_tol=1e-6)
                or not math.isclose(offset_row, round(offset_row), abs_tol=1e-6)
            ):
                raise FormatValidationError(
                    "DEM accuracy tile origins must align to the common grid"
                )
            datasets.append(dataset)

        aoi_to_dem = pyproj.Transformer.from_crs(
            aoi_source_crs, dem_crs, always_xy=True
        )
        aoi_in_dem = transform_geometry(
            aoi_to_dem.transform,
            _densify_geometry_for_crs(aoi, aoi_source_crs),
        )
        if aoi_in_dem.is_empty or not aoi_in_dem.is_valid:
            raise FormatValidationError("AOI cannot be transformed to DEM CRS")
        reference_to_dem = pyproj.Transformer.from_crs(
            reference_crs, dem_crs, always_xy=True
        )

        for observation in observations:
            x, y = reference_to_dem.transform(observation["x"], observation["y"])
            if not math.isfinite(x) or not math.isfinite(y):
                excluded["coordinate_transform_failed"] = (
                    excluded.get("coordinate_transform_failed", 0) + 1
                )
                continue
            if not aoi_in_dem.covers(Point(x, y)):
                excluded["outside_aoi"] = excluded.get("outside_aoi", 0) + 1
                continue

            candidates = []
            for dataset, tile_record in zip(datasets, tile_records, strict=True):
                bounds = dataset.bounds
                if not (
                    bounds.left <= x <= bounds.right
                    and bounds.bottom <= y <= bounds.top
                ):
                    continue
                try:
                    row, col = dataset.index(x, y)
                except Exception:
                    continue
                if not (0 <= row < dataset.height and 0 <= col < dataset.width):
                    continue
                window = Window(col, row, 1, 1)
                if int(dataset.read_masks(1, window=window)[0, 0]) == 0:
                    continue
                value = float(dataset.read(1, window=window)[0, 0])
                if not math.isfinite(value):
                    continue
                candidates.append((tile_record["filename"], value))

            if not candidates:
                excluded["no_valid_dem_pixel"] = (
                    excluded.get("no_valid_dem_pixel", 0) + 1
                )
                continue
            candidates.sort(key=lambda item: item[0])
            if any(
                abs(value - candidates[0][1]) > OVERLAP_EQUALITY_TOLERANCE_M
                for _, value in candidates[1:]
            ):
                excluded["overlap_value_conflict"] = (
                    excluded.get("overlap_value_conflict", 0) + 1
                )
                continue
            dem_value = candidates[0][1]
            residual = dem_value - observation["reference_elevation_m"]
            record = {
                "point_id": observation["point_id"],
                "terrain_stratum": observation["terrain_stratum"],
                "dem_elevation_m": dem_value,
                "reference_elevation_m": observation["reference_elevation_m"],
                "residual_m": residual,
                "reference_uncertainty_m": observation["reference_uncertainty_m"],
                "reference_uncertainty_kind": observation["reference_uncertainty_kind"],
                "reference_uncertainty_semantics": observation["reference_uncertainty_semantics"],
                "reference_uncertainty": observation.get("typed_reference_uncertainty"),
                "overlapping_valid_tiles": len(candidates),
            }
            residual_records.append(record)
            all_residuals.append(residual)
            residuals_by_stratum.setdefault(
                observation["terrain_stratum"], []
            ).append(residual)

    metrics = _metrics(all_residuals)
    stratum_metrics = {
        stratum: _metrics(values)
        for stratum, values in sorted(residuals_by_stratum.items())
    }
    reason_codes = []
    review_bound = False
    if declared_use is not None and independent_review is not None:
        expected_scope = (
            metadata.product_version_id,
            declared_use.pilot_area_id,
            declared_use.task_profile_id,
        )
        review_scope = (
            independent_review.product_version_id,
            independent_review.pilot_area_id,
            independent_review.task_profile_id,
        )
        review_bound = (
            declared_use.product_version_id == metadata.product_version_id
            and review_scope == expected_scope
            and independent_review.reviewer == metadata.independence_reviewer
            and independent_review.evidence_reference
            == metadata.independence_evidence_reference
            and independent_review.reviewed_at == metadata.independence_reviewed_at
        )
    metrics_scope = (
        "primary_confirmatory"
        if metadata.independence_status == "independent_confirmed" and review_bound
        else "descriptive_only"
    )
    accuracy_disposition = "not_assessed"
    metric_value = None

    conditional_requirement_comparison = None
    if (
        metadata.independence_status in {"unresolved", "dependent"}
        or (
            metadata.independence_status == "independent_confirmed"
            and not review_bound
        )
    ):
        reason_codes.append("source_dependence_conflict")
        accuracy_disposition = "not_evaluable"
    elif not all_residuals:
        reason_codes.append("insufficient_sample")
        accuracy_disposition = "not_evaluable"
    elif metadata.independence_status == "conditional_limited_use":
        reason_codes.append("source_dependence_conflict")
        accuracy_disposition = "conditional_limited_use"
        metrics_scope = "conditional_limited_use"
        if requirement is not None:
            metric_value = {
                "rmse_m": metrics["rmse_m"],
                "mae_m": metrics["mae_m"],
                "abs_bias_m": abs(metrics["bias_m"]) if metrics["bias_m"] is not None else None,
                "empirical_le90_m": metrics["empirical_le90_m"],
            }[requirement.metric]
            if len(all_residuals) >= requirement.minimum_valid_observations:
                conditional_requirement_comparison = {
                    "metric": requirement.metric,
                    "value_m": metric_value,
                    "maximum_value_m": requirement.maximum_value_m,
                    "within_limit": (
                        metric_value is not None
                        and metric_value <= requirement.maximum_value_m
                    ),
                    "not_confirmatory": True,
                }
            else:
                reason_codes.append("insufficient_sample")
    elif requirement is None:
        reason_codes.append("not_assessed")
    elif len(all_residuals) < requirement.minimum_valid_observations:
        reason_codes.append("insufficient_sample")
        accuracy_disposition = "not_evaluable"
    else:
        metric_value = {
            "rmse_m": metrics["rmse_m"],
            "mae_m": metrics["mae_m"],
            "abs_bias_m": abs(metrics["bias_m"]) if metrics["bias_m"] is not None else None,
            "empirical_le90_m": metrics["empirical_le90_m"],
        }[requirement.metric]
        if metric_value is None:
            reason_codes.append("not_assessed")
        elif metric_value <= requirement.maximum_value_m:
            accuracy_disposition = "accuracy_requirement_met_for_declared_use"
        else:
            accuracy_disposition = "accuracy_requirement_not_met"
            reason_codes.append("accuracy_requirement_not_met")

    return {
        "assessment_type": "dem_reference_residuals",
        "assessment_status": "computed",
        "accuracy_disposition": accuracy_disposition,
        "reason_codes": reason_codes,
        "metrics_scope": metrics_scope,
        "product_version_id": metadata.product_version_id,
        "product_manifest_sha256": canonical_manifest_sha,
        "input_hash_scheme": "canonical-json-v1",
        "product_manifest_hash_binding": "verified_canonical_manifest",
        "dem_tiles": tile_records,
        "reference_source_id": metadata.reference_source_id,
        "reference_release": metadata.reference_release,
        "reference_uncertainty_model": (
            {
                "schema": "geologia.reference-uncertainty.v1",
                "source": "hash_bound_sidecar",
                "sidecar_sha256": uncertainty_sidecar_sha,
                "record_count": len(observations),
                "interpretation": "typed_metadata_not_propagated",
                "note": "Typed records are provenance metadata only; no conversion, combination, or metric adjustment is performed.",
            }
            if uncertainty_sidecar_sha is not None
            else {
                "schema": "legacy-reference-uncertainty-v1",
                "source_field": "uncertainty_m",
                "kind": "unknown",
                "unit": "m",
                "interpretation": "legacy_untyped_not_propagated",
                "note": (
                    "Numeric values are preserved for traceability only; they are not "
                    "converted, combined, or used to adjust residual metrics."
                ),
            }
        ),
        "reference_uncertainty_sidecar_sha256": uncertainty_sidecar_sha,
        "reference_dataset_sha256": reference_sha,
        "reference_file_size_bytes": reference_size,
        "reference_metadata_reference": metadata.reference_metadata_reference,
        "dem_metadata_reference": metadata.dem_metadata_reference,
        "reference_vertical_datum": metadata.reference_vertical_datum,
        "dem_vertical_datum": metadata.dem_vertical_datum,
        "surface_type": metadata.dem_surface_type,
        "dem_epoch": metadata.dem_epoch,
        "reference_epoch": metadata.reference_epoch,
        "aoi_dataset_sha256": canonical_aoi_sha,
        "aoi_hash_binding": "verified_canonical_aoi_payload",
        "coverage_footprint_reference": coverage_footprint_reference,
        "independence_status": metadata.independence_status,
        "independence_evidence_reference": metadata.independence_evidence_reference,
        "independence_reviewer": metadata.independence_reviewer,
        "independence_reviewed_at": metadata.independence_reviewed_at.isoformat(),
        "observation_count": len(observations),
        "valid_residual_count": len(all_residuals),
        "excluded_counts": excluded,
        "metrics": metrics,
        "metrics_by_terrain_stratum": stratum_metrics,
        "accuracy_requirement": (
            requirement.model_dump(mode="json") if requirement is not None else None
        ),
        "evaluated_metric_value_m": metric_value,
        "conditional_requirement_comparison": conditional_requirement_comparison,
        "residuals": residual_records,
        "readiness_disposition": "not_assessed",
        "vertical_transformation_applied": False,
        "sampling_method": "nearest containing raster cell; no interpolation",
        "residual_convention": "DEM minus reference",
        "empirical_le90_method": "nearest-rank 90th percentile of absolute residuals",
        "scientific_interpretation": False,
    }
