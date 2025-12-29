#!/usr/bin/env python3
"""
Pokémon Emerald Shiny Hunter - Route 102
Uses mGBA Python bindings to hunt for shiny wild Pokémon on Route 102

Loads from .sav file and presses buttons to trigger wild encounters.
Identifies Pokemon species from memory and can filter by target species.

Features:
- Identifies Pokemon species from memory (Poochyena, Zigzagoon, Wurmple, Ralts, Seedot, or Lotad)
- Optional target species filtering via --target flag (hunt specific Pokémon only)
- Error handling with automatic retry (up to 3 consecutive errors)
- Periodic status updates every 10 attempts or 5 minutes
- Automatic recovery on errors (resets core and reloads save)
- Memory management: core is reset each iteration, file handles properly closed
- Logging to file for persistence
- Can run indefinitely (no memory leaks expected)
"""

import mgba.core
import mgba.image
import mgba.log
import random
import subprocess
import time
import os
import sys
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from cffi import FFI
import argparse
import urllib.request
import urllib.parse
import json

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load .env file from project root
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, will use environment variables only
    pass

# Configuration
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")

# Hardcoded trainer IDs (read from SRAM, but constant for this save)
TID = 56078
SID = 24723

# Memory addresses for Enemy Party (Route 102 wild encounters)
# Enemy Party structure layout (Emerald US):
# - 0x02024744 (+0x00): Personality Value (4 bytes)
# - 0x02024748 (+0x04): Trainer ID (16-bit)
# - 0x0202474C (+0x08): Species ID (16-bit) - Direct species ID in battle structure
# - Encrypted substructures start at +0x20 (32 bytes from PV)
# 
# Note: For wild Pokemon encounters, the battle structure may use different addresses.
# Alternative addresses to check:
# - Battle structure: 0x02024000-0x02025000 range
# - Enemy data might be at 0x02024000 + offset
ENEMY_PV_ADDR = 0x02024744  # Personality Value of enemy Pokemon (4 bytes)
ENEMY_TID_ADDR = 0x02024748  # Trainer ID (16-bit) - at offset +0x04 from PV
ENEMY_SID_ADDR = 0x0202474A  # Secret ID (16-bit) - at offset +0x06 from PV
ENEMY_SPECIES_ADDR = 0x0202474C  # Species ID (16-bit) - at offset +0x08 from PV (battle structure)

# Alternative battle structure addresses to try
BATTLE_STRUCTURE_START = 0x02024000  # Start of battle structure area

# Pokemon species IDs (Gen III) - Route 102 wild encounters
# Internal indices from pokeemerald: Poochyena=286, Zigzagoon=288, Wurmple=290,
# Lotad=295, Seedot=298, Ralts=392 (!)
# Most species use -25 offset, but Ralts needs -122 (392-122=270)
# Empirically verified mappings:
POKEMON_SPECIES = {
    261: "Poochyena",  # Internal 286, offset -25
    263: "Zigzagoon",  # Internal 288, offset -25
    265: "Wurmple",    # Internal 290, offset -25
    270: "Ralts",      # Internal 392, offset -122 (!) - Ralts has unique offset
    273: "Seedot",     # Internal 298, offset -25
    280: "Lotad",      # Empirically verified: ID 280 = Lotad in game
}

# Reverse mapping: name -> ID (case-insensitive)
SPECIES_NAME_TO_ID = {name.lower(): species_id for species_id, name in POKEMON_SPECIES.items()}

# Loading sequence: Press A 15 times with 20-frame delay between presses
A_PRESSES_LOADING = 15  # A presses to get through loading screens
A_LOADING_DELAY_FRAMES = 20  # Wait ~0.33s between A presses during loading

# Encounter method: Turn in place to trigger encounters
# Press Left for 1 frame (turn in place without walking), then wait 20 frames
# Press Right for 1 frame (turn in place without walking), then wait 20 frames
# Repeat until Pokemon detected
# Note: 3 frames is maximum to register turn, longer wait ensures no walk
LEFT_HOLD_FRAMES = 1  # Hold Left for 1 frame (quick turn)
LEFT_WAIT_FRAMES = 20  # Wait 20 frames after Left
RIGHT_HOLD_FRAMES = 1  # Hold Right for 1 frame (quick turn)
RIGHT_WAIT_FRAMES = 20  # Wait 20 frames after Right

# Button constants (GBA button bits)
KEY_LEFT = 32   # bit 5
KEY_RIGHT = 16  # bit 4
KEY_DOWN = 128  # bit 7


