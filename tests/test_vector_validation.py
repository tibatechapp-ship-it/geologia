import pytest

from geologia.vector import inspect_geojson


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Point", "coordinates": [[1, 2]]},
        {"type": "MultiPoint", "coordinates": [1, 2]},
        {"type": "LineString", "coordinates": [[1, 2]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
        {"type": "Point", "coordinates": [1, 2, float("nan")]},
        {"type": "Point", "coordinates": [1, 2, "bad"]},
    ],
)
def test_geojson_rejects_invalid_geometry_coordinate_structure(geometry):
    payload = {
        "type": "Feature",
        "properties": {},
        "geometry": geometry,
    }
    with pytest.raises(ValueError):
        inspect_geojson(payload)


def test_geojson_accepts_valid_polygon_and_three_dimensional_position():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [0, 0, 10], [1, 0, 11], [1, 1, 12],
                        [0, 1, 13], [0, 0, 10],
                    ]],
                },
            }
        ],
    }
    report = inspect_geojson(payload)
    assert report["coordinate_count"] == 5
    assert report["bbox_xy"] == [0.0, 0.0, 1.0, 1.0]
