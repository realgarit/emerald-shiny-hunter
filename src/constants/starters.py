"""
Starter Pokemon configuration for Pokemon Emerald.

Contains selection sequences and timing constants for each starter.
"""

from .species import SPECIES_TREECKO, SPECIES_TORCHIC, SPECIES_MUDKIP
from .keys import KEY_LEFT, KEY_RIGHT, KEY_A


# =============================================================================
# Starter Configuration
# =============================================================================
# Each starter has a different selection sequence based on bag position:
# - Torchic (center): Just A presses
# - Mudkip (right): A dialogue -> Right -> A select
# - Treecko (left): A dialogue -> Left -> A select

STARTER_CONFIG = {
    "torchic": {
        "name": "Torchic",
        "species_id": SPECIES_TORCHIC,
        "position": "center",
        "sequence": {
            # Torchic is default center position, just needs A presses
            "type": "simple",
            "a_presses": 26,
            "a_delay_frames": 15,
        },
    },
    "mudkip": {
        "name": "Mudkip",
        "species_id": SPECIES_MUDKIP,
        "position": "right",
        "sequence": {
            # Navigate right from center, then select
            "type": "navigate",
            "a_dialogue_presses": 20,
            "a_dialogue_delay_frames": 15,
            "wait_for_bag_frames": 30,
            "direction_key": KEY_RIGHT,
            "direction_presses": 1,
            "direction_delay_frames": 15,
            "wait_after_direction_frames": 12,
            "a_select_presses": 6,
            "a_select_delay_frames": 15,
            "max_retry_presses": 8,
        },
    },
    "treecko": {
        "name": "Treecko",
        "species_id": SPECIES_TREECKO,
        "position": "left",
        "sequence": {
            # Navigate left from center, then select
            "type": "navigate",
            "a_dialogue_presses": 20,
            "a_dialogue_delay_frames": 15,
            "wait_for_bag_frames": 30,
            "direction_key": KEY_LEFT,
            "direction_presses": 1,
            "direction_delay_frames": 15,
            "wait_after_direction_frames": 12,
            "a_select_presses": 6,
            "a_select_delay_frames": 15,
            "max_retry_presses": 8,
        },
    },
}


def get_starter_config(name: str) -> dict:
    """
    Get configuration for a starter Pokemon.

    Args:
        name: Starter name (case-insensitive): torchic, mudkip, or treecko

    Returns:
        Configuration dict or None if not found
    """
    return STARTER_CONFIG.get(name.lower())


def get_available_starters() -> list:
    """Get list of available starter names."""
    return list(STARTER_CONFIG.keys())


def get_starter_species_dict() -> dict:
    """Get species dict for all starters (species_id -> name)."""
    return {
        config["species_id"]: config["name"]
        for config in STARTER_CONFIG.values()
    }
