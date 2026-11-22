"""Tests for read-only pinned geoid byte-integrity verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_geoid_grid_integrity import (
    load_manifest,
    verify_directory,
    verify_file,
)

ROOT = Path(__file__).resolve().parents[1]


def test_pinned_manifest_is_well_formed_and_explicitly_not_scientific():
    manifest = load_manifest()
    assert manifest["schema"] == "geologia-geoid-grid-integrity/1"
    assert "not a geoid license approval" in manifest["purpose"]
    assert {item["model_id"] for item in manifest["grids"]} == {"EGM96", "EGM2008"}
    assert all(item["vertical_crs"].startswith("EPSG:") for item in manifest["grids"])


def test_byte_integrity_verifier_accepts_exact_pinned_bytes(tmp_path):
    data = b"fixture bytes for integrity-only verification"
    spec = {
        "model_id": "fixture",
        "file_name": "fixture.tif",
        "expected_size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    path = tmp_path / spec["file_name"]
    path.write_bytes(data)
    result = verify_file(path, spec)
    assert result["status"] == "byte_integrity_verified"
    assert result["actual_sha256"] == spec["sha256"]


def test_byte_integrity_verifier_rejects_hash_mismatch(tmp_path):
    data = b"not the pinned grid"
    path = tmp_path / "fixture.tif"
    path.write_bytes(data)
    spec = {
        "model_id": "fixture",
        "file_name": path.name,
        "expected_size_bytes": len(data),
        "sha256": "0" * 64,
    }
    result = verify_file(path, spec)
    assert result["status"] == "rejected"
    assert "SHA-256" in result["reason"]


def test_byte_integrity_verifier_rejects_size_mismatch_before_hash(tmp_path):
    path = tmp_path / "fixture.tif"
    path.write_bytes(b"short")
    spec = {
        "model_id": "fixture",
        "file_name": path.name,
        "expected_size_bytes": 999,
        "sha256": hashlib.sha256(b"short").hexdigest(),
    }
    result = verify_file(path, spec)
    assert result["status"] == "rejected"
    assert "size" in result["reason"]


def test_directory_report_never_claims_scientific_validation(tmp_path):
    manifest = {
        "schema": "geologia-geoid-grid-integrity/1",
        "grids": [
            {
                "model_id": "fixture",
                "file_name": "fixture.tif",
                "expected_size_bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
            }
        ],
    }
    (tmp_path / "fixture.tif").write_bytes(b"x")
    report = verify_directory(tmp_path, manifest)
    assert report["overall_status"] == "byte_integrity_verified"
    assert report["scientific_validation"] is False
    assert report["vertical_transformation_enabled"] is False
    assert len(report["limitations"]) == 4


def test_manifest_rejects_path_traversal_and_duplicate_names(tmp_path):
    path = tmp_path / "manifest.json"
    base = {
        "schema": "geologia-geoid-grid-integrity/1",
        "grids": [
            {
                "model_id": "x",
                "file_name": "../outside.tif",
                "expected_size_bytes": 1,
                "sha256": "a" * 64,
            }
        ],
    }
    path.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(ValueError, match="simple filenames"):
        load_manifest(path)
