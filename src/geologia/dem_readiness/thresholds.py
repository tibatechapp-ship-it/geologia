"""Immutable implementation of the operational screening thresholds in protocol v1.

These are workflow screening gates, not universal geodetic standards, not
statistical-power guarantees, and not DEM accuracy acceptance thresholds.
Changing them requires a dated protocol amendment before coverage inspection.
"""

from pydantic import BaseModel, ConfigDict, Field


class Section13Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exploratory_observations_per_primary_cell: int = Field(default=30, gt=0)
    confirmatory_observations_per_primary_cell: int = Field(default=50, gt=0)


class Section17Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exploratory_valid_locations_per_km2: int = Field(default=20, gt=0)
    confirmatory_valid_locations_per_km2: int = Field(default=40, gt=0)
    exploratory_occupied_blocks: int = Field(default=20, gt=0)
    confirmatory_occupied_blocks: int = Field(default=30, gt=0)
    exploratory_eligible_blocks_fraction: float = Field(default=0.60, ge=0, le=1)
    confirmatory_eligible_blocks_fraction: float = Field(default=0.75, ge=0, le=1)
    maximum_observation_fraction_in_one_block: float = Field(default=0.50, gt=0, le=1)
    confirmatory_observations_within_epoch_years: int = Field(default=5, gt=0)
    confirmatory_temporal_match_fraction: float = Field(default=0.70, ge=0, le=1)
    density_grid_width_km: float = Field(default=1.0, gt=0)
    spatial_block_width_km: float = Field(default=5.0, gt=0)


class Section20Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_block_width_km: float = Field(default=5.0, gt=0)
    sensitivity_block_widths_km: tuple[float, float] = (2.5, 10.0)
    bootstrap_replicates: int = Field(default=2000, gt=0)


class FrozenProtocolThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: str = "1"
    implementation_freeze_date: str = "2026-11-22"
    source_sections: tuple[str, ...] = ("13", "17", "20")
    section_13: Section13Thresholds = Section13Thresholds()
    section_17: Section17Thresholds = Section17Thresholds()
    section_20: Section20Thresholds = Section20Thresholds()
    interpretation: str = (
        "Operational screening only; not universal standards or power guarantees. "
        "Protocol amendments must be dated and made before coverage/residual inspection."
    )


FROZEN_V1_THRESHOLDS = FrozenProtocolThresholds()
