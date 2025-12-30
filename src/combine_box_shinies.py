#!/usr/bin/env python3
"""
Combine shiny Pokemon from multiple save states into PC boxes.
Uses base_with_boxes.ss0 (created by create_base_savestate.py) as the base.
"""

import mgba.core
import mgba.log
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    G_POKEMON_STORAGE_PTR, BOX_DATA_OFFSET,
    BOX_POKEMON_SIZE, POKEMON_PER_BOX, NUM_BOXES,
    PARTY_SLOT_1_ADDR, PARTY_SLOT_SIZE,
    ENEMY_PV_ADDR,
    SPECIES_NAMES, NATIONAL_DEX, INTERNAL_TO_NATIONAL,
    get_national_dex, get_species_name,
)
from utils import (
    read_u32, read_u8, read_bytes, write_bytes,
    get_substructure_order, convert_party_to_box,
)
from constants.memory import SUBSTRUCTURE_SIZE, POKEMON_ENCRYPTED_OFFSET

# Suppress GBA debug output
sys.stderr = open(os.devnull, 'w')
mgba.log.silence()

PROJECT_ROOT = Path(__file__).parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
SAVE_STATES_DIR = PROJECT_ROOT / "save_states"

# Party Pokemon size (100 bytes, vs 80 for box)
PARTY_POKEMON_SIZE = 100


def decrypt_species(core, base_addr, struct_size=80):
    """
    Decrypt species from Pokemon structure.
    Works for both BoxPokemon (80 bytes) and party Pokemon (100 bytes).
    Returns (pv, species_id, species_name)
    """
    pv = read_u32(core, base_addr)
    if pv == 0:
        return 0, 0, "(empty)"

    otid = read_u32(core, base_addr + 4)

    # Encrypted data at offset 0x20
    order = get_substructure_order(pv)
    growth_pos = order.index('G')
    enc_offset = growth_pos * SUBSTRUCTURE_SIZE

    enc_addr = base_addr + POKEMON_ENCRYPTED_OFFSET + enc_offset
    enc_val = read_u32(core, enc_addr)
    xor_key = otid ^ pv
    dec_val = enc_val ^ xor_key
    species_id = dec_val & 0xFFFF

    # Try to get species name using centralized lookups
    # First check if it's a known internal ID
    if species_id in SPECIES_NAMES:
        return pv, species_id, SPECIES_NAMES[species_id]

    # Check if it's a National Dex number and convert to internal
    if species_id in NATIONAL_DEX:
        internal_id = NATIONAL_DEX[species_id]
        if internal_id in SPECIES_NAMES:
            return pv, internal_id, SPECIES_NAMES[internal_id]

    # Try reverse lookup (species_id might be internal, check for national dex name)
    national_dex = get_national_dex(species_id)
    if national_dex > 0:
        # We found a valid national dex, get the name
        name = get_species_name(species_id)
        if not name.startswith("Unknown"):
            return pv, species_id, name

    # Fallback: try +/- 25 offset (Gen III internal vs national)
    for offset in [-25, 25]:
        corrected = species_id + offset
        if corrected in SPECIES_NAMES:
            return pv, corrected, SPECIES_NAMES[corrected]
        if corrected in NATIONAL_DEX:
            internal_id = NATIONAL_DEX[corrected]
            if internal_id in SPECIES_NAMES:
                return pv, internal_id, SPECIES_NAMES[internal_id]

    return pv, species_id, f"Unknown({species_id})"


def get_box_storage_base(core):
    """Get the base address where box Pokemon data starts."""
    storage_ptr = read_u32(core, G_POKEMON_STORAGE_PTR)
    if storage_ptr == 0:
        return None
    return storage_ptr + BOX_DATA_OFFSET


def get_box_slot_address(box_base, box_num, slot_num):
    """
    Calculate memory address for a specific box slot.
    box_num: 0-13 (Box 1 to Box 14)
    slot_num: 0-29 (30 slots per box)
    """
    offset = (box_num * POKEMON_PER_BOX + slot_num) * BOX_POKEMON_SIZE
    return box_base + offset


def scan_boxes(core, box_base):
    """Scan all boxes and return occupancy info."""
    print("\n[*] Scanning PC boxes...")

    total_occupied = 0
    first_empty = None

    for box_num in range(NUM_BOXES):
        occupied = 0
        for slot_num in range(POKEMON_PER_BOX):
            addr = get_box_slot_address(box_base, box_num, slot_num)
            pv = read_u32(core, addr)
            if pv != 0:
                occupied += 1
            elif first_empty is None:
                first_empty = (box_num, slot_num)

        if occupied > 0:
            print(f"    Box {box_num + 1}: {occupied}/30 Pokemon")
            total_occupied += occupied

    print(f"\n    Total Pokemon in boxes: {total_occupied}")
    if first_empty:
        print(f"    First empty slot: Box {first_empty[0] + 1}, Slot {first_empty[1] + 1}")

    return first_empty


def extract_pokemon_from_save(save_path):
    """Load a save state and extract the shiny Pokemon from enemy slot (during battle)."""
    print(f"\n[*] Loading: {save_path.name}")

    core = mgba.core.load_path(ROM_PATH)
    if not core:
        raise RuntimeError(f"Failed to load ROM")

    core.reset()

    with open(save_path, 'rb') as f:
        state_data = f.read()

    core.load_raw_state(state_data)

    # Run frames to stabilize
    for _ in range(60):
        core.run_frame()

    # Read Pokemon from enemy slot (shiny wild Pokemon during battle)
    # Enemy Pokemon structure is 100 bytes like party Pokemon
    enemy_data = read_bytes(core, ENEMY_PV_ADDR, PARTY_POKEMON_SIZE)
    pv, species_id, species_name = decrypt_species(core, ENEMY_PV_ADDR, PARTY_POKEMON_SIZE)

    print(f"    Extracted: {species_name} (ID={species_id}, PV=0x{pv:08X})")

    return enemy_data, species_name, pv


