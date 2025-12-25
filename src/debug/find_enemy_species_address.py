#!/usr/bin/env python3
"""
Debug script to find where the enemy/wild Pokemon species ID is stored in memory.
Scans memory around the enemy party address to find where species 261, 263, or 265 appears.
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
ENEMY_SPECIES_ADDR = 0x0202474C  # PV + 0x08

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
print("Finding Enemy Pokemon Species Memory Address")
print("=" * 60)
print(f"\n[*] Loading ROM: {ROM_PATH}")
core = mgba.core.load_path(ROM_PATH)
if not core:
    raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

core.reset()
core.autoload_save()

print("[*] Pressing A buttons to get through loading screens...")
# Press A 15 times to get through loading
for i in range(15):
    press_a(core, hold=5, release=5)
    run_frames(core, 20)  # 20 frame delay
    if (i + 1) % 5 == 0:
        print(f"  Press {i+1}/15...")

print("\n[*] Turning in place to trigger wild encounter...")
# Turn in place to trigger encounter
encounter_found = False
for turn in range(1000):
    # Press Left for 3 frames, wait 5 frames
    press_left(core, hold=3, release=0)
    run_frames(core, 5)
    
    # Check for Pokemon
    pv_check = read_u32(core, ENEMY_PV_ADDR)
    if pv_check != 0:
        print(f"  Pokemon detected after {turn * 2 + 1} turns!")
        encounter_found = True
        break
    
    # Press Right for 3 frames, wait 5 frames
    press_right(core, hold=3, release=0)
    run_frames(core, 5)
    
    # Check for Pokemon
    pv_check = read_u32(core, ENEMY_PV_ADDR)
    if pv_check != 0:
        print(f"  Pokemon detected after {turn * 2 + 2} turns!")
        encounter_found = True
        break
    
    if turn % 50 == 0 and turn > 0:
        print(f"  Still turning... ({turn * 2} turns)")

if not encounter_found:
    print("[!] No Pokemon encounter found - may need more turns")
    exit(1)

# Wait for battle structure to fully populate
print("\n[*] Waiting for battle structure to load...")
pv = read_u32(core, ENEMY_PV_ADDR)
print(f"  PV at 0x{ENEMY_PV_ADDR:08X}: 0x{pv:08X}")

# Wait longer for data to settle
for i in range(300):  # Wait up to 5 seconds
    run_frames(core, 1)
    # Check if we found a Route 101 species ID at the expected address
    species_check = read_u16(core, ENEMY_SPECIES_ADDR)
    if species_check in ROUTE101_IDS:
        print(f"  Found Route 101 species ID {species_check} after {i} frames!")
        break
    if i % 60 == 0 and i > 0:
        print(f"  Waiting... ({i}/300 frames)")

print("\n[*] Testing species address from Emerald US battle structure...")
print(f"[*] Species address: 0x{ENEMY_SPECIES_ADDR:08X} (PV + 0x08)")
print(f"[*] Looking for Route 101 IDs: 261 (Poochyena), 263 (Zigzagoon), 265 (Wurmple)")
print()

# Test the specific address
species_id = read_u16(core, ENEMY_SPECIES_ADDR)
print(f"[*] Value at 0x{ENEMY_SPECIES_ADDR:08X}: 0x{species_id:04X} ({species_id})")

if species_id in ROUTE101_IDS:
    species_name = ROUTE101_NAMES.get(species_id, f"ID {species_id}")
    print(f"[+] SUCCESS! Found {species_name} (ID: {species_id}) at correct address!")
    print()
    print("=" * 60)
    print("CONFIRMED ADDRESS:")
    print("=" * 60)
    print(f"  Species Address: 0x{ENEMY_SPECIES_ADDR:08X}")
    print(f"  Offset from PV: +0x08")
    print(f"  Species: {species_name} (ID: {species_id})")
    print("=" * 60)
else:
    print(f"[!] Value {species_id} is not a Route 101 species ID (expected 261, 263, or 265)")
    print()
    print("[*] Scanning nearby addresses for Route 101 species IDs...")
    print()
    
    # Scan around enemy PV for these specific IDs
    found_species = False
    for offset in range(-0x200, 0x200, 2):
        addr = ENEMY_PV_ADDR + offset
        try:
            val = read_u16(core, addr)
            if val in ROUTE101_IDS:
                name = ROUTE101_NAMES.get(val, f"ID {val}")
                print(f"  Found {name} (ID: {val}) at 0x{addr:08X} (PV{offset:+0x})")
                found_species = True
        except:
            pass
    
    if not found_species:
        print("  No Route 101 species IDs found in scanned range")
        print()
        print("  Dumping values around PV+0x08 to see what's there:")
        for offset in [-0x10, -0x08, 0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30]:
            addr = ENEMY_PV_ADDR + offset
            val = read_u16(core, addr)
            print(f"    PV{offset:+0x} (0x{addr:08X}): 0x{val:04X} ({val})")
    print()

# Scan a wide range around enemy PV
found_addresses = []
ENEMY_BASE = 0x02024744  # Enemy party base address

# Scan multiple ranges
scan_ranges = [
    (ENEMY_BASE - 0x200, ENEMY_BASE + 0x200, "Enemy PV region"),
    (0x02024000, 0x02025000, "Battle structure area"),
    (ENEMY_BASE, ENEMY_BASE + 0x64, "First enemy Pokemon structure (100 bytes)"),
]

print(f"[*] Scanning multiple memory regions...")
print()

for scan_start, scan_end, label in scan_ranges:
    print(f"[*] Scanning {label}: 0x{scan_start:08X} to 0x{scan_end:08X}")
    for addr in range(scan_start, scan_end, 2):
        try:
            value = read_u16(core, addr)
            if value in ROUTE101_IDS:
                # Check if PV is at expected offset
                pv_check = read_u32(core, addr - 0x08)  # Check if PV is 8 bytes before
                if pv_check == pv:
                    found_addresses.append((addr, value, f"{label} - PV matches at -0x08!"))
                else:
                    # Also check other common offsets
                    for offset in [-0x04, 0x00, 0x04, 0x08, 0x0C, 0x10]:
                        pv_check2 = read_u32(core, addr + offset)
                        if pv_check2 == pv:
                            found_addresses.append((addr, value, f"{label} - PV matches at +0x{offset:02X}!"))
                            break
                    else:
                        found_addresses.append((addr, value, f"{label} - PV not found at expected offsets"))
        except:
            continue

if found_addresses:
    print("=" * 60)
    print("FOUND SPECIES ADDRESSES:")
    print("=" * 60)
    for addr, species_id, note in found_addresses:
        species_name = ROUTE101_NAMES.get(species_id, f"ID {species_id}")
        offset_from_pv = addr - ENEMY_PV_ADDR
        print(f"  Address: 0x{addr:08X} (PV {offset_from_pv:+0x})")
        print(f"  Species: {species_name} (ID: {species_id})")
        print(f"  Note: {note}")
        print()
    
    # Find the one where PV matches
    best_match = None
    for addr, species_id, note in found_addresses:
        if "PV matches" in note:
            best_match = (addr, species_id)
            break
    
    if best_match:
        addr, species_id = best_match
        offset = addr - ENEMY_PV_ADDR
        print("=" * 60)
        print("RECOMMENDED ADDRESS:")
        print("=" * 60)
        print(f"  Species Address: 0x{addr:08X}")
        print(f"  Offset from PV: {offset:+0x} ({offset:+d})")
        print(f"  Calculation: ENEMY_PV_ADDR {offset:+0x}")
        print("=" * 60)
    else:
        print("[!] No address found where PV matches - may need different approach")
else:
    print("[!] No Route 101 species IDs found in scanned memory range")
    print()
    print("[*] Dumping memory around enemy PV address for analysis...")
    print()
    # Dump memory around PV to see what's there
    print(f"Memory dump around enemy PV (0x{ENEMY_PV_ADDR:08X}):")
    for i in range(-0x100, 0x100, 16):
        addr = ENEMY_PV_ADDR + i
        values = []
        for j in range(0, 16, 2):
            try:
                val = read_u16(core, addr + j)
                values.append(f"{val:04X}")
            except:
                values.append("----")
        print(f"  0x{addr:08X} ({i:+0x}): {' '.join(values)}")
    
    print()
    print("[*] Checking calculated offsets from PV...")
    # Try various offsets from PV
    offsets_to_try = [-0x88+0x08, -0x80, -0x7C, -0x78, -0x74, -0x70, -0x08, -0x04, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30]
    for offset in offsets_to_try:
        addr = ENEMY_PV_ADDR + offset
        try:
            value = read_u16(core, addr)
            if 1 <= value <= 386:  # Valid Pokemon ID range
                print(f"  PV{offset:+0x} (0x{addr:08X}): 0x{value:04X} ({value}) - {'VALID ROUTE 101 ID!' if value in ROUTE101_IDS else 'Other Pokemon ID'}")
        except:
            pass
    
    print()
    print("[!] Species might be:")
    print("    1. Encrypted and needs decryption")
    print("    2. Stored in a different memory region")
    print("    3. Not yet loaded at this point in the battle")

print("\n[*] Scan complete!")

