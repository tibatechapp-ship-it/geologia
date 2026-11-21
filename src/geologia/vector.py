"""Deterministic GeoJSON structural inspection; no scientific interpretation."""
import math
from collections import Counter
from typing import Any

GEOMETRY_TYPES = {
    "Point", "MultiPoint", "LineString", "MultiLineString",
    "Polygon", "MultiPolygon", "GeometryCollection",
}


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
    xs: list[float] = []
    ys: list[float] = []
    null_geometry_count = 0

    def walk_coordinates(value: Any) -> None:
        nonlocal coordinate_count
        if not isinstance(value, list) or not value:
            raise ValueError("coordinates must be non-empty arrays")
        if isinstance(value[0], (int, float)) and not isinstance(value[0], bool):
            if len(value) < 2:
                raise ValueError("coordinate positions require at least x and y")
            x, y = value[0], value[1]
            if (not isinstance(x, (int, float)) or isinstance(x, bool)
                    or not isinstance(y, (int, float)) or isinstance(y, bool)
                    or not math.isfinite(x) or not math.isfinite(y)):
                raise ValueError("coordinates must be finite numbers")
            xs.append(float(x))
            ys.append(float(y))
            coordinate_count += 1
            return
        for child in value:
            walk_coordinates(child)

    def walk_geometry(geometry: Any) -> None:
        nonlocal null_geometry_count
        if geometry is None:
            null_geometry_count += 1
            return
        if not isinstance(geometry, dict) or geometry.get("type") not in GEOMETRY_TYPES:
            raise ValueError("invalid GeoJSON geometry object")
        geometry_type = geometry["type"]
        geometry_counts[geometry_type] += 1
        if geometry_type == "GeometryCollection":
            geometries = geometry.get("geometries")
            if not isinstance(geometries, list):
                raise ValueError("GeometryCollection.geometries must be an array")
            for child in geometries:
                walk_geometry(child)
        else:
            if "coordinates" not in geometry:
                raise ValueError("geometry is missing coordinates")
            walk_coordinates(geometry["coordinates"])

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
    if xs:
        bbox = [min(xs), min(ys), max(xs), max(ys)]
    return {
        "validation": "structural_metrics",
        "feature_count": len(features),
        "geometry_counts": dict(sorted(geometry_counts.items())),
        "null_geometry_count": null_geometry_count,
        "coordinate_count": coordinate_count,
        "bbox_xy": bbox,
        "property_keys": sorted(property_keys),
    }
