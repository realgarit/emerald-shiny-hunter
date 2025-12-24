#!/usr/bin/env python3
"""
Debug script to find the button sequence for selecting Mudkip
Mudkip is to the right of Torchic, so we need: A presses -> Right -> A presses
"""

import mgba.core
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")

# Memory addresses
PARTY_PV_ADDR = 0x020244EC  # Personality Value
PARTY_TID_ADDR = 0x020244F0  # Trainer ID

# Pokemon species IDs (Gen III battle structure IDs)
POKEMON_SPECIES = {
    277: "Treecko",
    280: "Torchic",
    283: "Mudkip",
}

# Button constants (GBA button bits)
KEY_A = 1      # bit 0
KEY_B = 2      # bit 1
KEY_SELECT = 4
KEY_START = 8
KEY_RIGHT = 16  # bit 4
KEY_LEFT = 32   # bit 5
KEY_UP = 64     # bit 6
KEY_DOWN = 128  # bit 7

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
        # Read PV and TID
        pv = read_u32(core, pv_addr)
        tid = read_u16(core, tid_addr)
        
        # Encrypted data starts at exactly 32 bytes after PV address
        data_start = pv_addr + 32
        
        # Get substructure order
        order = get_substructure_order(pv)
        growth_pos = order.index('G')
        offset = growth_pos * 12
        
        # Read 32 bits from data_start + offset
        encrypted_val = read_u32(core, data_start + offset)
        
        # Decrypt: encrypted_val ^ (tid ^ pv)
        xor_key = (tid & 0xFFFF) ^ pv
        decrypted_val = encrypted_val ^ xor_key
        
        # Extract species ID (lower 16 bits)
        species_id = decrypted_val & 0xFFFF
        
        return species_id
    except Exception as e:
        return 0

def press_button(core, button, hold=5, release=5):
    """Press a button (button is the bit value)"""
    core._core.setKeys(core._core, button)
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def run_frames(core, n):
    """Advance emulation by n frames"""
    for _ in range(n):
        core.run_frame()

def test_sequence(core, a_before_right, wait_after_a, right_presses, a_after_right):
    """Test a specific button sequence
    
    Args:
        a_before_right: Number of A presses before pressing Right
        wait_after_a: Frames to wait after A presses before pressing Right
        right_presses: Number of Right presses (1 or 2)
        a_after_right: Number of A presses after pressing Right
    """
    # Reset and load save
    core.reset()
    core.autoload_save()
    run_frames(core, 60)  # Wait 1 second for save to load
    
    # Press A buttons to get to selection screen
    print(f"  Testing: {a_before_right} A -> wait {wait_after_a} -> {right_presses}x Right -> {a_after_right} A")
    print(f"    Pressing {a_before_right} A buttons...", end='', flush=True)
    
    for i in range(a_before_right):
        press_button(core, KEY_A, hold=5, release=5)
        run_frames(core, 15)  # 0.25s delay between presses
        if (i + 1) % 5 == 0:
            print(f" {i+1}...", end='', flush=True)
    
    print(" Done")
    
    # Wait before pressing Right (to ensure we're on selection screen)
    if wait_after_a > 0:
        print(f"    Waiting {wait_after_a} frames...", end='', flush=True)
        run_frames(core, wait_after_a)
        print(" Done")
    
    # Press Right to move to Mudkip (maybe need multiple presses)
    print(f"    Pressing Right {right_presses} time(s)...", end='', flush=True)
    for _ in range(right_presses):
        press_button(core, KEY_RIGHT, hold=5, release=5)
        run_frames(core, 15)  # Small delay after each Right
    print(" Done")
    
    # Press A buttons to select Mudkip
    print(f"    Pressing {a_after_right} A buttons...", end='', flush=True)
    pokemon_found = False
    presses_needed = 0
    
    for i in range(a_after_right):
        press_button(core, KEY_A, hold=5, release=5)
        run_frames(core, 15)  # 0.25s delay between presses
        
        # Check if Pokemon is found
        pv = read_u32(core, PARTY_PV_ADDR)
        if pv != 0:
            pokemon_found = True
            presses_needed = i + 1
            print(f" Pokemon found after {presses_needed} presses!")
            break
        
        if (i + 1) % 5 == 0:
            print(f" {i+1}...", end='', flush=True)
    
    if not pokemon_found:
        print(" No Pokemon found")
    
    # Wait a bit more and check again
    if not pokemon_found:
        print(f"    Waiting additional 60 frames...", end='', flush=True)
        run_frames(core, 60)
        pv = read_u32(core, PARTY_PV_ADDR)
        if pv != 0:
            pokemon_found = True
            presses_needed = a_after_right
            print(f" Pokemon found!")
        else:
            print(" Still no Pokemon")
    
    # If Pokemon found, check species
    species_id = 0
    species_name = "Unknown"
    if pokemon_found:
        run_frames(core, 60)  # Wait for data to settle
        species_id = decrypt_party_species(core, PARTY_PV_ADDR, PARTY_TID_ADDR)
        species_name = POKEMON_SPECIES.get(species_id, f"Unknown (ID: {species_id})")
    
    return pokemon_found, presses_needed, species_id, species_name

