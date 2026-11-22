"""Deterministic GeoJSON and CSV structural inspection; no scientific interpretation."""
import csv
import math
from collections import Counter
from pathlib import Path
from typing import Any

GEOMETRY_TYPES = {
    "Point", "MultiPoint", "LineString", "MultiLineString",
    "Polygon", "MultiPolygon", "GeometryCollection",
}


def _position(value: Any) -> tuple[float, ...]:
    """Validate finite, representable ordinates without accepting bool as an integer."""
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError("coordinate positions require at least x and y")
    ordinates = []
    for ordinate in value:
        if not isinstance(ordinate, (int, float)) or isinstance(ordinate, bool):
            raise ValueError("all coordinate ordinates must be finite numbers")
        try:
            numeric = float(ordinate)
        except (OverflowError, ValueError) as exc:
            raise ValueError("coordinate ordinates must be representable finite numbers") from exc
        if not math.isfinite(numeric):
            raise ValueError("all coordinate ordinates must be finite numbers")
        ordinates.append(numeric)
    return tuple(ordinates)


def inspect_geojson(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("GeoJSON root must be an object")
    kind = payload.get("type")
    if kind == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list):
            raise ValueError("FeatureCollection.features must be an array")
    elif kind == "Feature":
        features = [payload]
    else:
        raise ValueError("inspection requires a Feature or FeatureCollection")

    geometry_counts: Counter[str] = Counter()
    property_keys: set[str] = set()
    coordinate_count = 0
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    null_geometry_count = 0

    def add_position(position: Any) -> None:
        nonlocal coordinate_count, min_x, min_y, max_x, max_y
        ordinates = _position(position)
        min_x = min(min_x, ordinates[0])
        min_y = min(min_y, ordinates[1])
        max_x = max(max_x, ordinates[0])
        max_y = max(max_y, ordinates[1])
        coordinate_count += 1

    def line(value: Any) -> None:
        if not isinstance(value, list) or len(value) < 2:
            raise ValueError("LineString coordinates require at least two positions")
        for position in value:
            add_position(position)

    def ring(value: Any) -> None:
        if not isinstance(value, list) or len(value) < 4:
            raise ValueError("Polygon linear rings require at least four positions")
        first_position = _position(value[0])
        last_position = _position(value[-1])
        if first_position != last_position:
            raise ValueError("Polygon linear rings must be closed in every ordinate")
        for position in value:
            add_position(position)

    def polygon(value: Any) -> None:
        if not isinstance(value, list) or not value:
            raise ValueError("Polygon coordinates require at least one linear ring")
        for item in value:
            ring(item)

    def walk_geometry(geometry: Any) -> None:
        nonlocal null_geometry_count
        if geometry is None:
            null_geometry_count += 1
            return
        if not isinstance(geometry, dict) or geometry.get("type") not in GEOMETRY_TYPES:
            raise ValueError("invalid GeoJSON geometry object")
        geometry_type = geometry["type"]
        geometry_counts[geometry_type] += 1
        coordinates = geometry.get("coordinates")
        if geometry_type == "GeometryCollection":
            geometries = geometry.get("geometries")
            if not isinstance(geometries, list):
                raise ValueError("GeometryCollection.geometries must be an array")
            for child in geometries:
                walk_geometry(child)
        elif geometry_type == "Point":
            add_position(coordinates)
        elif geometry_type == "MultiPoint":
            if not isinstance(coordinates, list) or not coordinates:
                raise ValueError("MultiPoint coordinates must be a non-empty array")
            for position in coordinates:
                add_position(position)
        elif geometry_type == "LineString":
            line(coordinates)
        elif geometry_type == "MultiLineString":
            if not isinstance(coordinates, list) or not coordinates:
                raise ValueError("MultiLineString coordinates must be a non-empty array")
            for item in coordinates:
                line(item)
        elif geometry_type == "Polygon":
            polygon(coordinates)
        elif geometry_type == "MultiPolygon":
            if not isinstance(coordinates, list) or not coordinates:
                raise ValueError("MultiPolygon coordinates must be a non-empty array")
            for item in coordinates:
                polygon(item)

    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("FeatureCollection contains an invalid Feature")
        properties = feature.get("properties")
        if properties is not None:
            if not isinstance(properties, dict):
                raise ValueError("Feature.properties must be an object or null")
            property_keys.update(str(key) for key in properties)
        walk_geometry(feature.get("geometry"))

    bbox = None
    if coordinate_count:
        bbox = [min_x, min_y, max_x, max_y]
    return {
        "validation": "structural_metrics",
        "feature_count": len(features),
        "geometry_counts": dict(sorted(geometry_counts.items())),
        "null_geometry_count": null_geometry_count,
        "coordinate_count": coordinate_count,
        "bbox_xy": bbox,
        "property_keys": sorted(property_keys),
    }


def inspect_csv(path: Path) -> dict[str, Any]:
    """Stream CSV structure metrics without retaining row values or interpreting science."""
    headers: list[str] | None = None
    row_count = 0
    blank_rows = 0
    ragged_rows = 0
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source, strict=True)
            for row in reader:
                if headers is None:
                    if not row or all(not cell.strip() for cell in row):
                        continue
                    headers = [cell.strip() for cell in row]
                    continue
                if not row or all(not cell.strip() for cell in row):
                    blank_rows += 1
                    continue
                row_count += 1
                if len(row) != len(headers):
                    ragged_rows += 1
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("CSV must be valid UTF-8 with well-formed quoting") from exc
    if headers is None:
        raise ValueError("CSV has no non-empty header row")
    counts = Counter(headers)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    return {
        "validation": "structural_metrics",
        "row_count": row_count,
        "column_count": len(headers),
        "headers": headers,
        "duplicate_headers": duplicates,
        "blank_row_count": blank_rows,
        "ragged_row_count": ragged_rows,
    }
