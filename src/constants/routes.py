"""
Route encounter tables for Pokemon Emerald.

Contains all wild Pokemon encounters for routes and dungeons.
Ruby/Sapphire-only Pokemon are commented out for future support.
"""

from .species import (
    # Common Pokemon
    SPECIES_ZIGZAGOON, SPECIES_LINOONE,
    SPECIES_WURMPLE, SPECIES_SILCOON, SPECIES_CASCOON,
    SPECIES_POOCHYENA, SPECIES_MIGHTYENA,
    SPECIES_WINGULL, SPECIES_PELIPPER,
    SPECIES_TAILLOW, SPECIES_SWELLOW,
    SPECIES_ODDISH, SPECIES_GLOOM,
    SPECIES_MARILL, SPECIES_AZUMARILL,

    # Route 102
    SPECIES_RALTS,
    SPECIES_SEEDOT, SPECIES_NUZLEAF,
    SPECIES_LOTAD, SPECIES_LOMBRE,
    # SPECIES_SURSKIT,  # Ruby/Sapphire only

    # Route 110
    SPECIES_ELECTRIKE, SPECIES_MANECTRIC,
    SPECIES_PLUSLE, SPECIES_MINUN,
    SPECIES_GULPIN,

    # Route 111 (Desert)
    SPECIES_SANDSHREW,
    SPECIES_TRAPINCH,
    SPECIES_CACNEA,
    SPECIES_BALTOY,

    # Route 112
    SPECIES_MACHOP,
    SPECIES_NUMEL,

    # Route 113
    SPECIES_SPINDA,
    SPECIES_SLUGMA,
    SPECIES_SKARMORY,

    # Route 114
    SPECIES_SWABLU,
    SPECIES_SEVIPER,
    # SPECIES_ZANGOOSE,  # Ruby/Sapphire only

    # Route 115
    SPECIES_JIGGLYPUFF,

    # Route 116
    SPECIES_WHISMUR, SPECIES_LOUDRED,
    SPECIES_SKITTY,
    SPECIES_NINCADA,
    SPECIES_ABRA,

    # Route 117
    # SPECIES_ROSELIA,  # Ruby/Sapphire only
    SPECIES_VOLBEAT,
    SPECIES_ILLUMISE,

    # Route 118-120
    SPECIES_KECLEON,
    SPECIES_TROPIUS,
    SPECIES_ABSOL,

    # Route 121/123
    SPECIES_SHUPPET,
    SPECIES_DUSKULL,

    # Dungeons
    SPECIES_ZUBAT, SPECIES_GOLBAT,
    SPECIES_MAKUHITA, SPECIES_HARIYAMA,
    SPECIES_GEODUDE,
    SPECIES_ARON, SPECIES_LAIRON,
    SPECIES_SABLEYE,
    SPECIES_MAWILE,
    SPECIES_SLAKOTH,
    SPECIES_SHROOMISH,
    SPECIES_GRIMER,
    SPECIES_KOFFING,
    SPECIES_TORKOAL,
    SPECIES_SPOINK,
    # SPECIES_MEDITITE, SPECIES_MEDICHAM,  # Ruby/Sapphire only
    SPECIES_VULPIX,
    SPECIES_CHIMECHO,
    # SPECIES_LUNATONE,  # Ruby/Sapphire only
    SPECIES_SOLROCK,
    SPECIES_BAGON,
    SPECIES_SPHEAL,
    SPECIES_SNORUNT,
    SPECIES_CLAYDOL,
    SPECIES_BANETTE,
    SPECIES_DUSCLOPS,
    SPECIES_ALTARIA,

    # Safari Zone
    SPECIES_PIKACHU,
    SPECIES_DODUO, SPECIES_DODRIO,
    SPECIES_NATU, SPECIES_XATU,
    SPECIES_WOBBUFFET,
    SPECIES_GIRAFARIG,
    SPECIES_PHANPY,
    SPECIES_RHYHORN,
    SPECIES_HERACROSS,
    SPECIES_PINSIR,
    SPECIES_MAREEP,
    SPECIES_SUNKERN,
    SPECIES_HOOTHOOT,
    SPECIES_SPINARAK,
    SPECIES_AIPOM,
    SPECIES_TEDDIURSA,
    SPECIES_PINECO,
    SPECIES_HOUNDOUR,
    SPECIES_SNUBBULL,
    SPECIES_STANTLER,
    SPECIES_MILTANK,
    SPECIES_GLIGAR,
    SPECIES_LEDYBA,

    # Helper
    SPECIES_NAMES,
)


