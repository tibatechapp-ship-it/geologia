"""GeoJSON numeric and memory-bound regression tests."""
import pytest

from geologia.vector import _position, inspect_geojson


def test_coordinate_boolean_is_not_accepted_as_numeric():
    with pytest.raises(ValueError, match="finite numbers"):
        _position([True, 1])


def test_huge_integer_ordinate_returns_controlled_validation_error():
    with pytest.raises(ValueError, match="representable finite numbers"):
        _position([10**10000, 1])


def test_geojson_bbox_uses_constant_extra_coordinate_memory():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, 0], [1, 2], [3, 4]],
                },
            }
        ],
    }
    report = inspect_geojson(payload)
    assert report["coordinate_count"] == 3
    assert report["bbox_xy"] == [0.0, 0.0, 3.0, 4.0]
