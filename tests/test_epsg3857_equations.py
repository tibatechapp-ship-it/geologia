import copy
import math
import sys

import pytest

from geologia.epsg3857_equations import (
    EQUATION_SOURCE,
    LAT_LIMIT_DEG,
    R_3857,
    inverse_pseudo_mercator,
    load_equation_points,
    pseudo_mercator,
    reference_fingerprint,
    verify_equation_points,
)


def test_forward_x_is_radius_times_longitude():
    for lon in (-180.0, -37.5, 0.0, 46.6753, 180.0):
        x, _ = pseudo_mercator(lon, 0.0)
        assert x == R_3857 * math.radians(lon)


def test_equator_and_north_south_symmetry_are_numerically_stable():
    assert pseudo_mercator(15.0, 0.0)[1] == pytest.approx(0.0, abs=1e-8)
    for lat in (1e-6, 10.0, 24.7136, 84.9):
        y_plus = pseudo_mercator(0.0, lat)[1]
        y_minus = pseudo_mercator(0.0, -lat)[1]
        assert y_minus == pytest.approx(-y_plus, rel=1e-7, abs=0)


def test_epsg_world_extent_is_derived_from_equations():
    _, y_max = pseudo_mercator(0.0, LAT_LIMIT_DEG)
    assert y_max == pytest.approx(R_3857 * math.pi, abs=1e-6)
    assert LAT_LIMIT_DEG == pytest.approx(
        math.degrees(math.atan(math.sinh(math.pi))), abs=1e-12
    )
    assert 85.05 < LAT_LIMIT_DEG < 85.06


def test_forward_inverse_roundtrip_closes():
    for lon, lat in ((46.6753, 24.7136), (-9.0, 38.0), (110.0, -45.0)):
        x, y = pseudo_mercator(lon, lat)
        actual_lon, actual_lat = inverse_pseudo_mercator(x, y)
        assert abs(actual_lon - lon) < 1e-12
        assert abs(actual_lat - lat) < 1e-12


@pytest.mark.parametrize(
    ("lon", "lat"),
    [(181.0, 0.0), (-181.0, 0.0), (0.0, 85.1), (0.0, -85.1)],
)
def test_forward_refuses_coordinates_outside_epsg_domain(lon, lat):
    with pytest.raises(ValueError, match="EPSG:3857 domain"):
        pseudo_mercator(lon, lat)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "44.2"])
def test_forward_refuses_non_finite_or_non_numeric_values(value):
    with pytest.raises(ValueError):
        pseudo_mercator(value, 0.0)


def test_inverse_refuses_coordinates_outside_world_extent():
    extent = R_3857 * math.pi
    with pytest.raises(ValueError, match="EPSG:3857 domain"):
        inverse_pseudo_mercator(extent + 1.0, 0.0)
    with pytest.raises(ValueError, match="EPSG:3857 domain"):
        inverse_pseudo_mercator(0.0, -extent - 1.0)


def test_frozen_equation_points_are_reproduced():
    reference = load_equation_points()
    points = [p for p in reference["transformations"] if p["source"] == EQUATION_SOURCE]
    assert len(points) == 4
    result = verify_equation_points(reference, crosscheck_engine=False)
    assert result["ok"] is True, result["findings"]
    assert result["equation_points_checked"] == result["equation_points_total"] == 4
    assert result["engine_crosscheck_status"] == "not_requested"
    assert reference_fingerprint() and len(reference_fingerprint()) == 64


def test_corrupted_frozen_reference_is_a_hard_error():
    reference = copy.deepcopy(load_equation_points())
    target = next(p for p in reference["transformations"] if p["source"] == EQUATION_SOURCE)
    target["expected_y"] += 1.0
    result = verify_equation_points(reference, crosscheck_engine=False)
    assert result["ok"] is False
    assert any(item["code"] == "XFORM_MATH_MISMATCH" for item in result["findings"])


def test_equation_proof_remains_available_without_pyproj(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyproj", None)
    result = verify_equation_points()
    assert result["ok"] is True, result["findings"]
    assert result["equation_points_checked"] == 4
    assert result["engine_crosscheck_status"] == "unverifiable"
    assert any(item["code"] == "XFORM_ENGINE_ABSENT" for item in result["findings"])


def test_engine_crosscheck_is_explicit_when_available():
    try:
        import pyproj  # noqa: F401
    except ImportError:
        pytest.skip("pyproj is not installed")
    result = verify_equation_points()
    assert result["ok"] is True, result["findings"]
    assert result["engine_crosscheck_status"] == "passed"
