#!/usr/bin/env python3
"""
Select Best Shinies - Debug script to identify and keep the best shinies by IV total.

This script:
1. Creates a valid savestate from base_with_boxes.ss0
2. Scans boxes for Pokemon grouped by species
3. For each species with multiple Pokemon, identifies the top 3 by total IVs
4. Asks user confirmation to delete the rest
5. Outputs a new savestate with only the best kept

IV Structure (Gen III):
- IVs are in the Misc (M) substruct at offset 0x04
- Bit-packed: HP(5) | ATK(5) | DEF(5) | SPD(5) | SPA(5) | SPD(5) = 30 bits
"""

import mgba.core
import mgba.log
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import (
    G_POKEMON_STORAGE_PTR, BOX_DATA_OFFSET,
    BOX_POKEMON_SIZE, POKEMON_PER_BOX, NUM_BOXES,
    SPECIES_NAMES, NATIONAL_DEX,
    get_national_dex, get_species_name,
)
from utils import read_u32, read_bytes, write_bytes
from constants.memory import SUBSTRUCTURE_SIZE, POKEMON_ENCRYPTED_OFFSET, SUBSTRUCTURE_ORDERS

# Suppress GBA debug output
sys.stderr = open(os.devnull, 'w')
mgba.log.silence()

PROJECT_ROOT = Path(__file__).parent.parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
SAVE_STATES_DIR = PROJECT_ROOT / "save_states"


def get_substructure_order(pv: int) -> str:
    """Get the substructure order string based on Personality Value."""
    return SUBSTRUCTURE_ORDERS[pv % 24]


def decrypt_misc_substruct(core, base_addr: int) -> int:
    """
    Decrypt the Misc (M) substruct and return the raw 32-bit IV data.

    The Misc substruct contains IVs at offset 0x04 within the substruct.
    IVs are stored as a 32-bit value with bit-packed fields.
    """
    pv = read_u32(core, base_addr)
    if pv == 0:
        return 0

    otid = read_u32(core, base_addr + 4)

    # Find Misc (M) substruct position
    order = get_substructure_order(pv)
    misc_pos = order.index('M')
    misc_offset = misc_pos * SUBSTRUCTURE_SIZE

    # The IV data is at offset 0x04 within the Misc substruct
    # Misc substruct starts at base_addr + 0x20 (encrypted data start) + misc_offset
    iv_addr = base_addr + POKEMON_ENCRYPTED_OFFSET + misc_offset + 4

    # Read and decrypt the IV data
    enc_val = read_u32(core, iv_addr)
    xor_key = otid ^ pv
    dec_val = enc_val ^ xor_key

    return dec_val


def extract_ivs(iv_data: int) -> dict:
    """
    Extract individual IVs from the packed 32-bit value.

    Bit layout (from LSB):
    - Bits 0-4: HP IV (5 bits, 0-31)
    - Bits 5-9: Attack IV (5 bits, 0-31)
    - Bits 10-14: Defense IV (5 bits, 0-31)
    - Bits 15-19: Speed IV (5 bits, 0-31)
    - Bits 20-24: Sp. Attack IV (5 bits, 0-31)
    - Bits 25-29: Sp. Defense IV (5 bits, 0-31)
    """
    return {
        'hp': iv_data & 0x1F,
        'atk': (iv_data >> 5) & 0x1F,
        'def': (iv_data >> 10) & 0x1F,
        'spe': (iv_data >> 15) & 0x1F,
        'spa': (iv_data >> 20) & 0x1F,
        'spd': (iv_data >> 25) & 0x1F,
    }


def get_iv_total(ivs: dict) -> int:
    """Calculate total IV sum (max 186)."""
    return sum(ivs.values())


