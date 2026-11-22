"""Deterministic reference-observation coverage metrics for registered AOIs.

This module counts caller-curated, reviewer-attested independent sites. It does
not establish source independence, datum correctness, reference accuracy or DEM
accuracy; those remain separate evidence and review gates.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import date, datetime
from statistics import median
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from geologia.formats import FormatDependencyError, FormatValidationError
from .coverage import CoverageMetrics


NonEmpty = Annotated[str, Field(min_length=1)]
MAX_GRID_CELLS = 100_000
EQUAL_AREA_CRS = "EPSG:6933"
COMPUTATION_METHOD = "reference-coverage-v1.0"


class IndependenceReviewAttestation(BaseModel):
    """Human review record required before observations count as independent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: NonEmpty
    reviewer: NonEmpty
    reviewed_at: datetime
    definition: NonEmpty
    source_lineage_reviewed: bool
    spatial_independence_reviewed: bool
    source_dependence_conflicts: bool = False

    @model_validator(mode="after")
    def require_timezone(self) -> "IndependenceReviewAttestation":
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        return self


class ReferenceCoverageMetricsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    aoi_dataset_id: NonEmpty
    aoi_crs: NonEmpty
    reference_crs: NonEmpty
    dem_epoch: date
    primary_stratum_ids: list[NonEmpty] = Field(min_length=1, max_length=100)
    computed_by: NonEmpty
    analysis_code_commit: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{7,40}$")]
    independence_review: IndependenceReviewAttestation

    @model_validator(mode="after")
    def validate_unique_strata(self) -> "ReferenceCoverageMetricsRequest":
        if len(set(self.primary_stratum_ids)) != len(self.primary_stratum_ids):
            raise ValueError("primary_stratum_ids must be unique")
        return self


def _geojson_features(payload: dict[str, Any]) -> list[dict[str, Any]]:
    kind = payload.get("type")
    if kind == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list):
            raise FormatValidationError("reference FeatureCollection.features must be an array")
        return [item for item in features if isinstance(item, dict)]
    if kind == "Feature":
        return [payload]
    raise FormatValidationError(
        "reference observations must be a GeoJSON Feature or FeatureCollection"
    )


def _polygonal_aoi(payload: dict[str, Any]):
    from shapely.geometry import shape
    from shapely.ops import unary_union

    kind = payload.get("type")
    if kind == "FeatureCollection":
        raw = [
            feature.get("geometry")
            for feature in payload.get("features", [])
            if isinstance(feature, dict) and feature.get("geometry") is not None
        ]
    elif kind == "Feature":
        raw = [payload.get("geometry")]
    elif kind in {"Polygon", "MultiPolygon"}:
        raw = [payload]
    else:
        raise FormatValidationError("AOI must be a Polygon or MultiPolygon GeoJSON")
    try:
        geometries = [shape(item) for item in raw if isinstance(item, dict)]
        if not geometries:
            raise FormatValidationError("AOI contains no polygon geometry")
        geometry = unary_union(geometries)
    except FormatValidationError:
        raise
    except Exception as exc:
        raise FormatValidationError("AOI polygon geometry cannot be decoded") from exc
    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise FormatValidationError("AOI must resolve to Polygon or MultiPolygon")
    if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
        raise FormatValidationError("AOI polygon must be valid and have positive area")
    return geometry


def _grid_cells(aoi, cell_size: int):
    from shapely.geometry import box

    min_x, min_y, max_x, max_y = aoi.bounds
    min_col = math.floor(min_x / cell_size)
    max_col = math.floor(max_x / cell_size)
    min_row = math.floor(min_y / cell_size)
    max_row = math.floor(max_y / cell_size)
    candidate_count = (max_col - min_col + 1) * (max_row - min_row + 1)
    if candidate_count > MAX_GRID_CELLS:
        raise FormatValidationError(
            f"AOI requires {candidate_count} grid candidates; limit is {MAX_GRID_CELLS}"
        )
    eligible = set()
    for col in range(min_col, max_col + 1):
        for row in range(min_row, max_row + 1):
            cell = box(
                col * cell_size,
                row * cell_size,
                (col + 1) * cell_size,
                (row + 1) * cell_size,
            )
            if aoi.intersection(cell).area > 0:
                eligible.add((col, row))
    return eligible


