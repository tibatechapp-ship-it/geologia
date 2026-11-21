"""Integrity tests for authoritative geoid reference metadata (not grid transforms)."""
from __future__ import annotations

import json
from pathlib import Path


DATA = Path(__file__).parent / "data"


def test_geoid_model_reference_registry_has_primary_sources_and_explicit_limits():
    registry = json.loads((DATA / "geoid_model_reference.json").read_text())
    sources = json.loads((DATA / "reference_sources.json").read_text())
    source_ids = {item["id"] for item in sources["references"]}

    assert registry["primary_authority"] == "NGA Office of Geomatics"
    models = {item["id"]: item for item in registry["models"]}
    assert models["EGM96"]["grid_spacing"] == "15 arc-minutes"
    assert models["EGM96"]["vertical_crs"] == "EPSG:5773"
    assert models["EGM2008"]["grid_spacing"] == "2.5 arc-minutes"
    assert models["EGM2008"]["vertical_crs"] == "EPSG:3855"
    assert models["EGM2008"]["status"] == "NGA-current-published-model-at-reference-review"

    assert "epsg-5773" in source_ids
    assert "epsg-3855" in source_ids
    assert "nga-egm-downloads" in source_ids
    assert "nga-egm96-grid" in source_ids
    assert "nga-egm2008-grid" in source_ids
    assert "noaa-egm96-concept" in source_ids
    assert "geographiclib-geoid-500k-testdata" in source_ids

    status = registry["status"]
    assert status["grid_bundled"] is False
    assert status["numerical_known_answer_points_bundled"] is False
    assert status["vertical_transformation_implemented"] is False
    assert status["scientific_validation"] is False


def test_geoid_grid_manifest_requires_checksum_conventions_and_operation_metadata():
    registry = json.loads((DATA / "geoid_model_reference.json").read_text())
    required = set(registry["required_grid_manifest_fields"])
    assert {
        "original_sha256",
        "grid_spacing_and_extent",
        "tide_system_and_model_conventions",
        "license_evidence",
        "interpolation_method",
        "source_and_target_crs",
        "operation_area_of_use",
    } <= required

    gates = registry["acceptance_gates"]
    assert any("documented reference dataset" in gate for gate in gates)
    assert any("outside coverage" in gate for gate in gates)
    assert any("reject unavailable" in gate for gate in gates)


def test_geoid_numerical_reference_dataset_is_pinned_and_scientifically_scoped():
    registry = json.loads((DATA / "geoid_model_reference.json").read_text())
    dataset = next(
        item for item in registry["reference_datasets"]
        if item["id"] == "geographiclib-geoid-heights-500k"
    )

    assert dataset["point_count"] == 500000
    assert dataset["columns"] == [
        "latitude_degrees",
        "longitude_degrees",
        "EGM84_geoid_height_m",
        "EGM96_geoid_height_m",
        "EGM2008_geoid_height_m",
    ]
    assert dataset["distribution_sha256"] == (
        "e0b9804694b3eac78ffd0b3df9cffd30a134d72007276e732ff72f9651bc9995"
    )
    assert "NGA harmonic-synthesis programs" in dataset["oracle_method"]
    assert any(
        "Not an independent field survey" in limitation
        for limitation in dataset["limitations"]
    )
    assert registry["status"]["numerical_reference_dataset_identified"] is True
    assert registry["status"]["numerical_known_answer_points_bundled"] is False
