"""Independent EPSG:3857 equation checks adapted from Ali-Algomori.

Source: tibatechapp-ship-it/Ali-Algomori
- src/geologia/data_layer/transforms_math.py
- src/geologia/data/reference/transformations.json

Owner-authorized reuse (2026-11-22); see GEOLOGIA issue #98.
The equation proof is pure math and does not require pyproj. This module does
not validate geological meaning, CRS suitability, datum shifts, vertical
coordinates, or the accuracy of input coordinates.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

R_3857 = 6378137.0
LAT_LIMIT_DEG = math.degrees(math.atan(math.sinh(math.pi)))
EQUATION_SOURCE = "epsg_method_1024_equations"
_REFERENCE_PATH = Path(__file__).resolve().parent / "data" / "epsg3857_equation_points.json"


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def pseudo_mercator(lon_deg: float, lat_deg: float) -> tuple[float, float]:
    """Forward EPSG method 1024 within the EPSG:3857 coordinate domain."""
    lon = _finite_number(lon_deg, "longitude")
    lat = _finite_number(lat_deg, "latitude")
    if not -180.0 <= lon <= 180.0:
        raise ValueError("longitude outside EPSG:3857 domain")
    if not -LAT_LIMIT_DEG <= lat <= LAT_LIMIT_DEG:
        raise ValueError("latitude outside EPSG:3857 domain")
    lam = math.radians(lon)
    phi = math.radians(lat)
    return R_3857 * lam, R_3857 * math.log(math.tan(math.pi / 4.0 + phi / 2.0))


def inverse_pseudo_mercator(x: float, y: float) -> tuple[float, float]:
    """Inverse EPSG method 1024 within the EPSG:3857 world extent."""
    easting = _finite_number(x, "easting")
    northing = _finite_number(y, "northing")
    extent = R_3857 * math.pi
    if abs(easting) > extent or abs(northing) > extent:
        raise ValueError("coordinate outside EPSG:3857 domain")
    lon = math.degrees(easting / R_3857)
    lat = math.degrees(2.0 * math.atan(math.exp(northing / R_3857)) - math.pi / 2.0)
    return lon, lat


def load_equation_points() -> dict[str, Any]:
    """Load the pinned equation-derived control points packaged with GEOLOGIA."""
    return json.loads(_REFERENCE_PATH.read_text(encoding="utf-8"))


def reference_fingerprint() -> str:
    """SHA-256 of the packaged control-point file for provenance records."""
    return hashlib.sha256(_REFERENCE_PATH.read_bytes()).hexdigest()


def verify_equation_points(
    reference: dict[str, Any] | None = None,
    *,
    crosscheck_engine: bool = True,
) -> dict[str, Any]:
    """Re-derive frozen values; optionally compare the installed pyproj engine.

    Missing pyproj is reported as unverifiable for the engine check while the
    pure-equation proof still runs. Equation/reference mismatches are errors.
    """
    ref = reference if reference is not None else load_equation_points()
    targets = [
        point for point in ref.get("transformations", [])
        if point.get("source") == EQUATION_SOURCE
    ]
    findings: list[dict[str, str]] = []
    checked = 0
    engine_checked = 0
    engine_name: str | None = None
    engine_available = False

    if crosscheck_engine:
        try:
            import pyproj
            engine_name = f"pyproj {pyproj.__version__}"
            engine_available = True
        except ImportError:
            findings.append({
                "code": "XFORM_ENGINE_ABSENT",
                "severity": "warning",
                "message": "pyproj absent; engine cross-check is unverifiable, not passed",
            })

    for point in targets:
        name = str(point.get("name", "unnamed"))
        try:
            if point.get("kind") == "roundtrip":
                actual_x, actual_y = inverse_pseudo_mercator(point["x"], point["y"])
            else:
                actual_x, actual_y = pseudo_mercator(point["x"], point["y"])
            expected_x = _finite_number(point["expected_x"], "expected_x")
            expected_y = _finite_number(point["expected_y"], "expected_y")
            tolerance = _finite_number(point["tol"], "tolerance")
            if tolerance < 0:
                raise ValueError("tolerance must be non-negative")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            findings.append({
                "code": "XFORM_MATH_MISMATCH",
                "severity": "error",
                "message": f"{name}: equation or reference validation failed: {exc}",
            })
            continue

        error = max(abs(actual_x - expected_x), abs(actual_y - expected_y))
        if error > tolerance:
            findings.append({
                "code": "XFORM_MATH_MISMATCH",
                "severity": "error",
                "message": (
                    f"{name}: frozen value differs from EPSG method 1024 equations "
                    f"by {error:.3e}{point.get('tol_unit', '')} "
                    f"(tolerance {tolerance}); reference not trusted"
                ),
            })
            continue

        checked += 1
        findings.append({
            "code": "XFORM_MATH_OK",
            "severity": "info",
            "message": (
                f"{name}: frozen value reproduced from published equations "
                f"(max error {error:.3e}{point.get('tol_unit', '')})"
            ),
        })

        if engine_available:
            try:
                from pyproj import Transformer
                transformer = Transformer.from_crs(
                    point["from_crs"], point["to_crs"], always_xy=True
                )
                engine_x, engine_y = transformer.transform(
                    point["x"], point["y"], errcheck=True
                )
                engine_error = max(abs(engine_x - actual_x), abs(engine_y - actual_y))
            except Exception as exc:
                findings.append({
                    "code": "XFORM_CROSS_MISMATCH",
                    "severity": "error",
                    "message": f"{name}: pyproj cross-check failed: {type(exc).__name__}: {exc}",
                })
                continue
            if not math.isfinite(engine_error) or engine_error > tolerance:
                findings.append({
                    "code": "XFORM_CROSS_MISMATCH",
                    "severity": "error",
                    "message": (
                        f"{name}: {engine_name} disagrees with equations by "
                        f"{engine_error:.3e}{point.get('tol_unit', '')}"
                    ),
                })
            else:
                engine_checked += 1
                findings.append({
                    "code": "XFORM_CROSS_OK",
                    "severity": "info",
                    "message": f"{name}: {engine_name} agrees with equation result",
                })

    equation_ok = bool(targets) and checked == len(targets) and not any(
        item["severity"] == "error" and item["code"] == "XFORM_MATH_MISMATCH"
        for item in findings
    )
    cross_errors = any(
        item["severity"] == "error" and item["code"] == "XFORM_CROSS_MISMATCH"
        for item in findings
    )
    if not targets:
        findings.append({
            "code": "XFORM_MATH_NO_POINTS",
            "severity": "warning",
            "message": "No control points tagged for EPSG method 1024 were found",
        })

    engine_status = (
        "not_requested" if not crosscheck_engine else
        "unverifiable" if not engine_available else
        "failed" if cross_errors else
        "passed" if engine_checked == len(targets) and bool(targets) else "incomplete"
    )
    return {
        "ok": equation_ok and not cross_errors,
        "method": "EPSG:3857 method 1024",
        "equation_points_checked": checked,
        "equation_points_total": len(targets),
        "engine_crosscheck_status": engine_status,
        "engine": engine_name,
        "reference_sha256": reference_fingerprint() if reference is None else None,
        "findings": findings,
        "scope": (
            "Equation/control-point verification only; not CRS selection, datum "
            "transformation, vertical conversion, coordinate accuracy, or geology."
        ),
    }
