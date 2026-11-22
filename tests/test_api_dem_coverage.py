from fastapi.testclient import TestClient

from geologia.api import app


client = TestClient(app)


def _coverage_payload():
    return {
        "context": {
            "product_version_id": "copernicus-glo30-release-x",
            "pilot_area_id": "yemen-pilot-west-01",
            "reference_source_id": "icesat2-atl08-release-x",
            "primary_stratum_id": "steep-bare",
            "task_profile_id": "regional-reconnaissance-v1",
        },
        "phase": "exploratory",
        "actual_coverage": {
            "availability": "available",
            "value": "coverage://glo30/release-x/yemen-pilot-west-01",
        },
        "coverage_status": "verified",
        "metrics": {
            "valid_independent_locations": 60,
            "polygon_area_km2": 3.0,
            "occupied_1km_cells": 40,
            "eligible_1km_cells": 60,
            "occupied_5km_blocks": 20,
            "eligible_5km_blocks": 30,
            "max_block_observation_fraction": 0.5,
            "primary_cell_observation_counts": {
                "steep_bare": 30,
                "moderate_bare": 30,
            },
        },
    }


def test_dem_coverage_assessment_api_returns_contextual_gates():
    response = client.post("/api/v1/dem/coverage-assessments", json=_coverage_payload())
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "sufficient"
    assert result["context"]["pilot_area_id"] == "yemen-pilot-west-01"
    assert result["valid_independent_locations_per_km2"] == 20
    assert result["occupied_1km_cell_fraction"] == 2 / 3


def test_dem_coverage_api_rejects_analogue_region_as_coverage_evidence():
    payload = _coverage_payload()
    payload["analogue_region"] = "Asir western highlands"
    response = client.post("/api/v1/dem/coverage-assessments", json=payload)
    assert response.status_code == 422


def test_dem_coverage_threshold_endpoint_exposes_frozen_protocol():
    response = client.get("/api/v1/dem/coverage-thresholds")
    assert response.status_code == 200
    thresholds = response.json()
    assert thresholds["protocol_version"] == "1"
    assert thresholds["section_17"]["confirmatory_valid_locations_per_km2"] == 40
    assert thresholds["section_20"]["bootstrap_replicates"] == 2000
