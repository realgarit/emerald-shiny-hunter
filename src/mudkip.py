#!/usr/bin/env python3
"""
Shiny hunt for Mudkip starter.

Mudkip is to the right of Torchic, selected with A dialogue -> Right -> A select.
"""

import random
import time
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    SPECIES_TREECKO, SPECIES_TORCHIC, SPECIES_MUDKIP,
    PARTY_PV_ADDR, PARTY_TID_ADDR,
    RNG_SEED_ADDR,
)
from utils import (
    LogManager,
    decrypt_species, check_shiny,
    notify_shiny_found, open_file,
    save_screenshot, save_game_state,
)
from core import EmulatorBase

# Try to load dotenv for Discord webhook configuration
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Configuration
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")

# Hardcoded trainer IDs (constant for this save)
TID = 56078
SID = 24723

# Pokemon species for starters
POKEMON_SPECIES = {
    SPECIES_TREECKO: "Treecko",  # 277
    SPECIES_TORCHIC: "Torchic",  # 280
    SPECIES_MUDKIP: "Mudkip",    # 283
}

# Selection sequence constants for Mudkip (right of center)
# 20 A dialogue -> wait 0.5s -> 1x Right -> wait 0.2s -> 6 A select
A_PRESSES_DIALOGUE = 20
WAIT_FOR_BAG_FRAMES = 30
RIGHT_PRESS_COUNT = 1
RIGHT_PRESS_DELAY_FRAMES = 15
WAIT_AFTER_RIGHT_FRAMES = 12
A_PRESSES_SELECT = 6
A_SELECT_DELAY_FRAMES = 15
A_PRESS_DELAY_FRAMES = 15
MAX_RETRY_PRESSES = 8


