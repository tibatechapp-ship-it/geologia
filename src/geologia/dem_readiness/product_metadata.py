"""Product metadata schema used to derive, not caller-supply, readiness context."""

import math
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NonEmpty = Annotated[str, Field(min_length=1)]


class DEMProductMetadata(BaseModel):
    """Attributable product specification and license metadata for one release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema: Literal["geologia.dem-product-metadata.v1"]
    product_version_id: NonEmpty
    horizontal_crs: NonEmpty
    spec_source: NonEmpty
    spec_date: date
    metric_type: NonEmpty
    vertical_datum: NonEmpty
    surface_type: Literal["DSM", "DTM"]
    spatial_resolution_x: float = Field(gt=0)
    spatial_resolution_y: float = Field(gt=0)
    resolution_unit: NonEmpty
    license_reference: NonEmpty
    license_disposition: Literal["compatible", "incompatible", "unresolved"]
    evidence_reference: NonEmpty
    reviewer: NonEmpty
    reviewed_at: datetime

    @field_validator("spatial_resolution_x", "spatial_resolution_y")
    @classmethod
    def finite_resolution(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("spatial resolution must be finite")
        return value

    @model_validator(mode="after")
    def validate_metadata(self) -> "DEMProductMetadata":
        for name in self.model_fields:
            value = getattr(self, name)
            if isinstance(value, str) and not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must have a valid UTC offset")
        return self
