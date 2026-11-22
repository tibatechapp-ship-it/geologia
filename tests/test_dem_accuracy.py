import csv
import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from geologia.formats import FormatValidationError

from geologia.dem_readiness.manifest import DEMTileManifest
from geologia.dem_readiness.models import DeclaredUseContext, IndependentReviewEvidence

from geologia.dem_readiness.accuracy import (
    AccuracyRequirement,
    DEMAccuracyMetadata,
    compute_dem_reference_residuals,
)


NOW = datetime(2026, 11, 22, tzinfo=UTC)


def metadata(**overrides):
    values = {
        "product_version_id": "dem-release-2026-01",
        "dem_vertical_datum": "NAVD88",
        "reference_vertical_datum": "NAVD88",
        "dem_vertical_unit": "m",
        "reference_vertical_unit": "m",
        "dem_surface_type": "DTM",
        "reference_surface_type": "DTM",
        "dem_epoch": "2020",
        "reference_epoch": "2020",
        "reference_source_id": "gnss-control-network-1",
        "reference_release": "release-2026-01",
        "reference_horizontal_crs": "EPSG:32638",
        "aoi_crs": "EPSG:32638",
        "dem_metadata_reference": "metadata://dem/release-1",
        "reference_metadata_reference": "metadata://reference/release-1",
        "independence_status": "independent_confirmed",
        "independence_evidence_reference": "evidence://independence/review-1",
        "independence_reviewer": "reviewer-1",
        "independence_reviewed_at": NOW,
    }
    values.update(overrides)
    return DEMAccuracyMetadata(**values)


def requirement(**overrides):
    values = {
        "metric": "rmse_m",
        "maximum_value_m": 1.5,
        "minimum_valid_observations": 4,
        "requirement_reference": "task-profile://regional-recon-v1/accuracy",
        "approved_by": "reviewer-1",
        "frozen_at": NOW,
    }
    values.update(overrides)
    return AccuracyRequirement(**values)


def _write_dem(tmp_path, *, nodata_at=None, value=100):
    rasterio = pytest.importorskip("rasterio")
    numpy = pytest.importorskip("numpy")
    from rasterio.transform import from_origin

    path = tmp_path / "dem.tif"
    data = numpy.full((10, 10), value, dtype=numpy.float32)
    if nodata_at is not None:
        data[nodata_at] = -9999
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype="float32",
        crs="EPSG:32638",
        transform=from_origin(500000, 1700000, 30, 30),
        nodata=-9999,
    ) as dataset:
        dataset.write(data, 1)
    return path


def _write_reference_csv(tmp_path, *, elevations=(98, 99, 100, 101)):
    path = tmp_path / "reference.csv"
    points = [
        ("p1", 500015, 1699985, elevations[0]),
        ("p2", 500045, 1699955, elevations[1]),
        ("p3", 500075, 1699925, elevations[2]),
        ("p4", 500105, 1699895, elevations[3]),
    ]
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow([
            "point_id", "x", "y", "elevation_m", "terrain_stratum", "uncertainty_m"
        ])
        for point_id, x, y, elevation in points:
            writer.writerow([point_id, x, y, elevation, "steep_bare", 0.2])
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _aoi():
    return {
        "type": "Polygon",
        "coordinates": [[
            [500000, 1699700],
            [500300, 1699700],
            [500300, 1700000],
            [500000, 1700000],
            [500000, 1699700],
        ]],
    }