def combine_box_shinies():
    """Main function to combine shinies into PC boxes."""
    print("=" * 70)
    print("Combining Shiny Pokemon into PC Boxes")
    print("=" * 70)

    # Use base_with_boxes.ss0 as the base (created from .sav file with box data loaded)
    base_path = SAVE_STATES_DIR / "base_with_boxes.ss0"
    if not base_path.exists():
        print(f"\n[!] Base file not found: {base_path.name}")
        print("    Run: python3 src/debug/create_base_savestate.py")
        return

    print(f"\n[*] Using base: {base_path.name}")

    # Find shiny save states (exclude base and combined files)
    shiny_saves = []
    for f in SAVE_STATES_DIR.glob("*.ss0"):
        name = f.name.lower()
        if "base" in name:
            continue
        if "combined" in name:
            continue
        shiny_saves.append(f)

    if not shiny_saves:
        print(f"\n[!] No shiny save states found in {SAVE_STATES_DIR}")
        return

    print(f"\n[*] Found {len(shiny_saves)} shiny save state(s):")
    for s in sorted(shiny_saves):
        print(f"    - {s.name}")

    # Extract Pokemon from all shiny saves
    print("\n" + "=" * 70)
    print("Extracting Pokemon from save states")
    print("=" * 70)

    pokemon_to_add = []
    processed_saves = []  # Track successfully processed save states
    for save_path in sorted(shiny_saves):
        try:
            party_data, species_name, pv = extract_pokemon_from_save(save_path)
            if pv != 0:
                pokemon_to_add.append({
                    'data': party_data,
                    'species': species_name,
                    'pv': pv,
                    'source': save_path.name
                })
                processed_saves.append(save_path)
        except Exception as e:
            print(f"    [!] Failed: {e}")

    if not pokemon_to_add:
        print("\n[!] No Pokemon extracted!")
        return

    print(f"\n[+] Extracted {len(pokemon_to_add)} Pokemon")

    # Load base save and find box storage
    print("\n" + "=" * 70)
    print("Loading base save and scanning boxes")
    print("=" * 70)

    core = mgba.core.load_path(ROM_PATH)
    core.reset()

    with open(base_path, 'rb') as f:
        core.load_raw_state(f.read())

    for _ in range(60):
        core.run_frame()

    # Get box storage base address
    box_base = get_box_storage_base(core)
    if box_base is None:
        print("\n[!] Could not find box storage pointer!")
        print("    Make sure base.ss0 is a save state with the PC boxes open")
        return

    print(f"\n[*] Box storage at: 0x{box_base:08X}")

    # Scan boxes
    first_empty = scan_boxes(core, box_base)

    if first_empty is None:
        print("\n[!] All boxes are full!")
        return

    # Add Pokemon to boxes
    print("\n" + "=" * 70)
    print("Adding Pokemon to boxes")
    print("=" * 70)

    current_box, current_slot = first_empty
    added = 0

    for pokemon in pokemon_to_add:
        if current_box >= NUM_BOXES:
            print(f"\n[!] Boxes full! Added {added}/{len(pokemon_to_add)}")
            break

        # Get address for this slot
        addr = get_box_slot_address(box_base, current_box, current_slot)

        # Convert to box format and write
        box_data = convert_party_to_box(pokemon['data'])
        write_bytes(core, addr, box_data)

        added += 1
        print(f"    [{added}/{len(pokemon_to_add)}] {pokemon['species']} -> Box {current_box + 1}, Slot {current_slot + 1}")

        # Move to next slot
        current_slot += 1
        if current_slot >= POKEMON_PER_BOX:
            current_slot = 0
            current_box += 1

    # Save combined state
    print("\n" + "=" * 70)
    print("Saving combined save state")
    print("=" * 70)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = SAVE_STATES_DIR / f"combined_boxes_{timestamp}.ss0"

    state_data = core.save_raw_state()
    try:
        from cffi import FFI
        ffi = FFI()
        state_bytes = bytes(ffi.buffer(state_data))
    except:
        if hasattr(state_data, '__len__'):
            state_bytes = b''.join(bytes([state_data[i]]) for i in range(len(state_data)))
        else:
            state_bytes = bytes(state_data)

    with open(output_path, 'wb') as f:
        f.write(state_bytes)

    print(f"\n[+] Saved: {output_path.name}")
    print(f"[+] Added {added} Pokemon to boxes!")

    # Archive processed save states
    print("\n" + "=" * 70)
    print("Archiving processed save states")
    print("=" * 70)

    archive_dir = SAVE_STATES_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)

    archived = 0
    for save_path in processed_saves:
        try:
            dest = archive_dir / save_path.name
            save_path.rename(dest)
            print(f"    Archived: {save_path.name}")
            archived += 1
        except Exception as e:
            print(f"    [!] Failed to archive {save_path.name}: {e}")

    print(f"\n[+] Archived {archived} save state(s) to archive/")

    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)
    print(f"\nLoad '{output_path.name}' in mGBA to see your Pokemon in the boxes.")


def main():
    combine_box_shinies()


if __name__ == "__main__":
    main()
