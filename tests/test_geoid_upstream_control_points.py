"""Provenance and consistency checks for imported upstream geoid controls."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "src/geologia/data/geoid_upstream_control_points.json"
PINNED = ROOT / "src/geologia/data/geoid_grid_integrity.json"


def test_upstream_control_points_are_provenance_pinned_and_match_grid_hashes():
    controls = json.loads(CONTROLS.read_text(encoding="utf-8"))
    pinned = json.loads(PINNED.read_text(encoding="utf-8"))
    assert controls["schema"] == "geologia-upstream-geoid-control-points/1"
    provenance = controls["provenance"]
    assert provenance["repository"] == "tibatechapp-ship-it/Ali-Algomori"
    assert provenance["commit"] == "ca72da2599f6664fe8548047eeec593aab955682"
    assert provenance["source_path"].endswith("geoid_golden_nodes.json")
    assert len(provenance["source_git_blob_sha"]) == 40
    pinned_by_model = {item["model_id"]: item for item in pinned["grids"]}
    control_by_model = {item["model_id"]: item for item in controls["grids"]}
    assert set(control_by_model) == {"EGM96", "EGM2008"}
    assert set(control_by_model) == set(pinned_by_model)
    for model, control in control_by_model.items():
        assert control["grid_sha256"] == pinned_by_model[model]["sha256"]
        assert len(control["nodes"]) == 25
        for node in control["nodes"]:
            assert math.isfinite(node["lat"])
            assert math.isfinite(node["lon"])
            assert math.isfinite(node["undulation_m"])
            assert -90.0 <= node["lat"] <= 90.0
            assert -180.0 <= node["lon"] < 180.0
            assert -130.0 <= node["undulation_m"] <= 90.0


def test_upstream_control_points_are_not_scientific_authorization():
    controls = json.loads(CONTROLS.read_text(encoding="utf-8"))
    note = controls["provenance"]["interpretation"].lower()
    assert "not independently recomputed" in note
    assert "not a vertical transformation authorization" in note
