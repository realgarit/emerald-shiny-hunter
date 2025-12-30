#!/usr/bin/env python3
"""
Shiny hunt for wild Pokemon on Route 101 using flee method.

Based on route102.py flee method - flees from battle instead of resetting.
"""

import random
import time
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    SPECIES_POOCHYENA, SPECIES_ZIGZAGOON, SPECIES_WURMPLE,
    ENEMY_PV_ADDR, ENEMY_TID_ADDR, ENEMY_SID_ADDR, ENEMY_SPECIES_ADDR,
    RNG_SEED_ADDR,
    KEY_LEFT, KEY_RIGHT, KEY_DOWN, KEY_NONE,
    NATIONAL_DEX, get_internal_id,
)
from utils import (
    LogManager,
    read_u32, read_u16,
    check_shiny, decrypt_species_extended,
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

# Pokemon species for Route 101
# Using both internal IDs and National Dex numbers for robust matching
POKEMON_SPECIES = {
    SPECIES_POOCHYENA: "Poochyena",  # Internal: 286, National Dex: 261
    SPECIES_ZIGZAGOON: "Zigzagoon",  # Internal: 288, National Dex: 263
    SPECIES_WURMPLE: "Wurmple",      # Internal: 290, National Dex: 265
}

# Extended species dict including National Dex numbers for decryption fallback
POKEMON_SPECIES_EXTENDED = {
    **POKEMON_SPECIES,
    # National Dex numbers (used when decryption returns dex number instead of internal ID)
    get_internal_id(261): "Poochyena",  # Dex #261 -> Internal 286
    get_internal_id(263): "Zigzagoon",  # Dex #263 -> Internal 288
    get_internal_id(265): "Wurmple",    # Dex #265 -> Internal 290
    # Also accept raw National Dex numbers as fallback
    261: "Poochyena",
    263: "Zigzagoon",
    265: "Wurmple",
}

# Reverse mapping: name -> ID (case-insensitive)
SPECIES_NAME_TO_ID = {name.lower(): species_id for species_id, name in POKEMON_SPECIES_EXTENDED.items()}

# Loading sequence constants
A_PRESSES_LOADING = 15
A_LOADING_DELAY_FRAMES = 20

# Encounter method: Turn in place (matching route102 exactly)
# Hold=1 frame, Wait=20 frames
LEFT_HOLD_FRAMES = 1
LEFT_WAIT_FRAMES = 20
RIGHT_HOLD_FRAMES = 1
RIGHT_WAIT_FRAMES = 20


class ShinyHunter(EmulatorBase):
    """Shiny hunter for Route 101 wild encounters using flee method."""

    def __init__(self, suppress_debug=True, show_window=False, target_species=None):
        # Set up logging first
        self.log_dir = PROJECT_ROOT / "logs"

        # Set up target species filtering
        if target_species:
            target_lower = target_species.lower()
            if target_lower not in SPECIES_NAME_TO_ID:
                raise ValueError(f"Invalid target species: {target_species}. Must be one of: {', '.join(set(POKEMON_SPECIES.values()))}")
            self.target_species_id = SPECIES_NAME_TO_ID[target_lower]
            self.target_species_name = POKEMON_SPECIES_EXTENDED[self.target_species_id]
            self.target_species_ids = {self.target_species_id}
            # Also add the offset-corrected version
            for sid, name in POKEMON_SPECIES_EXTENDED.items():
                if name == self.target_species_name:
                    self.target_species_ids.add(sid)
            log_suffix = f"_{self.target_species_name.lower()}"
        else:
            self.target_species_id = None
            self.target_species_name = None
            self.target_species_ids = set(POKEMON_SPECIES_EXTENDED.keys())
            log_suffix = "_all"

        # Initialize logging
        self.log_manager = LogManager(self.log_dir, f"route101_hunt{log_suffix}")

        # Initialize base emulator
        super().__init__(
            rom_path=ROM_PATH,
            suppress_debug=suppress_debug,
            show_window=show_window,
            window_name="Shiny Hunter - Route 101"
        )

        # Run a few frames to populate the buffer
        for _ in range(10):
            self.core.run_frame()

        # Flee method tracking
        self.last_battle_pv = None
        self.last_direction = None

        self.attempts = 0
        self.start_time = time.time()

        print(f"[*] Logging to: {self.log_manager.get_log_path()}")
        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] TID: {TID}, SID: {SID}")
        print(f"[*] Shiny Formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8")
        print(f"[*] TID ^ SID = {TID} ^ {SID} = {TID ^ SID}")
        print(f"[*] Monitoring Enemy Party at 0x{ENEMY_PV_ADDR:08X}")
        if self.target_species_name:
            print(f"[*] Target species: {self.target_species_name} (non-targets will be logged/notified but hunt continues)")
        else:
            print(f"[*] Target species: {', '.join(set(POKEMON_SPECIES.values()))} (all species)")
        print(f"[*] Using FLEE method (flee from battle instead of resetting)")
        print(f"[*] Starting shiny hunt on Route 101...\n")

    def cleanup(self):
        """Clean up resources."""
        super().cleanup()
        if hasattr(self, 'log_manager'):
            self.log_manager.cleanup()

    def loading_sequence(self, verbose=False):
        """Execute the loading sequence: Press A 15 times with 20-frame delay."""
        if verbose:
            print(f"    Pressing {A_PRESSES_LOADING} A buttons (loading screens)...", end='', flush=True)

        for i in range(A_PRESSES_LOADING):
            self.press_a(hold_frames=5, release_frames=5)
            self.run_frames(A_LOADING_DELAY_FRAMES)
            if verbose and (i + 1) % 5 == 0:
                print(f" {i+1}...", end='', flush=True)

        if verbose:
            print(" Done")

    def encounter_sequence(self, verbose=False, max_turns=1000):
        """
        Execute the encounter sequence: Turn in place to trigger wild encounters.

        Uses flee method timings: Hold=1 frame, Wait=20 frames.
        Matches route102.py exactly.
        """
        if verbose:
            print(f"    Turning in place to trigger encounters...", end='', flush=True)

        # Clear all keys before starting
        self.set_keys(KEY_NONE)
        self.run_frames(10)

        turn_count = 0
        start_with_right = (self.last_direction == 'left')

        while turn_count < max_turns:
            if start_with_right:
                # Press Right first, then Left
                self.press_right(hold_frames=RIGHT_HOLD_FRAMES, release_frames=0)
                self.run_frames(RIGHT_WAIT_FRAMES)
                self.last_direction = 'right'

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    if verbose:
                        print(" Found!")
                    return True

                self.press_left(hold_frames=LEFT_HOLD_FRAMES, release_frames=0)
                self.run_frames(LEFT_WAIT_FRAMES)
                self.last_direction = 'left'

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    if verbose:
                        print(" Found!")
                    return True
            else:
                # Press Left first, then Right
                self.press_left(hold_frames=LEFT_HOLD_FRAMES, release_frames=0)
                self.run_frames(LEFT_WAIT_FRAMES)
                self.last_direction = 'left'

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    if verbose:
                        print(" Found!")
                    return True

                self.press_right(hold_frames=RIGHT_HOLD_FRAMES, release_frames=0)
                self.run_frames(RIGHT_WAIT_FRAMES)
                self.last_direction = 'right'

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    if verbose:
                        print(" Found!")
                    return True

            turn_count += 1

        return False

    def flee_sequence(self, verbose=False):
        """
        Execute the flee sequence: Skip battle text and flee from battle.

        Matches route102.py exactly.
        """
        # Wait for battle screen and "Wild ... appeared!" text
        self.run_frames(400)

        # Skip "Wild ... appeared!" text
        self.press_a(hold_frames=10, release_frames=20)

        # Wait for shiny animation + menu to fully appear
        self.run_frames(320)

        # Navigate to Run: Down -> Right -> A
        self.press_down(hold_frames=15, release_frames=20)
        self.press_right(hold_frames=15, release_frames=20)
        self.press_a(hold_frames=15, release_frames=40)

        # Skip "... fled!" text
        self.press_a(hold_frames=10, release_frames=40)

        # Clear keys
        self.set_keys(KEY_NONE)

        # Wait for transition back to overworld
        self.run_frames(250)

        # Store current PV - encounter_sequence will wait for this to CHANGE
        self.last_battle_pv = self.read_memory_u32(ENEMY_PV_ADDR)

    def get_pokemon_species(self):
        """Get the Pokemon species ID and name from memory."""
        # Try reading species ID directly from battle structure first
        try:
            species_id = self.read_memory_u16(ENEMY_SPECIES_ADDR)
            if species_id in POKEMON_SPECIES_EXTENDED:
                return species_id, POKEMON_SPECIES_EXTENDED[species_id]
        except:
            pass

        # Try decryption method
        species_id, species_name = decrypt_species_extended(
            self.core, ENEMY_PV_ADDR, ENEMY_TID_ADDR,
            POKEMON_SPECIES_EXTENDED, debug=(self.attempts <= 3)
        )
        return species_id, species_name

    def check_shiny(self):
        """Check if the wild Pokemon is shiny."""
        return check_shiny(self.core, ENEMY_PV_ADDR, TID, SID)

    def hunt(self, max_attempts=None, error_retry_limit=3):
        """
        Main hunting loop - FLEE VERSION.

        Flees from battle instead of resetting to maintain RNG state.
        """
        consecutive_errors = 0
        last_status_update = time.time()

        # Do initial setup once
        if not self.reset_to_save():
            print("[!] Failed to load save initially. Exiting.")
            return False

        # Initial RNG setup
        random_seed = random.randint(0, 0xFFFFFFFF)
        random_delay = random.randint(10, 100)
        self.run_frames(random_delay)
        self.write_rng_seed(random_seed)
        self.run_frames(random.randint(5, 20))

        # Initial loading sequence
        self.loading_sequence(verbose=True)
        self.write_rng_seed(random_seed)
        self.run_frames(5)
        self.run_frames(15)  # Wait for game to settle

        while True:
            if max_attempts and self.attempts >= max_attempts:
                print(f"\n[!] Reached maximum attempts ({max_attempts}). Stopping.")
                return False

            try:
                # Periodic status update
                elapsed = time.time() - self.start_time
                if self.attempts > 0 and ((self.attempts % 10 == 0) or (time.time() - last_status_update > 300)):
                    rate = self.attempts / elapsed if elapsed > 0 else 0
                    print(f"\n[Status] Attempt {self.attempts} | Rate: {rate:.2f}/s | "
                          f"Elapsed: {elapsed/60:.1f} min | Running smoothly...")
                    last_status_update = time.time()

                if self.attempts == 0:
                    print(f"\n[*] Starting hunt...")
                    if self.target_species_name:
                        print(f"    Target: {self.target_species_name} (non-targets will be logged/notified)")
                    else:
                        print(f"    Target: All Route 101 species")

                # Execute encounter sequence
                pokemon_found = self.encounter_sequence(verbose=(self.attempts == 0))

                if not pokemon_found:
                    continue

                # Wait for battle data to stabilize
                self.run_frames(30)

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv == 0:
                    continue

                # Valid new encounter
                self.attempts += 1
                consecutive_errors = 0

                # Get Pokemon species
                species_id, species_name = self.get_pokemon_species()

                # Handle non-target species
                if self.target_species_name and species_id not in self.target_species_ids:
                    print(f"\n[Attempt {self.attempts}] Pokemon found!")
                    print(f"  Species: {species_name} (ID: {species_id}) - NOT TARGET (continuing hunt)")

                    # Check if shiny anyway
                    is_shiny, pv, shiny_value, details = self.check_shiny()

                    if is_shiny:
                        print(f"  SHINY {species_name} found (not target, but shiny!)")
                        elapsed = time.time() - self.start_time
                        notify_shiny_found(species_name, self.attempts, pv, shiny_value, elapsed / 60, is_target=False)
                        save_game_state(self.core, PROJECT_ROOT / "save_states", species_name, self.run_frames)

                    self.flee_sequence(verbose=False)
                    continue

                # Check shiny for target species
                is_shiny, pv, shiny_value, details = self.check_shiny()

                elapsed = time.time() - self.start_time
                rate = self.attempts / elapsed if elapsed > 0 else 0

                # Progress update
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

                    # Save screenshot
                    screenshot_path = save_screenshot(self.core, PROJECT_ROOT / "screenshots")

                    # Send notifications
                    notify_shiny_found(species_name, self.attempts, pv, shiny_value, elapsed / 60)

                    # Save game state
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
                    self.flee_sequence(verbose=False)
                    continue

            except Exception as e:
                consecutive_errors += 1
                elapsed = time.time() - self.start_time
                print(f"\n[!] Error on attempt {self.attempts}: {e}")
                print(f"[!] Consecutive errors: {consecutive_errors}/{error_retry_limit}")

                if consecutive_errors >= error_retry_limit:
                    print("[!] Too many consecutive errors. Exiting.")
                    print(f"[!] Total attempts before error: {self.attempts - 1}")
                    print(f"[!] Total time: {elapsed/60:.1f} minutes")
                    import traceback
                    traceback.print_exc()
                    return False

                # Try to recover
                print("[*] Attempting recovery...")
                try:
                    if not self.reset_to_save():
                        raise Exception("Failed to reset to save")

                    random_seed = random.randint(0, 0xFFFFFFFF)
                    random_delay = random.randint(10, 100)
                    self.run_frames(random_delay)
                    self.write_rng_seed(random_seed)
                    self.run_frames(random.randint(5, 20))
                    self.loading_sequence(verbose=False)
                    self.write_rng_seed(random_seed)
                    self.run_frames(5)
                    self.run_frames(15)
                    time.sleep(2)
                except Exception as recovery_error:
                    print(f"[!] Recovery failed: {recovery_error}")
                    return False


def main():
    parser = argparse.ArgumentParser(
        description="Pokemon Emerald Shiny Hunter - Route 101 (Flee Method)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available species: {', '.join(set(POKEMON_SPECIES.values()))}\n"
               "Examples:\n"
               "  python route101.py --target zigzagoon\n"
               "  python route101.py --target poochyena --show-window\n"
               "  python route101.py  # Hunt all species\n\n"
               "Note: This version uses FLEE method (flees from battle instead of resetting).\n"
               "When --target is specified, non-target encounters are logged/notified but hunt continues."
    )
    parser.add_argument(
        '--target',
        type=str,
        choices=[name.lower() for name in set(POKEMON_SPECIES.values())],
        metavar='SPECIES',
        help=f'Target species to hunt (one of: {", ".join(set(POKEMON_SPECIES.values()))}). '
             f'If not specified, hunts all Route 101 species.'
    )
    parser.add_argument(
        '--show-window',
        action='store_true',
        help='Display a live visualization window showing the game while hunting'
    )
    args = parser.parse_args()

    hunter = None
    try:
        hunter = ShinyHunter(suppress_debug=True, show_window=args.show_window, target_species=args.target)
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
