#!/usr/bin/env python3
"""
Final button test using add_keys/clear_keys
"""

import mgba.core
import random

ROM_PATH = "Pokemon - Emerald Version (U).gba"
SAVE_STATE_PATH = "save-state-1.ss0"

TID = 56078
SID = 24723

def read_u32(core, address):
    byte0 = core._core.busRead8(core._core, address)
    byte1 = core._core.busRead8(core._core, address + 1)
    byte2 = core._core.busRead8(core._core, address + 2)
    byte3 = core._core.busRead8(core._core, address + 3)
    return byte0 | (byte1 << 8) | (byte2 << 16) | (byte3 << 24)

def press_a_button(core):
    """Press A using add_keys/clear_keys pattern"""
    core.add_keys(core.KEY_A)
    for _ in range(5):  # Hold for 5 frames
        core.run_frame()
    core.clear_keys(core.KEY_A)
    for _ in range(5):  # Release for 5 frames
        core.run_frame()

print("Testing button press with add_keys/clear_keys")

core = mgba.core.load_path(ROM_PATH)
core.reset()
core.autoload_save()

with open(SAVE_STATE_PATH, 'rb') as f:
    core.load_raw_state(f.read())

# RNG delay
delay = random.randint(30, 500)
print(f"RNG delay: {delay} frames")
for _ in range(delay):
    core.run_frame()

print("Press A #1")
press_a_button(core)
for _ in range(60):  # 1 second wait
    core.run_frame()

print("Press A #2")
press_a_button(core)
for _ in range(30):  # 0.5 second wait
    core.run_frame()

print("Press A #3")
press_a_button(core)

print("Waiting 300 frames for battle...")
for _ in range(300):
    core.run_frame()

# Check for Pokemon
party_addrs = [0x020244EC, 0x02024744, 0x020249EC]

print("\nChecking for Pokemon data...")
found = False
for addr in party_addrs:
    pv = read_u32(core, addr)
    if pv != 0:
        print(f"FOUND at 0x{addr:08X}: PV=0x{pv:08X}")
        pv_low = pv & 0xFFFF
        pv_high = (pv >> 16) & 0xFFFF
        shiny_val = (TID ^ SID) ^ (pv_low ^ pv_high)
        print(f"Shiny value: {shiny_val} ({'SHINY!' if shiny_val < 8 else 'Not shiny'})")
        found = True
        break

if not found:
    print("No Pokemon found - buttons didn't work")

