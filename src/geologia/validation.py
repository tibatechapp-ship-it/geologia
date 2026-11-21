"""Versioned, deterministic dataset checks; these checks are not scientific validation."""
import csv
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from geologia.vector import inspect_csv, inspect_geojson

WATER_LEVEL_PROFILE = {
    "id": "groundwater-level-timeseries",
    "version": "1.0.0",
    "timestamp_headers": ("timestamp", "datetime", "date"),
    "measurement_header": "water_level_m",
}


def _report(
    *,
    level: str,
    profile: dict[str, Any] | None,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    checks: list[dict[str, str]],
    **metrics: Any,
) -> dict[str, Any]:
    return {
        "validation_level": level,
        "validation_status": "failed" if errors else "passed",
        "profile": profile,
        "checks": checks,
        "errors": errors[:20],
        "error_count": len(errors),
        "warnings": warnings[:20],
        "warning_count": len(warnings),
        "scientific_interpretation": False,
        **metrics,
    }


def validate_csv_file(path: Path, data_role: str | None) -> dict[str, Any]:
    """Validate CSV structure and, when selected, the explicit v1 water-level schema."""
    profile = WATER_LEVEL_PROFILE if data_role == "water_levels_timeseries" else None
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: list[dict[str, str]] = []
    rows_checked = 0
    invalid_timestamps = 0
    invalid_measurements = 0
    try:
        metrics = inspect_csv(path)
    except (ValueError, OSError) as exc:
        errors.append({"code": "csv.parse", "message": str(exc)})
        checks.append({"code": "csv.parse", "status": "failed"})
        return _report(
            level="schema" if profile else "structural",
            profile=profile,
            errors=errors,
            warnings=warnings,
            checks=checks,
            rows_checked=0,
            invalid_timestamp_count=0,
            invalid_measurement_count=0,
        )

    headers = metrics["headers"]
    normalized = [header.strip().casefold() for header in headers]
    if any(not header for header in normalized):
        errors.append({"code": "csv.header.empty", "message": "Column names must not be empty."})
    header_counts = Counter(normalized)
    duplicates = sorted(name for name, count in header_counts.items() if name and count > 1)
    if duplicates:
        errors.append({
            "code": "csv.header.duplicate",
            "message": "Column names must be unique after trimming and case normalization.",
            "columns": duplicates,
        })
    checks.append({
        "code": "csv.header.unique",
        "status": "failed" if any(
            error["code"].startswith("csv.header.") for error in errors
        ) else "passed",
    })
    if metrics["ragged_row_count"]:
        errors.append({
            "code": "csv.rows.width",
            "message": "Every non-empty row must contain the same number of fields as the header.",
            "count": metrics["ragged_row_count"],
        })
    checks.append({
        "code": "csv.rows.width",
        "status": "failed" if metrics["ragged_row_count"] else "passed",
    })
    if metrics["blank_row_count"]:
        warnings.append({
            "code": "csv.rows.blank",
            "message": "Blank rows were ignored during validation.",
            "count": metrics["blank_row_count"],
        })
    if metrics["row_count"] == 0:
        warnings.append({
            "code": "csv.rows.empty",
            "message": "The CSV contains a header but no data rows.",
        })

    rows_checked = metrics["row_count"]
    if profile:
        timestamp_candidates = [
            name for name in profile["timestamp_headers"] if name in normalized
        ]
        measurement_index = (
            normalized.index(profile["measurement_header"])
            if profile["measurement_header"] in normalized else None
        )
        if not timestamp_candidates:
            errors.append({
                "code": "profile.timestamp.missing",
                "message": (
                    "Expected an ISO-8601 timestamp column named timestamp, datetime, or date."
                ),
            })
        if measurement_index is None:
            errors.append({
                "code": "profile.water_level_m.missing",
                "message": "Expected a water_level_m column; the unit must be explicit.",
            })
        checks.append({
            "code": "profile.required_columns",
            "status": (
                "failed" if not timestamp_candidates or measurement_index is None else "passed"
            ),
        })

        if timestamp_candidates or measurement_index is not None:
            rows_checked = 0
            timestamp_index = (
                normalized.index(timestamp_candidates[0]) if timestamp_candidates else None
            )
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as source:
                    reader = csv.reader(source, strict=True)
                    next(reader, None)
                    for row_number, row in enumerate(reader, start=2):
                        if not row or all(not cell.strip() for cell in row):
                            continue
                        rows_checked += 1
                        if len(row) != len(headers):
                            continue
                        if timestamp_index is not None:
                            timestamp_value = row[timestamp_index].strip()
                            try:
                                datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
                            except ValueError:
                                invalid_timestamps += 1
                                if invalid_timestamps <= 20:
                                    errors.append({
                                        "code": "profile.timestamp.invalid",
                                        "message": (
                                            "Timestamp must use an ISO-8601 date or datetime."
                                        ),
                                        "row": row_number,
                                    })
                        if measurement_index is not None:
                            measurement_value = row[measurement_index].strip()
                            try:
                                numeric = float(measurement_value)
                                if not math.isfinite(numeric):
                                    raise ValueError("not finite")
                            except ValueError:
                                invalid_measurements += 1
                                if invalid_measurements <= 20:
                                    errors.append({
                                        "code": "profile.water_level_m.invalid",
                                        "message": "water_level_m must be a finite numeric value.",
                                        "row": row_number,
                                    })
            except (UnicodeDecodeError, csv.Error, OSError) as exc:
                errors.append({"code": "csv.parse", "message": str(exc)})
        checks.append({
            "code": "profile.timestamp.iso8601",
            "status": (
                "failed" if invalid_timestamps else "passed" if timestamp_candidates else "not_run"
            ),
        })
        checks.append({
            "code": "profile.water_level_m.finite_numeric",
            "status": (
                "failed" if invalid_measurements else (
                    "passed" if measurement_index is not None else "not_run"
                )
            ),
        })
    else:
        rows_checked = metrics["row_count"]

    return _report(
        level="schema" if profile else "structural",
        profile=profile,
        errors=errors,
        warnings=warnings,
        checks=checks,
        rows_checked=rows_checked,
        invalid_timestamp_count=invalid_timestamps,
        invalid_measurement_count=invalid_measurements,
        structural_metrics=metrics,
    )


