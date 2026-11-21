"""Real parser-backed format fixtures and known-answer geospatial references."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from geologia.formats import (
    FormatValidationError,
    MAX_FORMAT_FILE_BYTES,
    inspect_geopackage,
    inspect_geotiff,
    inspect_las,
)

ROOT = Path(__file__).parent


def _make_gpkg(path: Path) -> Path:
    geopandas = pytest.importorskip("geopandas")
    pyogrio = pytest.importorskip("pyogrio")
    shapely = pytest.importorskip("shapely")
    frame = geopandas.GeoDataFrame(
        {"sample_id": [1, 2], "lithology": ["A", "B"]},
        geometry=[shapely.Point(1, 1), shapely.Point(2, 2)],
        crs="EPSG:4326",
    )
    pyogrio.write_dataframe(frame, path, driver="GPKG", layer="samples")
    return path


def _make_geotiff(path: Path) -> Path:
    rasterio = pytest.importorskip("rasterio")
    numpy = pytest.importorskip("numpy")
    from rasterio.transform import from_origin

    data = numpy.arange(64 * 64, dtype="float32").reshape((64, 64))
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=64,
        height=64,
        count=1,
        dtype="float32",
        crs="EPSG:32637",
        transform=from_origin(500000, 1500000, 30, 30),
        nodata=-9999,
        tiled=True,
        blockxsize=16,
        blockysize=16,
        compress="deflate",
    ) as dataset:
        dataset.write(data, 1)
        dataset.set_band_unit(1, "m")
        dataset.update_tags(AREA_OR_POINT="Area", vertical_datum="unspecified")
    return path


def _make_las(path: Path) -> Path:
    laspy = pytest.importorskip("laspy")
    numpy = pytest.importorskip("numpy")
    header = laspy.LasHeader(point_format=3, version="1.2")
    pyproj = pytest.importorskip("pyproj")
    header.add_crs(pyproj.CRS.from_epsg(32637))
    header.scales = numpy.array([0.01, 0.01, 0.01])
    header.offsets = numpy.array([500000.0, 1500000.0, 100.0])
    data = laspy.LasData(header)
    data.x = numpy.array([500001.0, 500002.0, 500003.0])
    data.y = numpy.array([1500001.0, 1500002.0, 1500003.0])
    data.z = numpy.array([101.0, 102.0, 103.0])
    data.write(path)
    return path


def test_real_geopackage_layer_metadata(tmp_path):
    path = _make_gpkg(tmp_path / "samples.gpkg")
    report = inspect_geopackage(path)
    assert report["sqlite_integrity"] == "passed"
    assert report["layer_count"] == 1
    layer = report["layers"][0]
    assert layer["name"] == "samples"
    assert layer["feature_count"] == 2
    assert layer["crs"] == "EPSG:4326"
    assert layer["coordinate_units"] == ["degree", "degree"]
    assert layer["vertical_reference"]["vertical_datum_verified"] is False
    assert report["scientific_validation"] is False


def test_corrupt_and_truncated_geopackage_rejected(tmp_path):
    malformed = tmp_path / "malformed.gpkg"
    malformed.write_bytes(b"not a sqlite database")
    with pytest.raises(FormatValidationError):
        inspect_geopackage(malformed)

    pytest.importorskip("pyogrio")
    truncated = _make_gpkg(tmp_path / "truncated.gpkg")
    truncated.write_bytes(truncated.read_bytes()[: max(100, truncated.stat().st_size // 2)])
    with pytest.raises(FormatValidationError):
        inspect_geopackage(truncated)


def test_real_geotiff_metadata_and_bounded_sample(tmp_path):
    path = _make_geotiff(tmp_path / "terrain.tif")
    report = inspect_geotiff(path)
    assert (report["width"], report["height"], report["band_count"]) == (64, 64, 1)
    assert report["crs"] == "EPSG:32637"
    assert report["band_units"] == ["m"]
    assert report["coordinate_units"] == ["metre", "metre"]
    assert report["sample_window"] == {"width": 32, "height": 32}
    assert report["vertical_reference"]["vertical_datum_verified"] is False


def test_truncated_geotiff_rejected(tmp_path):
    path = _make_geotiff(tmp_path / "truncated.tif")
    path.write_bytes(path.read_bytes()[:128])
    with pytest.raises(FormatValidationError):
        inspect_geotiff(path)


def test_real_las_header_and_point_sample(tmp_path):
    path = _make_las(tmp_path / "points.las")
    report = inspect_las(path)
    assert report["point_count"] == 3
    assert report["sampled_point_count"] == 3
    assert report["point_format_id"] == 3
    assert report["scale"] == [0.01, 0.01, 0.01]
    assert report["crs"] == "EPSG:32637"
    assert report["coordinate_units"] == ["metre", "metre"]
    assert report["scientific_validation"] is False


def test_truncated_las_point_records_rejected(tmp_path):
    path = _make_las(tmp_path / "truncated.las")
    with pytest.raises(FormatValidationError, match="extend beyond"):
        path_size = path.stat().st_size
        header = __import__("laspy").open(path).header
        point_end = int(header.offset_to_point_data) + 2 * int(header.point_format.size)
        path.write_bytes(path.read_bytes()[:point_end])
        assert path.stat().st_size < path_size
        inspect_las(path)


def test_sparse_oversized_file_rejected_before_parser(tmp_path):
    path = tmp_path / "oversized.tif"
    with path.open("wb") as stream:
        stream.truncate(MAX_FORMAT_FILE_BYTES + 1)
    with pytest.raises(FormatValidationError, match="size limit"):
        inspect_geotiff(path)


def test_known_answer_crs_transform_and_inverse():
    pyproj = pytest.importorskip("pyproj")
    reference = json.loads((ROOT / "data" / "geospatial_reference.json").read_text())
    item = reference["transform"]
    forward = pyproj.Transformer.from_crs(
        item["source_crs"], item["target_crs"], always_xy=True
    )
    actual = forward.transform(*item["input_xy"])
    assert actual == pytest.approx(
        item["expected_xy"], abs=item["absolute_tolerance_m"]
    )

    inverse_item = reference["inverse"]
    inverse = pyproj.Transformer.from_crs(
        inverse_item["source_crs"], inverse_item["target_crs"], always_xy=True
    )
    actual_inverse = inverse.transform(*inverse_item["input_xy"])
    assert actual_inverse == pytest.approx(
        inverse_item["expected_xy"], abs=inverse_item["absolute_tolerance_degrees"]
    )


def test_api_inspection_endpoint_persists_geotiff_report(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from geologia.api import app

    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(tmp_path / "api-uploads"))
    raster = _make_geotiff(tmp_path / "uploaded.tif")
    project = TestClient(app).post(
        "/api/v1/projects", json={"name": "Raster inspection"}
    ).json()
    upload = TestClient(app).post(
        f"/api/v1/projects/{project['id']}/datasets",
        content=raster.read_bytes(),
        headers={"X-Dataset-Name": "Reference raster", "X-Filename": "reference.tif"},
    )
    assert upload.status_code == 201
    dataset_id = upload.json()["id"]
    inspected = TestClient(app).post(f"/api/v1/datasets/{dataset_id}/inspect")
    assert inspected.status_code == 200
    report = inspected.json()
    assert report["format"] == "geotiff"
    assert report["operation"] == "geotiff_inspection"
    assert report["scientific_interpretation"] is False
    assert report["provenance"]["source_sha256"] == upload.json()["sha256"]
    assert report["provenance"]["parser"] == "rasterio"
    provenance = TestClient(app).get(
        f"/api/v1/datasets/{dataset_id}/provenance"
    )
    assert provenance.status_code == 200
    audit = provenance.json()
    assert audit["chain_integrity"] == "verified"
    assert [event["event_type"] for event in audit["events"]] == [
        "dataset_ingested", "dataset_inspected"
    ]
    from geologia import store

    with store.connect() as connection:
        connection.execute(
            "UPDATE provenance_events SET payload_json='not-json' WHERE dataset_id=? "
            "AND event_type='dataset_inspected'",
            (dataset_id,),
        )
    tampered = TestClient(app).get(
        f"/api/v1/datasets/{dataset_id}/provenance"
    ).json()
    assert tampered["chain_integrity"] == "failed"


def test_geopackage_missing_metadata_tables_rejected(tmp_path):
    import sqlite3

    path = tmp_path / "fake.gpkg"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
    with pytest.raises(FormatValidationError, match="metadata tables"):
        inspect_geopackage(path)


def test_geotiff_declared_pixel_bomb_rejected_before_sample(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    path = tmp_path / "oversized-dimensions.tif"
    with rasterio.open(
        path, "w", driver="GTiff", width=100001, height=1000, count=1,
        dtype="uint8", transform=from_origin(0, 0, 1, 1), tiled=True,
        blockxsize=256, blockysize=256, SPARSE_OK="TRUE",
    ):
        pass
    with pytest.raises(FormatValidationError, match="dimensions exceed"):
        inspect_geotiff(path)


def test_las_forged_point_count_rejected(tmp_path):
    import struct

    path = _make_las(tmp_path / "forged-count.las")
    content = bytearray(path.read_bytes())
    # LAS 1.2 legacy point count is a uint32 at byte offset 107.
    content[107:111] = struct.pack("<I", 0xFFFFFFFF)
    path.write_bytes(content)
    with pytest.raises(FormatValidationError, match="extend beyond"):
        inspect_las(path)

def test_geojson_reference_dataset_matches_known_projection_results():
    pytest.importorskip("pyproj")
    from geologia.geospatial import reproject_geojson

    source = json.loads((ROOT / "data" / "reference_points.geojson").read_text())
    reference = json.loads((ROOT / "data" / "reference_projection.json").read_text())
    transformed, info = reproject_geojson(
        source, reference["source_crs"], reference["target_crs"]
    )
    expected = {
        item["reference_id"]: item["expected_xy"] for item in reference["points"]
    }
    for feature in transformed["features"]:
        reference_id = feature["properties"]["reference_id"]
        assert feature["geometry"]["coordinates"] == pytest.approx(
            expected[reference_id], abs=reference["absolute_tolerance_m"]
        )
    assert info["axis_order"] == "x,y (always_xy)"
    assert info["tool_versions"]["pyproj"]
