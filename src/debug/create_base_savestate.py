#!/usr/bin/env python3
"""
Create base_with_boxes.ss0 from .sav file with box data loaded into RAM.
Required for combine_box_shinies.py to work correctly.
"""

import mgba.core
import mgba.log
import os
import sys
from pathlib import Path
from cffi import FFI

sys.stderr = open(os.devnull, 'w')
mgba.log.silence()

PROJECT_ROOT = Path(__file__).parent.parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")
SAVE_STATES_DIR = PROJECT_ROOT / "save_states"

def read_u32(core, addr):
    b0 = core._core.busRead8(core._core, addr)
    b1 = core._core.busRead8(core._core, addr + 1)
    b2 = core._core.busRead8(core._core, addr + 2)
    b3 = core._core.busRead8(core._core, addr + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

def main():
    print("Loading from .sav file...")

    core = mgba.core.load_path(ROM_PATH)
    core.reset()
    core.autoload_save()

    # Run frames to let game load - need many more for save data to fully load
    for _ in range(600):
        core.run_frame()

    # Check storage pointer
    storage_ptr = read_u32(core, 0x03005D94)
    print(f"gPokemonStoragePtr: 0x{storage_ptr:08X}")

    if storage_ptr != 0:
        box_base = storage_ptr + 4
        print(f"Box 1 base: 0x{box_base:08X}")

        print("\nFirst 10 slots of Box 1:")
        for i in range(10):
            addr = box_base + i * 80
            pv = read_u32(core, addr)
            if pv != 0:
                print(f"  Slot {i+1}: PV=0x{pv:08X} (occupied)")
            else:
                print(f"  Slot {i+1}: (empty)")

        # If we found box data, save a state
        pv = read_u32(core, box_base)
        if pv != 0:
            print("\n[+] Box data found! Saving state...")
            output_path = SAVE_STATES_DIR / "base_with_boxes.ss0"
            state_data = core.save_raw_state()
            ffi = FFI()
            state_bytes = bytes(ffi.buffer(state_data))
            with open(output_path, 'wb') as f:
                f.write(state_bytes)
            print(f"[+] Saved to: {output_path.name} ({len(state_bytes)} bytes)")
        else:
            print("\n[!] Box 1 Slot 1 is empty")
    else:
        print("Storage pointer is NULL")

if __name__ == "__main__":
    main()