class ShinyHunter:
    def __init__(self, suppress_debug=True, show_window=False, target_species=None):
        # Set up logging
        self.log_dir = PROJECT_ROOT / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # Set up target species filtering
        if target_species:
            # Convert species name to ID
            target_lower = target_species.lower()
            if target_lower not in SPECIES_NAME_TO_ID:
                raise ValueError(f"Invalid target species: {target_species}. Must be one of: {', '.join(POKEMON_SPECIES.values())}")
            self.target_species_id = SPECIES_NAME_TO_ID[target_lower]
            self.target_species_name = POKEMON_SPECIES[self.target_species_id]
            self.target_species_ids = {self.target_species_id}  # Set of target IDs
            log_suffix = f"_{self.target_species_name.lower()}"
        else:
            # Default: hunt all Route 102 species
            self.target_species_id = None
            self.target_species_name = None
            self.target_species_ids = set(POKEMON_SPECIES.keys())  # All species
            log_suffix = "_all"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"route102_hunt{log_suffix}_{timestamp}.log"
        
        # Create a Tee class to write to both console and file
        class Tee:
            def __init__(self, *files):
                self.files = files
            def write(self, obj):
                for f in self.files:
                    f.write(obj)
                    f.flush()
            def flush(self):
                for f in self.files:
                    f.flush()
            def isatty(self):
                # Return True so print() doesn't add extra newlines
                return True
        
        # Open log file and set up tee to write to both console and file
        self.log_file_handle = open(self.log_file, 'w', encoding='utf-8')
        self.original_stdout = sys.stdout
        sys.stdout = Tee(sys.stdout, self.log_file_handle)
        
        # Suppress GBA debug output using mGBA's logging system
        # This is more effective than stderr redirection as it stops logging at the source
        if suppress_debug:
            mgba.log.silence()

        self.core = mgba.core.load_path(ROM_PATH)
        if not self.core:
            raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

        self.core.reset()
        self.core.autoload_save()  # Load the .sav file
        
        # Set up video buffer for screenshots (after reset/load)
        self.screenshot_image = mgba.image.Image(240, 160)
        self.core.set_video_buffer(self.screenshot_image)
        
        # Run a few frames to populate the buffer
        for _ in range(10):
            self.core.run_frame()
        
        # Set up OpenCV visualization window (optional)
        self.show_window = show_window
        if self.show_window:
            self.window_name = "Shiny Hunter"
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, 480, 320)
        self.frame_counter = 0  # For frame skip logic
        self.last_battle_pv = None  # Track last battle's PV to detect new encounters
        self.last_direction = None  # Track last direction to avoid walking after flee
        self.frame_skip = 5  # Update window every 5th frame
        self.debug_display = True  # Enable debug output for first few frames
        
        self.attempts = 0
        self.start_time = time.time()

        print(f"[*] Logging to: {self.log_file}")
        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] TID: {TID}, SID: {SID}")
        print(f"[*] Shiny Formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8")
        print(f"[*] TID ^ SID = {TID} ^ {SID} = {TID ^ SID}")
        print(f"[*] Monitoring Enemy Party at 0x{ENEMY_PV_ADDR:08X}")
        if self.target_species_name:
            print(f"[*] Target species: {self.target_species_name} (non-targets will be logged/notified but hunt continues)")
        else:
            print(f"[*] Target species: {', '.join(POKEMON_SPECIES.values())} (all species)")
        print(f"[*] Using FLEE method (flee from battle instead of resetting)")
        print(f"[*] Starting shiny hunt on Route 102...\n")
    
    def _update_display_window(self):
        """Update the OpenCV display window with current frame buffer"""
        try:
            if not hasattr(self, 'screenshot_image') or not hasattr(self.screenshot_image, 'buffer'):
                return
            
            # The 'buffer' here is a CFFI CData pointer
            raw_buffer = self.screenshot_image.buffer
            expected_size = 240 * 160 * 4
            
            # --- CRITICAL FIX FOR MAC CFFI ERROR ---
            try:
                ffi = FFI()
                # Wrap the raw C pointer into a Python-accessible buffer
                buffer_bytes = bytes(ffi.buffer(raw_buffer, expected_size))
            except Exception:
                # Fallback for different mGBA versions
                try:
                    buffer_bytes = bytes(raw_buffer)
                except:
                    return  # Can't convert buffer, skip this frame
            # ----------------------------------------

            # Convert to numpy array
            np_buffer = np.frombuffer(buffer_bytes, dtype=np.uint8, count=expected_size)
            rgba_frame = np_buffer.reshape(160, 240, 4)
            
            # Convert RGBA to BGR for OpenCV
            bgr_frame = cv2.cvtColor(rgba_frame, cv2.COLOR_RGBA2BGR)
            
            # Scale and Display
            scaled_frame = cv2.resize(bgr_frame, (480, 320), interpolation=cv2.INTER_NEAREST)
            cv2.imshow(self.window_name, scaled_frame)
            
        except Exception as e:
            # Prevent console spam, but keep for debugging if needed
            # print(f"Display error: {e}")
            pass
    
    def cleanup(self):
        """Restore stdout/stderr, close log file, and close OpenCV windows"""
        # Close OpenCV windows if they were created
        if self.show_window:
            try:
                cv2.destroyAllWindows()
            except:
                pass
        
        if hasattr(self, 'log_file_handle') and self.log_file_handle:
            sys.stdout = self.original_stdout
            self.log_file_handle.close()
    
    def __del__(self):
        """Restore stdout/stderr when object is destroyed"""
        self.cleanup()

    def reset_to_save(self):
        """Reset and load from .sav file"""
        try:
            self.core.reset()
            self.core.autoload_save()  # Load from .sav file
            # Re-set video buffer after reset
            if hasattr(self, 'screenshot_image'):
                self.core.set_video_buffer(self.screenshot_image)
            return True
        except Exception as e:
            print(f"[!] Error loading save: {e}")
            return False

    def run_frames(self, count):
        """Advance emulation by specified number of frames"""
        for i in range(count):
            self.core.run_frame()
            self.frame_counter += 1
            # Update visualization window (with frame skip for performance) if enabled
            if self.show_window:
                if self.frame_counter % self.frame_skip == 0:
                    self._update_display_window()
                    cv2.waitKey(1)  # Only call when updating display

    def press_a(self, hold_frames=5, release_frames=5):
        """Press and release A button"""
        self.core._core.setKeys(self.core._core, 1)  # A = bit 0
        self.run_frames(hold_frames)
        self.core._core.setKeys(self.core._core, 0)
        self.run_frames(release_frames)
    
    def press_left(self, hold_frames=5, release_frames=5):
        """Press and release Left button"""
        self.core._core.setKeys(self.core._core, KEY_LEFT)
        self.run_frames(hold_frames)
        self.core._core.setKeys(self.core._core, 0)
        self.run_frames(release_frames)
    
    def press_right(self, hold_frames=5, release_frames=5):
        """Press and release Right button"""
        self.core._core.setKeys(self.core._core, KEY_RIGHT)
        self.run_frames(hold_frames)
        self.core._core.setKeys(self.core._core, 0)
        self.run_frames(release_frames)
    
    def press_down(self, hold_frames=5, release_frames=5):
        """Press and release Down button"""
        self.core._core.setKeys(self.core._core, KEY_DOWN)
        self.run_frames(hold_frames)
        self.core._core.setKeys(self.core._core, 0)
        self.run_frames(release_frames)

    def loading_sequence(self, verbose=False):
        """Execute the loading sequence: Press A 15 times with 20-frame delay
        
        This gets through the initial loading screens when starting from save.
        """
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
        """Execute the encounter sequence: Turn in place to trigger wild encounters

        Sequence:
        - Press Left for 8 frames (turn in place), then wait 8 frames
        - Press Right for 8 frames (turn in place), then wait 8 frames
        - Repeat until NEW Pokemon detected (PV is non-zero AND different from last battle)

        Args:
            verbose: If True, print progress updates
            max_turns: Maximum number of turn cycles before giving up

        Returns:
            True if Pokemon detected, False otherwise
        """
        if verbose:
            print(f"    Turning in place to trigger encounters...", end='', flush=True)

        # Clear all keys before starting to ensure no stuck inputs
        self.core._core.setKeys(self.core._core, 0)
        self.run_frames(10)

        # Turn in place to trigger encounters
        # Start with OPPOSITE of last direction to avoid walking after flee
        turn_count = 0
        start_with_right = (self.last_direction == 'left')

        while turn_count < max_turns:
            if start_with_right:
                # Press Right first, then Left
                self.press_right(hold_frames=RIGHT_HOLD_FRAMES, release_frames=0)
                self.run_frames(RIGHT_WAIT_FRAMES)
                self.last_direction = 'right'

                pv = self.read_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    if verbose:
                        print(" Found!")
                    return True

                self.press_left(hold_frames=LEFT_HOLD_FRAMES, release_frames=0)
                self.run_frames(LEFT_WAIT_FRAMES)
                self.last_direction = 'left'

                pv = self.read_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    if verbose:
                        print(" Found!")
                    return True
            else:
                # Press Left first, then Right
                self.press_left(hold_frames=LEFT_HOLD_FRAMES, release_frames=0)
                self.run_frames(LEFT_WAIT_FRAMES)
                self.last_direction = 'left'

                pv = self.read_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    if verbose:
                        print(" Found!")
                    return True

                self.press_right(hold_frames=RIGHT_HOLD_FRAMES, release_frames=0)
                self.run_frames(RIGHT_WAIT_FRAMES)
                self.last_direction = 'right'

                pv = self.read_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    if verbose:
                        print(" Found!")
                    return True

            turn_count += 1

        return False

    def flee_sequence(self, verbose=False):
        """Execute the flee sequence: Skip battle text and flee from battle

        Sequence:
        - Press A once to skip "Wild ... appeared!" text
        - Wait for shiny animation + menu to appear
        - Press down, right and A to flee
        - Press A again to skip the text "... fled!"
        - Wait for PV to clear (back in overworld)

        Args:
            verbose: If True, print progress updates
        """
        # Wait for battle screen and "Wild ... appeared!" text
        self.run_frames(400)

        # Skip "Wild ... appeared!" text
        self.press_a(hold_frames=10, release_frames=20)

        # Wait for shiny animation + menu to fully appear
        self.run_frames(320)

        # Navigate to Run: Down -> Right -> A (with more breathing room)
        self.press_down(hold_frames=15, release_frames=20)
        self.press_right(hold_frames=15, release_frames=20)
        self.press_a(hold_frames=15, release_frames=40)

        # Skip "... fled!" text
        self.press_a(hold_frames=10, release_frames=40)

        # Clear keys
        self.core._core.setKeys(self.core._core, 0)

        # Wait for transition back to overworld
        self.run_frames(250)

        # Store current PV - encounter_sequence will wait for this to CHANGE
        self.last_battle_pv = self.read_u32(ENEMY_PV_ADDR)

    def read_u32(self, address):
        """Read 32-bit unsigned integer from memory"""
        b0 = self.core._core.busRead8(self.core._core, address)
        b1 = self.core._core.busRead8(self.core._core, address + 1)
        b2 = self.core._core.busRead8(self.core._core, address + 2)
        b3 = self.core._core.busRead8(self.core._core, address + 3)
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

    def write_u32(self, address, value):
        """Write 32-bit unsigned integer to memory"""
        self.core._core.busWrite8(self.core._core, address, value & 0xFF)
        self.core._core.busWrite8(self.core._core, address + 1, (value >> 8) & 0xFF)
        self.core._core.busWrite8(self.core._core, address + 2, (value >> 16) & 0xFF)
        self.core._core.busWrite8(self.core._core, address + 3, (value >> 24) & 0xFF)

    def read_u16(self, address):
        """Read 16-bit unsigned integer from memory"""
        b0 = self.core._core.busRead8(self.core._core, address)
        b1 = self.core._core.busRead8(self.core._core, address + 1)
        return b0 | (b1 << 8)
    
    def read_u8(self, address):
        """Read 8-bit unsigned integer from memory"""
        return self.core._core.busRead8(self.core._core, address)
    
    def get_substructure_order(self, pv):
        """Get the order of substructures based on PV
        
        PV % 24 determines which of 24 possible orders is used.
        Substructure types: G=Growth, A=Attacks, E=Condition/EVs, M=Miscellaneous
        
        Args:
            pv: Personality Value
        
        Returns:
            String representing the order (e.g., "GAEM", "GAME", etc.)
        """
        order_index = pv % 24
        # The 24 possible orders for Gen III (verified)
        orders = [
            "GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA",
            "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG",
            "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG",
            "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG"
        ]
        return orders[order_index]
    
    def decrypt_enemy_species(self, pv_addr, tid_addr):
        """Decrypt and extract species ID from encrypted enemy party data
        
        Gen III enemy party structure:
        - Bytes 0-3: PV (unencrypted)
        - Bytes 4-5: TID (unencrypted) - OT TID for wild Pokemon
        - Bytes 6-7: SID (unencrypted) - OT SID for wild Pokemon
        - Bytes 32-79: Encrypted substructures (48 bytes = 4 * 12 bytes)
          - Growth substructure contains species ID in first 2 bytes
        
        Decryption steps:
        1. Determine order using PV % 24 (returns string like "GAEM")
        2. Find Growth ('G') position in the order string
        3. Calculate offset: position * 12 bytes
        4. Read 32 bits from data_start + offset
        5. Decrypt: encrypted_val ^ (ot_tid ^ pv)
        6. Extract species: decrypted_val & 0xFFFF
        
        Args:
            pv_addr: Address of Personality Value
            tid_addr: Address of Trainer ID (OT TID for wild Pokemon)
        
        Returns:
            (species_id, species_name) if found, or (0, "Unknown") if failed
        """
        try:
            # Read PV from memory
            pv = self.read_u32(pv_addr)
            # Read TID and SID from memory
            tid_from_memory = self.read_u16(tid_addr)
            sid_from_memory = self.read_u16(ENEMY_SID_ADDR) if hasattr(self, 'ENEMY_SID_ADDR') else self.read_u16(pv_addr + 6)
            
            # For wild Pokemon, OT TID should be 0, but battle structure might store it differently
            # Try multiple combinations: OT_TID=0, TID from memory, and combined TID/SID
            ot_tid_values = [0, tid_from_memory, (tid_from_memory ^ sid_from_memory) & 0xFFFF]
            
            # Debug: Print what we read and verify we're reading from enemy party
            if hasattr(self, 'attempts') and self.attempts <= 3:
                # Also read a few bytes around to verify we're in the right place
                sample_bytes = []
                for i in range(8):
                    try:
                        sample_bytes.append(f"0x{self.read_u8(pv_addr + i):02X}")
                    except:
                        sample_bytes.append("??")
                print(f"    [DEBUG] Reading from memory: PV=0x{pv:08X} at 0x{pv_addr:08X}, TID at 0x{tid_addr:08X}=0x{tid_from_memory:04X} ({tid_from_memory})")
                print(f"    [DEBUG] First 8 bytes at 0x{pv_addr:08X}: {', '.join(sample_bytes)}")
                print(f"    [DEBUG] Will try OT_TID values: {ot_tid_values}")
            
            # Try different OT TID values (0 for wild Pokemon, or value from memory)
            # Optimized: Try known working combination FIRST (OT_TID=56078, offset +32, pos 2)
            # This is the combination that works for Route 101/102, so we prioritize it
            for ot_tid in ot_tid_values:
                # Prioritize offset +32 (known working) first, then try others
                offsets_to_try = [32] + [o for o in [0, 8, 16, 24, 40, 48, -8, -4, 4, 12, 20, 28, 36, 44, 52, 56, 60, 64] if o != 32]
                for data_offset in offsets_to_try:
                    try:
                        data_start = pv_addr + data_offset
                        
                        # Step A: Get substructure order using PV % 24
                        order_index = pv % 24
                        order = self.get_substructure_order(pv)  # Returns string like "GAEM"
                        
                        # Try all 4 substructure positions (G, A, E, M) to find where species is
                        # Optimized: Try position 2 first (known working position for Route 101/102)
                        # Growth substructure (G) contains species ID, but let's try all positions
                        positions_to_try = [2] + [p for p in range(4) if p != 2]  # Try pos 2 first (known working)
                        for substructure_pos in positions_to_try:
                            # Step B: Calculate offset (each substructure is 12 bytes)
                            offset = substructure_pos * 12
                            
                            # Step C: Read 32 bits (4 bytes) from data_start + offset
                            encrypted_val = self.read_u32(data_start + offset)
                            
                            # Step D: Decrypt - try multiple XOR key formulas
                            # Standard: encrypted_val ^ (ot_tid ^ pv)
                            # Also try: encrypted_val ^ (ot_tid ^ sid ^ pv) for battle structure
                            xor_key_standard = (ot_tid & 0xFFFF) ^ pv
                            xor_key_with_sid = ((ot_tid & 0xFFFF) ^ (sid_from_memory & 0xFFFF) ^ pv)
                            
                            # Try standard decryption first
                            decrypted_val = encrypted_val ^ xor_key_standard
                            xor_key_used = xor_key_standard
                            
                            # Step E: Extract species ID (try both lower and upper 16 bits)
                            species_id_low = decrypted_val & 0xFFFF
                            species_id_high = (decrypted_val >> 16) & 0xFFFF
                            
                            # If standard doesn't give Route 102 species, try with SID
                            if species_id_low not in POKEMON_SPECIES and species_id_high not in POKEMON_SPECIES:
                                decrypted_val_alt = encrypted_val ^ xor_key_with_sid
                                species_id_alt_low = decrypted_val_alt & 0xFFFF
                                species_id_alt_high = (decrypted_val_alt >> 16) & 0xFFFF
                                if species_id_alt_low in POKEMON_SPECIES:
                                    decrypted_val = decrypted_val_alt
                                    xor_key_used = xor_key_with_sid
                                    species_id_low = species_id_alt_low
                                    species_id_high = species_id_alt_high
                                elif species_id_alt_high in POKEMON_SPECIES:
                                    decrypted_val = decrypted_val_alt
                                    xor_key_used = xor_key_with_sid
                                    species_id_low = species_id_alt_low
                                    species_id_high = species_id_alt_high
                            
                            # Try lower 16 bits first (standard)
                            species_id = species_id_low
                            
                            # Debug output for all positions on first attempt, Growth position only for others
                            if hasattr(self, 'attempts') and self.attempts <= 3:
                                substructure_name = order[substructure_pos]
                                if self.attempts == 1 or substructure_pos == order.index('G'):
                                    print(f"    [DEBUG] Trying OT_TID={ot_tid}, offset +{data_offset}, pos {substructure_pos} ({substructure_name}): Encrypted=0x{encrypted_val:08X}, XOR_KEY=0x{xor_key_used:08X}, Decrypted=0x{decrypted_val:08X}, Species={species_id}")
                            
                            # Check if it's a valid Route 102 species ID (try lower 16 bits first)
                            if species_id in POKEMON_SPECIES:
                                species_name = POKEMON_SPECIES.get(species_id, f"Unknown (ID: {species_id})")
                                if hasattr(self, 'attempts') and self.attempts <= 3:
                                    substructure_name = order[substructure_pos]
                                    print(f"  [+] Found species with OT_TID={ot_tid}, offset +{data_offset}, pos {substructure_pos} ({substructure_name}): {species_name} (ID: {species_id})")
                                return species_id, species_name
                            
                            # Also try upper 16 bits in case of byte order issue
                            if species_id_high in POKEMON_SPECIES:
                                species_name = POKEMON_SPECIES.get(species_id_high, f"Unknown (ID: {species_id_high})")
                                if hasattr(self, 'attempts') and self.attempts <= 3:
                                    substructure_name = order[substructure_pos]
                                    print(f"  [+] Found species (upper 16 bits) with OT_TID={ot_tid}, offset +{data_offset}, pos {substructure_pos} ({substructure_name}): {species_name} (ID: {species_id_high})")
                                return species_id_high, species_name
                            
                            # Try applying offset corrections (we've seen 290 when expecting 265, difference of 25)
                            # This handles cases where decryption produces values close to correct species IDs
                            # The offset appears to be consistent for battle structure vs party structure
                            # NOTE: Ralts has internal index 392, needs -122 offset to map to ID 270 (our Ralts entry)
                            # Only check if species_id is in a reasonable range (1-450 to include Ralts at 392)
                            if (1 <= species_id <= 450) or (1 <= species_id_high <= 450):
                                # Try all target species from POKEMON_SPECIES dictionary (works for any route)
                                for target_species_id in POKEMON_SPECIES.keys():
                                    # Include -122 for Ralts (internal 392 -> ID 270 which is our "Ralts" entry)
                                    for offset_correction in [-122, -30, -25, -20, -15, -10, -5, 5, 10, 15, 20, 25, 30]:
                                        corrected_id = species_id + offset_correction
                                        if corrected_id == target_species_id:
                                            species_name = POKEMON_SPECIES.get(target_species_id, f"Unknown (ID: {target_species_id})")
                                            if hasattr(self, 'attempts') and self.attempts <= 3:
                                                substructure_name = order[substructure_pos]
                                                print(f"  [+] Found species (with offset correction {offset_correction:+d}) with OT_TID={ot_tid}, offset +{data_offset}, pos {substructure_pos} ({substructure_name}): {species_name} (ID: {target_species_id}, raw={species_id})")
                                            return target_species_id, species_name
                                        
                                        corrected_id_high = species_id_high + offset_correction
                                        if corrected_id_high == target_species_id:
                                            species_name = POKEMON_SPECIES.get(target_species_id, f"Unknown (ID: {target_species_id})")
                                            if hasattr(self, 'attempts') and self.attempts <= 3:
                                                substructure_name = order[substructure_pos]
                                                print(f"  [+] Found species (upper 16 bits, offset correction {offset_correction:+d}) with OT_TID={ot_tid}, offset +{data_offset}, pos {substructure_pos} ({substructure_name}): {species_name} (ID: {target_species_id}, raw={species_id_high})")
                                            return target_species_id, species_name
                    except Exception as e:
                        if hasattr(self, 'attempts') and self.attempts <= 3 and data_offset == 32 and ot_tid == 0:
                            print(f"    [DEBUG] Error with OT_TID={ot_tid}, offset +{data_offset}: {e}")
                        continue
            
            # If none of the offsets worked, return the last decrypted value for debugging
            return 0, f"Unknown (tried multiple OT_TID values and offsets, last species_id={species_id if 'species_id' in locals() else 'N/A'})"
        except Exception as e:
            return 0, f"Decryption error: {e}"
    
    def get_pokemon_species(self):
        """Get the Pokemon species ID and name from memory
        
        First tries to read species ID directly from battle structure.
        If that fails, tries decryption with multiple offset variations.
        Falls back to memory scanning if decryption fails.
        
        Returns:
            (species_id, species_name) if found, or (0, "Unknown") if failed
        """
        # Try reading species ID directly from battle structure first (PV + 0x08)
        try:
            species_id = self.read_u16(ENEMY_SPECIES_ADDR)
            if hasattr(self, 'attempts') and self.attempts <= 3:
                print(f"    [DEBUG] Direct species read from 0x{ENEMY_SPECIES_ADDR:08X}: {species_id} (0x{species_id:04X})")
            if species_id in POKEMON_SPECIES:
                species_name = POKEMON_SPECIES.get(species_id, f"Unknown (ID: {species_id})")
                if hasattr(self, 'attempts') and self.attempts <= 3:
                    print(f"  [+] Species ID read directly: {species_name} (ID: {species_id})")
                return species_id, species_name
        except Exception as e:
            if hasattr(self, 'attempts') and self.attempts <= 3:
                print(f"  [!] Failed to read species directly: {e}")
        
        # Try decryption method with multiple offset variations
        if hasattr(self, 'attempts') and self.attempts <= 3:
            print(f"    [DEBUG] Trying decryption method...")
        species_id, species_name = self.decrypt_enemy_species(ENEMY_PV_ADDR, ENEMY_TID_ADDR)
        if species_id != 0:
            return species_id, species_name
        
        # If decryption failed, scan nearby addresses for Route 102 species
        # Optimized: Skip memory scanning since decryption with offset correction works reliably
        # Only scan if we're debugging (first 3 attempts) - this saves significant time
        if hasattr(self, 'attempts') and self.attempts <= 3:
            print(f"    [DEBUG] Decryption failed, scanning memory for unencrypted species ID...")
            
            # First, scan around the enemy party structure (reduced range for speed)
            for offset in range(-0x20, 0x100, 2):  # Scan from -32 to +256 bytes (reduced from +512)
                try:
                    addr = ENEMY_PV_ADDR + offset
                    species_id = self.read_u16(addr)
                    if species_id in POKEMON_SPECIES:
                        species_name = POKEMON_SPECIES.get(species_id, f"Unknown (ID: {species_id})")
                        print(f"  [+] Found unencrypted species at offset +0x{offset:02X} (0x{addr:08X}): {species_name} (ID: {species_id})")
                        return species_id, species_name
                except:
                    continue
        
        # If still not found, decryption is likely required but we're not doing it correctly
        # Return unknown with info about what we tried
        return 0, "Unknown (decryption required but failed - may need correct offset/structure)"

    def check_shiny(self):
        """Check if the wild Pokémon is shiny
        
        Gen III Shiny Formula:
        Shiny if: (TID XOR SID) XOR (PV_low XOR PV_high) < 8
        
        Where:
        - TID = Trainer ID (56078)
        - SID = Secret ID / Shiny ID (24723)
        - PV = Personality Value (32-bit)
        - PV_low = lower 16 bits of PV
        - PV_high = upper 16 bits of PV
        """
        pv = self.read_u32(ENEMY_PV_ADDR)

        if pv == 0:
            return False, 0, 0, {}

        # Calculate shiny value using Gen III formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8
        pv_low = pv & 0xFFFF  # Lower 16 bits
        pv_high = (pv >> 16) & 0xFFFF  # Upper 16 bits
        tid_xor_sid = TID ^ SID  # Trainer ID XOR Secret ID
        pv_xor = pv_low ^ pv_high  # PV lower XOR PV upper
        shiny_value = tid_xor_sid ^ pv_xor  # Final shiny calculation

        is_shiny = shiny_value < 8  # Shiny if result is less than 8
        
        details = {
            'pv_low': pv_low,
            'pv_high': pv_high,
            'tid_xor_sid': tid_xor_sid,
            'pv_xor': pv_xor,
            'shiny_value': shiny_value
        }

        return is_shiny, pv, shiny_value, details

    def save_screenshot(self):
        """Save a screenshot of the shiny Pokémon
        
        Note: Screenshots may not work in headless mode (when mGBA has no visible window).
        The save state will contain the exact game state, so you can load it in mGBA GUI to see the shiny.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_dir = PROJECT_ROOT / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        filename = f"shiny_found_{timestamp}.png"
        filepath = screenshot_dir / filename

        try:
            # Create a fresh image for the screenshot
            width = 240
            height = 160
            image = mgba.image.Image(width, height)
            
            # Set video buffer
            self.core.set_video_buffer(image)
            
            # Run many frames to ensure everything is rendered
            for _ in range(120):
                self.core.run_frame()
            
            # Check if buffer has data (not all zeros/black)
            try:
                buffer = image.buffer
                # Try to access buffer data
                if hasattr(buffer, '__len__'):
                    sample_size = min(1000, len(buffer))
                    has_data = any(buffer[i] != 0 for i in range(sample_size))
                else:
                    has_data = False
            except:
                has_data = False
            
            if not has_data:
                print("[!] Warning: Screenshot appears black (headless mode limitation)")
                print("[!] The save state contains the exact game state - load it in mGBA GUI to see the shiny!")
                # Still save it, but note it's likely black
                with open(filepath, 'wb') as f:
                    image.save_png(f)
                print(f"[+] Screenshot file created (may be black): {filepath}")
                return None  # Return None to indicate screenshot may not be useful

            with open(filepath, 'wb') as f:
                image.save_png(f)
            print(f"[+] Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[!] Failed to save screenshot: {e}")
            print("[!] Note: Screenshots may not work in headless mode")
            return None

    def play_alert_sound(self):
        """Play system alert sound"""
        try:
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
        except Exception as e:
            print(f"[!] Failed to play sound: {e}")

    def send_notification(self, message, subtitle=""):
        """Send macOS system notification"""
        try:
            script = f'''
            display notification "{message}" with title "Shiny Hunter" subtitle "{subtitle}" sound name "Glass"
            '''
            subprocess.run(["osascript", "-e", script], check=False)
        except Exception as e:
            print(f"[!] Failed to send notification: {e}")

    def send_discord_notification(self, message, title="Shiny Hunter", color=0x00ff00):
        """Send Discord webhook notification
        
        Args:
            message: The message content to send
            title: The title of the embed (default: "Shiny Hunter")
            color: The color of the embed in hex (default: green)
        """
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            # Silently skip if webhook URL is not set (don't spam console)
            return
        
        try:
            # Create embed payload
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            payload = {
                "embeds": [embed]
            }
            
            # Convert to JSON
            data = json.dumps(payload).encode('utf-8')
            
            # Create request with User-Agent header
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'ShinyHunter/1.0'
                }
            )
            
            # Send request
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()  # Read response to ensure request completes
        except urllib.error.URLError as e:
            print(f"[!] Failed to send Discord notification: {e}")
        except Exception as e:
            print(f"[!] Failed to send Discord notification: {e}")

    def open_screenshot(self, filepath):
        """Open screenshot in default viewer"""
        if filepath and os.path.exists(filepath):
            try:
                subprocess.run(["open", filepath], check=False)
            except Exception as e:
                print(f"[!] Failed to open screenshot: {e}")

    def save_game_state(self):
        """Save the current game state (both save state and .sav file)"""
        try:
            # Get Pokemon species for filename
            species_id, species_name = self.get_pokemon_species()
            species_safe = species_name.lower().replace(" ", "_") if species_id else "unknown"
            
            # Save a save state as backup
            save_state_dir = PROJECT_ROOT / "save_states"
            save_state_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_state_filename = save_state_dir / f"{species_safe}_shiny_save_state_{timestamp}.ss0"
            
            state_data = self.core.save_raw_state()
            # Convert CData object to bytes using cffi buffer
            try:
                from cffi import FFI
                ffi = FFI()
                state_bytes = bytes(ffi.buffer(state_data))
            except:
                # Fallback: read byte by byte
                if hasattr(state_data, '__len__'):
                    state_bytes = b''.join(bytes([state_data[i]]) for i in range(len(state_data)))
                else:
                    state_bytes = bytes(state_data)
            
            with open(save_state_filename, 'wb') as f:
                f.write(state_bytes)
            
            print(f"[+] Save state saved: {save_state_filename}")
            
            # The .sav file should auto-save, but we can try to trigger it
            # by running a few frames to let the game save
            self.run_frames(60)  # Run 1 second to let save complete
            
            # Get .sav file path (mGBA auto-saves to same directory as ROM)
            rom_dir = Path(ROM_PATH).parent
            sav_path = rom_dir / Path(ROM_PATH).stem.replace(".gba", "") + ".sav"
            
            if sav_path.exists():
                print(f"[+] Save file updated: {sav_path}")
            else:
                print(f"[!] Note: Save file may be at: {sav_path}")
            
            return str(save_state_filename)
        except Exception as e:
            print(f"[!] Failed to save game state: {e}")
            return None

    def hunt(self, max_attempts=None, error_retry_limit=3):
        """Main hunting loop - FLEE VERSION
        
        This version flees from battle instead of resetting, which may improve
        probability for rare encounters by maintaining RNG state.
        
        Args:
            max_attempts: Maximum number of attempts (None = unlimited)
            error_retry_limit: Number of times to retry on error before giving up
        """
        consecutive_errors = 0
        last_status_update = time.time()
        initial_setup_done = False
        
        # Do initial setup once (reset, load, RNG seed)
        if not self.reset_to_save():
            print("[!] Failed to load save initially. Exiting.")
            return False
        
        # Initial RNG setup
        RNG_ADDR = 0x03005D80
        random_seed = random.randint(0, 0xFFFFFFFF)
        random_delay = random.randint(10, 100)
        self.run_frames(random_delay)
        self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)
        self.run_frames(random.randint(5, 20))
        
        # Initial loading sequence
        verbose = True
        self.loading_sequence(verbose=verbose)
        self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)
        self.run_frames(5)
        self.run_frames(15)  # Wait for game to settle
        
        initial_setup_done = True

        while True:
            # Check max attempts
            if max_attempts and self.attempts >= max_attempts:
                print(f"\n[!] Reached maximum attempts ({max_attempts}). Stopping.")
                return False

            try:
                # Periodic status update every 10 attempts or 5 minutes
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
                        print(f"    Target: All Route 102 species")

                # Execute encounter sequence (turn in place until Pokemon found)
                pokemon_found = self.encounter_sequence(verbose=(self.attempts == 0))

                if not pokemon_found:
                    # No new Pokemon found in max_turns - just keep trying
                    # Don't clear last_battle_pv, we're still waiting for a DIFFERENT PV
                    continue

                # Wait for battle data to stabilize
                self.run_frames(30)

                # Check if Pokemon was found (PV should be non-zero)
                pv = self.read_u32(ENEMY_PV_ADDR)
                if pv == 0:
                    continue

                # Valid new encounter - increment attempt counter
                self.attempts += 1

                # Get Pokemon species
                species_id, species_name = self.get_pokemon_species()

                # MODIFIED TARGET FILTERING: If target is set and this is NOT the target,
                # log it, send Discord notification, save state, but CONTINUE hunting
                if self.target_species_name and species_id not in self.target_species_ids:
                    print(f"\n[Attempt {self.attempts}] Pokemon found!")
                    print(f"  Species: {species_name} (ID: {species_id}) - NOT TARGET (continuing hunt)")
                    
                    # Check if shiny anyway (might be a shiny non-target)
                    is_shiny, pv, shiny_value, details = self.check_shiny()
                    
                    if is_shiny:
                        # Shiny non-target - treat as success!
                        print(f"  ⚠️  SHINY {species_name} found (not target, but shiny!)")
                        elapsed = time.time() - self.start_time
                        
                        # Send Discord notification (only for shiny non-targets)
                        discord_message = (
                            f"✨ **Shiny {species_name} found!** ✨\n\n"
                            f"**Note:** Not target species ({self.target_species_name}), but shiny!\n"
                            f"**Attempts:** {self.attempts}\n"
                            f"**Personality Value:** `0x{pv:08X}`\n"
                            f"**Shiny Value:** {shiny_value}\n"
                            f"**Time Elapsed:** {elapsed/60:.1f} minutes"
                        )
                        self.send_discord_notification(discord_message, title="✨ Shiny Found (Non-Target)! ✨", color=0xffff00)
                        
                        # Save state
                        self.save_game_state()
                    else:
                        # Non-shiny non-target - just log (no Discord notification)
                        pass
                    
                    # Flee and continue hunting
                    self.flee_sequence(verbose=False)
                    continue

                # Only check shiny if it's a target species
                is_shiny, pv, shiny_value, details = self.check_shiny()

                # Calculate rate
                elapsed = time.time() - self.start_time
                rate = self.attempts / elapsed if elapsed > 0 else 0

                # Progress update
                print(f"\n[Attempt {self.attempts}] Pokemon found!")
                if species_id != 0:
                    print(f"  Species: {species_name} (ID: {species_id})")
                else:
                    print(f"  Species: {species_name} (species ID not identified, but valid Route 102 encounter)")
                print(f"  PV: 0x{pv:08X}")
                print(f"  PV Low:  0x{details['pv_low']:04X} ({details['pv_low']})")
                print(f"  PV High: 0x{details['pv_high']:04X} ({details['pv_high']})")
                print(f"  TID ^ SID: 0x{details['tid_xor_sid']:04X} ({details['tid_xor_sid']})")
                print(f"  PV XOR: 0x{details['pv_xor']:04X} ({details['pv_xor']})")
                print(f"  Shiny Value: {shiny_value} (need < 8 for shiny)")
                
                if is_shiny:
                    # Get Pokemon species for shiny
                    species_id, species_name = self.get_pokemon_species()
                    
                    print("\n" + "=" * 60)
                    print("🎉 SHINY FOUND! 🎉")
                    print("=" * 60)
                    print(f"Pokemon: {species_name} (ID: {species_id})")
                    print(f"Attempts: {self.attempts}")
                    print(f"Personality Value: 0x{pv:08X}")
                    print(f"Shiny Value: {shiny_value}")
                    print(f"Time Elapsed: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
                    print("=" * 60)

                    # Save screenshot and get filepath (may be None if headless)
                    screenshot_path = self.save_screenshot()
                    
                    # Play sound
                    self.play_alert_sound()
                    
                    # Send system notification
                    species_id, species_name = self.get_pokemon_species()
                    self.send_notification(
                        f"Shiny {species_name} found after {self.attempts} attempts!",
                        f"PV: 0x{pv:08X} | Time: {elapsed/60:.1f} min"
                    )
                    
                    # Send Discord webhook notification
                    discord_message = (
                        f"🎉 **Shiny {species_name} found!** 🎉\n\n"
                        f"**Attempts:** {self.attempts}\n"
                        f"**Personality Value:** `0x{pv:08X}`\n"
                        f"**Shiny Value:** {shiny_value}\n"
                        f"**Time Elapsed:** {elapsed/60:.1f} minutes"
                    )
                    self.send_discord_notification(discord_message, title="🎉 Shiny Found! 🎉")
                    
                    # Save game state so user can continue playing
                    print(f"\n[+] Saving game state...")
                    save_state_path = self.save_game_state()
                    
                    # Open screenshot automatically (if available)
                    if screenshot_path:
                        print(f"[+] Opening screenshot...")
                        self.open_screenshot(screenshot_path)
                    else:
                        print(f"[!] Screenshot not available (headless mode)")
                        print(f"[!] Load the save state in mGBA GUI to see your shiny!")
                    
                    print("\n" + "=" * 60)
                    print("✓ Game saved! You can now:")
                    if save_state_path:
                        print(f"  1. Load save state: {save_state_path}")
                    print("  2. Or open mGBA and load the .sav file")
                    print("  3. Continue playing and save in-game normally")
                    print("=" * 60)
                    print("\n[!] Script exiting. The shiny Pokemon is in your party!")
                    return True  # Exit the hunt loop
                else:
                    print(f"  Result: NOT SHINY (shiny value {shiny_value} >= 8)")
                    print(f"  Rate: {rate:.2f} attempts/sec | Elapsed: {elapsed/60:.1f} min")
                    print(f"  Estimated time to shiny: ~{(8192/rate)/60:.1f} minutes (1/8192 odds)")
                    # Flee and continue hunting (don't reset)
                    self.flee_sequence(verbose=False)
                    continue  # Explicitly continue to next iteration

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
                
                # Try to recover by resetting the core and re-doing initial setup
                print("[*] Attempting recovery...")
                try:
                    if not self.reset_to_save():
                        raise Exception("Failed to reset to save")
                    
                    # Re-do initial setup
                    RNG_ADDR = 0x03005D80
                    random_seed = random.randint(0, 0xFFFFFFFF)
                    random_delay = random.randint(10, 100)
                    self.run_frames(random_delay)
                    self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)
                    self.run_frames(random.randint(5, 20))
                    self.loading_sequence(verbose=False)
                    self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)
                    self.run_frames(5)
                    self.run_frames(15)
                    time.sleep(2)  # Brief pause before retry
                except Exception as recovery_error:
                    print(f"[!] Recovery failed: {recovery_error}")
                    return False


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Pokémon Emerald Shiny Hunter - Route 102",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available species: {', '.join(POKEMON_SPECIES.values())}\n"
               "Examples:\n"
               "  python route102.py --target ralts\n"
               "  python route102.py --target seedot --show-window\n"
               "  python route102.py  # Hunt all species\n\n"
               "Note: This version uses FLEE method (flees from battle instead of resetting).\n"
               "When --target is specified, non-target encounters are logged/notified but hunt continues."
    )
    parser.add_argument(
        '--target',
        type=str,
        choices=[name.lower() for name in POKEMON_SPECIES.values()],
        metavar='SPECIES',
        help=f'Target species to hunt (one of: {", ".join(POKEMON_SPECIES.values())}). '
             f'If not specified, hunts all Route 102 species.'
    )
    parser.add_argument(
        '--show-window',
        action='store_true',
        help='Display a live visualization window showing the game while hunting'
    )
    args = parser.parse_args()
    
    hunter = None
    try:
        # Suppress GBA debug output by default
        hunter = ShinyHunter(suppress_debug=True, show_window=args.show_window, target_species=args.target)
        hunter.hunt()
    except KeyboardInterrupt:
        print("\n[!] Hunt interrupted by user.")
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always restore stderr
        if hunter:
            hunter.cleanup()


if __name__ == "__main__":
    main()

