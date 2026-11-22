"""Integrity and scope tests for the geoid model reference registry."""
import json
from pathlib import Path


DATA = Path(__file__).parent / "data"


def test_geoid_models_are_mapped_to_official_vertical_crs_and_grid_resolution():
    registry = json.loads((DATA / "geoid_model_reference.json").read_text(encoding="utf-8"))
    models = {model["id"]: model for model in registry["models"]}

    assert registry["primary_authority"] == "NGA Office of Geomatics"
    assert models["EGM96"]["grid_spacing"] == "15 arc-minutes"
    assert models["EGM96"]["vertical_crs"] == "EPSG:5773"
    assert models["EGM2008"]["grid_spacing"] == "2.5 arc-minutes"
    assert models["EGM2008"]["vertical_crs"] == "EPSG:3855"
    assert models["EGM96"]["status"] == "legacy"


def test_geoid_reference_registry_preserves_unimplemented_validation_boundary():
    registry = json.loads((DATA / "geoid_model_reference.json").read_text(encoding="utf-8"))
    status = registry["status"]

    assert status["grid_bundled"] is False
    assert status["numerical_known_answer_points_bundled"] is False
    assert status["vertical_transformation_implemented"] is False
    assert status["scientific_validation"] is False
    assert status["reference_dataset_download_verified"] is False

    required = set(registry["required_grid_manifest_fields"])
    assert {
        "original_sha256",
        "grid_format_dimensions_spacing_and_extent",
        "tide_system_and_model_conventions",
        "license_evidence",
        "interpolation_method",
        "source_and_target_crs",
        "operation_area_of_use",
    } <= required
    assert any("outside coverage" in gate for gate in registry["acceptance_gates"])
    assert any("silently fall back" in gate for gate in registry["acceptance_gates"])


def test_geographiclib_reference_digest_is_pinned_but_not_claimed_verified():
    registry = json.loads((DATA / "geoid_model_reference.json").read_text(encoding="utf-8"))
    reference = registry["reference_dataset"]

    assert reference["point_count"] == 500000
    assert len(reference["published_sha256"]) == 64
    assert reference["published_sha256"] == (
        "e0b9804694b3eac78ffd0b3df9cffd30a134d72007276e732ff72f9651bc9995"
    )
    assert registry["status"]["reference_dataset_download_verified"] is False
    assert any("Not field-survey truth" in item for item in reference["limitations"])


def test_reference_sources_include_primary_authority_and_cross_implementation_data():
    sources = json.loads((DATA / "reference_sources.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in sources["references"]}

    assert "NGA" in by_id["nga-egm-portal"]["publisher"]
    assert by_id["epsg-5773"]["code"] == 5773
    assert by_id["epsg-3855"]["code"] == 3855
    assert "sha256_published" in by_id["geographiclib-geoid-500k"]
