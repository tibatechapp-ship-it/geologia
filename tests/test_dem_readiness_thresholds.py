import pytest
from pydantic import ValidationError

from geologia.dem_readiness.thresholds import FROZEN_V1_THRESHOLDS


def test_protocol_v1_thresholds_match_registered_protocol():
    thresholds = FROZEN_V1_THRESHOLDS
    assert thresholds.protocol_version == "1"
    assert thresholds.section_13.exploratory_observations_per_primary_cell == 30
    assert thresholds.section_13.confirmatory_observations_per_primary_cell == 50
    assert thresholds.section_17.exploratory_valid_locations_per_km2 == 20
    assert thresholds.section_17.confirmatory_valid_locations_per_km2 == 40
    assert thresholds.section_17.exploratory_occupied_blocks == 20
    assert thresholds.section_17.confirmatory_occupied_blocks == 30
    assert thresholds.section_17.exploratory_eligible_blocks_fraction == 0.60
    assert thresholds.section_17.confirmatory_eligible_blocks_fraction == 0.75
    assert thresholds.section_17.maximum_observation_fraction_in_one_block == 0.50
    assert thresholds.section_17.confirmatory_temporal_match_fraction == 0.70
    assert thresholds.section_20.primary_block_width_km == 5.0
    assert thresholds.section_20.sensitivity_block_widths_km == (2.5, 10.0)
    assert thresholds.section_20.bootstrap_replicates == 2000


def test_frozen_thresholds_cannot_be_mutated():
    with pytest.raises(ValidationError):
        FROZEN_V1_THRESHOLDS.protocol_version = "2"
