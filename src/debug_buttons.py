#!/usr/bin/env python3
"""
Figure out exact button sequence needed
Loads from .sav file and presses A until game has loaded
"""
import mgba.core
import random
import time
from pathlib import Path

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
TID = 56078
SID = 24723

def read_u32(core, address):
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    b2 = core._core.busRead8(core._core, address + 2)
    b3 = core._core.busRead8(core._core, address + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

def press_a(core, hold=5, release=5):
    core._core.setKeys(core._core, 1)
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def run_frames(core, n):
    for _ in range(n):
        core.run_frame()

core = mgba.core.load_path(ROM_PATH)

print("=== Testing Multiple Runs for PV Variation ===")
print("Running 5 iterations to check if PV changes...\n")

pv_list = []

for run in range(5):
    core.reset()
    core.autoload_save()  # Load from .sav file
    
    # RNG variation: Write random seed to RNG address after loading
    # Emerald RNG seed is at 0x03005D80
    RNG_ADDR = 0x03005D80
    random_seed = random.randint(0, 0xFFFFFFFF)
    core._core.busWrite32(core._core, RNG_ADDR, random_seed)
    
    # Also wait some frames to let things settle
    random_delay = random.randint(10, 100)
    run_frames(core, random_delay)
    
    print(f"Run {run + 1}: Loading from .sav file (RNG seed: 0x{random_seed:08X}, delay: {random_delay} frames)...")
    
    # Press A repeatedly until we find Pokemon
    # Using 1 second pause (60 frames at 60 FPS) between presses
    total_presses = 0
    max_presses = 15  # Should find it at 12
    
    for i in range(max_presses):
        press_a(core, hold=5, release=5)
        total_presses += 1
        
        # 1 second pause (60 frames at 60 FPS)
        run_frames(core, 60)
        time.sleep(1.0)  # Also add actual 1 second sleep
        
        pv = read_u32(core, 0x020244EC)
        if pv != 0:
            print(f"  Pokemon found after {total_presses} A presses!")
            print(f"  PV: 0x{pv:08X}")

            # Calculate shiny
            pv_low = pv & 0xFFFF
            pv_high = (pv >> 16) & 0xFFFF
            shiny_val = (TID ^ SID) ^ (pv_low ^ pv_high)
            print(f"  Shiny value: {shiny_val} ({'SHINY!' if shiny_val < 8 else 'Not shiny'})")
            pv_list.append(pv)
            break
    
    if pv == 0:
        print(f"  Failed to find Pokemon after {max_presses} presses")
        pv_list.append(0)

print(f"\n=== Results ===")
print(f"PVs found: {[f'0x{pv:08X}' if pv != 0 else 'None' for pv in pv_list]}")
unique_pvs = set(pv_list)
if len(unique_pvs) > 1:
    print(f"✓ SUCCESS: Found {len(unique_pvs)} different PV values!")
else:
    print(f"✗ WARNING: All runs produced the same PV value (0x{list(unique_pvs)[0]:08X})")
