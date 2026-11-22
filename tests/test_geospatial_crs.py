"""CRS metadata and explicit horizontal-only reprojection boundaries."""
import pytest

from geologia.geospatial import inspect_crs, reproject_geojson


@pytest.fixture(autouse=True)
def _requires_pyproj():
    pytest.importorskip("pyproj")


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("EPSG:4979", "EPSG:3857"),
        ("EPSG:4326", "EPSG:3855"),
        ("EPSG:9518", "EPSG:3857"),
    ],
)
def test_vertical_or_3d_crs_operations_are_rejected(source, target):
    payload = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [44.2, 15.3]},
    }
    with pytest.raises(ValueError, match="vertical or 3D CRS operations"):
        reproject_geojson(payload, source, target)


def test_crs_inspection_identifies_vertical_and_3d_crs_dimensions():
    vertical = inspect_crs("EPSG:3855")
    three_dimensional = inspect_crs("EPSG:4979")
    horizontal = inspect_crs("EPSG:4326")

    assert vertical["is_vertical"] is True
    assert vertical["is_3d"] is False
    assert three_dimensional["is_3d"] is True
    assert horizontal["is_3d"] is False
    assert horizontal["is_compound"] is False


def test_horizontal_reprojection_explicitly_preserves_z_without_conversion():
    payload = {
        "type": "Feature",
        "properties": {"site": "A"},
        "geometry": {"type": "Point", "coordinates": [44.2, 15.3, 125.4]},
    }
    transformed, info = reproject_geojson(payload, "EPSG:4326", "EPSG:3857")

    position = transformed["geometry"]["coordinates"]
    assert position[0] != 44.2
    assert position[1] != 15.3
    assert position[2] == 125.4
    assert "preserved unchanged" in info["vertical_coordinate_policy"]
    assert "no vertical datum conversion" in info["vertical_coordinate_policy"]
