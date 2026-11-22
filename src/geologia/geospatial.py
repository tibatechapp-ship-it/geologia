"""CRS validation and GeoJSON coordinate transformation via optional pyproj."""
from __future__ import annotations

import math
from typing import Any


def _pyproj():
    try:
        from pyproj import CRS, Transformer
        from pyproj.exceptions import ProjError
    except ImportError as exc:
        raise RuntimeError("CRS tools require the optional 'gis' extra (pyproj)") from exc
    return CRS, Transformer, ProjError


def _is_three_dimensional(crs: Any) -> bool:
    """Detect 3D CRS by axis dimensionality across supported pyproj releases."""
    return len(crs.axis_info) > 2 and not crs.is_compound


def inspect_crs(value: str) -> dict[str, Any]:
    CRS, _, _ = _pyproj()
    try:
        crs = CRS.from_user_input(value)
    except Exception as exc:
        raise ValueError("unrecognized CRS; use an EPSG code or valid CRS definition") from exc
    authority = crs.to_authority()
    return {
        "input": value,
        "canonical": crs.to_string(),
        "name": crs.name,
        "authority": authority[0] if authority else None,
        "code": authority[1] if authority else None,
        "is_geographic": bool(crs.is_geographic),
        "is_projected": bool(crs.is_projected),
        "is_vertical": bool(crs.is_vertical),
        "is_compound": bool(crs.is_compound),
        "is_3d": len(crs.axis_info) >= 3,
        "axis_units": [axis.unit_name for axis in crs.axis_info],
        "axis_directions": [axis.direction for axis in crs.axis_info],
    }


def reproject_geojson(
    payload: dict[str, Any], source: str, target: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    CRS, Transformer, ProjError = _pyproj()
    try:
        source_crs = CRS.from_user_input(source)
        target_crs = CRS.from_user_input(target)
    except Exception as exc:
        raise ValueError("invalid source or target CRS") from exc

    if (
        source_crs.is_vertical
        or target_crs.is_vertical
        or source_crs.is_compound
        or target_crs.is_compound
        or len(source_crs.axis_info) >= 3
        or len(target_crs.axis_info) >= 3
    ):
        raise ValueError(
            "vertical or 3D CRS operations are not supported; "
            "GEOLOGIA currently performs horizontal 2D reprojection only"
        )

    try:
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    except Exception as exc:
        raise ValueError("invalid source or target CRS operation") from exc

    def transform_position(position: Any) -> list[float]:
        if not isinstance(position, list) or len(position) < 2:
            raise ValueError("coordinate position must contain at least x and y")
        x, y = position[0], position[1]
        if (not isinstance(x, (int, float)) or isinstance(x, bool)
                or not isinstance(y, (int, float)) or isinstance(y, bool)
                or not math.isfinite(x) or not math.isfinite(y)):
            raise ValueError("coordinate values must be finite numbers")
        try:
            tx, ty = transformer.transform(float(x), float(y), errcheck=True)
        except ProjError as exc:
            raise ValueError("coordinate transformation failed for one or more positions") from exc
        if not math.isfinite(tx) or not math.isfinite(ty):
            raise ValueError("transformation produced non-finite coordinates")
        return [tx, ty, *position[2:]]

    def transform_coordinates(value: Any) -> Any:
        if not isinstance(value, list) or not value:
            raise ValueError("coordinate arrays must be non-empty")
        if isinstance(value[0], (int, float)) and not isinstance(value[0], bool):
            return transform_position(value)
        return [transform_coordinates(child) for child in value]

    def transform_geometry(geometry: Any) -> Any:
        if geometry is None:
            return None
        if not isinstance(geometry, dict):
            raise ValueError("geometry must be an object or null")
        output = dict(geometry)
        if output.get("type") == "GeometryCollection":
            geometries = output.get("geometries")
            if not isinstance(geometries, list):
                raise ValueError("GeometryCollection.geometries must be an array")
            output["geometries"] = [transform_geometry(item) for item in geometries]
        else:
            if "coordinates" not in output:
                raise ValueError("geometry is missing coordinates")
            output["coordinates"] = transform_coordinates(output["coordinates"])
        output.pop("bbox", None)
        return output

    def transform_object(obj: Any) -> Any:
        if not isinstance(obj, dict):
            raise ValueError("GeoJSON object must be an object")
        output = dict(obj)
        kind = output.get("type")
        if kind == "FeatureCollection":
            features = output.get("features")
            if not isinstance(features, list):
                raise ValueError("FeatureCollection.features must be an array")
            output["features"] = [transform_object(feature) for feature in features]
        elif kind == "Feature":
            output["geometry"] = transform_geometry(output.get("geometry"))
        elif kind in {"Point", "MultiPoint", "LineString", "MultiLineString",
                      "Polygon", "MultiPolygon"}:
            output["coordinates"] = transform_coordinates(output.get("coordinates"))
        elif kind == "GeometryCollection":
            output["geometries"] = [transform_geometry(g) for g in output.get("geometries", [])]
        else:
            raise ValueError("unsupported GeoJSON type for reprojection")
        output.pop("bbox", None)
        output.pop("crs", None)
        return output

    transformed = transform_object(payload)
    import pyproj

    info = {
        "source_crs": source_crs.to_string(),
        "target_crs": target_crs.to_string(),
        "axis_order": "x,y (always_xy)",
        "vertical_coordinate_policy": (
            "third and higher GeoJSON ordinates are preserved unchanged; "
            "no vertical datum conversion is performed"
        ),
        "bbox_policy": "existing bbox values removed because they are not transformed",
        "stored_source_modified": False,
        "operation_description": transformer.description,
        "operation_definition": transformer.definition,
        "operation_accuracy_m": (
            float(transformer.accuracy) if transformer.accuracy >= 0 else None
        ),
        "tool_versions": {"pyproj": pyproj.__version__},
    }
    return transformed, info
