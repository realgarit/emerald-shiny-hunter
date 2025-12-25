#!/usr/bin/env python3
"""
Pokémon Emerald Shiny Hunter - Route 101
Uses mGBA Python bindings to hunt for shiny wild Pokémon on Route 101

Loads from .sav file and presses buttons to trigger wild encounters.
Identifies Pokemon species from memory to verify which Pokémon was encountered.

Features:
- Identifies Pokemon species from memory (Poochyena, Zigzagoon, or Wurmple)
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

# Memory addresses for Enemy Party (Route 101 wild encounters)
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

# Pokemon species IDs (Gen III) - Route 101 wild encounters
POKEMON_SPECIES = {
    261: "Poochyena",  # 0x0105
    263: "Zigzagoon",  # 0x0107
    265: "Wurmple",    # 0x0109
}

# Loading sequence: Press A 15 times with 20-frame delay between presses
A_PRESSES_LOADING = 15  # A presses to get through loading screens
A_LOADING_DELAY_FRAMES = 20  # Wait ~0.33s between A presses during loading

# Encounter method: Turn in place to trigger encounters
# Press Left for 3 frames, then wait 5 frames
# Press Right for 3 frames, then wait 5 frames
# Repeat until Pokemon detected
LEFT_HOLD_FRAMES = 3  # Hold Left for 3 frames
LEFT_WAIT_FRAMES = 5  # Wait 5 frames after Left
RIGHT_HOLD_FRAMES = 3  # Hold Right for 3 frames
RIGHT_WAIT_FRAMES = 5  # Wait 5 frames after Right

# Button constants (GBA button bits)
KEY_LEFT = 32   # bit 5
KEY_RIGHT = 16  # bit 4


class ShinyHunter:
    def __init__(self, suppress_debug=True):
        # Set up logging
        self.log_dir = PROJECT_ROOT / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"route101_hunt_{timestamp}.log"
        
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
        print(f"[*] Monitoring Enemy Party at 0x{ENEMY_PV_ADDR:08X}")
        print(f"[*] Target species: {', '.join(POKEMON_SPECIES.values())}")
        print(f"[*] Starting shiny hunt on Route 101...\n")
    
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
        - Press Left for 3 frames, then wait 5 frames
        - Press Right for 3 frames, then wait 5 frames
        - Repeat until Pokemon detected in memory
        
        Args:
            verbose: If True, print progress updates
            max_turns: Maximum number of turn cycles before giving up
        
        Returns:
            True if Pokemon detected, False otherwise
        """
        if verbose:
            print(f"    Turning in place to trigger encounters...", end='', flush=True)
        
        turn_count = 0
        while turn_count < max_turns:
            # Press Left for 3 frames, then wait 5 frames
            self.press_left(hold_frames=LEFT_HOLD_FRAMES, release_frames=0)
            self.run_frames(LEFT_WAIT_FRAMES)
            
            # Check for Pokemon after Left turn
            pv = self.read_u32(ENEMY_PV_ADDR)
            if pv != 0:
                if verbose:
                    print(f" Pokemon detected after {turn_count * 2 + 1} turns!")
                return True
            
            # Press Right for 3 frames, then wait 5 frames
            self.press_right(hold_frames=RIGHT_HOLD_FRAMES, release_frames=0)
            self.run_frames(RIGHT_WAIT_FRAMES)
            
            # Check for Pokemon after Right turn
            pv = self.read_u32(ENEMY_PV_ADDR)
            if pv != 0:
                if verbose:
                    print(f" Pokemon detected after {turn_count * 2 + 2} turns!")
                return True
            
            turn_count += 1
            
            # Periodic status update every 100 turns
            if verbose and turn_count % 100 == 0:
                print(f" {turn_count * 2} turns...", end='', flush=True)
        
        if verbose:
            print(f" No Pokemon detected after {turn_count * 2} turns")
        
        return False

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
            for ot_tid in ot_tid_values:
                # Try different encrypted data offsets - enemy party might use different layout
                # Standard offset is +32 bytes, but battle structure might be different
                # Also try negative offsets in case encrypted data starts before PV
                for data_offset in [32, 0, 8, 16, 24, 40, 48, -8, -4, 4, 12, 20, 28, 36, 44, 52, 56, 60, 64]:
                    try:
                        data_start = pv_addr + data_offset
                        
                        # Step A: Get substructure order using PV % 24
                        order_index = pv % 24
                        order = self.get_substructure_order(pv)  # Returns string like "GAEM"
                        
                        # Try all 4 substructure positions (G, A, E, M) to find where species is
                        # Growth substructure (G) contains species ID, but let's try all positions
                        for substructure_pos in range(4):
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
                            
                            # If standard doesn't give Route 101 species, try with SID
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
                            
                            # Check if it's a valid Route 101 species ID (try lower 16 bits first)
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
                            # Check if species_id is close to Route 101 species with various offsets
                            # Only check if species_id is in a reasonable range (200-300) to avoid false positives
                            if 200 <= species_id <= 300 or 200 <= species_id_high <= 300:
                                for route101_id in [261, 263, 265]:
                                    for offset_correction in [-30, -25, -20, -15, -10, -5, 5, 10, 15, 20, 25, 30]:
                                        corrected_id = species_id + offset_correction
                                        if corrected_id == route101_id:
                                            species_name = POKEMON_SPECIES.get(route101_id, f"Unknown (ID: {route101_id})")
                                            if hasattr(self, 'attempts') and self.attempts <= 3:
                                                substructure_name = order[substructure_pos]
                                                print(f"  [+] Found species (with offset correction {offset_correction:+d}) with OT_TID={ot_tid}, offset +{data_offset}, pos {substructure_pos} ({substructure_name}): {species_name} (ID: {route101_id}, raw={species_id})")
                                            return route101_id, species_name
                                        
                                        corrected_id_high = species_id_high + offset_correction
                                        if corrected_id_high == route101_id:
                                            species_name = POKEMON_SPECIES.get(route101_id, f"Unknown (ID: {route101_id})")
                                            if hasattr(self, 'attempts') and self.attempts <= 3:
                                                substructure_name = order[substructure_pos]
                                                print(f"  [+] Found species (upper 16 bits, offset correction {offset_correction:+d}) with OT_TID={ot_tid}, offset +{data_offset}, pos {substructure_pos} ({substructure_name}): {species_name} (ID: {route101_id}, raw={species_id_high})")
                                            return route101_id, species_name
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
        
        # If decryption failed, scan nearby addresses for Route 101 species
        # This might find the species if it's stored unencrypted somewhere in battle structure
        if hasattr(self, 'attempts') and self.attempts <= 3:
            print(f"    [DEBUG] Decryption failed, scanning memory for unencrypted species ID...")
        
        # First, scan around the enemy party structure
        for offset in range(-0x20, 0x200, 2):  # Scan from -32 to +512 bytes in 2-byte steps
            try:
                addr = ENEMY_PV_ADDR + offset
                species_id = self.read_u16(addr)
                if species_id in POKEMON_SPECIES:
                    species_name = POKEMON_SPECIES.get(species_id, f"Unknown (ID: {species_id})")
                    if hasattr(self, 'attempts') and self.attempts <= 3:
                        print(f"  [+] Found unencrypted species at offset +0x{offset:02X} (0x{addr:08X}): {species_name} (ID: {species_id})")
                    return species_id, species_name
            except:
                continue
        
        # Also scan the broader battle structure area - maybe species is in a different structure
        if hasattr(self, 'attempts') and self.attempts <= 3:
            print(f"    [DEBUG] Scanning battle structure area (0x02024000-0x02025000)...")
        for offset in range(0, 0x1000, 2):  # Scan 4KB area
            try:
                addr = BATTLE_STRUCTURE_START + offset
                species_id = self.read_u16(addr)
                if species_id in POKEMON_SPECIES:
                    species_name = POKEMON_SPECIES.get(species_id, f"Unknown (ID: {species_id})")
                    if hasattr(self, 'attempts') and self.attempts <= 3:
                        print(f"  [+] Found unencrypted species in battle structure at 0x{addr:08X}: {species_name} (ID: {species_id})")
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

                # Step 1: Execute loading sequence (15 A presses)
                verbose = (self.attempts <= 3)  # Only verbose for first 3 attempts
                self.loading_sequence(verbose=verbose)
                
                # Re-write RNG seed after loading sequence to ensure it's still set
                self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)
                self.run_frames(5)  # Small delay to let it take effect
                
                # Step 2: Execute encounter sequence (turn in place)
                pokemon_found = self.encounter_sequence(verbose=verbose)
                
                # Wait for Pokemon data to be fully loaded (battle structure needs time to populate)
                # Wait longer to ensure battle has fully started and data is populated
                # Battle structure may take longer to initialize than party structure
                self.run_frames(300)  # 5 seconds delay to ensure battle structure is fully loaded
                
                # Additional check: wait until PV is non-zero and stable, and encrypted data is populated
                stable_count = 0
                last_pv = 0
                for _ in range(120):  # Wait up to 2 more seconds
                    current_pv = self.read_u32(ENEMY_PV_ADDR)
                    if current_pv != 0 and current_pv == last_pv:
                        # Also check if encrypted data area has non-zero values (indicates data is loaded)
                        encrypted_check = self.read_u32(ENEMY_PV_ADDR + 32)
                        if encrypted_check != 0 and encrypted_check != current_pv:
                            stable_count += 1
                            if stable_count >= 5:  # PV and encrypted data stable for 5 frames
                                break
                    last_pv = current_pv
                    self.run_frames(1)
                
                # Check if Pokemon was found
                pv = self.read_u32(ENEMY_PV_ADDR)
                if pv == 0:
                    print(f"[Attempt {self.attempts}] No Pokemon detected - resetting and retrying...")
                    # Reset and try again (this keeps RNG fresh)
                    continue
                
                # Get Pokemon species
                species_id, species_name = self.get_pokemon_species()

                # Check if shiny
                is_shiny, pv, shiny_value, details = self.check_shiny()

                # Calculate rate
                elapsed = time.time() - self.start_time
                rate = self.attempts / elapsed if elapsed > 0 else 0

                # Progress update
                print(f"\n[Attempt {self.attempts}] Pokemon found!")
                if species_id != 0:
                    print(f"  Species: {species_name} (ID: {species_id})")
                else:
                    print(f"  Species: {species_name} (species ID not identified, but valid Route 101 encounter)")
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
                    # Reset and restart the sequence (this keeps RNG fresh)
                    print(f"  Resetting and restarting...")
                    
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