def decrypt_species(core, base_addr: int):
    """
    Decrypt species from Pokemon structure.
    Returns (pv, species_id, species_name)
    """
    pv = read_u32(core, base_addr)
    if pv == 0:
        return 0, 0, "(empty)"

    otid = read_u32(core, base_addr + 4)

    # Find Growth (G) substruct for species
    order = get_substructure_order(pv)
    growth_pos = order.index('G')
    enc_offset = growth_pos * SUBSTRUCTURE_SIZE

    enc_addr = base_addr + POKEMON_ENCRYPTED_OFFSET + enc_offset
    enc_val = read_u32(core, enc_addr)
    xor_key = otid ^ pv
    dec_val = enc_val ^ xor_key
    species_id = dec_val & 0xFFFF

    # Try to get species name
    if species_id in SPECIES_NAMES:
        return pv, species_id, SPECIES_NAMES[species_id]

    if species_id in NATIONAL_DEX:
        internal_id = NATIONAL_DEX[species_id]
        if internal_id in SPECIES_NAMES:
            return pv, internal_id, SPECIES_NAMES[internal_id]

    national_dex = get_national_dex(species_id)
    if national_dex > 0:
        name = get_species_name(species_id)
        if not name.startswith("Unknown"):
            return pv, species_id, name

    for offset in [-25, 25]:
        corrected = species_id + offset
        if corrected in SPECIES_NAMES:
            return pv, corrected, SPECIES_NAMES[corrected]

    return pv, species_id, f"Unknown({species_id})"


def get_box_storage_base(core):
    """Get the base address where box Pokemon data starts."""
    storage_ptr = read_u32(core, G_POKEMON_STORAGE_PTR)
    if storage_ptr == 0:
        return None
    return storage_ptr + BOX_DATA_OFFSET


def get_box_slot_address(box_base: int, box_num: int, slot_num: int) -> int:
    """Calculate memory address for a specific box slot."""
    offset = (box_num * POKEMON_PER_BOX + slot_num) * BOX_POKEMON_SIZE
    return box_base + offset


def format_ivs(ivs: dict) -> str:
    """Format IVs for display."""
    return (f"HP:{ivs['hp']:2d} ATK:{ivs['atk']:2d} DEF:{ivs['def']:2d} "
            f"SPE:{ivs['spe']:2d} SPA:{ivs['spa']:2d} SPD:{ivs['spd']:2d}")


def scan_boxes_with_ivs(core, box_base: int) -> list:
    """
    Scan all boxes and return list of Pokemon with their IVs.
    Returns list of dicts with: box, slot, addr, species, species_name, pv, ivs, iv_total
    """
    pokemon_list = []

    for box_num in range(NUM_BOXES):
        for slot_num in range(POKEMON_PER_BOX):
            addr = get_box_slot_address(box_base, box_num, slot_num)
            pv = read_u32(core, addr)

            if pv != 0:
                _, species_id, species_name = decrypt_species(core, addr)
                iv_data = decrypt_misc_substruct(core, addr)
                ivs = extract_ivs(iv_data)
                iv_total = get_iv_total(ivs)

                pokemon_list.append({
                    'box': box_num,
                    'slot': slot_num,
                    'addr': addr,
                    'species': species_id,
                    'species_name': species_name,
                    'pv': pv,
                    'ivs': ivs,
                    'iv_total': iv_total,
                })

    return pokemon_list


def clear_box_slot(core, addr: int):
    """Clear a box slot by zeroing out all 80 bytes."""
    empty_data = bytes(BOX_POKEMON_SIZE)
    write_bytes(core, addr, empty_data)


def reorganize_boxes(core, box_base: int, pokemon_list: list):
    """
    Reorganize Pokemon in boxes: sort by species name, then by IV total (descending).
    Pokemon are placed sequentially starting from Box 1, Slot 1.
    """
    if not pokemon_list:
        return

    # First, read all Pokemon data from memory before we start moving things
    pokemon_with_data = []
    for pokemon in pokemon_list:
        data = read_bytes(core, pokemon['addr'], BOX_POKEMON_SIZE)
        pokemon_with_data.append({
            **pokemon,
            'data': data
        })

    # Sort by species name (alphabetically), then by IV total (descending)
    sorted_pokemon = sorted(
        pokemon_with_data,
        key=lambda x: (x['species_name'], -x['iv_total'])
    )

    # Clear all boxes first
    print("\n[*] Clearing all box slots...")
    for box_num in range(NUM_BOXES):
        for slot_num in range(POKEMON_PER_BOX):
            addr = get_box_slot_address(box_base, box_num, slot_num)
            clear_box_slot(core, addr)

    # Write Pokemon back in sorted order
    print("[*] Writing Pokemon in sorted order...")
    current_species = None
    for i, pokemon in enumerate(sorted_pokemon):
        box_num = i // POKEMON_PER_BOX
        slot_num = i % POKEMON_PER_BOX

        if box_num >= NUM_BOXES:
            print(f"[!] Warning: Not enough box space for all Pokemon!")
            break

        addr = get_box_slot_address(box_base, box_num, slot_num)
        write_bytes(core, addr, pokemon['data'])

        # Print species header when species changes
        if pokemon['species_name'] != current_species:
            current_species = pokemon['species_name']
            print(f"\n    {current_species}:")

        print(f"      Box {box_num+1:2d} Slot {slot_num+1:2d}: "
              f"{format_ivs(pokemon['ivs'])} | Total: {pokemon['iv_total']:3d}")

    print(f"\n[+] Reorganized {len(sorted_pokemon)} Pokemon")


