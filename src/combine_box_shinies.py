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

# Suppress GBA debug output
sys.stderr = open(os.devnull, 'w')
mgba.log.silence()

PROJECT_ROOT = Path(__file__).parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
SAVE_STATES_DIR = PROJECT_ROOT / "save_states"

# Memory addresses
G_POKEMON_STORAGE_PTR = 0x03005D94
BOX_DATA_OFFSET = 4  # Box data starts 4 bytes after storage pointer

# Structure sizes
BOX_POKEMON_SIZE = 80   # 80 bytes per Pokemon in box
PARTY_POKEMON_SIZE = 100  # 100 bytes per Pokemon in party
POKEMON_PER_BOX = 30
NUM_BOXES = 14

# Party slot address
PARTY_SLOT_1_ADDR = 0x020244EC

# Enemy Pokemon address (where shiny wild Pokemon are during battle)
ENEMY_PV_ADDR = 0x02024744

# Species ID mappings (internal -> name)
# Internal IDs need offset correction to match National Dex
INTERNAL_SPECIES = {
    286: ("Poochyena", -25),   # 286 - 25 = 261
    288: ("Zigzagoon", -25),   # 288 - 25 = 263
    290: ("Wurmple", -25),     # 290 - 25 = 265
    295: ("Lotad", -25),       # 295 - 25 = 270
    298: ("Seedot", -25),      # 298 - 25 = 273
    392: ("Ralts", -122),      # 392 - 122 = 270 (unique offset!)
}

# National Dex IDs (for display)
NATIONAL_SPECIES = {
    261: "Poochyena",
    263: "Zigzagoon",
    265: "Wurmple",
    270: "Lotad",
    273: "Seedot",
    277: "Treecko",
    280: "Torchic",
    283: "Mudkip",
}

def read_u32(core, address):
    """Read 32-bit unsigned integer from memory"""
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    b2 = core._core.busRead8(core._core, address + 2)
    b3 = core._core.busRead8(core._core, address + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

def read_u8(core, address):
    """Read 8-bit unsigned integer from memory"""
    return core._core.busRead8(core._core, address)

def read_bytes(core, address, length):
    """Read multiple bytes from memory"""
    return bytes([core._core.busRead8(core._core, address + i) for i in range(length)])

def write_bytes(core, address, data):
    """Write multiple bytes to memory"""
    for i, byte in enumerate(data):
        core._core.busWrite8(core._core, address + i, byte)

def get_substructure_order(pv):
    """Get the order of substructures based on PV"""
    order_index = pv % 24
    orders = [
        "GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA",
        "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG",
        "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG",
        "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG"
    ]
    return orders[order_index]

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
    enc_offset = growth_pos * 12

    enc_addr = base_addr + 0x20 + enc_offset
    enc_val = read_u32(core, enc_addr)
    xor_key = otid ^ pv
    dec_val = enc_val ^ xor_key
    species_id = dec_val & 0xFFFF

    # Try to get species name
    # First check if it's an internal ID
    if species_id in INTERNAL_SPECIES:
        name, offset = INTERNAL_SPECIES[species_id]
        return pv, species_id, name

    # Check if it's a National Dex ID
    if species_id in NATIONAL_SPECIES:
        return pv, species_id, NATIONAL_SPECIES[species_id]

    # Try offset corrections
    for offset in [-25, -122]:
        corrected = species_id + offset
        if corrected in NATIONAL_SPECIES:
            return pv, species_id, NATIONAL_SPECIES[corrected]

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

def convert_party_to_box(party_data):
    """
    Convert 100-byte party Pokemon to 80-byte box format.
    Box format uses only the first 80 bytes.
    """
    return party_data[:BOX_POKEMON_SIZE]

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
