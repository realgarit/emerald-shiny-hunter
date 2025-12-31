#!/usr/bin/env python3
"""
Unified shiny hunting script for Pokemon Emerald.

Supports:
- Starter Pokemon (Torchic, Mudkip, Treecko) using soft reset method
- Wild encounters on all routes and dungeons using flee method

Usage:
    # Starters (soft reset method)
    python3 src/hunt.py --starter torchic
    python3 src/hunt.py --starter mudkip --show-window

    # Wild encounters (flee method)
    python3 src/hunt.py --route 101
    python3 src/hunt.py --route 102 --target ralts
    python3 src/hunt.py --location petalburg_woods --target slakoth
    python3 src/hunt.py --list-routes
"""

import random
import time
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    # Memory addresses
    PARTY_PV_ADDR,
    ENEMY_PV_ADDR, ENEMY_TID_ADDR, ENEMY_SPECIES_ADDR,
    # Keys
    KEY_NONE, KEY_LEFT, KEY_RIGHT,
    # Routes/dungeons
    ROUTE_ENCOUNTERS, DUNGEON_ENCOUNTERS,
    get_route_species, get_route_name,
    get_available_routes, get_available_dungeons,
    # Species
    SPECIES_NAMES, get_internal_id,
    # Starters
    STARTER_CONFIG, get_starter_config, get_available_starters, get_starter_species_dict,
)
from utils import (
    LogManager,
    check_shiny, decrypt_species, decrypt_species_extended,
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

# Timing constants
A_PRESSES_LOADING = 15
A_LOADING_DELAY_FRAMES = 20
LEFT_HOLD_FRAMES = 1
LEFT_WAIT_FRAMES = 20
RIGHT_HOLD_FRAMES = 1
RIGHT_WAIT_FRAMES = 20


def build_extended_species_dict(base_species: dict) -> dict:
    """
    Build extended species dict including National Dex fallbacks.

    Args:
        base_species: Dict mapping internal species ID to name

    Returns:
        Extended dict with National Dex number fallbacks
    """
    extended = dict(base_species)

    # Add National Dex number fallbacks for Gen III Pokemon
    for species_id, name in list(base_species.items()):
        # Gen III Pokemon have internal IDs 277-411 (National Dex 252-386)
        if species_id >= 277:
            national_dex = species_id - 25
            extended[national_dex] = name

    return extended


# =============================================================================
# Starter Shiny Hunter (Soft Reset Method)
# =============================================================================

class StarterShinyHunter(EmulatorBase):
    """Shiny hunter for starter Pokemon using soft reset method."""

    def __init__(self, starter_name, suppress_debug=True, show_window=False):
        """
        Initialize the starter shiny hunter.

        Args:
            starter_name: Name of starter (torchic, mudkip, or treecko)
            suppress_debug: Whether to suppress mGBA debug output
            show_window: Whether to show live game window
        """
        self.starter_config = get_starter_config(starter_name)
        if not self.starter_config:
            available = ', '.join(get_available_starters())
            raise ValueError(f"Unknown starter: {starter_name}. Available: {available}")

        self.starter_name = self.starter_config["name"]
        self.species_id = self.starter_config["species_id"]
        self.species_dict = get_starter_species_dict()

        # Initialize logging
        self.log_dir = PROJECT_ROOT / "logs"
        self.log_manager = LogManager(self.log_dir, f"{self.starter_name.lower()}_hunt")

        # Initialize base emulator
        super().__init__(
            rom_path=ROM_PATH,
            suppress_debug=suppress_debug,
            show_window=show_window,
            window_name=f"Shiny Hunter - {self.starter_name}"
        )

        self.attempts = 0
        self.start_time = time.time()

        print(f"[*] Logging to: {self.log_manager.get_log_path()}")
        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] TID: {TID}, SID: {SID}")
        print(f"[*] Shiny Formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8")
        print(f"[*] TID ^ SID = {TID} ^ {SID} = {TID ^ SID}")
        print(f"[*] Target: {self.starter_name} ({self.starter_config['position']} position)")
        print(f"[*] Using SOFT RESET method")
        print(f"[*] Starting shiny hunt...\n")

    def cleanup(self):
        """Clean up resources."""
        super().cleanup()
        if hasattr(self, 'log_manager'):
            self.log_manager.cleanup()

    def selection_sequence(self, verbose=False):
        """
        Execute the selection sequence for this starter.

        Uses config from constants/starters.py.
        """
        seq = self.starter_config["sequence"]

        if seq["type"] == "simple":
            # Torchic: Just press A repeatedly
            a_presses = seq["a_presses"]
            a_delay = seq["a_delay_frames"]

            if verbose:
                print(f"[*] Pressing A button up to {a_presses} times...")

            for i in range(a_presses):
                self.press_a(hold_frames=5, release_frames=5)

                # Check for Pokemon after each press (early exit)
                pv = self.read_memory_u32(PARTY_PV_ADDR)
                if pv != 0:
                    if verbose:
                        print(f"    Pokemon found after {i+1} presses!")
                    return True

                self.run_frames(a_delay)

                if verbose and (i + 1) % 5 == 0:
                    print(f"    Press {i+1}/{a_presses}...", end='\r')

            if verbose:
                print(f"    Press {a_presses}/{a_presses} complete!")

        else:
            # Mudkip/Treecko: Navigate then select
            a_dialogue = seq["a_dialogue_presses"]
            a_dialogue_delay = seq["a_dialogue_delay_frames"]
            wait_bag = seq["wait_for_bag_frames"]
            direction_key = seq["direction_key"]
            direction_presses = seq["direction_presses"]
            direction_delay = seq["direction_delay_frames"]
            wait_after = seq["wait_after_direction_frames"]
            a_select = seq["a_select_presses"]
            a_select_delay = seq["a_select_delay_frames"]
            max_retry = seq["max_retry_presses"]

            direction_name = "Left" if direction_key == KEY_LEFT else "Right"

            if verbose:
                print(f"[*] {a_dialogue} A dialogue -> wait -> "
                      f"{direction_presses}x {direction_name} -> wait -> {a_select} A select")

            # Step 1: Press A buttons to get through dialogue
            if verbose:
                print(f"    Pressing {a_dialogue} A buttons (dialogue)...", end='', flush=True)

            for i in range(a_dialogue):
                self.press_a(hold_frames=5, release_frames=5)
                self.run_frames(a_dialogue_delay)
                if verbose and (i + 1) % 5 == 0:
                    print(f" {i+1}...", end='', flush=True)

            if verbose:
                print(" Done")

            # Step 2: Wait for bag screen
            if verbose:
                print(f"    Waiting for bag screen...", end='', flush=True)
            self.run_frames(wait_bag)
            if verbose:
                print(" Done")

            # Step 3: Press direction key(s)
            if verbose:
                print(f"    Pressing {direction_name}...", end='', flush=True)

            for _ in range(direction_presses):
                if direction_key == KEY_LEFT:
                    self.press_left(hold_frames=10, release_frames=5)
                else:
                    self.press_right(hold_frames=10, release_frames=5)
                self.run_frames(direction_delay)

            if verbose:
                print(" Done")

            # Step 4: Wait after direction
            self.run_frames(wait_after)

            # Step 5: Press A to select and confirm
            if verbose:
                print(f"    Pressing {a_select} A buttons (select)...", end='', flush=True)

            for i in range(a_select):
                self.press_a(hold_frames=5, release_frames=5)
                self.run_frames(a_select_delay)

                # Check for Pokemon
                pv = self.read_memory_u32(PARTY_PV_ADDR)
                if pv != 0:
                    if verbose:
                        print(f" Found after {i+1}!")
                    return True

            if verbose:
                print(" Done")

            # Step 6: Retry presses if needed
            for i in range(max_retry):
                self.press_a(hold_frames=5, release_frames=5)
                self.run_frames(a_select_delay)

                pv = self.read_memory_u32(PARTY_PV_ADDR)
                if pv != 0:
                    return True

        return False

    def get_pokemon_species(self):
        """Get the Pokemon species ID and name from memory."""
        pv, species_id, species_name = decrypt_species(
            self.core, PARTY_PV_ADDR, self.species_dict,
            debug=(self.attempts <= 3)
        )
        return species_id, species_name

    def check_shiny(self):
        """Check if the starter Pokemon is shiny."""
        return check_shiny(self.core, PARTY_PV_ADDR, TID, SID)

    def hunt(self, max_attempts=None, error_retry_limit=3):
        """Main hunting loop for starter Pokemon using soft reset method."""
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