# =============================================================================
# Route Encounters (Emerald)
# =============================================================================
# Ruby/Sapphire-only Pokemon are commented out for future support.

ROUTE_ENCOUNTERS = {
    # -------------------------------------------------------------------------
    # Early Game Routes
    # -------------------------------------------------------------------------
    101: {
        "name": "Route 101",
        "walking": [
            SPECIES_ZIGZAGOON,
            SPECIES_WURMPLE,
            SPECIES_POOCHYENA,
        ],
    },
    102: {
        "name": "Route 102",
        "walking": [
            SPECIES_ZIGZAGOON,
            SPECIES_WURMPLE,
            SPECIES_POOCHYENA,
            SPECIES_RALTS,
            # SPECIES_SURSKIT,  # Ruby/Sapphire only
            SPECIES_SEEDOT,
            SPECIES_LOTAD,
        ],
    },
    103: {
        "name": "Route 103",
        "walking": [
            SPECIES_POOCHYENA,
            SPECIES_ZIGZAGOON,
            SPECIES_WINGULL,
        ],
    },
    104: {
        "name": "Route 104",
        "walking": [
            SPECIES_ZIGZAGOON,
            SPECIES_WURMPLE,
            SPECIES_POOCHYENA,
            SPECIES_TAILLOW,
            SPECIES_WINGULL,
            SPECIES_MARILL,
        ],
    },

    # -------------------------------------------------------------------------
    # Mid Game Routes
    # -------------------------------------------------------------------------
    110: {
        "name": "Route 110",
        "walking": [
            SPECIES_ELECTRIKE,
            SPECIES_WINGULL,
            SPECIES_PLUSLE,
            SPECIES_MINUN,
            SPECIES_ODDISH,
            SPECIES_ZIGZAGOON,
            SPECIES_GULPIN,
            SPECIES_POOCHYENA,
        ],
    },
    111: {
        "name": "Route 111 (Desert)",
        "walking": [
            SPECIES_SANDSHREW,
            SPECIES_TRAPINCH,
            SPECIES_CACNEA,
            SPECIES_BALTOY,
        ],
    },
    112: {
        "name": "Route 112",
        "walking": [
            SPECIES_MACHOP,
            SPECIES_NUMEL,
            SPECIES_MARILL,
        ],
    },
    113: {
        "name": "Route 113",
        "walking": [
            SPECIES_SANDSHREW,
            SPECIES_SPINDA,
            SPECIES_SLUGMA,
            SPECIES_SKARMORY,
        ],
    },
    114: {
        "name": "Route 114",
        "walking": [
            SPECIES_LOTAD,
            SPECIES_SEEDOT,
            SPECIES_SWABLU,
            # SPECIES_SURSKIT,  # Ruby/Sapphire only
            SPECIES_NUZLEAF,
            SPECIES_SEVIPER,
            SPECIES_LOMBRE,
            # SPECIES_ZANGOOSE,  # Ruby/Sapphire only
        ],
    },
    115: {
        "name": "Route 115",
        "walking": [
            SPECIES_TAILLOW,
            SPECIES_SWABLU,
            SPECIES_JIGGLYPUFF,
            SPECIES_SWELLOW,
            SPECIES_WINGULL,
        ],
    },
    116: {
        "name": "Route 116",
        "walking": [
            SPECIES_ZIGZAGOON,
            SPECIES_WHISMUR,
            SPECIES_POOCHYENA,
            SPECIES_SKITTY,
            SPECIES_TAILLOW,
            SPECIES_NINCADA,
            SPECIES_ABRA,
        ],
    },
    117: {
        "name": "Route 117",
        "walking": [
            SPECIES_ZIGZAGOON,
            # SPECIES_ROSELIA,  # Ruby/Sapphire only
            SPECIES_ODDISH,
            SPECIES_POOCHYENA,
            # SPECIES_SURSKIT,  # Ruby/Sapphire only
            SPECIES_VOLBEAT,
            SPECIES_ILLUMISE,
            SPECIES_SEEDOT,
            SPECIES_MARILL,
        ],
    },

    # -------------------------------------------------------------------------
    # Late Game Routes
    # -------------------------------------------------------------------------
    118: {
        "name": "Route 118",
        "walking": [
            SPECIES_ZIGZAGOON,
            SPECIES_ELECTRIKE,
            SPECIES_KECLEON,
            SPECIES_LINOONE,
            SPECIES_WINGULL,
            SPECIES_MANECTRIC,
        ],
    },
    119: {
        "name": "Route 119",
        "walking": [
            SPECIES_ODDISH,
            SPECIES_ZIGZAGOON,
            SPECIES_LINOONE,
            SPECIES_KECLEON,
            SPECIES_TROPIUS,
        ],
    },
    120: {
        "name": "Route 120",
        "walking": [
            SPECIES_ODDISH,
            SPECIES_LINOONE,
            SPECIES_MIGHTYENA,
            SPECIES_MARILL,
            SPECIES_ZIGZAGOON,
            SPECIES_POOCHYENA,
            # SPECIES_SURSKIT,  # Ruby/Sapphire only
            SPECIES_KECLEON,
            SPECIES_ABSOL,
            SPECIES_SEEDOT,
        ],
    },
    121: {
        "name": "Route 121",
        "walking": [
            SPECIES_SHUPPET,
            SPECIES_DUSKULL,
            SPECIES_GLOOM,
            SPECIES_WINGULL,
            SPECIES_KECLEON,
            SPECIES_ODDISH,
            SPECIES_ZIGZAGOON,
            SPECIES_LINOONE,
            SPECIES_POOCHYENA,
            SPECIES_MIGHTYENA,
        ],
    },
    123: {
        "name": "Route 123",
        "walking": [
            SPECIES_SHUPPET,
            SPECIES_DUSKULL,
            SPECIES_GLOOM,
            SPECIES_WINGULL,
            SPECIES_KECLEON,
            SPECIES_ODDISH,
            SPECIES_ZIGZAGOON,
            SPECIES_LINOONE,
            SPECIES_POOCHYENA,
            SPECIES_MIGHTYENA,
        ],
    },
}


