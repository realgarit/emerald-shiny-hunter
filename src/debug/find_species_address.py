#!/usr/bin/env python3
"""
Debug script to find where the Pokemon species ID is actually stored in memory.
Scans memory around the PV address to find where species 252, 255, or 258 appears.
"""
import mgba.core
import os
import sys
from pathlib import Path

# Suppress GBA debug output
sys.stderr = open(os.devnull, 'w')

PROJECT_ROOT = Path(__file__).parent.parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
PARTY_PV_ADDR = 0x020244EC
PARTY_SPECIES_ADDR = 0x020244F4  # PV + 0x08

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

def run_frames(core, n):
    for _ in range(n):
        core.run_frame()

# Starter species IDs (Emerald US battle structure)
STARTER_IDS = [277, 280, 283]  # Treecko, Torchic, Mudkip
STARTER_NAMES = {277: "Treecko", 280: "Torchic", 283: "Mudkip"}

print("=" * 60)
print("Finding Pokemon Species Memory Address")
print("=" * 60)
print(f"\n[*] Loading ROM: {ROM_PATH}")
core = mgba.core.load_path(ROM_PATH)
if not core:
    raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

core.reset()
core.autoload_save()

print("[*] Pressing A buttons to get to Pokemon selection...")
# Press A up to 26 times (maximum needed)
for i in range(26):
    press_a(core, hold=5, release=5)
    run_frames(core, 15)  # 15 frame delay
    if i % 5 == 0:
        print(f"  Press {i+1}/26...")
    
    # Check if Pokemon is loaded after each press
    pv_check = read_u32(core, PARTY_PV_ADDR)
    if pv_check != 0:
        print(f"  Pokemon found after {i+1} presses!")
        break

# Wait longer for data to settle (battle structure may load later)
print("\n[*] Waiting for battle structure to load...")
for i in range(300):  # Wait up to 5 seconds
    run_frames(core, 1)
    # Check if we found a starter ID at the expected address
    species_check = read_u16(core, PARTY_SPECIES_ADDR)
    if species_check in STARTER_IDS:
        print(f"  Found starter ID {species_check} after {i} frames!")
        break
    if i % 60 == 0 and i > 0:
        print(f"  Waiting... ({i}/300 frames)")

# Check if Pokemon is loaded
pv = read_u32(core, PARTY_PV_ADDR)
print(f"\n[*] PV at 0x{PARTY_PV_ADDR:08X}: 0x{pv:08X}")
if pv == 0:
    print("[!] No Pokemon found - may need more presses")
    exit(1)

print("\n[*] Testing species address from Emerald US battle structure...")
print(f"[*] Species address: 0x{PARTY_SPECIES_ADDR:08X} (PV + 0x08)")
print(f"[*] Looking for starter IDs: 277 (Treecko), 280 (Torchic), 283 (Mudkip)")
print()

# Test the specific address
species_id = read_u16(core, PARTY_SPECIES_ADDR)
print(f"[*] Value at 0x{PARTY_SPECIES_ADDR:08X}: 0x{species_id:04X} ({species_id})")

if species_id in STARTER_IDS:
    species_name = STARTER_NAMES.get(species_id, f"ID {species_id}")
    print(f"[+] SUCCESS! Found {species_name} (ID: {species_id}) at correct address!")
    print()
    print("=" * 60)
    print("CONFIRMED ADDRESS:")
    print("=" * 60)
    print(f"  Species Address: 0x{PARTY_SPECIES_ADDR:08X}")
    print(f"  Offset from PV: +0x08")
    print(f"  Species: {species_name} (ID: {species_id})")
    print("=" * 60)
