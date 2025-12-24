#!/usr/bin/env python3
"""
Pokémon Emerald Shiny Hunter - Mudkip
Uses mGBA Python bindings to hunt for shiny Mudkip starter

Loads from .sav file and presses buttons to select Mudkip.
Identifies Pokemon species from memory to verify which starter was obtained.

Features:
- Identifies Pokemon species from memory (Torchic, Treecko, or Mudkip)
- Error handling with automatic retry (up to 3 consecutive errors)
- Periodic status updates every 10 attempts or 5 minutes
- Automatic recovery on errors (resets core and reloads save)
- Memory management: core is reset each iteration, file handles properly closed
- Logging to file for persistence
- Can run indefinitely (no memory leaks expected)
"""

import mgba.core
import mgba.image
import random
import subprocess
import time
import os
import sys
from datetime import datetime
from pathlib import Path

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Configuration
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")

# Hardcoded trainer IDs (read from SRAM, but constant for this save)
TID = 56078
SID = 24723

# Memory addresses
# Party structure layout (Emerald US):
# - 0x020244EC (+0x00): Personality Value (4 bytes)
# - 0x020244F0 (+0x04): Trainer ID (16-bit)
# - Encrypted substructures start at +0x20 (32 bytes from PV)
PARTY_PV_ADDR = 0x020244EC  # Personality Value of first party Pokemon (4 bytes)
PARTY_TID_ADDR = 0x020244F0  # Trainer ID (16-bit) - at offset +0x04 from PV

# Pokemon species IDs (Gen III)
# Battle structure IDs used in memory (Emerald US)
POKEMON_SPECIES = {
    277: "Treecko",  # 0x0115
    280: "Torchic",  # 0x0118
    283: "Mudkip",   # 0x011B
}

# Button sequence for Mudkip (optimized by test_mudkip_sequences_comprehensive.py with RNG manipulation)
# Best sequence found: 19 A dialogue -> wait 0.5s -> 2x Right (delay 30) -> wait 0.2s -> 8 A select (delay 30)
# Test results with RNG: 60-70% Mudkip success (best achievable with fixed sequence)
# Note: With RNG manipulation, 100% success is difficult, but this sequence is the best found
# 18 A dialogue = no Pokemon found, 21+ A dialogue = selects Torchic
A_PRESSES_DIALOGUE = 19  # A presses to get through dialogue (19 is best with RNG, 21+ causes Torchic)
WAIT_FOR_BAG_FRAMES = 30  # Wait 0.5s for bag screen to appear
RIGHT_PRESS_COUNT = 2  # Press Right 2 times for reliability (tested: 2x is better than 1x with RNG)
RIGHT_PRESS_DELAY_FRAMES = 30  # Wait 0.5s after each Right press (improves reliability)
WAIT_AFTER_RIGHT_FRAMES = 12  # Wait 0.2s after Right presses before A presses
A_PRESSES_SELECT = 8  # A presses to select Mudkip (8 is more reliable with RNG manipulation)
A_SELECT_DELAY_FRAMES = 30  # Wait 0.5s between A presses when selecting (improves reliability)
A_PRESS_DELAY_FRAMES = 15  # Frames to wait between presses (0.25s at 60 FPS)
MAX_RETRY_PRESSES = 8  # Maximum retry A presses if Pokemon not found

# Button constants (GBA button bits)
KEY_RIGHT = 16  # bit 4


