#!/usr/bin/env python3
"""Quick test of shiny hunter - run 5 iterations"""
import mgba.core
import random
from pathlib import Path

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
SAVE_STATE_PATH = str(PROJECT_ROOT / "save_states" / "save-state-1.ss0")
TID = 56078
SID = 24723
PARTY_PV_ADDR = 0x020244EC
RNG_ADDR = 0x03005D80

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

# Initialize
core = mgba.core.load_path(ROM_PATH)
core.reset()
core.autoload_save()

print(f"[*] TID: {TID}, SID: {SID}")
print(f"[*] Testing 5 iterations with RNG manipulation...\n")

with open(SAVE_STATE_PATH, 'rb') as f:
    state_data = f.read()

for i in range(5):
    # Load state
    core.load_raw_state(state_data)

    # Vary the timing throughout the selection
    # This should affect when the RNG is called for Pokemon generation
    base_delay = random.randint(50, 200)  # Variable initial delay
    run_frames(core, base_delay)

    # Selection sequence with variable timing between presses
    for press_num in range(16):
        press_a(core, hold=5, release=5)
        # Variable wait between presses
        wait = random.randint(20, 50)
        run_frames(core, wait)

    # Check result
    pv = read_u32(core, PARTY_PV_ADDR)

    if pv != 0:
        pv_low = pv & 0xFFFF
        pv_high = (pv >> 16) & 0xFFFF
        shiny_value = (TID ^ SID) ^ (pv_low ^ pv_high)
        status = "SHINY!" if shiny_value < 8 else "Not shiny"
        print(f"[{i+1:3d}] PV: {pv:08X} | Shiny: {shiny_value:5d} | {status}")
    else:
        print(f"[{i+1:3d}] No Pokemon found")

print("\nTest complete!")