def validate_geojson_payload(payload: Any, data_role: str | None) -> dict[str, Any]:
    """Validate GeoJSON structure and the explicit AOI polygon role constraint."""
    profile = (
        {"id": "area-of-interest-boundary", "version": "1.0.0"}
        if data_role == "aoi_boundary" else None
    )
    errors: list[dict[str, Any]] = []
    checks: list[dict[str, str]] = []
    try:
        metrics = inspect_geojson(payload)
    except ValueError as exc:
        errors.append({"code": "geojson.structure", "message": str(exc)})
        checks.append({"code": "geojson.structure", "status": "failed"})
        return _report(
            level="schema" if profile else "structural",
            profile=profile,
            errors=errors,
            warnings=[],
            checks=checks,
        )

    checks.append({"code": "geojson.structure", "status": "passed"})
    if profile:
        geometry_counts = metrics["geometry_counts"]
        polygon_count = geometry_counts.get("Polygon", 0) + geometry_counts.get("MultiPolygon", 0)
        other_count = sum(
            count for kind, count in geometry_counts.items()
            if kind not in {"Polygon", "MultiPolygon"}
        )
        if polygon_count == 0 or other_count or metrics["null_geometry_count"]:
            errors.append({
                "code": "profile.aoi.polygon_required",
                "message": (
                    "AOI boundary datasets must contain polygon or multipolygon features only."
                ),
            })
        checks.append({
            "code": "profile.aoi.polygon_required",
            "status": "failed" if errors else "passed",
        })

    return _report(
        level="schema" if profile else "structural",
        profile=profile,
        errors=errors,
        warnings=[],
        checks=checks,
        structural_metrics=metrics,
    )
