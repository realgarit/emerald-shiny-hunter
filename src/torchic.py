#!/usr/bin/env python3
"""
Shiny hunt for Torchic starter.

Torchic is the default starter (center position), selected with just A presses.
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

# Selection sequence constants for Torchic (center position, just A presses)
A_PRESSES_NEEDED = 26
A_PRESS_DELAY_FRAMES = 15


class ShinyHunter(EmulatorBase):
    """Shiny hunter for Torchic starter."""

    def __init__(self, suppress_debug=True, show_window=False):
        # Initialize logging
        self.log_dir = PROJECT_ROOT / "logs"
        self.log_manager = LogManager(self.log_dir, "torchic_hunt")

        # Initialize base emulator
        super().__init__(
            rom_path=ROM_PATH,
            suppress_debug=suppress_debug,
            show_window=show_window,
            window_name="Shiny Hunter - Torchic"
        )

        self.attempts = 0
        self.start_time = time.time()

        print(f"[*] Logging to: {self.log_manager.get_log_path()}")
        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] TID: {TID}, SID: {SID}")
        print(f"[*] Shiny Formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8")
        print(f"[*] TID ^ SID = {TID} ^ {SID} = {TID ^ SID}")
        print(f"[*] Target: Torchic (center position)")
        print(f"[*] Starting shiny hunt...\n")

    def cleanup(self):
        """Clean up resources."""
        super().cleanup()
        if hasattr(self, 'log_manager'):
            self.log_manager.cleanup()

    def selection_sequence(self, verbose=False):
        """
        Execute the selection sequence for Torchic.

        Torchic is the default center position, so we just press A.
        """
        if verbose:
            print(f"[*] Pressing A button up to {A_PRESSES_NEEDED} times...")

        for i in range(A_PRESSES_NEEDED):
            self.press_a(hold_frames=5, release_frames=5)

            # Check for Pokemon after each press (early exit if found)
            pv = self.read_memory_u32(PARTY_PV_ADDR)
            if pv != 0:
                if verbose:
                    print(f"    Pokemon found after {i+1} presses!")
                return True

            self.run_frames(A_PRESS_DELAY_FRAMES)

            if verbose and (i + 1) % 5 == 0:
                print(f"    Press {i+1}/{A_PRESSES_NEEDED}...", end='\r')

        if verbose:
            print(f"    Press {A_PRESSES_NEEDED}/{A_PRESSES_NEEDED} complete!")

        return False

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
                # Reset and load from .sav file
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
                self.selection_sequence(verbose=(self.attempts <= 3))

                # Re-write RNG seed and wait for data
                self.write_rng_seed(random_seed)
                self.run_frames(5)
                self.run_frames(60)

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
    parser = argparse.ArgumentParser(description='Hunt for shiny Torchic in Pokemon Emerald')
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
