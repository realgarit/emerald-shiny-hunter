"""
Constants package for Pokemon Emerald Shiny Hunter.

This package provides centralized constants for:
- Species IDs (from pokeemerald decompilation)
- Memory addresses (Emerald US)
- GBA button/key constants

Usage:
    from constants import SPECIES_TORCHIC, PARTY_PV_ADDR, KEY_A
    from constants.species import STARTER_SPECIES, get_species_name
    from constants.memory import get_substructure_order
    from constants.keys import keys_to_string
"""

# Species constants
from .species import (
    # Special values
    SPECIES_NONE,
    SPECIES_EGG,

    # Starters
    SPECIES_TREECKO,
    SPECIES_GROVYLE,
    SPECIES_SCEPTILE,
    SPECIES_TORCHIC,
    SPECIES_COMBUSKEN,
    SPECIES_BLAZIKEN,
    SPECIES_MUDKIP,
    SPECIES_MARSHTOMP,
    SPECIES_SWAMPERT,

    # Route 101
    SPECIES_POOCHYENA,
    SPECIES_ZIGZAGOON,
    SPECIES_WURMPLE,

    # Route 102
    SPECIES_LOTAD,
    SPECIES_SEEDOT,
    SPECIES_RALTS,

    # Lookup helpers
    SPECIES_NAMES,
    SPECIES_BY_NAME,
    get_species_name,
    get_species_id,

    # National Dex mappings
    NATIONAL_DEX,
    INTERNAL_TO_NATIONAL,
    get_national_dex,
    get_internal_id,
    species_from_national_dex,

    # Route encounter tables
    ROUTE_101_SPECIES,
    ROUTE_102_SPECIES,
    STARTER_SPECIES,
)

# Memory address constants
from .memory import (
    # Party addresses
    PARTY_COUNT_ADDR,
    PARTY_SLOT_1_ADDR,
    PARTY_SLOT_SIZE,
    PARTY_PV_ADDR,
    PARTY_TID_ADDR,

    # Enemy addresses
    ENEMY_PV_ADDR,
    ENEMY_TID_ADDR,
    ENEMY_SID_ADDR,
    ENEMY_SPECIES_ADDR,

    # Box storage
    G_POKEMON_STORAGE_PTR,
    BOX_DATA_OFFSET,
    BOX_POKEMON_SIZE,
    POKEMON_PER_BOX,
    NUM_BOXES,

    # RNG
    RNG_SEED_ADDR,

    # Structure helpers
    SUBSTRUCTURE_ORDERS,
    get_substructure_order,
    get_party_slot_address,
    get_box_slot_address,
)

# Key constants
from .keys import (
    KEY_A,
    KEY_B,
    KEY_SELECT,
    KEY_START,
    KEY_RIGHT,
    KEY_LEFT,
    KEY_UP,
    KEY_DOWN,
    KEY_R,
    KEY_L,
    KEY_NONE,
    KEY_SOFT_RESET,

    # Timing constants
    DEFAULT_HOLD_FRAMES,
    DEFAULT_RELEASE_FRAMES,
    A_PRESS_DELAY_FRAMES,
    A_LOADING_DELAY_FRAMES,

    # Helper
    keys_to_string,
)

__all__ = [
    # Species
    "SPECIES_NONE", "SPECIES_EGG",
    "SPECIES_TREECKO", "SPECIES_GROVYLE", "SPECIES_SCEPTILE",
    "SPECIES_TORCHIC", "SPECIES_COMBUSKEN", "SPECIES_BLAZIKEN",
    "SPECIES_MUDKIP", "SPECIES_MARSHTOMP", "SPECIES_SWAMPERT",
    "SPECIES_POOCHYENA", "SPECIES_ZIGZAGOON", "SPECIES_WURMPLE",
    "SPECIES_LOTAD", "SPECIES_SEEDOT", "SPECIES_RALTS",
    "SPECIES_NAMES", "SPECIES_BY_NAME",
    "get_species_name", "get_species_id",
    "NATIONAL_DEX", "INTERNAL_TO_NATIONAL",
    "get_national_dex", "get_internal_id", "species_from_national_dex",
    "ROUTE_101_SPECIES", "ROUTE_102_SPECIES", "STARTER_SPECIES",

    # Memory
    "PARTY_COUNT_ADDR", "PARTY_SLOT_1_ADDR", "PARTY_SLOT_SIZE",
    "PARTY_PV_ADDR", "PARTY_TID_ADDR",
    "ENEMY_PV_ADDR", "ENEMY_TID_ADDR", "ENEMY_SID_ADDR", "ENEMY_SPECIES_ADDR",
    "G_POKEMON_STORAGE_PTR", "BOX_DATA_OFFSET",
    "BOX_POKEMON_SIZE", "POKEMON_PER_BOX", "NUM_BOXES",
    "RNG_SEED_ADDR",
    "SUBSTRUCTURE_ORDERS", "get_substructure_order",
    "get_party_slot_address", "get_box_slot_address",

    # Keys
    "KEY_A", "KEY_B", "KEY_SELECT", "KEY_START",
    "KEY_RIGHT", "KEY_LEFT", "KEY_UP", "KEY_DOWN",
    "KEY_R", "KEY_L", "KEY_NONE", "KEY_SOFT_RESET",
    "DEFAULT_HOLD_FRAMES", "DEFAULT_RELEASE_FRAMES",
    "A_PRESS_DELAY_FRAMES", "A_LOADING_DELAY_FRAMES",
    "keys_to_string",
]