def _compute(dem, reference, reference_sha, **kwargs):
    assessment_metadata = kwargs.pop("metadata", metadata())
    declared_use = kwargs.pop(
        "declared_use",
        DeclaredUseContext(
            product_name="GEOLOGIA",
            product_version_id=assessment_metadata.product_version_id,
            pilot_area_id="pilot-yemen-1",
            task_profile_id="regional-recon-v1",
            intended_user="geological researcher",
            declared_scale="regional reconnaissance",
        ),
    )
    independent_review = kwargs.pop(
        "independent_review",
        IndependentReviewEvidence(
            product_version_id=assessment_metadata.product_version_id,
            pilot_area_id=declared_use.pilot_area_id,
            task_profile_id=declared_use.task_profile_id,
            reviewer=assessment_metadata.independence_reviewer,
            evidence_reference=assessment_metadata.independence_evidence_reference,
            reviewed_at=assessment_metadata.independence_reviewed_at,
        ),
    )
    manifest = kwargs.pop(
        "product_manifest",
        DEMTileManifest(
            schema="geologia.dem-tile-manifest.v1",
            product_version_id=assessment_metadata.product_version_id,
            tile_dataset_ids=(dem.name,),
            tile_dataset_sha256s=(hashlib.sha256(dem.read_bytes()).hexdigest(),),
        ),
    )
    canonical_hash = lambda payload: hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        .encode("utf-8")
    ).hexdigest()
    aoi = _aoi()
    manifest_sha = kwargs.pop(
        "product_manifest_sha256",
        canonical_hash(manifest.model_dump(mode="json")),
    )
    aoi_sha = kwargs.pop("aoi_dataset_sha256", canonical_hash(aoi))
    return compute_dem_reference_residuals(
        [dem],
        reference,
        aoi,
        metadata=assessment_metadata,
        declared_use=declared_use,
        independent_review=independent_review,
        product_manifest_sha256=manifest_sha,
        reference_dataset_sha256=reference_sha,
        aoi_dataset_sha256=aoi_sha,
        product_manifest=manifest,
        coverage_footprint_reference="coverage://dem-release/aoi-1",
        **kwargs,
    )


def test_dem_residual_metrics_are_computed_directly_and_requirement_is_scoped(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)

    report = _compute(
        dem,
        reference,
        reference_sha,
        requirement=requirement(),
    )

    assert report["assessment_status"] == "computed"
    assert report["accuracy_disposition"] == "accuracy_requirement_met_for_declared_use"
    assert report["metrics_scope"] == "primary_confirmatory"
    assert report["valid_residual_count"] == 4
    assert report["metrics"]["bias_m"] == pytest.approx(0.5)
    assert report["metrics"]["mae_m"] == pytest.approx(1.0)
    assert report["metrics"]["rmse_m"] == pytest.approx((1.5) ** 0.5)
    assert report["metrics"]["empirical_le90_m"] == pytest.approx(2.0)
    assert report["residual_convention"] == "DEM minus reference"
    assert report["readiness_disposition"] == "not_assessed"


def test_accuracy_requirement_not_met_is_reported_without_readiness_claim(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)

    report = _compute(
        dem,
        reference,
        reference_sha,
        requirement=requirement(maximum_value_m=1.0),
    )

    assert report["accuracy_disposition"] == "accuracy_requirement_not_met"
    assert report["reason_codes"] == ["accuracy_requirement_not_met"]
    assert report["readiness_disposition"] == "not_assessed"


def test_vertical_datum_mismatch_prevents_residual_comparison(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)

    report = _compute(
        dem,
        reference,
        reference_sha,
        metadata=metadata(reference_vertical_datum="EGM2008"),
        requirement=requirement(),
    )

    assert report["assessment_status"] == "not_evaluable"
    assert report["reason_codes"] == ["vertical_datum_mismatch"]
    assert report["metrics"] is None


def test_unresolved_reference_independence_is_descriptive_only(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)

    report = _compute(
        dem,
        reference,
        reference_sha,
        metadata=metadata(independence_status="unresolved"),
        requirement=requirement(),
    )

    assert report["metrics_scope"] == "descriptive_only"
    assert report["accuracy_disposition"] == "not_evaluable"
    assert report["reason_codes"] == ["source_dependence_conflict"]


def test_nodata_reference_points_are_excluded_and_sample_gate_applies(tmp_path):
    dem = _write_dem(tmp_path, nodata_at=(0, 0))
    reference, reference_sha = _write_reference_csv(tmp_path)

    report = _compute(
        dem,
        reference,
        reference_sha,
        requirement=requirement(minimum_valid_observations=4),
    )

    assert report["valid_residual_count"] == 3
    assert report["excluded_counts"]["no_valid_dem_pixel"] == 1
    assert report["accuracy_disposition"] == "not_evaluable"
    assert report["reason_codes"] == ["insufficient_sample"]


