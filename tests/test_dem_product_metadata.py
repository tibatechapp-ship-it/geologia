from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from geologia.dem_readiness.product_metadata import DEMProductMetadata


def valid_metadata(**overrides):
    values = {
        "schema": "geologia.dem-product-metadata.v1",
        "product_version_id": "dem-release-2026-01",
        "horizontal_crs": "EPSG:32638",
        "spec_source": "official product specification",
        "spec_date": date(2026, 1, 1),
        "metric_type": "elevation",
        "vertical_datum": "NAVD88",
        "surface_type": "DTM",
        "spatial_resolution_x": 30.0,
        "spatial_resolution_y": 30.0,
        "resolution_unit": "metre",
        "license_reference": "license://product/release-1",
        "license_disposition": "compatible",
        "evidence_reference": "metadata://product/release-1",
        "reviewer": "metadata-reviewer",
        "reviewed_at": datetime(2026, 11, 22, tzinfo=UTC),
    }
    values.update(overrides)
    return DEMProductMetadata(**values)


def test_product_metadata_is_attributable_and_version_bound():
    metadata = valid_metadata()
    assert metadata.product_version_id == "dem-release-2026-01"
    assert metadata.license_disposition == "compatible"


def test_product_metadata_rejects_non_finite_resolution():
    with pytest.raises(ValidationError):
        valid_metadata(spatial_resolution_x=float("inf"))


def test_product_metadata_rejects_unknown_license_disposition():
    with pytest.raises(ValidationError):
        valid_metadata(license_disposition="assume_ok")


def test_product_metadata_requires_timezone_aware_review():
    with pytest.raises(ValidationError):
        valid_metadata(reviewed_at=datetime(2026, 11, 22))
