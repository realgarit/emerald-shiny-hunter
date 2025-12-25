#!/usr/bin/env python3
"""
Scan the entire 100-byte enemy Pokemon structure to find where species ID is stored
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

def press_a(core, hold=5, release=5):
    """Press and release A button"""
    core._core.setKeys(core._core, 1)
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def press_left(core, hold=3, release=0):
    """Press and release Left button"""
    core._core.setKeys(core._core, 32)
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def press_right(core, hold=3, release=0):
    """Press and release Right button"""
    core._core.setKeys(core._core, 16)
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def run_frames(core, n):
    for _ in range(n):
        core.run_frame()

print("=" * 60)
print("Scanning 100-byte Enemy Pokemon Structure")
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

print("\n[*] Scanning entire 100-byte enemy Pokemon structure...")
print(f"    Base address: 0x{ENEMY_PV_ADDR:08X}")
print(f"    Scanning from 0x{ENEMY_PV_ADDR:08X} to 0x{ENEMY_PV_ADDR + 100:08X}")
print()

found_species = []
# Scan the entire 100-byte structure in 2-byte steps (for 16-bit values)
for offset in range(0, 100, 2):
    addr = ENEMY_PV_ADDR + offset
    try:
        value = read_u16(core, addr)
        if value in ROUTE101_IDS:
            species_name = ROUTE101_NAMES.get(value, f"ID {value}")
            found_species.append((offset, addr, value, species_name))
            print(f"  [+] Found {species_name} (ID: {value}) at offset +0x{offset:02X} (0x{addr:08X})")
    except:
        pass

if found_species:
    print("\n" + "=" * 60)
    print("FOUND SPECIES ADDRESSES:")
    print("=" * 60)
    for offset, addr, species_id, species_name in found_species:
        print(f"  Offset: +0x{offset:02X} ({offset:+d}) from PV")
        print(f"  Address: 0x{addr:08X}")
        print(f"  Species: {species_name} (ID: {species_id})")
        print()
    
    # Show the best match (first one found)
    offset, addr, species_id, species_name = found_species[0]
    print("=" * 60)
    print("RECOMMENDED ADDRESS:")
    print("=" * 60)
    print(f"  ENEMY_SPECIES_ADDR = 0x{addr:08X}")
    print(f"  Offset from PV: +0x{offset:02X} ({offset:+d})")
    print(f"  Calculation: ENEMY_PV_ADDR + 0x{offset:02X}")
    print("=" * 60)
else:
    print("[!] No Route 101 species IDs found in 100-byte structure")
    print("\n[*] Dumping all 16-bit values in the structure for analysis...")
    print()
    print("Offset | Address      | Value (hex) | Value (dec) | Note")
    print("-" * 70)
    for offset in range(0, 100, 2):
        addr = ENEMY_PV_ADDR + offset
        try:
            value = read_u16(core, addr)
            note = ""
            if offset == 0:
                note = "PV (low 16 bits)"
            elif offset == 2:
                note = "PV (high 16 bits)"
            elif offset == 4:
                note = "TID?"
            elif offset == 6:
                note = "SID?"
            elif 1 <= value <= 386:
                note = f"Valid Pokemon ID (not Route 101)"
            elif value == 0:
                note = "Zero"
            
            print(f"  +{offset:02X}  | 0x{addr:08X} | 0x{value:04X}     | {value:10d} | {note}")
        except:
            print(f"  +{offset:02X}  | 0x{addr:08X} | ERROR       |            |")

print("\n[*] Scan complete!")

