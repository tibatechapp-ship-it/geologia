"""Strict JSON parsing regressions for uploaded GeoJSON."""
import pytest

from geologia.api import _read_json


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"type":"Feature","type":"FeatureCollection"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        _read_json(path)


def test_duplicate_keys_in_nested_objects_are_rejected(tmp_path):
    path = tmp_path / "nested-duplicate.json"
    path.write_text('{"properties":{"id":1,"id":2}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        _read_json(path)


def test_excessive_json_nesting_returns_controlled_error(tmp_path):
    path = tmp_path / "deep.json"
    path.write_text("[" * 1500 + "0" + "]" * 1500, encoding="utf-8")
    with pytest.raises(ValueError, match="nesting exceeds"):
        _read_json(path)