# =============================================================================
# Wild Pokemon Shiny Hunter (Flee Method)
# =============================================================================

class WildShinyHunter(EmulatorBase):
    """Shiny hunter for wild Pokemon encounters using flee method."""

    def __init__(self, location_id, suppress_debug=True, show_window=False, target_species=None):
        """
        Initialize the shiny hunter.

        Args:
            location_id: Route number (int) or dungeon key (str)
            suppress_debug: Whether to suppress mGBA debug output
            show_window: Whether to show live game window
            target_species: Optional target species name to hunt
        """
        self.location_id = location_id
        self.location_name = get_route_name(location_id)

        # Get species for this location
        base_species = get_route_species(location_id)
        if not base_species:
            raise ValueError(f"Unknown location: {location_id}")

        self.species_dict = build_extended_species_dict(base_species)

        # Build reverse mapping: name -> IDs
        self.species_name_to_ids = {}
        for species_id, name in self.species_dict.items():
            name_lower = name.lower()
            if name_lower not in self.species_name_to_ids:
                self.species_name_to_ids[name_lower] = set()
            self.species_name_to_ids[name_lower].add(species_id)

        # Set up logging
        self.log_dir = PROJECT_ROOT / "logs"
        location_slug = str(location_id).replace(" ", "_").lower()

        # Set up target species filtering
        if target_species:
            target_lower = target_species.lower()
            if target_lower not in self.species_name_to_ids:
                available = ', '.join(sorted(set(base_species.values())))
                raise ValueError(f"Invalid target species: {target_species}. Available: {available}")
            self.target_species_name = target_species.title()
            self.target_species_ids = self.species_name_to_ids[target_lower]
            log_suffix = f"_{target_lower}"
        else:
            self.target_species_name = None
            self.target_species_ids = set(self.species_dict.keys())
            log_suffix = "_all"

        # Initialize logging
        self.log_manager = LogManager(self.log_dir, f"hunt_{location_slug}{log_suffix}")

        # Initialize base emulator
        super().__init__(
            rom_path=ROM_PATH,
            suppress_debug=suppress_debug,
            show_window=show_window,
            window_name=f"Shiny Hunter - {self.location_name}"
        )

        # Run a few frames to populate the buffer
        for _ in range(10):
            self.core.run_frame()

        # Flee method tracking
        self.last_battle_pv = None
        self.last_direction = None

        self.attempts = 0
        self.start_time = time.time()

        # Print startup info
        print(f"[*] Logging to: {self.log_manager.get_log_path()}")
        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] Location: {self.location_name}")
        print(f"[*] TID: {TID}, SID: {SID}")
        print(f"[*] Shiny Formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8")
        print(f"[*] TID ^ SID = {TID} ^ {SID} = {TID ^ SID}")
        print(f"[*] Monitoring Enemy Party at 0x{ENEMY_PV_ADDR:08X}")
        if self.target_species_name:
            print(f"[*] Target species: {self.target_species_name} (non-targets will be logged/notified)")
        else:
            species_list = ', '.join(sorted(set(base_species.values())))
            print(f"[*] Target species: {species_list}")
        print(f"[*] Using FLEE method (flee from battle instead of resetting)")
        print(f"[*] Starting shiny hunt...\n")

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
        """Execute the flee sequence: Skip battle text and flee from battle."""
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
            if species_id in self.species_dict:
                return species_id, self.species_dict[species_id]
        except:
            pass

        # Try decryption method
        species_id, species_name = decrypt_species_extended(
            self.core, ENEMY_PV_ADDR, ENEMY_TID_ADDR,
            self.species_dict, debug=(self.attempts <= 3)
        )
        return species_id, species_name

    def check_shiny(self):
        """Check if the wild Pokemon is shiny."""
        return check_shiny(self.core, ENEMY_PV_ADDR, TID, SID)

    def hunt(self, max_attempts=None, error_retry_limit=3):
        """
        Main hunting loop using flee method.

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
        self.run_frames(15)

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
                    print(f"\n[*] Starting hunt on {self.location_name}...")
                    if self.target_species_name:
                        print(f"    Target: {self.target_species_name} (non-targets will be logged/notified)")
                    else:
                        print(f"    Target: All species at this location")

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
                    print(f"Location: {self.location_name}")
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


def list_locations():
    """Print all available hunting locations."""
    print("=" * 60)
    print("Available Hunting Locations")
    print("=" * 60)

    print("\n### Starters (Soft Reset Method) ###")
    for starter_name in get_available_starters():
        config = get_starter_config(starter_name)
        print(f"  {starter_name}: {config['name']} ({config['position']} position)")

    print("\n### Routes (Flee Method) ###")
    for route_num in get_available_routes():
        species = get_route_species(route_num)
        species_list = ', '.join(sorted(set(species.values())))
        print(f"  {route_num}: {species_list}")

    print("\n### Dungeons/Special Areas (Flee Method) ###")
    for dungeon_key in get_available_dungeons():
        species = get_route_species(dungeon_key)
        name = get_route_name(dungeon_key)
        species_list = ', '.join(sorted(set(species.values())))
        print(f"  {dungeon_key}: {name}")
        print(f"      {species_list}")

    print("\n" + "=" * 60)
    print("Usage examples:")
    print("  python3 src/hunt.py --starter torchic")
    print("  python3 src/hunt.py --starter mudkip --show-window")
    print("  python3 src/hunt.py --route 101")
    print("  python3 src/hunt.py --route 102 --target ralts")
    print("  python3 src/hunt.py --location petalburg_woods --target slakoth")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Pokemon Emerald Shiny Hunter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Use --list-routes to see all available locations and species.\n\n"
               "Examples:\n"
               "  # Starters (soft reset method)\n"
               "  python3 src/hunt.py --starter torchic\n"
               "  python3 src/hunt.py --starter mudkip --show-window\n\n"
               "  # Wild encounters (flee method)\n"
               "  python3 src/hunt.py --route 101\n"
               "  python3 src/hunt.py --route 102 --target ralts\n"
               "  python3 src/hunt.py --location petalburg_woods --target slakoth\n\n"
               "Starters use soft reset method. Wild encounters use flee method.\n"
               "When --target is specified for wild hunts, non-target shinies are still saved."
    )

    # Hunt type arguments (mutually exclusive)
    hunt_group = parser.add_mutually_exclusive_group()
    hunt_group.add_argument(
        '--starter', '-s',
        type=str,
        metavar='NAME',
        help='Starter Pokemon to hunt (torchic, mudkip, or treecko)'
    )
    hunt_group.add_argument(
        '--route', '-r',
        type=int,
        metavar='NUM',
        help='Route number to hunt on (e.g., 101, 102, 117)'
    )
    hunt_group.add_argument(
        '--location', '-l',
        type=str,
        metavar='KEY',
        help='Dungeon/area key to hunt in (e.g., petalburg_woods, granite_cave)'
    )
    hunt_group.add_argument(
        '--list-routes',
        action='store_true',
        help='List all available starters, routes, and dungeons'
    )

    parser.add_argument(
        '--target', '-t',
        type=str,
        metavar='SPECIES',
        help='Target species to hunt for wild encounters (case-insensitive)'
    )
    parser.add_argument(
        '--show-window', '-w',
        action='store_true',
        help='Display a live visualization window showing the game while hunting'
    )

    args = parser.parse_args()

    # Handle --list-routes
    if args.list_routes:
        list_locations()
        return

    hunter = None
    try:
        # Handle starter hunting
        if args.starter:
            starter_name = args.starter.lower()
            if starter_name not in get_available_starters():
                print(f"[!] Unknown starter: {args.starter}")
                print(f"[!] Available starters: {', '.join(get_available_starters())}")
                return

            if args.target:
                print("[!] Warning: --target is ignored for starter hunting")

            hunter = StarterShinyHunter(
                starter_name=starter_name,
                suppress_debug=True,
                show_window=args.show_window
            )
            hunter.hunt()

        # Handle route hunting
        elif args.route:
            location_id = args.route
            if location_id not in ROUTE_ENCOUNTERS:
                print(f"[!] Unknown route: {location_id}")
                print(f"[!] Available routes: {', '.join(map(str, get_available_routes()))}")
                return

            hunter = WildShinyHunter(
                location_id=location_id,
                suppress_debug=True,
                show_window=args.show_window,
                target_species=args.target
            )
            hunter.hunt()

        # Handle dungeon/location hunting
        elif args.location:
            location_id = args.location.lower()
            if location_id not in DUNGEON_ENCOUNTERS:
                print(f"[!] Unknown location: {location_id}")
                print(f"[!] Available dungeons: {', '.join(get_available_dungeons())}")
                return

            hunter = WildShinyHunter(
                location_id=location_id,
                suppress_debug=True,
                show_window=args.show_window,
                target_species=args.target
            )
            hunter.hunt()

        else:
            print("[!] Please specify what to hunt:")
            print("    --starter NAME   Hunt a starter (torchic, mudkip, treecko)")
            print("    --route NUM      Hunt on a route (101, 102, etc.)")
            print("    --location KEY   Hunt in a dungeon (petalburg_woods, etc.)")
            print("\nUse --list-routes to see all available options")
            return

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
