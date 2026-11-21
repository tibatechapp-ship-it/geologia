from geologia.validation import validate_csv_file, validate_geojson_payload


def test_water_level_profile_accepts_explicit_units_and_iso_dates(tmp_path):
    path = tmp_path / "water-levels.csv"
    path.write_text(
        "well_id,timestamp,water_level_m\n"
        "W-01,2026-01-01T00:00:00Z,125.4\n"
        "W-01,2026-01-02,126.1\n",
        encoding="utf-8",
    )
    report = validate_csv_file(path, "water_levels_timeseries")
    assert report["validation_status"] == "passed"
    assert report["validation_level"] == "schema"
    assert report["profile"]["id"] == "groundwater-level-timeseries"
    assert report["rows_checked"] == 2
    assert report["scientific_interpretation"] is False


def test_water_level_profile_rejects_missing_units_invalid_dates_and_nonfinite_values(tmp_path):
    path = tmp_path / "invalid-water-levels.csv"
    path.write_text(
        "well_id,date,water_level\n"
        "W-01,not-a-date,NaN\n",
        encoding="utf-8",
    )
    report = validate_csv_file(path, "water_levels_timeseries")
    codes = {item["code"] for item in report["errors"]}
    assert report["validation_status"] == "failed"
    assert "profile.water_level_m.missing" in codes
    assert "profile.timestamp.invalid" in codes
    assert report["invalid_timestamp_count"] == 1


def test_generic_csv_flags_duplicate_headers_and_ragged_rows(tmp_path):
    path = tmp_path / "generic.csv"
    path.write_text("ID,id,value\nA,1,2\nB,3\n", encoding="utf-8")
    report = validate_csv_file(path, None)
    codes = {item["code"] for item in report["errors"]}
    assert report["validation_status"] == "failed"
    assert "csv.header.duplicate" in codes
    assert "csv.rows.width" in codes


def test_aoi_profile_requires_polygon_features():
    point = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [44.2, 15.3]},
    }
    report = validate_geojson_payload(point, "aoi_boundary")
    assert report["validation_status"] == "failed"
    assert report["profile"]["id"] == "area-of-interest-boundary"
    assert report["errors"][0]["code"] == "profile.aoi.polygon_required"


def test_aoi_profile_accepts_closed_polygon_feature():
    polygon = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [44.0, 15.0], [45.0, 15.0], [45.0, 16.0],
                [44.0, 16.0], [44.0, 15.0],
            ]],
        },
    }
    report = validate_geojson_payload(polygon, "aoi_boundary")
    assert report["validation_status"] == "passed"
    assert report["checks"][-1]["code"] == "profile.aoi.polygon_required"


def test_unprofiled_geojson_reports_structural_level_only():
    point = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [44.2, 15.3]},
    }
    report = validate_geojson_payload(point, None)
    assert report["validation_status"] == "passed"
    assert report["validation_level"] == "structural"
    assert report["profile"] is None
