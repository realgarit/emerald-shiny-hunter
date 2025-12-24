#!/usr/bin/env python3
"""
Script to combine 3 shiny starter Pokemon from different save states into one save file.

Extracts Pokemon data from save states and writes them to party slots programmatically.
"""

import mgba.core
import os
import sys
from pathlib import Path
from datetime import datetime

# Suppress GBA debug output
sys.stderr = open(os.devnull, 'w')

PROJECT_ROOT = Path(__file__).parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
SAVE_STATES_DIR = PROJECT_ROOT / "save_states"

# Memory addresses for party Pokemon slots
# Each Pokemon is 100 bytes (0x64)
# Slot 1: 0x020244EC
# Slot 2: 0x020244EC + 0x64 = 0x02024550
# Slot 3: 0x02024550 + 0x64 = 0x020245B4
PARTY_SLOT_SIZE = 0x64  # 100 bytes per Pokemon
PARTY_SLOT_1_ADDR = 0x020244EC
PARTY_SLOT_2_ADDR = 0x02024550
PARTY_SLOT_3_ADDR = 0x020245B4

# Party count address (1 byte, number of Pokemon in party)
PARTY_COUNT_ADDR = 0x020244E9

POKEMON_SPECIES = {
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

def read_u16(core, address):
    """Read 16-bit unsigned integer from memory"""
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    return b0 | (b1 << 8)

def read_u8(core, address):
    """Read 8-bit unsigned integer from memory"""
    return core._core.busRead8(core._core, address)

def read_bytes(core, address, length):
    """Read multiple bytes from memory"""
    return bytes([core._core.busRead8(core._core, address + i) for i in range(length)])

def write_u8(core, address, value):
    """Write 8-bit unsigned integer to memory"""
    core._core.busWrite8(core._core, address, value & 0xFF)

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

def decrypt_party_species(core, pv_addr, tid_addr):
    """Decrypt and extract species ID from encrypted party data"""
    try:
        pv = read_u32(core, pv_addr)
        tid = read_u16(core, tid_addr)
        
        data_start = pv_addr + 32
        order = get_substructure_order(pv)
        growth_pos = order.index('G')
        offset = growth_pos * 12
        
        encrypted_val = read_u32(core, data_start + offset)
        xor_key = (tid & 0xFFFF) ^ pv
        decrypted_val = encrypted_val ^ xor_key
        species_id = decrypted_val & 0xFFFF
        
        return species_id
    except Exception as e:
        return 0

def extract_pokemon_from_save_state(save_state_path):
    """Load a save state and extract the Pokemon data from slot 1"""
    print(f"\n[*] Loading save state: {save_state_path.name}")
    
    core = mgba.core.load_path(ROM_PATH)
    if not core:
        raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")
    
    # Reset core before loading save state
    core.reset()
    
    # Load the save state
    with open(save_state_path, 'rb') as f:
        state_data = f.read()
    
    core.load_raw_state(state_data)
    
    # Run a few frames to ensure memory is stable
    for _ in range(60):
        core.run_frame()
    
    # Read the full Pokemon data (100 bytes)
    pokemon_data = read_bytes(core, PARTY_SLOT_1_ADDR, PARTY_SLOT_SIZE)
    
    # Get species for verification
    pv = read_u32(core, PARTY_SLOT_1_ADDR)
    tid = read_u16(core, PARTY_SLOT_1_ADDR + 4)
    species_id = decrypt_party_species(core, PARTY_SLOT_1_ADDR, PARTY_SLOT_1_ADDR + 4)
    species_name = POKEMON_SPECIES.get(species_id, f"Unknown({species_id})")
    
    print(f"    Extracted: {species_name} (PV: 0x{pv:08X}, Species ID: {species_id})")
    
    return pokemon_data, species_name, species_id

def combine_shinies():
    """Programmatically combine shinies by extracting from save states and writing to party slots"""
    print("=" * 80)
    print("Combining Shiny Starters")
    print("=" * 80)
    print()
    
    # Find save state files
    save_states = {
        'mudkip': None,
        'torchic': None,
        'treecko': None,
    }
    
    for file in SAVE_STATES_DIR.glob("*.ss0"):
        name_lower = file.name.lower()
        if 'mudkip' in name_lower:
            save_states['mudkip'] = file
        elif 'torchic' in name_lower:
            save_states['torchic'] = file
        elif 'treecko' in name_lower:
            save_states['treecko'] = file
    
    # Check which ones we found
    found = {k: v for k, v in save_states.items() if v is not None}
    missing = [k for k, v in save_states.items() if v is None]
    
    if not found:
        print("[!] No shiny save states found!")
        print(f"    Looking in: {SAVE_STATES_DIR}")
        return
    
    print(f"[*] Found {len(found)} shiny save state(s):")
    for name, path in found.items():
        print(f"    - {name}: {path.name}")
    
    if missing:
        print(f"\n[!] Missing save states for: {', '.join(missing)}")
        print("    You can still proceed with the ones you have.")
    
    # Ask which save to use as the base
    print("\n[*] Which save state should be the base (slot 1)?")
    print("    This will be the main save file that gets the other Pokemon added to it.")
    for i, (name, path) in enumerate(found.items(), 1):
        print(f"    {i}. {name} ({path.name})")
    
    # For now, use the first one found (you can modify this)
    base_name = list(found.keys())[0]
    base_path = found[base_name]
    
    print(f"\n[*] Using '{base_name}' as base save (slot 1)")
    
    # Extract Pokemon from all save states
    pokemon_data = {}
    for name, path in found.items():
        if path:
            try:
                data, species, species_id = extract_pokemon_from_save_state(path)
                pokemon_data[name] = {
                    'data': data,
                    'species': species,
                    'species_id': species_id,
                    'path': path
                }
            except Exception as e:
                print(f"[!] Failed to extract {name}: {e}")
                continue
    
    if len(pokemon_data) < 2:
        print("\n[!] Need at least 2 Pokemon to combine. Found:", len(pokemon_data))
        return
    
    # Determine slot assignments
    # Base Pokemon goes to slot 1, others to slots 2 and 3
    slot_assignments = {}
    slot_assignments[1] = base_name
    
    other_names = [n for n in pokemon_data.keys() if n != base_name]
    for i, name in enumerate(other_names[:2], start=2):  # Max 2 more (slots 2 and 3)
        slot_assignments[i] = name
    
    print("\n[*] Slot assignments:")
    for slot, name in sorted(slot_assignments.items()):
        species = pokemon_data[name]['species']
        print(f"    Slot {slot}: {name} ({species})")
    
    # Load the base save state
    print(f"\n[*] Loading base save state: {base_path.name}")
    core = mgba.core.load_path(ROM_PATH)
    if not core:
        raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")
    
    # Reset core before loading save state
    core.reset()
    
    with open(base_path, 'rb') as f:
        state_data = f.read()
    
    core.load_raw_state(state_data)
    
    # Run frames to stabilize
    for _ in range(60):
        core.run_frame()
    
    # Write Pokemon to their assigned slots
    print("\n[*] Writing Pokemon to party slots...")
    slot_addresses = {
        1: PARTY_SLOT_1_ADDR,
        2: PARTY_SLOT_2_ADDR,
        3: PARTY_SLOT_3_ADDR,
    }
    
    for slot, name in sorted(slot_assignments.items()):
        if slot == 1:
            # Slot 1 already has the base Pokemon, skip
            continue
        
        addr = slot_addresses[slot]
        data = pokemon_data[name]['data']
        species = pokemon_data[name]['species']
        
        print(f"    Writing {species} to slot {slot} (address 0x{addr:08X})...")
        write_bytes(core, addr, data)
    
    # Update party count
    party_count = len(slot_assignments)
    print(f"\n[*] Setting party count to {party_count}...")
    write_u8(core, PARTY_COUNT_ADDR, party_count)
    
    # Verify the Pokemon are in the party
    print("\n[*] Verifying party...")
    for slot, name in sorted(slot_assignments.items()):
        addr = slot_addresses[slot]
        pv = read_u32(core, addr)
        tid = read_u16(core, addr + 4)
        species_id = decrypt_party_species(core, addr, addr + 4)
        species_name = POKEMON_SPECIES.get(species_id, f"Unknown({species_id})")
        
        if pv != 0:
            print(f"    Slot {slot}: {species_name} (PV: 0x{pv:08X}) ✓")
        else:
            print(f"    Slot {slot}: Empty ✗")
    
    # Save the combined state
    print("\n[*] Saving combined save state...")
    save_state_dir = PROJECT_ROOT / "save_states"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_filename = save_state_dir / f"combined_shinies_{timestamp}.ss0"
    
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
    
    with open(combined_filename, 'wb') as f:
        f.write(state_bytes)
    
    print(f"[+] Combined save state saved: {combined_filename}")
    
    # Also try to save to .sav file
    print("\n[*] To save to .sav file:")
    print("    1. Load this save state in mGBA")
    print("    2. Save the game normally (this will update the .sav file)")
    print("    3. Then you can use PKHeX with the .sav file if needed")
    
    print("\n[+] Done! Your combined shiny starters are in the save state.")
    print(f"    Load '{combined_filename.name}' in mGBA to use it.")

def main():
    print("=" * 80)
    print("Shiny Starter Combiner")
    print("=" * 80)
    print()
    print("This script combines your 3 shiny starters into one save file.")
    print("It extracts Pokemon data from save states and writes them to party slots.")
    print()
    
    combine_shinies()

if __name__ == "__main__":
    main()

