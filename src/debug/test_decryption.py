#!/usr/bin/env python3
"""
Test script to try decrypting species with different OT TID values
"""
import mgba.core
import os
import sys
from pathlib import Path

# Suppress GBA debug output
sys.stderr = open(os.devnull, 'w')

PROJECT_ROOT = Path(__file__).parent.parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
ENEMY_PV_ADDR = 0x02024744
ENEMY_TID_ADDR = 0x02024748

# Route 101 species IDs
ROUTE101_IDS = [261, 263, 265]  # Poochyena, Zigzagoon, Wurmple
ROUTE101_NAMES = {261: "Poochyena", 263: "Zigzagoon", 265: "Wurmple"}

def read_u16(core, address):
    """Read 16-bit unsigned integer from memory"""
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    return b0 | (b1 << 8)

def read_u32(core, address):
    """Read 32-bit unsigned integer from memory"""
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    b2 = core._core.busRead8(core._core, address + 2)
    b3 = core._core.busRead8(core._core, address + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

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

def press_a(core, hold=5, release=5):
    """Press and release A button"""
    core._core.setKeys(core._core, 1)  # A = bit 0
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def press_left(core, hold=3, release=0):
    """Press and release Left button"""
    core._core.setKeys(core._core, 32)  # Left = bit 5
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def press_right(core, hold=3, release=0):
    """Press and release Right button"""
    core._core.setKeys(core._core, 16)  # Right = bit 4
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def run_frames(core, n):
    for _ in range(n):
        core.run_frame()

print("=" * 60)
print("Testing Decryption with Different OT TID Values")
print("=" * 60)
print(f"\n[*] Loading ROM: {ROM_PATH}")
core = mgba.core.load_path(ROM_PATH)
if not core:
    raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

core.reset()
core.autoload_save()

print("[*] Pressing A buttons to get through loading screens...")
for i in range(15):
    press_a(core, hold=5, release=5)
    run_frames(core, 20)
    if (i + 1) % 5 == 0:
        print(f"  Press {i+1}/15...")

print("\n[*] Turning in place to trigger wild encounter...")
encounter_found = False
for turn in range(1000):
    press_left(core, hold=3, release=0)
    run_frames(core, 5)
    
    pv_check = read_u32(core, ENEMY_PV_ADDR)
    if pv_check != 0:
        print(f"  Pokemon detected after {turn * 2 + 1} turns!")
        encounter_found = True
        break
    
    press_right(core, hold=3, release=0)
    run_frames(core, 5)
    
    pv_check = read_u32(core, ENEMY_PV_ADDR)
    if pv_check != 0:
        print(f"  Pokemon detected after {turn * 2 + 2} turns!")
        encounter_found = True
        break
    
    if turn % 50 == 0 and turn > 0:
        print(f"  Still turning... ({turn * 2} turns)")

if not encounter_found:
    print("[!] No Pokemon encounter found")
    exit(1)

# Wait for battle structure to fully populate
print("\n[*] Waiting for battle structure to load...")
pv = read_u32(core, ENEMY_PV_ADDR)
print(f"  PV at 0x{ENEMY_PV_ADDR:08X}: 0x{pv:08X}")

# Wait longer for data to settle
for i in range(300):
    run_frames(core, 1)
    if i % 60 == 0 and i > 0:
        print(f"  Waiting... ({i}/300 frames)")

# Read values from memory
pv = read_u32(core, ENEMY_PV_ADDR)
tid_from_memory = read_u16(core, ENEMY_TID_ADDR)

print(f"\n[*] Memory values:")
print(f"  PV: 0x{pv:08X} ({pv})")
print(f"  TID at 0x{ENEMY_TID_ADDR:08X}: 0x{tid_from_memory:04X} ({tid_from_memory})")

# Get substructure order
order = get_substructure_order(pv)
growth_pos = order.index('G')
print(f"\n[*] Substructure order: {order}")
print(f"  Growth ('G') is at position {growth_pos}")

# Try different OT TID values
ot_tid_values = [0, tid_from_memory]

# Also try different data offsets
data_offsets = [32, 0, 8, 16, 24, 40, 48]

print(f"\n[*] Testing decryption with different OT TID values and offsets...")
print()

found = False
for ot_tid in ot_tid_values:
    for data_offset in data_offsets:
        try:
            data_start = ENEMY_PV_ADDR + data_offset
            offset = growth_pos * 12
            
            # Read encrypted value
            encrypted_val = read_u32(core, data_start + offset)
            
            # Decrypt
            xor_key = (ot_tid & 0xFFFF) ^ pv
            decrypted_val = encrypted_val ^ xor_key
            species_id = decrypted_val & 0xFFFF
            
            # Check if it's a valid Route 101 species
            if species_id in ROUTE101_IDS:
                species_name = ROUTE101_NAMES.get(species_id, f"ID {species_id}")
                print(f"[+] SUCCESS! Found {species_name} (ID: {species_id})")
                print(f"    OT TID: {ot_tid}")
                print(f"    Data offset: +{data_offset} (0x{data_offset:02X})")
                print(f"    Encrypted value: 0x{encrypted_val:08X}")
                print(f"    XOR key: 0x{xor_key:08X}")
                print(f"    Decrypted value: 0x{decrypted_val:08X}")
                print(f"    Species ID: {species_id}")
                found = True
                break
            elif 1 <= species_id <= 386:  # Valid Pokemon ID range
                print(f"  OT_TID={ot_tid:5d}, offset=+{data_offset:2d}: Species={species_id:3d} (not Route 101)")
        except Exception as e:
            pass
    
    if found:
        break

if not found:
    print("[!] No Route 101 species found with any combination")
    print("\n[*] Trying all substructure positions...")
    
    for ot_tid in ot_tid_values:
        for data_offset in data_offsets:
            for substructure_pos in range(4):
                try:
                    data_start = ENEMY_PV_ADDR + data_offset
                    offset = substructure_pos * 12
                    
                    encrypted_val = read_u32(core, data_start + offset)
                    xor_key = (ot_tid & 0xFFFF) ^ pv
                    decrypted_val = encrypted_val ^ xor_key
                    species_id = decrypted_val & 0xFFFF
                    
                    if species_id in ROUTE101_IDS:
                        substructure_char = order[substructure_pos]
                        species_name = ROUTE101_NAMES.get(species_id, f"ID {species_id}")
                        print(f"[+] SUCCESS! Found {species_name} (ID: {species_id})")
                        print(f"    OT TID: {ot_tid}")
                        print(f"    Data offset: +{data_offset} (0x{data_offset:02X})")
                        print(f"    Substructure position: {substructure_pos} ({substructure_char})")
                        print(f"    Encrypted value: 0x{encrypted_val:08X}")
                        print(f"    XOR key: 0x{xor_key:08X}")
                        print(f"    Decrypted value: 0x{decrypted_val:08X}")
                        print(f"    Species ID: {species_id}")
                        found = True
                        break
                except:
                    pass
            
            if found:
                break
        
        if found:
            break

if not found:
    print("\n[!] Still no Route 101 species found")
    print("\n[*] Dumping encrypted data at PV+0x20 for manual analysis...")
    data_start = ENEMY_PV_ADDR + 32
    for i in range(4):
        offset = i * 12
        encrypted_val = read_u32(core, data_start + offset)
        substructure_char = order[i]
        print(f"  Position {i} ({substructure_char}): 0x{encrypted_val:08X}")

print("\n[*] Test complete!")