else:
    print(f"[!] Value {species_id} is not a starter ID (expected 277, 280, or 283)")
    print()
    print("[*] Scanning nearby addresses for starter IDs (277, 280, 283)...")
    print()
    
    # Scan around PV for these specific IDs
    found_starter = False
    for offset in range(-0x100, 0x100, 2):
        addr = PARTY_PV_ADDR + offset
        try:
            val = read_u16(core, addr)
            if val in STARTER_IDS:
                name = STARTER_NAMES.get(val, f"ID {val}")
                print(f"  Found {name} (ID: {val}) at 0x{addr:08X} (PV{offset:+0x})")
                found_starter = True
        except:
            pass
    
    if not found_starter:
        print("  No starter IDs found in scanned range")
        print()
        print("  Dumping values around PV+0x08 to see what's there:")
        for offset in [-0x10, -0x08, 0x00, 0x08, 0x10]:
            addr = PARTY_PV_ADDR + offset
            val = read_u16(core, addr)
            print(f"    PV{offset:+0x} (0x{addr:08X}): 0x{val:04X} ({val})")
    print()

# Scan a wide range around PV and party base
found_addresses = []
PARTY_BASE = 0x02024190  # Known party base address

# Scan multiple ranges
scan_ranges = [
    (PARTY_BASE - 0x100, PARTY_BASE + 0x200, "Party base region"),
    (PARTY_PV_ADDR - 0x200, PARTY_PV_ADDR + 0x100, "PV region"),
    (PARTY_BASE, PARTY_BASE + 0x64, "First Pokemon structure (100 bytes)"),
]

print(f"[*] Scanning multiple memory regions...")
print()

for scan_start, scan_end, label in scan_ranges:
    print(f"[*] Scanning {label}: 0x{scan_start:08X} to 0x{scan_end:08X}")
    for addr in range(scan_start, scan_end, 2):
        try:
            value = read_u16(core, addr)
            if value in STARTER_IDS:
                # Check if PV is at expected offset (0x80 bytes after species)
                pv_check = read_u32(core, addr + 0x80)
                if pv_check == pv:
                    found_addresses.append((addr, value, f"{label} - PV matches at +0x80!"))
                else:
                    # Also check other common offsets
                    for offset in [0x78, 0x7C, 0x84, 0x88]:
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
        species_name = {252: "Treecko", 255: "Torchic", 258: "Mudkip"}.get(species_id, f"ID {species_id}")
        offset_from_pv = addr - PARTY_PV_ADDR
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
        offset = addr - PARTY_PV_ADDR
        print("=" * 60)
        print("RECOMMENDED ADDRESS:")
        print("=" * 60)
        print(f"  Species Address: 0x{addr:08X}")
        print(f"  Offset from PV: {offset:+0x} ({offset:+d})")
        print(f"  Calculation: PARTY_PV_ADDR {offset:+0x}")
        print("=" * 60)
    else:
        print("[!] No address found where PV matches - may need different approach")
else:
    print("[!] No starter species IDs found in scanned memory range")
    print()
    print("[*] Dumping memory around PV address for analysis...")
    print()
    # Dump memory around PV to see what's there
    print(f"Memory dump around PV (0x{PARTY_PV_ADDR:08X}):")
    for i in range(-0x100, 0x100, 16):
        addr = PARTY_PV_ADDR + i
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
    offsets_to_try = [-0x88+0x08, -0x80, -0x7C, -0x78, -0x74, -0x70, -0x08, -0x04, 0x04, 0x08]
    for offset in offsets_to_try:
        addr = PARTY_PV_ADDR + offset
        try:
            value = read_u16(core, addr)
            if 1 <= value <= 386:  # Valid Pokemon ID range
                print(f"  PV{offset:+0x} (0x{addr:08X}): 0x{value:04X} ({value}) - {'VALID POKEMON ID!' if value in [252, 255, 258] else 'Other Pokemon ID'}")
        except:
            pass
    
    print()
    print("[!] Species might be:")
    print("    1. Encrypted and needs decryption")
    print("    2. Stored in a different memory region")
    print("    3. Not yet loaded at this point in the game")

print("\n[*] Scan complete!")

