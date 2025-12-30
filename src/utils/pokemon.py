"""
Pokemon data utilities for Pokemon Emerald Shiny Hunter.

Provides functions for:
- Species decryption from encrypted Pokemon data
- Shiny value calculation
- Substructure handling
"""

from typing import Tuple, Dict, Optional

from .memory import read_u8, read_u16, read_u32

# Import constants
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from constants.memory import SUBSTRUCTURE_ORDERS, SUBSTRUCTURE_SIZE, POKEMON_ENCRYPTED_OFFSET
from constants.species import NATIONAL_DEX, INTERNAL_TO_NATIONAL, get_national_dex, get_internal_id


def get_substructure_order(pv: int) -> str:
    """
    Get the substructure order string based on Personality Value.

    Args:
        pv: The Pokemon's Personality Value (32-bit)

    Returns:
        4-character string representing substructure order (e.g., "GAEM")
    """
    return SUBSTRUCTURE_ORDERS[pv % 24]


def decrypt_species(
    core,
    base_addr: int,
    pokemon_species: Dict[int, str],
    debug: bool = False
) -> Tuple[int, int, str]:
    """
    Decrypt species from Pokemon structure (works for party and box Pokemon).

    Gen III Pokemon data structure:
    - Bytes 0-3: PV (unencrypted)
    - Bytes 4-7: OTID (unencrypted)
    - Bytes 32-79: Encrypted substructures (4 x 12 bytes)

    Decryption: encrypted_val ^ (otid ^ pv)

    Args:
        core: mGBA core instance
        base_addr: Base address of Pokemon structure
        pokemon_species: Dict mapping species ID to name
        debug: If True, print debug information

    Returns:
        Tuple of (pv, species_id, species_name)
    """
    pv = read_u32(core, base_addr)
    if pv == 0:
        return 0, 0, "(empty)"

    otid = read_u32(core, base_addr + 4)

    # Get substructure order and find Growth position
    order = get_substructure_order(pv)
    growth_pos = order.index('G')
    enc_offset = growth_pos * SUBSTRUCTURE_SIZE

    # Read and decrypt
    enc_addr = base_addr + POKEMON_ENCRYPTED_OFFSET + enc_offset
    enc_val = read_u32(core, enc_addr)
    xor_key = otid ^ pv
    dec_val = enc_val ^ xor_key
    species_id = dec_val & 0xFFFF

    if debug:
        print(f"    [DEBUG] PV=0x{pv:08X}, OTID=0x{otid:08X}, Order='{order}'")
        print(f"    [DEBUG] Growth at pos {growth_pos}, offset={enc_offset}")
        print(f"    [DEBUG] Encrypted=0x{enc_val:08X}, XOR=0x{xor_key:08X}, Decrypted=0x{dec_val:08X}")
        print(f"    [DEBUG] Species ID={species_id}")

    # Check direct match
    if species_id in pokemon_species:
        return pv, species_id, pokemon_species[species_id]

    # Try National Dex conversion (species_id might be National Dex number)
    # If species_id is a National Dex number (1-386), convert to internal ID
    if species_id in NATIONAL_DEX:
        internal_id = NATIONAL_DEX[species_id]
        if internal_id in pokemon_species:
            if debug:
                print(f"    [DEBUG] Found via National Dex conversion: Dex #{species_id} -> Internal {internal_id}")
            return pv, internal_id, pokemon_species[internal_id]

    # Try reverse: if species_id is internal ID, check if National Dex number is in dict
    national_dex = get_national_dex(species_id)
    if national_dex in pokemon_species:
        if debug:
            print(f"    [DEBUG] Found via reverse National Dex: Internal {species_id} -> Dex #{national_dex}")
        return pv, national_dex, pokemon_species[national_dex]

    # Fallback: try offset corrections for edge cases
    for offset_correction in [-25, 25]:  # Only the Gen III offset (internal - national = 25)
        corrected_id = species_id + offset_correction
        if corrected_id in pokemon_species:
            if debug:
                print(f"    [DEBUG] Found with offset correction {offset_correction}: {corrected_id}")
            return pv, corrected_id, pokemon_species[corrected_id]

    return pv, species_id, f"Unknown({species_id})"


