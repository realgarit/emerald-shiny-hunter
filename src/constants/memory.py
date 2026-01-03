"""
Memory Address Constants for Pokemon Emerald (US).

These addresses are specific to the US version of Pokemon Emerald.
Memory addresses are used to read/write Pokemon data from the game's RAM.
"""

# =============================================================================
# Party Pokemon Memory Addresses
# =============================================================================
# Party structure layout (Emerald US):
# - Each Pokemon is 100 bytes (0x64)
# - Maximum 6 Pokemon in party

PARTY_COUNT_ADDR = 0x020244E9       # Number of Pokemon in party (1 byte)
PARTY_SLOT_1_ADDR = 0x020244EC      # First party Pokemon slot
PARTY_SLOT_SIZE = 0x64              # 100 bytes per party Pokemon

# Calculated slot addresses
PARTY_SLOT_2_ADDR = PARTY_SLOT_1_ADDR + PARTY_SLOT_SIZE      # 0x02024550
PARTY_SLOT_3_ADDR = PARTY_SLOT_1_ADDR + (PARTY_SLOT_SIZE * 2)  # 0x020245B4
PARTY_SLOT_4_ADDR = PARTY_SLOT_1_ADDR + (PARTY_SLOT_SIZE * 3)  # 0x02024618
PARTY_SLOT_5_ADDR = PARTY_SLOT_1_ADDR + (PARTY_SLOT_SIZE * 4)  # 0x0202467C
PARTY_SLOT_6_ADDR = PARTY_SLOT_1_ADDR + (PARTY_SLOT_SIZE * 5)  # 0x020246E0

# Party Pokemon structure offsets
PARTY_PV_OFFSET = 0x00              # Personality Value (4 bytes)
PARTY_TID_OFFSET = 0x04             # Trainer ID (2 bytes)
PARTY_SID_OFFSET = 0x06             # Secret ID (2 bytes)
PARTY_ENCRYPTED_OFFSET = 0x20       # Encrypted substructures start (48 bytes)

# Convenience: First party slot with offsets applied
PARTY_PV_ADDR = PARTY_SLOT_1_ADDR + PARTY_PV_OFFSET      # 0x020244EC
PARTY_TID_ADDR = PARTY_SLOT_1_ADDR + PARTY_TID_OFFSET    # 0x020244F0

# =============================================================================
# Enemy Pokemon Memory Addresses (Wild Encounters / Battles)
# =============================================================================
# Enemy Party structure (during battle):
# - Same structure as party Pokemon
# - Located in a different memory region

ENEMY_PV_ADDR = 0x02024744          # Enemy Personality Value (4 bytes)
ENEMY_TID_ADDR = 0x02024748         # Enemy OT Trainer ID (2 bytes)
ENEMY_SID_ADDR = 0x0202474A         # Enemy OT Secret ID (2 bytes)
ENEMY_SPECIES_ADDR = 0x0202474C     # Enemy Species ID (2 bytes) - battle structure
ENEMY_LEVEL_OFFSET = 0x54           # Level offset within party Pokemon struct (84 bytes)

# Battle structure area (for memory scanning)
BATTLE_STRUCTURE_START = 0x02024000
BATTLE_STRUCTURE_END = 0x02025000

# =============================================================================
# PC Box Storage Memory Addresses
# =============================================================================
# PC Box structure:
# - Each box holds 30 Pokemon
# - Each box Pokemon is 80 bytes
# - 14 boxes total

G_POKEMON_STORAGE_PTR = 0x03005D94  # Pointer to PC storage structure
BOX_DATA_OFFSET = 4                  # Box data starts 4 bytes after pointer

BOX_POKEMON_SIZE = 80               # 80 bytes per box Pokemon
POKEMON_PER_BOX = 30                # 30 Pokemon per box
NUM_BOXES = 14                      # 14 total boxes

# =============================================================================
# RNG (Random Number Generator) Address
# =============================================================================
# Emerald uses a linear congruential generator (LCG)
# Writing to this address can manipulate RNG for shiny hunting

RNG_SEED_ADDR = 0x03005D80          # RNG seed (4 bytes)

# =============================================================================
# Trainer ID Addresses (in SRAM/Save Data)
# =============================================================================
# These are typically read once and cached since they don't change

SRAM_TID_ADDR = 0x0E000000          # Save file Trainer ID location
SRAM_SID_ADDR = 0x0E000002          # Save file Secret ID location

# =============================================================================
# Pokemon Structure Offsets (Common to Party and Box)
# =============================================================================
# Gen III Pokemon data structure:
# - Bytes 0-3: Personality Value (unencrypted)
# - Bytes 4-5: Original Trainer ID (unencrypted)
# - Bytes 6-7: Original Trainer SID (unencrypted)
# - Bytes 8-11: Nickname (unencrypted)
# - Bytes 32-79: Encrypted substructures (4 x 12 bytes = 48 bytes)
#   - Growth: Species, Item, Experience, PP Bonuses, Friendship
#   - Attacks: Moves and PP
#   - EVs/Condition: EVs, Contest stats, Pokerus
#   - Misc: Met location, Origins, IVs, Ribbons