def test_accuracy_metadata_rejects_timezone_without_valid_offset():
    from datetime import tzinfo

    class InvalidTimezone(tzinfo):
        def utcoffset(self, dt):
            return None

        def dst(self, dt):
            return None

    with pytest.raises(ValidationError):
        metadata(independence_reviewed_at=datetime(2026, 11, 22, tzinfo=InvalidTimezone()))


def test_accuracy_requirement_rejects_non_finite_limit():
    with pytest.raises(ValidationError):
        requirement(maximum_value_m=float("nan"))


def test_confirmatory_accuracy_requires_exact_review_scope(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)
    wrong_scope_review = IndependentReviewEvidence(
        product_version_id="dem-release-2026-01",
        pilot_area_id="different-pilot-area",
        task_profile_id="regional-recon-v1",
        reviewer="reviewer-1",
        evidence_reference="evidence://independence/review-1",
        reviewed_at=NOW,
    )

    report = _compute(
        dem,
        reference,
        reference_sha,
        independent_review=wrong_scope_review,
        requirement=requirement(),
    )

    assert report["metrics_scope"] == "descriptive_only"
    assert report["accuracy_disposition"] == "not_evaluable"
    assert "source_dependence_conflict" in report["reason_codes"]


def test_confirmatory_accuracy_requires_review_record(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)

    report = _compute(
        dem,
        reference,
        reference_sha,
        independent_review=None,
        requirement=requirement(),
    )

    assert report["metrics_scope"] == "descriptive_only"
    assert report["accuracy_disposition"] == "not_evaluable"


def test_manifest_hash_must_match_canonical_manifest_content(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)

    with pytest.raises(FormatValidationError, match="manifest SHA-256"):
        _compute(
            dem,
            reference,
            reference_sha,
            product_manifest=DEMTileManifest(
                schema="geologia.dem-tile-manifest.v1",
                product_version_id="dem-release-2026-01",
                tile_dataset_ids=(dem.name,),
                tile_dataset_sha256s=(hashlib.sha256(dem.read_bytes()).hexdigest(),),
            ),
            product_manifest_sha256="f" * 64,
        )


def test_aoi_hash_must_match_canonical_geometry(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)
    with pytest.raises(FormatValidationError, match="AOI SHA-256"):
        _compute(
            dem,
            reference,
            reference_sha,
            aoi_dataset_sha256="d" * 64,
        )


def test_successful_report_records_canonical_hash_binding(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)
    report = _compute(dem, reference, reference_sha)
    assert report["aoi_hash_binding"] == "verified_canonical_aoi_payload"
    assert report["product_manifest_hash_binding"] == "verified_canonical_manifest"


def test_manifest_tile_hash_membership_must_match_dem_bytes(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)
    wrong_tile_manifest = DEMTileManifest(
        schema="geologia.dem-tile-manifest.v1",
        product_version_id="dem-release-2026-01",
        tile_dataset_ids=(dem.name,),
        tile_dataset_sha256s=("0" * 64,),
    )

    with pytest.raises(FormatValidationError, match="tile SHA-256 membership"):
        _compute(
            dem,
            reference,
            reference_sha,
            product_manifest=wrong_tile_manifest,
        )


def test_manifest_product_version_must_match_accuracy_metadata(tmp_path):
    dem = _write_dem(tmp_path)
    reference, reference_sha = _write_reference_csv(tmp_path)
    mismatched_manifest = DEMTileManifest(
        schema="geologia.dem-tile-manifest.v1",
        product_version_id="another-release",
        tile_dataset_ids=(dem.name,),
        tile_dataset_sha256=(hashlib.sha256(dem.read_bytes()).hexdigest(),),
    )

    with pytest.raises(FormatValidationError, match="product version"):
        _compute(
            dem,
            reference,
            reference_sha,
            product_manifest=mismatched_manifest,
        )
