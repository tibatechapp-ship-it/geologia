"""Typed manifest contract for one logical DEM product made from raster tiles."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


NonEmpty = Annotated[str, Field(min_length=1)]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]


class DEMTileManifest(BaseModel):
    """Exact, immutable tile membership for one logical DEM product release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema: Literal["geologia.dem-tile-manifest.v1"]
    product_version_id: NonEmpty
    tile_dataset_ids: tuple[NonEmpty, ...] = Field(min_length=1, max_length=256)
    tile_dataset_sha256s: tuple[SHA256, ...] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_tile_membership(self) -> "DEMTileManifest":
        if len(self.tile_dataset_ids) != len(self.tile_dataset_sha256s):
            raise ValueError("each DEM tile dataset ID must have exactly one SHA-256")
        if len(set(self.tile_dataset_ids)) != len(self.tile_dataset_ids):
            raise ValueError("DEM tile dataset IDs must be unique")
        if any(not value.strip() for value in self.tile_dataset_ids):
            raise ValueError("DEM tile dataset IDs must be non-empty")
        if not self.product_version_id.strip():
            raise ValueError("product_version_id must be non-empty")
        return self
