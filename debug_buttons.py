#!/usr/bin/env python3
"""
Figure out exact button sequence needed
"""
import mgba.core
import random

ROM_PATH = "Pokemon - Emerald Version (U).gba"
SAVE_STATE_PATH = "save-state-1.ss0"
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
core.reset()
core.autoload_save()

with open(SAVE_STATE_PATH, 'rb') as f:
    core.load_raw_state(f.read())

print("=== Finding Exact Button Sequence ===")

# RNG delay
delay = random.randint(30, 500)
print(f"RNG delay: {delay} frames")
run_frames(core, delay)

# Press A repeatedly until we find Pokemon
total_presses = 0
for i in range(20):
    press_a(core, hold=5, release=5)
    run_frames(core, 30)
    total_presses += 1

    pv = read_u32(core, 0x020244EC)
    if pv != 0:
        print(f"\nPokemon found after {total_presses} A presses!")
        print(f"PV: 0x{pv:08X}")

        # Calculate shiny
        pv_low = pv & 0xFFFF
        pv_high = (pv >> 16) & 0xFFFF
        shiny_val = (TID ^ SID) ^ (pv_low ^ pv_high)
        print(f"Shiny value: {shiny_val} ({'SHINY!' if shiny_val < 8 else 'Not shiny'})")
        break
    else:
        print(f"Press {total_presses}: no Pokemon yet")

else:
    print("Failed to find Pokemon after 20 presses")