def _cell_for_point(point, cell_size: int, eligible: set[tuple[int, int]]):
    col = math.floor(point.x / cell_size)
    row = math.floor(point.y / cell_size)
    if (col, row) in eligible:
        return col, row
    candidates = [
        (candidate_col, candidate_row)
        for candidate_col in range(col - 1, col + 2)
        for candidate_row in range(row - 1, row + 2)
        if (candidate_col, candidate_row) in eligible
    ]
    if not candidates:
        raise FormatValidationError("AOI point cannot be assigned to a registered grid cell")
    return min(
        candidates,
        key=lambda cell: (
            abs(cell[0] - col) + abs(cell[1] - row),
            cell[0],
            cell[1],
        ),
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _finite_nonnegative(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _metadata_completeness(records: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "vertical_datum",
        "reference_method",
        "horizontal_uncertainty_m",
        "vertical_uncertainty_m",
        "horizontal_reference_frame",
        "coordinate_epoch",
        "geoid_model",
    )
    missing = {
        field: sum(
            1
            for record in records
            if record.get(field) is None
            or (isinstance(record.get(field), str) and not record[field].strip())
        )
        for field in fields
    }
    return {
        "eligible_observation_count": len(records),
        "missing_count_by_field": missing,
        "complete_for_all_fields": bool(records) and all(value == 0 for value in missing.values()),
    }


def compute_reference_coverage_metrics(
    reference_payload: dict[str, Any],
    aoi_payload: dict[str, Any],
    *,
    reference_crs: str,
    aoi_crs: str,
    dem_epoch: date,
    primary_stratum_ids: list[str],
    independence_review: IndependenceReviewAttestation,
) -> dict[str, Any]:
    """Compute frozen v1 spatial and temporal reference-coverage metrics."""
    try:
        import pyproj
        from shapely.geometry import Point
        from shapely.ops import transform as transform_geometry
    except ImportError as exc:
        raise FormatDependencyError(
            "reference coverage metrics require the optional pyproj and shapely dependencies"
        ) from exc

    aoi = _polygonal_aoi(aoi_payload)
    reference_crs_obj = pyproj.CRS.from_user_input(reference_crs)
    aoi_crs_obj = pyproj.CRS.from_user_input(aoi_crs)
    if reference_crs_obj.is_compound or reference_crs_obj.is_vertical:
        raise FormatValidationError("reference CRS must be a horizontal 2D CRS")
    if aoi_crs_obj.is_compound or aoi_crs_obj.is_vertical:
        raise FormatValidationError("AOI CRS must be a horizontal 2D CRS")
    area_crs = pyproj.CRS.from_user_input(EQUAL_AREA_CRS)
    aoi_to_area = pyproj.Transformer.from_crs(aoi_crs_obj, area_crs, always_xy=True)
    reference_to_area = pyproj.Transformer.from_crs(
        reference_crs_obj, area_crs, always_xy=True
    )
    aoi_area = transform_geometry(aoi_to_area.transform, aoi)
    aoi_area_m2 = float(aoi_area.area)
    if not math.isfinite(aoi_area_m2) or aoi_area_m2 <= 0:
        raise FormatValidationError("AOI area cannot be measured in the equal-area CRS")

    eligible_1km = _grid_cells(aoi_area, 1000)
    eligible_5km = _grid_cells(aoi_area, 5000)
    features = _geojson_features(reference_payload)
    review_complete = (
        independence_review.source_lineage_reviewed
        and independence_review.spatial_independence_reviewed
        and not independence_review.source_dependence_conflicts
    )
    review_conflict = independence_review.source_dependence_conflicts

    excluded: Counter[str] = Counter()
    observation_ids: set[str] = set()
    accepted_records: list[dict[str, Any]] = []
    site_records: dict[str, dict[str, Any]] = {}
    source_counts: Counter[str] = Counter()
    temporal_bins: Counter[str] = Counter()
    within_five_years = 0
    uncertainty_horizontal: list[float] = []
    uncertainty_vertical: list[float] = []

    for index, feature in enumerate(features):
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            excluded["feature_properties_or_geometry_missing"] += 1
            continue
        required = (
            "observation_id",
            "site_id",
            "source_id",
            "observed_at",
            "primary_stratum_id",
            "independence_group_id",
            "independence_status",
            "quality_flag",
        )
        if any(
            not isinstance(properties.get(field), str) or not properties[field].strip()
            for field in required
        ):
            excluded["required_property_missing"] += 1
            continue
        observation_id = properties["observation_id"].strip()
        site_id = properties["site_id"].strip()
        if observation_id in observation_ids:
            raise FormatValidationError(f"duplicate observation_id at feature {index}")
        observation_ids.add(observation_id)

        if properties["primary_stratum_id"].strip() not in primary_stratum_ids:
            excluded["unregistered_primary_stratum"] += 1
            continue
        if properties["quality_flag"].strip().lower() != "accepted":
            excluded["quality_flag_not_accepted"] += 1
            continue
        independence_status = properties["independence_status"].strip().lower()
        if independence_status != "independent":
            excluded[f"independence_status_{independence_status}"] += 1
            continue
        if not review_complete:
            exclusion_reason = (
                "source_dependence_conflict"
                if review_conflict
                else "independence_review_incomplete"
            )
            excluded[exclusion_reason] += 1
            continue

        observed_at = _parse_timestamp(properties.get("observed_at"))
        if observed_at is None:
            excluded["observation_timestamp_invalid"] += 1
            continue
        if geometry.get("type") != "Point":
            excluded["geometry_not_point"] += 1
            continue
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            excluded["point_coordinates_invalid"] += 1
            continue
        try:
            x, y = float(coordinates[0]), float(coordinates[1])
        except (TypeError, ValueError):
            excluded["point_coordinates_invalid"] += 1
            continue
        if not math.isfinite(x) or not math.isfinite(y):
            excluded["point_coordinates_invalid"] += 1
            continue
        point = transform_geometry(reference_to_area.transform, Point(x, y))
        if not aoi_area.covers(point):
            excluded["outside_aoi"] += 1
            continue

        record = {
            "observation_id": observation_id,
            "site_id": site_id,
            "source_id": properties["source_id"].strip(),
            "primary_stratum_id": properties["primary_stratum_id"].strip(),
            "independence_group_id": properties["independence_group_id"].strip(),
            "observed_at": observed_at,
            "vertical_datum": properties.get("vertical_datum"),
            "reference_method": properties.get("reference_method"),
            "horizontal_uncertainty_m": _finite_nonnegative(
                properties.get("horizontal_uncertainty_m")
            ),
            "vertical_uncertainty_m": _finite_nonnegative(
                properties.get("vertical_uncertainty_m")
            ),
            "horizontal_reference_frame": properties.get("horizontal_reference_frame"),
            "coordinate_epoch": properties.get("coordinate_epoch"),
            "geoid_model": properties.get("geoid_model"),
            "point": point,
        }
        accepted_records.append(record)
        source_counts[record["source_id"]] += 1

        years_from_epoch = abs((observed_at.date() - dem_epoch).days) / 365.2425
        if years_from_epoch <= 3:
            temporal_bins["0_3_years"] += 1
        elif years_from_epoch <= 5:
            temporal_bins["3_5_years"] += 1
        elif years_from_epoch <= 10:
            temporal_bins["5_10_years"] += 1
        else:
            temporal_bins["over_10_years"] += 1
        if years_from_epoch <= 5:
            within_five_years += 1

        previous = site_records.get(site_id)
        if previous is not None:
            same_location = (
                math.isclose(previous["point"].x, point.x, abs_tol=1e-6)
                and math.isclose(previous["point"].y, point.y, abs_tol=1e-6)
            )
            same_stratum = previous["primary_stratum_id"] == record["primary_stratum_id"]
            same_group = previous["independence_group_id"] == record["independence_group_id"]
            if not same_location or not same_stratum or not same_group:
                raise FormatValidationError(
                    f"site_id {site_id!r} maps to inconsistent coordinates or strata"
                )
        else:
            site_records[site_id] = record

        if record["horizontal_uncertainty_m"] is not None:
            uncertainty_horizontal.append(record["horizontal_uncertainty_m"])
        if record["vertical_uncertainty_m"] is not None:
            uncertainty_vertical.append(record["vertical_uncertainty_m"])

    site_list = list(site_records.values())
    cells_1km = {
        _cell_for_point(record["point"], 1000, eligible_1km)
        for record in site_list
    } if site_list else set()
    cells_5km = {
        _cell_for_point(record["point"], 5000, eligible_5km)
        for record in site_list
    } if site_list else set()
    block_counts = Counter(
        _cell_for_point(record["point"], 5000, eligible_5km)
        for record in site_list
    )
    max_block_fraction = (
        max(block_counts.values()) / len(site_list) if site_list else None
    )
    stratum_counts = Counter({stratum: 0 for stratum in primary_stratum_ids})
    stratum_counts.update(record["primary_stratum_id"] for record in site_list)
    observation_count = len(accepted_records)
    temporal_fraction = (
        within_five_years / observation_count if observation_count else None
    )
    metrics = CoverageMetrics(
        valid_independent_locations=len(site_list),
        polygon_area_km2=aoi_area_m2 / 1_000_000,
        occupied_1km_cells=len(cells_1km),
        eligible_1km_cells=len(eligible_1km),
        occupied_5km_blocks=len(cells_5km),
        eligible_5km_blocks=len(eligible_5km),
        max_block_observation_fraction=max_block_fraction,
        primary_cell_observation_counts=dict(stratum_counts),
        temporal_match_fraction=temporal_fraction,
    )

    def uncertainty_summary(values: list[float]) -> dict[str, float | None]:
        return {
            "count": len(values),
            "minimum_m": min(values) if values else None,
            "median_m": median(values) if values else None,
            "maximum_m": max(values) if values else None,
        }

    metadata_completeness = _metadata_completeness(accepted_records)
    if review_conflict:
        review_status = "attested_conflict"
        reason_codes = ["source_dependence_conflict"]
    elif not review_complete:
        review_status = "incomplete"
        reason_codes = ["unresolved"]
    else:
        review_status = "attested_complete"
        reason_codes = []
    if not metadata_completeness["complete_for_all_fields"]:
        reason_codes.append("metadata_insufficient")

    return {
        "report_type": "reference_coverage_metrics",
        "status": "measured" if review_complete else "not_evaluable",
        "computation_method": COMPUTATION_METHOD,
        "analysis_crs": EQUAL_AREA_CRS,
        "grid_origin_m": [0, 0],
        "grid_cell_sizes_m": {"density_cells": 1000, "spatial_blocks": 5000},
        "dem_epoch": dem_epoch.isoformat(),
        "primary_stratum_ids": primary_stratum_ids,
        "aoi_area_km2": aoi_area_m2 / 1_000_000,
        "reference_feature_count": len(features),
        "eligible_reference_observation_count": observation_count,
        "unique_independent_site_count": len(site_list),
        "excluded_by_reason": dict(excluded),
        "source_observation_counts": dict(source_counts),
        "temporal_observation_bins": {
            key: temporal_bins.get(key, 0)
            for key in ("0_3_years", "3_5_years", "5_10_years", "over_10_years")
        },
        "observations_within_5_years": within_five_years,
        "metadata_completeness": metadata_completeness,
        "uncertainty_summary": {
            "horizontal": uncertainty_summary(uncertainty_horizontal),
            "vertical": uncertainty_summary(uncertainty_vertical),
        },
        "independence_review": independence_review.model_dump(mode="json"),
        "independence_review_status": review_status,
        "independence_review_reference": independence_review.reference,
        "spatial_site_rule": (
            "One spatial count per unique site_id; repeated observations remain temporal records."
        ),
        "point_inclusion_rule": "AOI covers point in EPSG:6933; boundary included.",
        "metrics": metrics.model_dump(mode="json"),
        "reason_codes": reason_codes,
        "dem_accuracy_validated": False,
        "vertical_datum_harmonized": False,
        "source_independence_independently_proven": False,
    }