POKEMON_PV_OFFSET = 0x00            # Personality Value
POKEMON_OTID_OFFSET = 0x04          # Original Trainer ID
POKEMON_OTSID_OFFSET = 0x06         # Original Trainer Secret ID
POKEMON_NICKNAME_OFFSET = 0x08      # Nickname start
POKEMON_ENCRYPTED_OFFSET = 0x20     # Start of encrypted data

# Substructure size
SUBSTRUCTURE_SIZE = 12              # Each substructure is 12 bytes

# =============================================================================
# Substructure Orders
# =============================================================================
# PV % 24 determines the order of the 4 substructures (GAEM)
# G = Growth, A = Attacks, E = EVs/Condition, M = Misc

SUBSTRUCTURE_ORDERS = [
    "GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA",
    "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG",
    "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG",
    "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG"
]


def get_substructure_order(pv: int) -> str:
    """
    Get the substructure order string based on Personality Value.

    Args:
        pv: The Pokemon's Personality Value (32-bit)

    Returns:
        4-character string representing substructure order (e.g., "GAEM")
    """
    return SUBSTRUCTURE_ORDERS[pv % 24]


def get_party_slot_address(slot: int) -> int:
    """
    Get the memory address for a party slot (0-5).

    Args:
        slot: Party slot number (0-5)

    Returns:
        Memory address for that party slot
    """
    if not 0 <= slot < 6:
        raise ValueError(f"Invalid party slot: {slot}. Must be 0-5.")
    return PARTY_SLOT_1_ADDR + (slot * PARTY_SLOT_SIZE)


def get_box_slot_address(box_base: int, box_num: int, slot_num: int) -> int:
    """
    Calculate memory address for a specific PC box slot.

    Args:
        box_base: Base address of box storage (from G_POKEMON_STORAGE_PTR)
        box_num: Box number (0-13)
        slot_num: Slot within box (0-29)

    Returns:
        Memory address for that box slot
    """
    if not 0 <= box_num < NUM_BOXES:
        raise ValueError(f"Invalid box number: {box_num}. Must be 0-13.")
    if not 0 <= slot_num < POKEMON_PER_BOX:
        raise ValueError(f"Invalid slot number: {slot_num}. Must be 0-29.")

    offset = (box_num * POKEMON_PER_BOX + slot_num) * BOX_POKEMON_SIZE
    return box_base + offset


# =============================================================================
# Party Pokemon Structure Offsets (for healer.py and battle.py)
# =============================================================================
POKEMON_HP_OFFSET = 0x56              # Current HP in party struct (16-bit)
POKEMON_MAX_HP_OFFSET = 0x58          # Max HP in party struct (16-bit)
POKEMON_STATUS_OFFSET = 0x50          # Status condition (32-bit)

# =============================================================================
# Save Block Pointers (for healer.py)
# =============================================================================
G_SAVE_BLOCK_1_PTR = 0x03005D8C       # Pointer to SaveBlock1
SB1_PARTY_OFFSET = 0x234              # Party offset within SaveBlock1

# =============================================================================
# Battle State Memory Addresses (for battle.py)
# =============================================================================
# From pokeemerald decompilation symbols

# Battle state flags
G_BATTLE_TYPE_FLAGS = 0x02022fec      # gBattleTypeFlags (32-bit) - non-zero = in battle
G_BATTLE_OUTCOME = 0x0202433a         # gBattleOutcome (8-bit)

# Battle Pokemon data
G_BATTLE_MONS = 0x02024084            # gBattleMons array base
BATTLE_MON_SIZE = 0x58                # Size of each BattlePokemon struct (88 bytes)
BATTLE_MON_HP_OFFSET = 0x28           # HP offset within BattlePokemon (16-bit)
BATTLE_MON_MAX_HP_OFFSET = 0x2A       # Max HP offset within BattlePokemon (16-bit)

# Enemy battle mon (index 1 in singles battles, player = 0)
G_ENEMY_BATTLE_MON = G_BATTLE_MONS + BATTLE_MON_SIZE  # 0x020240DC

# Move learning detection
G_MOVE_TO_LEARN = 0x020244e2          # gMoveToLearn (16-bit) - non-zero when learning prompt

# Battle outcome constants
BATTLE_OUTCOME_NONE = 0
BATTLE_OUTCOME_WON = 1
BATTLE_OUTCOME_LOST = 2
BATTLE_OUTCOME_DREW = 3
BATTLE_OUTCOME_RAN = 4
BATTLE_OUTCOME_PLAYER_TELEPORTED = 5
BATTLE_OUTCOME_MON_FLED = 6
BATTLE_OUTCOME_CAUGHT = 7
