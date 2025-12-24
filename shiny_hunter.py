#!/usr/bin/env python3
"""
Pokémon Emerald Shiny Hunter - Automated Starter Reset Script
Uses mGBA Python bindings to hunt for shiny starters

Save state should be positioned before selecting the starter from Birch's bag.
"""

import mgba.core
import mgba.image
import random
import subprocess
import time
from datetime import datetime

# Configuration
ROM_PATH = "Pokemon - Emerald Version (U).gba"
SAVE_STATE_PATH = "save-state-1.ss0"

# Hardcoded trainer IDs (read from SRAM, but constant for this save)
TID = 56078
SID = 24723

# Memory addresses
PARTY_PV_ADDR = 0x020244EC  # Personality Value of first party Pokemon


class ShinyHunter:
    def __init__(self):
        self.core = mgba.core.load_path(ROM_PATH)
        if not self.core:
            raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

        self.core.reset()
        self.core.autoload_save()  # Load the .sav file
        self.attempts = 0
        self.start_time = time.time()

        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] TID: {TID}, SID: {SID}")
        print(f"[*] Starting shiny hunt...\n")

    def load_save_state(self):
        """Load the save state to reset the hunt"""
        try:
            with open(SAVE_STATE_PATH, 'rb') as f:
                state_data = f.read()
            self.core.load_raw_state(state_data)
            # Don't call autoload_save() here - it might overwrite memory
            return True
        except Exception as e:
            print(f"[!] Error loading save state: {e}")
            return False

    def run_frames(self, count):
        """Advance emulation by specified number of frames"""
        for _ in range(count):
            self.core.run_frame()

    def press_a(self, hold_frames=5, release_frames=5):
        """Press and release A button"""
        self.core._core.setKeys(self.core._core, 1)  # A = bit 0
        self.run_frames(hold_frames)
        self.core._core.setKeys(self.core._core, 0)
        self.run_frames(release_frames)

    def selection_sequence(self):
        """Execute the full selection button sequence (16 A presses)"""
        for _ in range(16):
            self.press_a(hold_frames=5, release_frames=5)
            self.run_frames(30)  # Wait between presses

    def read_u32(self, address):
        """Read 32-bit unsigned integer from memory"""
        b0 = self.core._core.busRead8(self.core._core, address)
        b1 = self.core._core.busRead8(self.core._core, address + 1)
        b2 = self.core._core.busRead8(self.core._core, address + 2)
        b3 = self.core._core.busRead8(self.core._core, address + 3)
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

    def check_shiny(self):
        """Check if the starter Pokémon is shiny"""
        pv = self.read_u32(PARTY_PV_ADDR)

        if pv == 0:
            return False, 0, 0

        # Calculate shiny value using Gen III formula
        pv_low = pv & 0xFFFF
        pv_high = (pv >> 16) & 0xFFFF
        shiny_value = (TID ^ SID) ^ (pv_low ^ pv_high)

        is_shiny = shiny_value < 8

        return is_shiny, pv, shiny_value

    def save_screenshot(self):
        """Save a screenshot of the shiny Pokémon"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"shiny_found_{timestamp}.png"

        try:
            width = 240
            height = 160
            image = mgba.image.Image(width, height)
            self.core.set_video_buffer(image)
            self.core.run_frame()

            with open(filename, 'wb') as f:
                image.save_png(f)
            print(f"[+] Screenshot saved: {filename}")
        except Exception as e:
            print(f"[!] Failed to save screenshot: {e}")

    def play_alert_sound(self):
        """Play system alert sound"""
        try:
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
        except Exception as e:
            print(f"[!] Failed to play sound: {e}")

    def hunt(self):
        """Main hunting loop"""
        while True:
            self.attempts += 1

            # Load save state
            if not self.load_save_state():
                print("[!] Failed to load save state. Exiting.")
                break

            # RNG variation: Write random seed to RNG address after loading state
            # Emerald RNG seed is at 0x03005D80
            RNG_ADDR = 0x03005D80
            random_seed = random.randint(0, 0xFFFFFFFF)

            # Write random seed to RNG memory location
            self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)

            # Also wait some frames to let things settle
            random_delay = random.randint(10, 100)
            self.run_frames(random_delay)

            # Execute selection sequence (16 A presses)
            self.selection_sequence()

            # Check if shiny
            is_shiny, pv, shiny_value = self.check_shiny()

            # Calculate rate
            elapsed = time.time() - self.start_time
            rate = self.attempts / elapsed if elapsed > 0 else 0

            # Progress update
            if pv != 0:
                print(f"[{self.attempts:6d}] PV: {pv:08X} | Shiny: {shiny_value:5d} | Rate: {rate:.2f}/s", end="")

                if is_shiny:
                    print("\n")
                    print("=" * 60)
                    print("SHINY FOUND!")
                    print("=" * 60)
                    print(f"Attempts: {self.attempts}")
                    print(f"Personality Value: 0x{pv:08X}")
                    print(f"Shiny Value: {shiny_value}")
                    print(f"Time Elapsed: {elapsed:.2f} seconds")
                    print("=" * 60)

                    self.save_screenshot()
                    self.play_alert_sound()
                    break
                else:
                    print("\r", end="")  # Overwrite line
            else:
                print(f"[{self.attempts:6d}] No Pokemon found - check save state position", end="\r")


def main():
    try:
        hunter = ShinyHunter()
        hunter.hunt()
    except KeyboardInterrupt:
        print("\n[!] Hunt interrupted by user.")
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
