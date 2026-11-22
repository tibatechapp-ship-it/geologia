from pathlib import Path

import pytest

from geologia.formats import FormatValidationError, inspect_dem_tile_collection_coverage

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
from_origin = pytest.importorskip("rasterio.transform").from_origin


def _write_tile(path: Path, left: float, *, nodata_cell=None):
    values = np.ones((10, 10), dtype=np.uint8)
    if nodata_cell is not None:
        values[nodata_cell] = 0
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype="uint8",
        crs="EPSG:32638",
        transform=from_origin(left, 1700000, 30, 30),
        nodata=0,
    ) as dataset:
        dataset.write(values, 1)


def _aoi(left: float, right: float):
    return {
        "type": "Polygon",
        "coordinates": [[
            [left, 1699700],
            [right, 1699700],
            [right, 1700000],
            [left, 1700000],
            [left, 1699700],
        ]],
    }


def test_adjacent_dem_tiles_cover_aoi_without_double_counting(tmp_path):
    first, second = tmp_path / "tile-a.tif", tmp_path / "tile-b.tif"
    _write_tile(first, 500000)
    _write_tile(second, 500300)

    report = inspect_dem_tile_collection_coverage(
        [first, second], _aoi(500000, 500600), "EPSG:32638"
    )

    assert report["coverage_status"] == "full_aoi_extent_and_valid_pixels"
    assert report["aoi_fully_within_raster_extent"] is True
    assert report["aoi_pixel_centres_in_mosaic"] == 200
    assert report["valid_aoi_pixel_centres"] == 200
    assert report["overlap_area_m2"] == pytest.approx(0, abs=0.01)
    assert report["uncovered_aoi_area_m2"] == pytest.approx(0, abs=0.01)
    assert report["tile_count"] == 2
    assert len(report["tiles"][0]["sha256"]) == 64


def test_tile_gap_is_reported_and_valid_centres_are_not_overstated(tmp_path):
    first, second = tmp_path / "tile-a.tif", tmp_path / "tile-c.tif"
    _write_tile(first, 500000)
    _write_tile(second, 500600)

    report = inspect_dem_tile_collection_coverage(
        [first, second], _aoi(500000, 500900), "EPSG:32638"
    )

    assert report["aoi_fully_within_raster_extent"] is False
    assert report["uncovered_aoi_area_m2"] > 0
    assert report["aoi_pixel_centres_in_mosaic"] == 300
    assert report["valid_aoi_pixel_centres"] == 200
    assert report["coverage_status"] == "partial_valid_data_within_raster_extent"


def test_overlapping_tiles_are_union_counted_once(tmp_path):
    first, second = tmp_path / "tile-a.tif", tmp_path / "tile-overlap.tif"
    _write_tile(first, 500000)
    _write_tile(second, 500150)

    report = inspect_dem_tile_collection_coverage(
        [first, second], _aoi(500000, 500450), "EPSG:32638"
    )

    assert report["overlap_area_m2"] > 0
    assert report["aoi_pixel_centres_in_mosaic"] == 150
    assert report["valid_aoi_pixel_centres"] == 150
    assert report["valid_pixel_fraction_within_mosaic"] == 1.0


def test_tile_collection_rejects_non_aligned_grid_origins(tmp_path):
    first, second = tmp_path / "tile-a.tif", tmp_path / "tile-offset.tif"
    _write_tile(first, 500000)
    _write_tile(second, 500015)

    with pytest.raises(FormatValidationError, match="not aligned"):
        inspect_dem_tile_collection_coverage(
            [first, second], _aoi(500000, 500315), "EPSG:32638"
        )


def test_hgt_tile_collection_coverage_if_driver_is_available(tmp_path):
    path = tmp_path / "N15E042.hgt"
    values = np.full((1201, 1201), 100, dtype=">i2")
    path.write_bytes(values.tobytes())
    try:
        with rasterio.open(path) as dataset:
            if dataset.crs is None or not dataset.crs.is_geographic:
                pytest.skip("installed GDAL HGT driver does not expose geographic CRS")
    except rasterio.errors.RasterioIOError:
        pytest.skip("installed GDAL does not support SRTMHGT")
    aoi = {
        "type": "Polygon",
        "coordinates": [[
            [42.1, 15.1],
            [42.2, 15.1],
            [42.2, 15.2],
            [42.1, 15.2],
            [42.1, 15.1],
        ]],
    }

    report = inspect_dem_tile_collection_coverage([path], aoi, "EPSG:4326")

    assert report["tile_count"] == 1
    assert report["mosaic_crs"] == "EPSG:4326"
    assert report["aoi_fully_within_raster_extent"] is True
    assert report["valid_aoi_pixel_centres"] > 0
