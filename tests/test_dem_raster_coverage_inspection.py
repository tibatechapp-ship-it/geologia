from pathlib import Path

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
from rasterio.transform import from_origin

from geologia.formats import FormatValidationError, inspect_dem_aoi_coverage


def _write_dem(path: Path, *, crs="EPSG:32638"):
    values = np.ones((10, 10), dtype=np.uint8)
    values[0, 0] = 0
    values[1, 1] = 0
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype="uint8",
        crs=crs,
        transform=from_origin(500000, 1700000, 30, 30),
        nodata=0,
    ) as dataset:
        dataset.write(values, 1)


def _aoi(left=500000, bottom=1699700, right=500300, top=1700000):
    return {
        "type": "Polygon",
        "coordinates": [[
            [left, bottom],
            [right, bottom],
            [right, top],
            [left, top],
            [left, bottom],
        ]],
    }


def test_dem_aoi_inspection_measures_extent_and_valid_mask(tmp_path):
    dem = tmp_path / "dem.tif"
    _write_dem(dem)

    report = inspect_dem_aoi_coverage(dem, _aoi(), "EPSG:32638")

    assert report["inspection_status"] == "measured"
    assert report["coverage_status"] == "partial_valid_data_within_raster_extent"
    assert report["raster_extent_intersection_fraction_of_aoi"] == pytest.approx(1.0)
    assert report["aoi_pixel_centres_inside_raster"] == 100
    assert report["valid_aoi_pixel_centres"] == 98
    assert report["valid_pixel_fraction_within_raster_extent"] == pytest.approx(0.98)
    assert report["valid_pixel_coverage_fraction_estimate"] == pytest.approx(0.98)
    assert report["dem_accuracy_validated"] is False
    assert report["vertical_datum_verified"] is False


def test_dem_aoi_inspection_reports_partial_extent_without_inventing_pass(tmp_path):
    dem = tmp_path / "dem.tif"
    _write_dem(dem)

    report = inspect_dem_aoi_coverage(
        dem,
        _aoi(left=499850, right=500300),
        "EPSG:32638",
    )

    assert report["raster_extent_intersection_fraction_of_aoi"] == pytest.approx(2 / 3)
    assert report["coverage_status"] == "partial_valid_data_within_raster_extent"


def test_dem_aoi_inspection_reports_no_extent_overlap(tmp_path):
    dem = tmp_path / "dem.tif"
    _write_dem(dem)

    report = inspect_dem_aoi_coverage(
        dem,
        _aoi(left=501000, right=501300),
        "EPSG:32638",
    )

    assert report["coverage_status"] == "no_extent_overlap"
    assert report["aoi_pixel_centres_inside_raster"] == 0
    assert report["valid_aoi_pixel_centres"] == 0
    assert report["raster_extent_intersection_fraction_of_aoi"] == 0


def test_dem_aoi_inspection_requires_projected_raster_crs(tmp_path):
    dem = tmp_path / "geographic.tif"
    _write_dem(dem, crs="EPSG:4326")

    with pytest.raises(FormatValidationError, match="projected horizontal CRS"):
        inspect_dem_aoi_coverage(dem, _aoi(), "EPSG:32638")


def test_dem_aoi_inspection_rejects_invalid_aoi_geometry(tmp_path):
    dem = tmp_path / "dem.tif"
    _write_dem(dem)
    invalid = {"type": "Point", "coordinates": [500000, 1700000]}

    with pytest.raises(FormatValidationError, match="Polygon or MultiPolygon"):
        inspect_dem_aoi_coverage(dem, invalid, "EPSG:32638")


def test_dem_aoi_inspection_marks_full_only_when_extent_and_all_centres_are_valid(tmp_path):
    dem = tmp_path / "full-dem.tif"
    values = np.ones((10, 10), dtype=np.uint8)
    with rasterio.open(
        dem,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype="uint8",
        crs="EPSG:32638",
        transform=from_origin(500000, 1700000, 30, 30),
        nodata=0,
    ) as dataset:
        dataset.write(values, 1)

    report = inspect_dem_aoi_coverage(dem, _aoi(), "EPSG:32638")

    assert report["coverage_status"] == "full_aoi_extent_and_valid_pixels"
    assert report["aoi_fully_within_raster_extent"] is True
    assert report["all_aoi_pixel_centres_valid"] is True