def decrypt_species_extended(
    core,
    pv_addr: int,
    tid_addr: int,
    pokemon_species: Dict[int, str],
    debug: bool = False
) -> Tuple[int, str]:
    """
    Extended species decryption with multiple offset and TID variations.

    Tries multiple combinations to find the correct species ID.
    Used for wild encounters where the exact structure may vary.

    Args:
        core: mGBA core instance
        pv_addr: Address of Personality Value
        tid_addr: Address of Trainer ID
        pokemon_species: Dict mapping species ID to name
        debug: If True, print debug information

    Returns:
        Tuple of (species_id, species_name)
    """
    pv = read_u32(core, pv_addr)
    if pv == 0:
        return 0, "(empty)"

    tid_from_memory = read_u16(core, tid_addr)
    sid_from_memory = read_u16(core, pv_addr + 6)

    # Try multiple OT TID values
    ot_tid_values = [0, tid_from_memory, (tid_from_memory ^ sid_from_memory) & 0xFFFF]

    if debug:
        print(f"    [DEBUG] PV=0x{pv:08X}, TID={tid_from_memory}, SID={sid_from_memory}")
        print(f"    [DEBUG] Trying OT_TID values: {ot_tid_values}")

    for ot_tid in ot_tid_values:
        # Prioritize offset +32 (known working)
        offsets_to_try = [32, 0, 8, 16, 24, 40, 48]

        for data_offset in offsets_to_try:
            data_start = pv_addr + data_offset
            order = get_substructure_order(pv)

            # Try position 2 first (known working), then others
            positions_to_try = [2, 0, 1, 3]

            for substructure_pos in positions_to_try:
                offset = substructure_pos * SUBSTRUCTURE_SIZE
                encrypted_val = read_u32(core, data_start + offset)

                # Decrypt
                xor_key = (ot_tid & 0xFFFF) ^ pv
                decrypted_val = encrypted_val ^ xor_key
                species_id = decrypted_val & 0xFFFF

                # Check direct match
                if species_id in pokemon_species:
                    if debug:
                        print(f"    [DEBUG] Found: OT_TID={ot_tid}, offset +{data_offset}, pos {substructure_pos}")
                    return species_id, pokemon_species[species_id]

                # Try National Dex conversion (species_id might be National Dex number)
                if species_id in NATIONAL_DEX:
                    internal_id = NATIONAL_DEX[species_id]
                    if internal_id in pokemon_species:
                        if debug:
                            print(f"    [DEBUG] Found via National Dex: Dex #{species_id} -> Internal {internal_id}")
                        return internal_id, pokemon_species[internal_id]

                # Try reverse: if species_id is internal ID, check if National Dex is in dict
                national_dex = get_national_dex(species_id)
                if national_dex in pokemon_species:
                    if debug:
                        print(f"    [DEBUG] Found via reverse National Dex: Internal {species_id} -> Dex #{national_dex}")
                    return national_dex, pokemon_species[national_dex]

                # Fallback: try Gen III offset correction
                for offset_correction in [-25, 25]:
                    corrected_id = species_id + offset_correction
                    if corrected_id in pokemon_species:
                        if debug:
                            print(f"    [DEBUG] Found with correction {offset_correction}: {corrected_id}")
                        return corrected_id, pokemon_species[corrected_id]

    return 0, f"Unknown (decryption failed)"


def calculate_shiny_value(tid: int, sid: int, pv: int) -> Tuple[bool, int, dict]:
    """
    Calculate if a Pokemon is shiny using Gen III formula.

    Formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8

    Args:
        tid: Trainer ID
        sid: Secret ID
        pv: Personality Value

    Returns:
        Tuple of (is_shiny, shiny_value, details_dict)
    """
    pv_low = pv & 0xFFFF
    pv_high = (pv >> 16) & 0xFFFF
    tid_xor_sid = tid ^ sid
    pv_xor = pv_low ^ pv_high
    shiny_value = tid_xor_sid ^ pv_xor

    is_shiny = shiny_value < 8

    details = {
        'pv_low': pv_low,
        'pv_high': pv_high,
        'tid_xor_sid': tid_xor_sid,
        'pv_xor': pv_xor,
        'shiny_value': shiny_value
    }

    return is_shiny, shiny_value, details


def check_shiny(core, pv_addr: int, tid: int, sid: int) -> Tuple[bool, int, int, dict]:
    """
    Check if a Pokemon at the given address is shiny.

    Args:
        core: mGBA core instance
        pv_addr: Address of Personality Value
        tid: Trainer ID
        sid: Secret ID

    Returns:
        Tuple of (is_shiny, pv, shiny_value, details_dict)
    """
    pv = read_u32(core, pv_addr)

    if pv == 0:
        return False, 0, 0, {}

    is_shiny, shiny_value, details = calculate_shiny_value(tid, sid, pv)
    return is_shiny, pv, shiny_value, details


def convert_party_to_box(party_data: bytes) -> bytes:
    """
    Convert 100-byte party Pokemon to 80-byte box format.

    Box format uses only the first 80 bytes of the party structure.

    Args:
        party_data: 100-byte party Pokemon data

    Returns:
        80-byte box Pokemon data
    """
    return party_data[:80]