# =============================================================================
# Dungeon/Special Area Encounters (Emerald)
# =============================================================================

DUNGEON_ENCOUNTERS = {
    "petalburg_woods": {
        "name": "Petalburg Woods",
        "walking": [
            SPECIES_ZIGZAGOON,
            SPECIES_WURMPLE,
            SPECIES_POOCHYENA,
            SPECIES_TAILLOW,
            SPECIES_SLAKOTH,
            SPECIES_SILCOON,
            SPECIES_CASCOON,
            SPECIES_SHROOMISH,
        ],
    },
    "rusturf_tunnel": {
        "name": "Rusturf Tunnel",
        "walking": [
            SPECIES_WHISMUR,
        ],
    },
    "granite_cave": {
        "name": "Granite Cave",
        "walking": [
            SPECIES_ZUBAT,
            SPECIES_MAKUHITA,
            SPECIES_ABRA,
            SPECIES_GEODUDE,
            SPECIES_ARON,
            SPECIES_SABLEYE,
            SPECIES_MAWILE,
        ],
    },
    "fiery_path": {
        "name": "Fiery Path",
        "walking": [
            SPECIES_GRIMER,
            SPECIES_KOFFING,
            SPECIES_NUMEL,
            SPECIES_MACHOP,
            SPECIES_SLUGMA,
            SPECIES_TORKOAL,
        ],
    },
    "jagged_pass": {
        "name": "Jagged Pass",
        "walking": [
            SPECIES_MACHOP,
            SPECIES_NUMEL,
            SPECIES_SPOINK,
        ],
    },
    "mt_pyre_inside": {
        "name": "Mt. Pyre (Inside)",
        "walking": [
            SPECIES_SHUPPET,
            SPECIES_DUSKULL,
        ],
    },
    "mt_pyre_outside": {
        "name": "Mt. Pyre (Outside)",
        "walking": [
            # SPECIES_MEDITITE,  # Ruby/Sapphire only
            SPECIES_SHUPPET,
            SPECIES_DUSKULL,
            SPECIES_VULPIX,
            SPECIES_WINGULL,
        ],
    },
    "mt_pyre_summit": {
        "name": "Mt. Pyre (Summit)",
        "walking": [
            SPECIES_SHUPPET,
            SPECIES_DUSKULL,
            SPECIES_CHIMECHO,
        ],
    },
    "meteor_falls": {
        "name": "Meteor Falls",
        "walking": [
            SPECIES_ZUBAT,
            SPECIES_GOLBAT,
            # SPECIES_LUNATONE,  # Ruby/Sapphire only
            SPECIES_SOLROCK,
            SPECIES_BAGON,
        ],
    },
    "shoal_cave": {
        "name": "Shoal Cave",
        "walking": [
            SPECIES_ZUBAT,
            SPECIES_SPHEAL,
            SPECIES_GOLBAT,
            SPECIES_SNORUNT,
        ],
    },
    "cave_of_origin": {
        "name": "Cave of Origin",
        "walking": [
            SPECIES_ZUBAT,
            SPECIES_GOLBAT,
            SPECIES_SABLEYE,
            SPECIES_MAWILE,
        ],
    },
    "victory_road": {
        "name": "Victory Road",
        "walking": [
            SPECIES_GOLBAT,
            SPECIES_HARIYAMA,
            SPECIES_ZUBAT,
            SPECIES_LOUDRED,
            SPECIES_MAKUHITA,
            SPECIES_LAIRON,
            SPECIES_WHISMUR,
            SPECIES_ARON,
            # SPECIES_MEDICHAM,  # Ruby/Sapphire only
            # SPECIES_MEDITITE,  # Ruby/Sapphire only
            SPECIES_SABLEYE,
            SPECIES_MAWILE,
        ],
    },
    "sky_pillar": {
        "name": "Sky Pillar",
        "walking": [
            SPECIES_GOLBAT,
            SPECIES_SABLEYE,
            SPECIES_MAWILE,
            SPECIES_CLAYDOL,
            SPECIES_BANETTE,
            SPECIES_DUSCLOPS,
            SPECIES_ALTARIA,
        ],
    },
    "safari_zone": {
        "name": "Safari Zone",
        "walking": [
            SPECIES_ODDISH,
            SPECIES_GLOOM,
            SPECIES_PIKACHU,
            SPECIES_DODUO,
            SPECIES_DODRIO,
            SPECIES_NATU,
            SPECIES_XATU,
            SPECIES_WOBBUFFET,
            SPECIES_GIRAFARIG,
            SPECIES_PHANPY,
            SPECIES_RHYHORN,
            SPECIES_HERACROSS,
            SPECIES_PINSIR,
            SPECIES_MAREEP,
            SPECIES_SUNKERN,
            SPECIES_HOOTHOOT,
            SPECIES_SPINARAK,
            SPECIES_AIPOM,
            SPECIES_TEDDIURSA,
            SPECIES_PINECO,
            SPECIES_HOUNDOUR,
            SPECIES_SNUBBULL,
            SPECIES_STANTLER,
            SPECIES_MILTANK,
            SPECIES_GLIGAR,
            SPECIES_LEDYBA,
        ],
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_route_species(route_id) -> dict:
    """
    Get species dict for a route or dungeon.

    Args:
        route_id: Route number (int) or dungeon key (str)

    Returns:
        Dict mapping internal species ID to name
    """
    if isinstance(route_id, int):
        route = ROUTE_ENCOUNTERS.get(route_id)
    else:
        route = DUNGEON_ENCOUNTERS.get(route_id)

    if not route:
        return {}

    return {sid: SPECIES_NAMES.get(sid, f"Pokemon({sid})") for sid in route["walking"]}


def get_route_name(route_id) -> str:
    """Get the display name for a route or dungeon."""
    if isinstance(route_id, int):
        route = ROUTE_ENCOUNTERS.get(route_id)
    else:
        route = DUNGEON_ENCOUNTERS.get(route_id)

    return route["name"] if route else f"Unknown ({route_id})"


def get_available_routes() -> list:
    """Get list of available route numbers."""
    return sorted(ROUTE_ENCOUNTERS.keys())


def get_available_dungeons() -> list:
    """Get list of available dungeon keys."""
    return sorted(DUNGEON_ENCOUNTERS.keys())


def get_all_locations() -> dict:
    """Get combined dict of all routes and dungeons."""
    locations = {}
    for route_num, data in ROUTE_ENCOUNTERS.items():
        locations[route_num] = data
    for dungeon_key, data in DUNGEON_ENCOUNTERS.items():
        locations[dungeon_key] = data
    return locations