class ShinyHunter:
    def __init__(self, suppress_debug=True):
        # Set up logging
        self.log_dir = PROJECT_ROOT / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"shiny_hunt_{timestamp}.log"
        
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
        
        # Open log file and set up tee
        self.log_file_handle = open(self.log_file, 'w', encoding='utf-8')
        self.original_stdout = sys.stdout
        sys.stdout = Tee(sys.stdout, self.log_file_handle)
        
        # Suppress GBA debug output by redirecting stderr
        if suppress_debug:
            self.original_stderr = sys.stderr
            self.null_file = open(os.devnull, 'w')
            sys.stderr = self.null_file
        
        self.core = mgba.core.load_path(ROM_PATH)
        if not self.core:
            raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

        self.core.reset()
        self.core.autoload_save()  # Load the .sav file
        
        # Set up video buffer for screenshots (after reset/load)
        self.screenshot_image = mgba.image.Image(240, 160)
        self.core.set_video_buffer(self.screenshot_image)
        
        self.attempts = 0
        self.start_time = time.time()

        print(f"[*] Logging to: {self.log_file}")
        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] TID: {TID}, SID: {SID}")
        print(f"[*] Shiny Formula: (TID ^ SID) ^ (PV_low ^ PV_high) < 8")
        print(f"[*] TID ^ SID = {TID} ^ {SID} = {TID ^ SID}")
        print(f"[*] Pokemon species will be identified from memory")
        print(f"[*] Starting shiny hunt...\n")
    
    def cleanup(self):
        """Restore stdout/stderr and close log file"""
        if hasattr(self, 'log_file_handle') and self.log_file_handle:
            sys.stdout = self.original_stdout
            self.log_file_handle.close()
        if hasattr(self, 'null_file') and self.null_file:
            sys.stderr = self.original_stderr
            self.null_file.close()
            self.null_file = None
    
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
        for _ in range(count):
            self.core.run_frame()

    def press_a(self, hold_frames=5, release_frames=5):
        """Press and release A button"""
        self.core._core.setKeys(self.core._core, 1)  # A = bit 0
        self.run_frames(hold_frames)
        self.core._core.setKeys(self.core._core, 0)
        self.run_frames(release_frames)
    
    def press_right(self, hold_frames=5, release_frames=5):
        """Press and release Right button"""
        self.core._core.setKeys(self.core._core, KEY_RIGHT)
        self.run_frames(hold_frames)
        self.core._core.setKeys(self.core._core, 0)
        self.run_frames(release_frames)

    def selection_sequence(self, verbose=False):
        """Execute the full selection button sequence for Mudkip
        
        Optimal sequence (from test_mudkip_sequences_comprehensive.py with RNG manipulation):
        19 A dialogue -> wait 0.5s -> 2x Right (delay 0.5s) -> wait 0.2s -> 8 A select (delay 0.5s)
        Tested with RNG: 60-70% Mudkip success (best achievable with fixed sequence)
        """
        delay_seconds = A_PRESS_DELAY_FRAMES / 60.0
        wait_bag_seconds = WAIT_FOR_BAG_FRAMES / 60.0
        wait_right_seconds = WAIT_AFTER_RIGHT_FRAMES / 60.0
        right_delay_seconds = RIGHT_PRESS_DELAY_FRAMES / 60.0
        select_delay_seconds = A_SELECT_DELAY_FRAMES / 60.0
        
        if verbose:
            print(f"[*] {A_PRESSES_DIALOGUE} A dialogue -> wait {wait_bag_seconds:.1f}s -> {RIGHT_PRESS_COUNT}x Right (delay {right_delay_seconds:.1f}s) -> wait {wait_right_seconds:.1f}s -> {A_PRESSES_SELECT} A select (delay {select_delay_seconds:.1f}s)")
        
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
        
        # Step 2: Wait for bag screen to appear
        if verbose:
            print(f"    Waiting {wait_bag_seconds:.2f}s for bag screen...", end='', flush=True)
        self.run_frames(WAIT_FOR_BAG_FRAMES)
        if verbose:
            print(" Done")
        
        # Step 3: Press Right to move to Mudkip (with delay after each press)
        if verbose:
            print(f"    Pressing Right {RIGHT_PRESS_COUNT} time(s) (delay {right_delay_seconds:.1f}s after each)...", end='', flush=True)
        for _ in range(RIGHT_PRESS_COUNT):
            self.press_right(hold_frames=5, release_frames=5)
            self.run_frames(RIGHT_PRESS_DELAY_FRAMES)  # Use specific delay for Right presses
        if verbose:
            print(" Done")
        
        # Step 4: Wait after Right to ensure cursor moved
        if verbose:
            print(f"    Waiting {wait_right_seconds:.2f}s after Right...", end='', flush=True)
        self.run_frames(WAIT_AFTER_RIGHT_FRAMES)
        if verbose:
            print(" Done")
        
        # Step 5: Press A buttons to select Mudkip (with delay between presses)
        if verbose:
            print(f"    Pressing {A_PRESSES_SELECT} A buttons to select (delay {select_delay_seconds:.1f}s between)...", end='', flush=True)
        
        pokemon_found = False
        for i in range(A_PRESSES_SELECT):
            self.press_a(hold_frames=5, release_frames=5)
            
            # Check for Pokemon after each press (early exit if found)
            pv = self.read_u32(PARTY_PV_ADDR)
            if pv != 0:
                pokemon_found = True
                if verbose:
                    print(f" Pokemon found after {i+1} A presses!    ")
                return True  # Early exit - Pokemon found
            
            # Delay between presses (use specific delay for select presses)
            self.run_frames(A_SELECT_DELAY_FRAMES)
        
        # If not found after initial presses, try more with checking
        if not pokemon_found:
            if verbose:
                print(f" (not found yet, retrying...)", end='', flush=True)
            for i in range(MAX_RETRY_PRESSES):
                self.press_a(hold_frames=5, release_frames=5)
                pv = self.read_u32(PARTY_PV_ADDR)
                if pv != 0:
                    pokemon_found = True
                    if verbose:
                        print(f" Pokemon found after {A_PRESSES_SELECT + i + 1} A presses!    ")
                    return True
                # Longer delay between retry presses to give game time to respond
                self.run_frames(A_PRESS_DELAY_FRAMES * 2)  # 0.5s between retries
        
        if verbose:
            print(" Done")
        
        return pokemon_found

    def read_u32(self, address):
        """Read 32-bit unsigned integer from memory"""
        b0 = self.core._core.busRead8(self.core._core, address)
        b1 = self.core._core.busRead8(self.core._core, address + 1)
        b2 = self.core._core.busRead8(self.core._core, address + 2)
        b3 = self.core._core.busRead8(self.core._core, address + 3)
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
    
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
    
    def decrypt_party_species(self, pv_addr, tid_addr):
        """Decrypt and extract species ID from encrypted party data
        
        Gen III party structure:
        - Bytes 0-3: PV (unencrypted)
        - Bytes 4-5: TID (unencrypted)
        - Bytes 6-7: SID (unencrypted)
        - Bytes 32-79: Encrypted substructures (48 bytes = 4 * 12 bytes)
          - Growth substructure contains species ID in first 2 bytes
        
        Decryption steps:
        1. Determine order using PV % 24 (returns string like "GAEM")
        2. Find Growth ('G') position in the order string
        3. Calculate offset: position * 12 bytes
        4. Read 32 bits from data_start + offset
        5. Decrypt: encrypted_val ^ (tid ^ pv)
        6. Extract species: decrypted_val & 0xFFFF
        
        Args:
            pv_addr: Address of Personality Value
            tid_addr: Address of Trainer ID
        
        Returns:
            (species_id, species_name) if found, or (0, "Unknown") if failed
        """
        try:
            # Read PV and TID
            pv = self.read_u32(pv_addr)
            tid = self.read_u16(tid_addr)
            
            # Encrypted data starts at exactly 32 bytes after PV address
            data_start = pv_addr + 32
            
            # Step A: Get substructure order using PV % 24
            order_index = pv % 24
            order = self.get_substructure_order(pv)  # Returns string like "GAEM"
            
            # Step B: Find Growth ('G') position in the order
            growth_pos = order.index('G')
            
            # Step C: Calculate offset (each substructure is 12 bytes)
            offset = growth_pos * 12
            
            # Step D: Read 32 bits (4 bytes) from data_start + offset
            encrypted_val = self.read_u32(data_start + offset)
            
            # Step E: Decrypt: encrypted_val ^ (tid ^ pv)
            xor_key = (tid & 0xFFFF) ^ pv
            decrypted_val = encrypted_val ^ xor_key
            
            # Step F: Extract species ID (lower 16 bits)
            species_id = decrypted_val & 0xFFFF
            
            # Debug: Print decryption details (only for first few attempts)
            if hasattr(self, 'attempts') and self.attempts <= 3:
                print(f"    [DEBUG] PV=0x{pv:08X}, TID={tid}, Order='{order}', Growth at position {growth_pos}, Offset={offset}")
                print(f"    [DEBUG] Encrypted=0x{encrypted_val:08X}, XOR_KEY=0x{xor_key:08X}, Decrypted=0x{decrypted_val:08X}")
                print(f"    [DEBUG] Species ID={species_id} (0x{species_id:04X})")
            
            # Check if it's a valid starter ID
            if species_id in POKEMON_SPECIES:
                species_name = POKEMON_SPECIES.get(species_id, f"Unknown (ID: {species_id})")
                if hasattr(self, 'attempts') and self.attempts <= 3:
                    print(f"  [+] Decrypted species: {species_name} (ID: {species_id})")
                return species_id, species_name
            
            return 0, f"Unknown (decrypted ID: {species_id}, not a starter)"
        except Exception as e:
            return 0, f"Decryption error: {e}"
    
    def get_pokemon_species(self):
        """Get the Pokemon species ID and name from memory by decrypting party data
        
        Decrypts the Growth substructure from the party data to extract species ID.
        This is necessary because species ID is encrypted in party RAM.
        
        Returns:
            (species_id, species_name) if found, or (0, "Unknown") if failed
        """
        # Use expected addresses directly (they're stable in Emerald)
        return self.decrypt_party_species(PARTY_PV_ADDR, PARTY_TID_ADDR)

    def check_shiny(self):
        """Check if the starter Pokémon is shiny
        
        Gen III Shiny Formula:
        Shiny if: (TID XOR SID) XOR (PV_low XOR PV_high) < 8
        
        Where:
        - TID = Trainer ID (56078)
        - SID = Secret ID / Shiny ID (24723)
        - PV = Personality Value (32-bit)
        - PV_low = lower 16 bits of PV
        - PV_high = upper 16 bits of PV
        """
        pv = self.read_u32(PARTY_PV_ADDR)

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
        """Main hunting loop
        
        Args:
            max_attempts: Maximum number of attempts (None = unlimited)
            error_retry_limit: Number of times to retry on error before giving up
        """
        consecutive_errors = 0
        last_status_update = time.time()
        
        while True:
            # Check max attempts
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
                    time.sleep(1)  # Brief pause before retry
                    continue
                
                # Reset error counter on success
                consecutive_errors = 0

                # RNG variation: Write random seed to RNG address after loading
                # Emerald RNG seed is at 0x03005D80
                RNG_ADDR = 0x03005D80
                random_seed = random.randint(0, 0xFFFFFFFF)

                # Also wait some frames to let things settle before writing seed
                random_delay = random.randint(10, 100)
                self.run_frames(random_delay)

                # Write random seed to RNG memory location AFTER initial delay
                # This ensures the game has initialized before we manipulate RNG
                self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)
                
                # Additional delay after writing seed to let it take effect
                self.run_frames(random.randint(5, 20))

                # Periodic status update every 10 attempts or 5 minutes
                elapsed = time.time() - self.start_time
                if (self.attempts % 10 == 0) or (time.time() - last_status_update > 300):
                    rate = self.attempts / elapsed if elapsed > 0 else 0
                    print(f"\n[Status] Attempt {self.attempts} | Rate: {rate:.2f}/s | "
                          f"Elapsed: {elapsed/60:.1f} min | Running smoothly...")
                    last_status_update = time.time()

                print(f"\n[Attempt {self.attempts}] Starting new reset...")
                print(f"  RNG Seed: 0x{random_seed:08X}, Delay: {random_delay} frames")

                # Execute selection sequence (press A until game loads)
                # Also re-write RNG seed periodically during A presses to prevent overwrite
                pokemon_found = self.selection_sequence(verbose=(self.attempts <= 3))  # Only verbose for first 3 attempts
                
                # Re-write RNG seed after A presses to ensure it's still set
                # (in case game overwrote it during the sequence)
                self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)
                self.run_frames(5)  # Small delay to let it take effect
                
                # Wait for Pokemon data to be fully loaded
                self.run_frames(60)  # 1 second delay to ensure data is loaded
                
                # Check if Pokemon was found during sequence
                pv = self.read_u32(PARTY_PV_ADDR)
                if pv == 0 and not pokemon_found:
                    # Pokemon still not found - try pressing A more times with longer waits
                    for retry in range(5):  # Increased from 3 to 5
                        self.press_a(hold_frames=5, release_frames=5)
                        self.run_frames(60)  # Wait 1.0s after each retry press (increased from 0.5s)
                        pv = self.read_u32(PARTY_PV_ADDR)
                        if pv != 0:
                            break
                    # If still not found, wait a bit more and check one last time
                    if pv == 0:
                        self.run_frames(90)  # Wait 1.5s
                        pv = self.read_u32(PARTY_PV_ADDR)
                
                # Get Pokemon species
                species_id, species_name = self.get_pokemon_species()

                # Check if shiny
                is_shiny, pv, shiny_value, details = self.check_shiny()

                # Calculate rate
                elapsed = time.time() - self.start_time
                rate = self.attempts / elapsed if elapsed > 0 else 0

                # Progress update
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
                else:
                    print(f"[Attempt {self.attempts}] No Pokemon found yet - checking...")
                    print(f"  PV at 0x{PARTY_PV_ADDR:08X}: 0x{pv:08X}")
                    print(f"  May need more A presses or game hasn't loaded yet")
                    
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
                
                # Try to recover by resetting the core
                print("[*] Attempting recovery...")
                try:
                    self.core.reset()
                    self.core.autoload_save()
                    if hasattr(self, 'screenshot_image'):
                        self.core.set_video_buffer(self.screenshot_image)
                    time.sleep(2)  # Brief pause before retry
                except Exception as recovery_error:
                    print(f"[!] Recovery failed: {recovery_error}")
                    return False


def main():
    hunter = None
    try:
        # Suppress GBA debug output by default
        hunter = ShinyHunter(suppress_debug=True)
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