class ShinyHunter(EmulatorBase):
    """Shiny hunter for Mudkip starter."""

    def __init__(self, suppress_debug=True, show_window=False):
        # Initialize logging
        self.log_dir = PROJECT_ROOT / "logs"
        self.log_manager = LogManager(self.log_dir, "mudkip_hunt")

        # Initialize base emulator
        super().__init__(
            rom_path=ROM_PATH,
            suppress_debug=suppress_debug,
            show_window=show_window,
            window_name="Shiny Hunter - Mudkip"
        )

        self.attempts = 0
        self.start_time = time.time()

        print(f"[*] Logging to: {self.log_manager.get_log_path()}")
        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] TID: {TID}, SID: {SID}")
        print(f"[*] Shiny Formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8")
        print(f"[*] TID ^ SID = {TID} ^ {SID} = {TID ^ SID}")
        print(f"[*] Target: Mudkip (right position)")
        print(f"[*] Starting shiny hunt...\n")

    def cleanup(self):
        """Clean up resources."""
        super().cleanup()
        if hasattr(self, 'log_manager'):
            self.log_manager.cleanup()

    def selection_sequence(self, verbose=False):
        """
        Execute the selection sequence for Mudkip.

        Sequence: 20 A dialogue -> wait 0.5s -> 1x Right -> wait 0.2s -> 6 A select
        """
        wait_bag_seconds = WAIT_FOR_BAG_FRAMES / 60.0
        wait_right_seconds = WAIT_AFTER_RIGHT_FRAMES / 60.0

        if verbose:
            print(f"[*] {A_PRESSES_DIALOGUE} A dialogue -> wait {wait_bag_seconds:.1f}s -> "
                  f"{RIGHT_PRESS_COUNT}x Right -> wait {wait_right_seconds:.1f}s -> {A_PRESSES_SELECT} A select")

        # Step 1: Press A buttons to get through dialogue
        if verbose:
            print(f"    Pressing {A_PRESSES_DIALOGUE} A buttons (dialogue)...", end='', flush=True)

        for i in range(A_PRESSES_DIALOGUE):
            self.press_a(hold_frames=5, release_frames=5)
            self.run_frames(A_PRESS_DELAY_FRAMES)
            if verbose and (i + 1) % 5 == 0:
                print(f" {i+1}...", end='', flush=True)

        if verbose:
            print(" Done")

        # Step 2: Wait for bag screen
        if verbose:
            print(f"    Waiting {wait_bag_seconds:.2f}s for bag screen...", end='', flush=True)
        self.run_frames(WAIT_FOR_BAG_FRAMES)
        if verbose:
            print(" Done")

        # Step 3: Press Right to move to Mudkip
        if verbose:
            print(f"    Pressing Right {RIGHT_PRESS_COUNT} time(s)...", end='', flush=True)
        for _ in range(RIGHT_PRESS_COUNT):
            self.press_right(hold_frames=5, release_frames=5)
            self.run_frames(RIGHT_PRESS_DELAY_FRAMES)
        if verbose:
            print(" Done")

        # Step 4: Wait after Right
        if verbose:
            print(f"    Waiting {wait_right_seconds:.2f}s after Right...", end='', flush=True)
        self.run_frames(WAIT_AFTER_RIGHT_FRAMES)
        if verbose:
            print(" Done")

        # Step 5: Press A buttons to select Mudkip
        if verbose:
            print(f"    Pressing {A_PRESSES_SELECT} A buttons to select...", end='', flush=True)

        pokemon_found = False
        for i in range(A_PRESSES_SELECT):
            self.press_a(hold_frames=5, release_frames=5)

            pv = self.read_memory_u32(PARTY_PV_ADDR)
            if pv != 0:
                pokemon_found = True
                if verbose:
                    print(f" Pokemon found after {i+1} A presses!")
                return True

            self.run_frames(A_SELECT_DELAY_FRAMES)

        # Retry if not found
        if not pokemon_found:
            if verbose:
                print(f" (not found yet, retrying...)", end='', flush=True)
            for i in range(MAX_RETRY_PRESSES):
                self.press_a(hold_frames=5, release_frames=5)
                pv = self.read_memory_u32(PARTY_PV_ADDR)
                if pv != 0:
                    if verbose:
                        print(f" Pokemon found after {A_PRESSES_SELECT + i + 1} A presses!")
                    return True
                self.run_frames(A_PRESS_DELAY_FRAMES * 2)

        if verbose:
            print(" Done")

        return pokemon_found

    def get_pokemon_species(self):
        """Get the Pokemon species ID and name from memory."""
        pv, species_id, species_name = decrypt_species(
            self.core, PARTY_PV_ADDR, POKEMON_SPECIES,
            debug=(self.attempts <= 3)
        )
        return species_id, species_name

    def check_shiny(self):
        """Check if the starter Pokemon is shiny."""
        return check_shiny(self.core, PARTY_PV_ADDR, TID, SID)

    def hunt(self, max_attempts=None, error_retry_limit=3):
        """Main hunting loop for starter Pokemon."""
        consecutive_errors = 0
        last_status_update = time.time()

        while True:
            if max_attempts and self.attempts >= max_attempts:
                print(f"\n[!] Reached maximum attempts ({max_attempts}). Stopping.")
                return False

            self.attempts += 1

            try:
                if not self.reset_to_save():
                    consecutive_errors += 1
                    print(f"[!] Failed to load save (error {consecutive_errors}/{error_retry_limit})")
                    if consecutive_errors >= error_retry_limit:
                        print("[!] Too many consecutive errors. Exiting.")
                        return False
                    time.sleep(1)
                    continue

                consecutive_errors = 0

                # RNG manipulation
                random_seed = random.randint(0, 0xFFFFFFFF)
                random_delay = random.randint(10, 100)
                self.run_frames(random_delay)
                self.write_rng_seed(random_seed)
                self.run_frames(random.randint(5, 20))

                # Periodic status update
                elapsed = time.time() - self.start_time
                if (self.attempts % 10 == 0) or (time.time() - last_status_update > 300):
                    rate = self.attempts / elapsed if elapsed > 0 else 0
                    print(f"\n[Status] Attempt {self.attempts} | Rate: {rate:.2f}/s | "
                          f"Elapsed: {elapsed/60:.1f} min | Running smoothly...")
                    last_status_update = time.time()

                print(f"\n[Attempt {self.attempts}] Starting new reset...")
                print(f"  RNG Seed: 0x{random_seed:08X}, Delay: {random_delay} frames")

                # Execute selection sequence
                pokemon_found = self.selection_sequence(verbose=(self.attempts <= 3))

                # Re-write RNG seed and wait for data
                self.write_rng_seed(random_seed)
                self.run_frames(5)
                self.run_frames(60)

                # Extra retries if not found
                pv = self.read_memory_u32(PARTY_PV_ADDR)
                if pv == 0 and not pokemon_found:
                    for retry in range(5):
                        self.press_a(hold_frames=5, release_frames=5)
                        self.run_frames(60)
                        pv = self.read_memory_u32(PARTY_PV_ADDR)
                        if pv != 0:
                            break
                    if pv == 0:
                        self.run_frames(90)
                        pv = self.read_memory_u32(PARTY_PV_ADDR)

                # Get Pokemon species
                species_id, species_name = self.get_pokemon_species()

                # Check if shiny
                is_shiny, pv, shiny_value, details = self.check_shiny()

                elapsed = time.time() - self.start_time
                rate = self.attempts / elapsed if elapsed > 0 else 0

                if pv != 0:
                    print(f"\n[Attempt {self.attempts}] Pokemon found!")
                    print(f"  Species: {species_name} (ID: {species_id})")
                    print(f"  PV: 0x{pv:08X}")
                    print(f"  PV Low:  0x{details['pv_low']:04X} ({details['pv_low']})")
                    print(f"  PV High: 0x{details['pv_high']:04X} ({details['pv_high']})")
                    print(f"  TID ^ SID: 0x{details['tid_xor_sid']:04X} ({details['tid_xor_sid']})")
                    print(f"  PV XOR: 0x{details['pv_xor']:04X} ({details['pv_xor']})")
                    print(f"  Shiny Value: {shiny_value} (need < 8 for shiny)")

                    if is_shiny:
                        print("\n" + "=" * 60)
                        print("SHINY FOUND!")
                        print("=" * 60)
                        print(f"Pokemon: {species_name} (ID: {species_id})")
                        print(f"Attempts: {self.attempts}")
                        print(f"Personality Value: 0x{pv:08X}")
                        print(f"Shiny Value: {shiny_value}")
                        print(f"Time Elapsed: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
                        print("=" * 60)

                        screenshot_path = save_screenshot(self.core, PROJECT_ROOT / "screenshots")
                        notify_shiny_found(species_name, self.attempts, pv, shiny_value, elapsed / 60)

                        print(f"\n[+] Saving game state...")
                        save_state_path = save_game_state(self.core, PROJECT_ROOT / "save_states", species_name, self.run_frames)

                        if screenshot_path:
                            print(f"[+] Opening screenshot...")
                            open_file(screenshot_path)
                        else:
                            print(f"[!] Screenshot not available (headless mode)")
                            print(f"[!] Load the save state in mGBA GUI to see your shiny!")

                        print("\n" + "=" * 60)
                        print("Game saved! You can now:")
                        if save_state_path:
                            print(f"  1. Load save state: {save_state_path}")
                        print("  2. Or open mGBA and load the .sav file")
                        print("  3. Continue playing and save in-game normally")
                        print("=" * 60)
                        print("\n[!] Script exiting. The shiny Pokemon is in your party!")
                        return True
                    else:
                        print(f"  Result: NOT SHINY (shiny value {shiny_value} >= 8)")
                        print(f"  Rate: {rate:.2f} attempts/sec | Elapsed: {elapsed/60:.1f} min")
                        print(f"  Estimated time to shiny: ~{(8192/rate)/60:.1f} minutes (1/8192 odds)")
                else:
                    print(f"[Attempt {self.attempts}] No Pokemon found yet - checking...")
                    print(f"  PV at 0x{PARTY_PV_ADDR:08X}: 0x{pv:08X}")

            except Exception as e:
                consecutive_errors += 1
                elapsed = time.time() - self.start_time
                print(f"\n[!] Error on attempt {self.attempts}: {e}")
                print(f"[!] Consecutive errors: {consecutive_errors}/{error_retry_limit}")

                if consecutive_errors >= error_retry_limit:
                    print("[!] Too many consecutive errors. Exiting.")
                    import traceback
                    traceback.print_exc()
                    return False

                print("[*] Attempting recovery...")
                try:
                    self.reset_to_save()
                    time.sleep(2)
                except Exception as recovery_error:
                    print(f"[!] Recovery failed: {recovery_error}")
                    return False


def main():
    parser = argparse.ArgumentParser(description='Hunt for shiny Mudkip in Pokemon Emerald')
    parser.add_argument('--show-window', action='store_true',
                        help='Show live visualization window')
    args = parser.parse_args()

    hunter = None
    try:
        hunter = ShinyHunter(suppress_debug=True, show_window=args.show_window)
        hunter.hunt()
    except KeyboardInterrupt:
        print("\n[!] Hunt interrupted by user.")
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hunter:
            hunter.cleanup()


if __name__ == "__main__":
    main()