print("=" * 70)
print("Finding Button Sequence for Mudkip Selection")
print("=" * 70)
print(f"\n[*] Loading ROM: {ROM_PATH}")

core = mgba.core.load_path(ROM_PATH)
if not core:
    raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

print("[*] Testing different button sequences...\n")

# We know from Torchic that we need ~23 A presses to get to selection
# So we'll test:
# - Same number of A presses as Torchic, then Right, then A presses
# - Maybe one less A press before Right (in case Right moves us forward)
# - Maybe one more A press before Right

test_cases = [
    # (A presses before Right, wait frames, Right presses, A presses after Right)
    # Try pressing Right much earlier - maybe we're selecting Torchic before we press Right
    (20, 30, 1, 3),   # 20 A, wait 0.5s, Right, 3 A
    (20, 60, 1, 3),   # 20 A, wait 1s, Right, 3 A
    (21, 30, 1, 2),   # 21 A, wait 0.5s, Right, 2 A
    (21, 60, 1, 2),   # 21 A, wait 1s, Right, 2 A
    (22, 30, 1, 1),   # 22 A, wait 0.5s, Right, 1 A
    (22, 60, 1, 1),   # 22 A, wait 1s, Right, 1 A
    (22, 0, 1, 2),    # 22 A, no wait, Right, 2 A (immediate Right)
    (21, 0, 1, 3),    # 21 A, no wait, Right, 3 A (immediate Right)
]

successful_sequences = []

for i, (a_before, wait, right_count, a_after) in enumerate(test_cases, 1):
    print(f"\n[Test {i}/{len(test_cases)}]")
    found, presses, species_id, species_name = test_sequence(core, a_before, wait, right_count, a_after)
    
    if found:
        successful_sequences.append((a_before, wait, right_count, a_after, presses, species_id, species_name))
        status = "✓ MUDKIP!" if species_id == 283 else f"✗ {species_name} (wrong!)"
        print(f"  {status}: Pokemon found after {presses} A presses")
    else:
        print(f"  ✗ Failed: No Pokemon found")

print("\n" + "=" * 70)
print("Results Summary")
print("=" * 70)

if successful_sequences:
    print("\n[*] Successful sequences found:")
    # successful_sequences format: (a_before, wait, right_count, a_after, presses, species_id, species_name)
    mudkip_sequences = [s for s in successful_sequences if s[5] == 283]
    
    if mudkip_sequences:
        print("\n[*] Sequences that correctly select MUDKIP:")
        for a_before, wait, right_count, a_after, presses, species_id, species_name in mudkip_sequences:
            wait_sec = wait / 60.0
            print(f"  ✓ {a_before} A -> wait {wait_sec:.1f}s -> {right_count}x Right -> {a_after} A")
        
        # Recommend the one with fewest total presses
        best = min(mudkip_sequences, key=lambda x: x[0] + x[2] + x[3])
        wait_sec = best[1] / 60.0
        print(f"\n[*] Recommended sequence (fewest presses):")
        print(f"  {best[0]} A presses -> wait {wait_sec:.1f}s -> {best[2]}x Right -> {best[3]} A presses")
        print(f"  Total: {best[0] + best[2] + best[3]} button presses")
    else:
        print("\n[!] WARNING: No sequences correctly selected Mudkip!")
        print("[!] All sequences selected:")
        for a_before, wait, right_count, a_after, presses, species_id, species_name in successful_sequences:
            wait_sec = wait / 60.0
            print(f"  - {a_before} A -> wait {wait_sec:.1f}s -> {right_count}x Right -> {a_after} A: {species_name} (ID: {species_id})")
else:
    print("\n[!] No successful sequences found. May need to adjust test cases.")

print("\nTest complete!")