def select_best_shinies():
    """Main function to select best shinies by IV total."""
    print("=" * 70)
    print("Select Best Shinies by IV Total")
    print("=" * 70)

    # Load base save state
    base_path = SAVE_STATES_DIR / "base_with_boxes.ss0"
    if not base_path.exists():
        print(f"\n[!] Base file not found: {base_path.name}")
        print("    Run: python3 src/debug/create_base_savestate.py")
        return

    print(f"\n[*] Loading: {base_path.name}")

    core = mgba.core.load_path(ROM_PATH)
    if not core:
        print("[!] Failed to load ROM")
        return

    core.reset()

    with open(base_path, 'rb') as f:
        core.load_raw_state(f.read())

    # Run frames to stabilize
    for _ in range(60):
        core.run_frame()

    # Get box storage
    box_base = get_box_storage_base(core)
    if box_base is None:
        print("\n[!] Could not find box storage pointer!")
        return

    print(f"[*] Box storage at: 0x{box_base:08X}")

    # Scan all boxes with IV data
    print("\n[*] Scanning boxes for Pokemon with IVs...")
    pokemon_list = scan_boxes_with_ivs(core, box_base)

    if not pokemon_list:
        print("\n[!] No Pokemon found in boxes!")
        return

    print(f"[+] Found {len(pokemon_list)} Pokemon in boxes")

    # Group by species
    species_groups = defaultdict(list)
    for pokemon in pokemon_list:
        species_groups[pokemon['species_name']].append(pokemon)

    print(f"[+] {len(species_groups)} unique species")

    # Process each species with multiple Pokemon
    print("\n" + "=" * 70)
    print("Species Analysis")
    print("=" * 70)

    to_delete = []

    for species_name, group in sorted(species_groups.items()):
        count = len(group)

        if count == 1:
            print(f"\n{species_name}: 1 Pokemon (keeping)")
            pokemon = group[0]
            print(f"  Box {pokemon['box']+1} Slot {pokemon['slot']+1}: "
                  f"{format_ivs(pokemon['ivs'])} | Total: {pokemon['iv_total']}")
            continue

        # Sort by IV total (descending)
        sorted_group = sorted(group, key=lambda x: x['iv_total'], reverse=True)

        print(f"\n{'='*70}")
        print(f"{species_name}: {count} Pokemon")
        print(f"{'='*70}")

        # Show all Pokemon for this species
        print("\nAll Pokemon (sorted by IV total):")
        for i, pokemon in enumerate(sorted_group, 1):
            marker = "KEEP" if i <= 3 else "DELETE"
            print(f"  {i:2d}. [{marker:6s}] Box {pokemon['box']+1:2d} Slot {pokemon['slot']+1:2d}: "
                  f"{format_ivs(pokemon['ivs'])} | Total: {pokemon['iv_total']:3d}")

        if count > 3:
            # Mark Pokemon beyond top 3 for deletion
            delete_candidates = sorted_group[3:]

            print(f"\nTop 3 to KEEP:")
            for i, pokemon in enumerate(sorted_group[:3], 1):
                print(f"  {i}. Box {pokemon['box']+1} Slot {pokemon['slot']+1}: "
                      f"{format_ivs(pokemon['ivs'])} | Total: {pokemon['iv_total']}")

            print(f"\n{len(delete_candidates)} Pokemon to DELETE:")
            for pokemon in delete_candidates:
                print(f"  - Box {pokemon['box']+1} Slot {pokemon['slot']+1}: "
                      f"{format_ivs(pokemon['ivs'])} | Total: {pokemon['iv_total']}")

            # Ask for confirmation
            response = input(f"\nDelete {len(delete_candidates)} {species_name}? (y/n): ").strip().lower()
            if response == 'y':
                to_delete.extend(delete_candidates)
                print(f"[+] Marked {len(delete_candidates)} for deletion")
            else:
                print("[*] Skipped")

    # Build list of Pokemon to keep (excluding deleted ones)
    delete_addrs = set(p['addr'] for p in to_delete)
    pokemon_to_keep = [p for p in pokemon_list if p['addr'] not in delete_addrs]

    if not to_delete:
        print("\n" + "=" * 70)
        print("No Pokemon to delete!")
        print("=" * 70)

        # Still offer to reorganize
        response = input("\nReorganize boxes by species anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("[*] Cancelled")
            return

        # Reorganize and save
        print("\n" + "=" * 70)
        print("Reorganizing boxes by species")
        print("=" * 70)
        reorganize_boxes(core, box_base, pokemon_to_keep)

        # Save new state
        print("\n" + "=" * 70)
        print("Saving new save state")
        print("=" * 70)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = SAVE_STATES_DIR / f"best_shinies_{timestamp}.ss0"

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
        print(f"[+] Reorganized {len(pokemon_to_keep)} Pokemon by species!")

        print("\n" + "=" * 70)
        print("Done!")
        print("=" * 70)
        return

    # Confirm final deletion
    print("\n" + "=" * 70)
    print(f"FINAL SUMMARY: {len(to_delete)} Pokemon to delete")
    print("=" * 70)

    for pokemon in to_delete:
        print(f"  - {pokemon['species_name']} @ Box {pokemon['box']+1} Slot {pokemon['slot']+1}: "
              f"Total IVs = {pokemon['iv_total']}")

    response = input(f"\nProceed with deleting {len(to_delete)} Pokemon and reorganizing? (y/n): ").strip().lower()
    if response != 'y':
        print("[*] Cancelled")
        return

    # Reorganize boxes with only the Pokemon to keep
    print("\n" + "=" * 70)
    print(f"Deleting {len(to_delete)} Pokemon and reorganizing boxes")
    print("=" * 70)
    reorganize_boxes(core, box_base, pokemon_to_keep)

    # Save new state
    print("\n" + "=" * 70)
    print("Saving new save state")
    print("=" * 70)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = SAVE_STATES_DIR / f"best_shinies_{timestamp}.ss0"

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
    print(f"[+] Deleted {len(to_delete)} Pokemon, kept {len(pokemon_to_keep)} sorted by species!")

    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


def test_first_slot():
    """Test function to read and display IVs of first box slot."""
    print("=" * 70)
    print("TEST: Reading first box slot IVs")
    print("=" * 70)

    base_path = SAVE_STATES_DIR / "base_with_boxes.ss0"
    if not base_path.exists():
        print(f"\n[!] Base file not found: {base_path.name}")
        return

    print(f"\n[*] Loading: {base_path.name}")

    core = mgba.core.load_path(ROM_PATH)
    if not core:
        print("[!] Failed to load ROM")
        return

    core.reset()

    with open(base_path, 'rb') as f:
        core.load_raw_state(f.read())

    for _ in range(60):
        core.run_frame()

    box_base = get_box_storage_base(core)
    if box_base is None:
        print("\n[!] Could not find box storage pointer!")
        return

    print(f"[*] Box storage at: 0x{box_base:08X}")

    # Read first slot
    addr = get_box_slot_address(box_base, 0, 0)
    pv = read_u32(core, addr)

    if pv == 0:
        print("\n[!] First box slot is empty!")
        return

    # Get species
    _, species_id, species_name = decrypt_species(core, addr)

    # Get IVs
    iv_data = decrypt_misc_substruct(core, addr)
    ivs = extract_ivs(iv_data)
    iv_total = get_iv_total(ivs)

    print(f"\n[+] Box 1, Slot 1:")
    print(f"    Species: {species_name} (ID={species_id})")
    print(f"    PV: 0x{pv:08X}")
    print(f"    IVs: {format_ivs(ivs)}")
    print(f"    Total: {iv_total}/186")

    # Also show raw data for debugging
    otid = read_u32(core, addr + 4)
    order = get_substructure_order(pv)
    misc_pos = order.index('M')
    print(f"\n    [DEBUG] OTID: 0x{otid:08X}")
    print(f"    [DEBUG] Substruct order: {order}")
    print(f"    [DEBUG] Misc substruct position: {misc_pos}")
    print(f"    [DEBUG] Raw IV data: 0x{iv_data:08X}")


def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_first_slot()
    else:
        select_best_shinies()


if __name__ == "__main__":
    main()
