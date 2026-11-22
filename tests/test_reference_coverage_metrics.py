from datetime import date

import pytest

from geologia.dem_readiness.reference_coverage import (
    IndependenceReviewAttestation,
    compute_reference_coverage_metrics,
)
from geologia.formats import FormatValidationError


def _aoi():
    return {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [0, 0],
                [10000, 0],
                [10000, 10000],
                [0, 10000],
                [0, 0],
            ]],
        },
    }


def _feature(index, x, y, *, site=None, observed_at=None, quality="accepted", status="independent"):
    return {
        "type": "Feature",
        "properties": {
            "observation_id": f"obs-{index}",
            "site_id": site or f"site-{index}",
            "source_id": "reference-source-1",
            "observed_at": observed_at or "2024-01-01T00:00:00Z",
            "primary_stratum_id": "steep-bare",
            "independence_group_id": "reviewed-group-1",
            "independence_status": status,
            "quality_flag": quality,
            "vertical_datum": "EGM2008",
            "height_type": "orthometric",
            "reference_method": "static GNSS",
            "horizontal_uncertainty_m": 0.02,
            "vertical_uncertainty_m": 0.03,
            "uncertainty_confidence_level": 0.95,
            "horizontal_reference_frame": "ITRF2014",
            "coordinate_epoch": "2020.0",
            "geoid_model": "EGM2008",
        },
        "geometry": {"type": "Point", "coordinates": [x, y]},
    }


def _review(**overrides):
    values = {
        "reference": "review://independence/1",
        "reviewer": "reviewer-1",
        "reviewed_at": "2026-11-22T02:00:00Z",
        "definition": "Unique sites reviewed for source lineage and spatial independence.",
        "source_lineage_reviewed": True,
        "spatial_independence_reviewed": True,
        "source_dependence_conflicts": False,
    }
    values.update(overrides)
    return IndependenceReviewAttestation.model_validate(values)


def _compute(features, review=None, primary_stratum_ids=None):
    pytest.importorskip("pyproj")
    pytest.importorskip("shapely")
    return compute_reference_coverage_metrics(
        {"type": "FeatureCollection", "features": features},
        _aoi(),
        reference_crs="EPSG:6933",
        aoi_crs="EPSG:6933",
        dem_epoch=date(2025, 1, 1),
        primary_stratum_ids=primary_stratum_ids or ["steep-bare"],
        independence_review=review or _review(),
    )


def test_reference_metrics_compute_frozen_density_blocks_and_temporal_match():
    features = [
        _feature(1, 100, 100, observed_at="2024-01-01T00:00:00Z"),
        _feature(2, 1100, 100, observed_at="2023-01-01T00:00:00Z"),
        _feature(3, 5100, 100, observed_at="2022-01-01T00:00:00Z"),
        _feature(4, 6100, 100, observed_at="2021-01-01T00:00:00Z"),
        _feature(5, 100, 5100, observed_at="2020-06-01T00:00:00Z"),
    ]

    report = _compute(features)
    metrics = report["metrics"]

    assert report["status"] == "measured"
    assert report["independence_review_status"] == "attested_complete"
    assert metrics["valid_independent_locations"] == 5
    assert metrics["polygon_area_km2"] == pytest.approx(100)
    assert metrics["occupied_1km_cells"] == 5
    assert metrics["eligible_1km_cells"] == 100
    assert metrics["occupied_5km_blocks"] == 3
    assert metrics["eligible_5km_blocks"] == 4
    assert metrics["max_block_observation_fraction"] == pytest.approx(0.4)
    assert metrics["primary_cell_observation_counts"] == {"steep-bare": 5}
    assert metrics["temporal_match_fraction"] == 1
    assert report["metadata_completeness"]["complete_for_all_fields"] is True


def test_repeated_observation_at_same_site_counts_once_spatially():
    features = [
        _feature(1, 100, 100, site="site-a"),
        _feature(2, 100, 100, site="site-a", observed_at="2023-01-01T00:00:00Z"),
        _feature(3, 5100, 100, site="site-b"),
    ]

    report = _compute(features)

    assert report["eligible_reference_observation_count"] == 3
    assert report["unique_independent_site_count"] == 2
    assert report["metrics"]["valid_independent_locations"] == 2
    assert report["metrics"]["occupied_5km_blocks"] == 2


def test_unreviewed_independence_is_not_counted_as_independent():
    features = [_feature(index, index * 100, 100) for index in range(1, 4)]
    report = _compute(features, _review(spatial_independence_reviewed=False))

    assert report["status"] == "not_evaluable"
    assert report["metrics"]["valid_independent_locations"] == 0
    assert report["excluded_by_reason"]["independence_review_incomplete"] == 3
    assert "unresolved" in report["reason_codes"]


def test_conflicting_source_lineage_is_not_counted_as_independent():
    features = [_feature(1, 100, 100)]
    report = _compute(features, _review(source_dependence_conflicts=True))

    assert report["status"] == "not_evaluable"
    assert report["metrics"]["valid_independent_locations"] == 0
    assert "source_dependence_conflict" in report["reason_codes"]


def test_exclusions_are_reported_without_silent_point_dropping():
    features = [
        _feature(1, 100, 100),
        _feature(2, 11000, 11000),
        _feature(3, 200, 200, quality="rejected"),
        _feature(4, 300, 300, status="dependent"),
    ]
    report = _compute(features)

    assert report["metrics"]["valid_independent_locations"] == 1
    assert report["excluded_by_reason"]["outside_aoi"] == 1
    assert report["excluded_by_reason"]["quality_flag_not_accepted"] == 1
    assert report["excluded_by_reason"]["independence_status_dependent"] == 1


def test_duplicate_observation_id_is_rejected():
    features = [_feature(1, 100, 100), _feature(1, 200, 200)]
    with pytest.raises(FormatValidationError, match="duplicate observation_id"):
        _compute(features)


def test_inconsistent_repeated_site_id_is_rejected():
    features = [
        _feature(1, 100, 100, site="same-site"),
        _feature(2, 200, 200, site="same-site"),
    ]
    with pytest.raises(FormatValidationError, match="inconsistent coordinates"):
        _compute(features)


def test_registered_primary_strata_keep_zero_count_cells_visible():
    report = _compute(
        [_feature(1, 100, 100)],
        primary_stratum_ids=["steep-bare", "urban-built-up"],
    )

    assert report["metrics"]["primary_cell_observation_counts"] == {
        "steep-bare": 1,
        "urban-built-up": 0,
    }
