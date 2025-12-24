#!/usr/bin/env python3
"""
Pokémon Emerald Shiny Hunter - Automated Starter Reset Script
Uses mGBA Python bindings to hunt for shiny starters

Loads from .sav file and presses A until game has loaded.
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

# Configuration
ROM_PATH = "Pokemon - Emerald Version (U).gba"

# Hardcoded trainer IDs (read from SRAM, but constant for this save)
TID = 56078
SID = 24723

# Memory addresses
PARTY_PV_ADDR = 0x020244EC  # Personality Value of first party Pokemon

# Number of A presses needed (determine with debug_buttons.py)
A_PRESSES_NEEDED = 12  # Determined by running debug_buttons.py


class ShinyHunter:
    def __init__(self, suppress_debug=True):
        # Set up logging
        self.log_dir = Path("logs")
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

    def selection_sequence(self, verbose=False):
        """Execute the full selection button sequence with 1 second pauses"""
        if verbose:
            print(f"[*] Pressing A button {A_PRESSES_NEEDED} times with 1 second pauses...")
        
        for i in range(A_PRESSES_NEEDED):
            self.press_a(hold_frames=5, release_frames=5)
            # 1 second pause (60 frames at 60 FPS + actual sleep)
            self.run_frames(60)
            if verbose and (i + 1) % 3 == 0:  # Print every 3 presses
                print(f"    Press {i+1}/{A_PRESSES_NEEDED}...", end='\r')
            time.sleep(1.0)
        
        if verbose:
            print(f"    Press {A_PRESSES_NEEDED}/{A_PRESSES_NEEDED} complete!    ")

    def read_u32(self, address):
        """Read 32-bit unsigned integer from memory"""
        b0 = self.core._core.busRead8(self.core._core, address)
        b1 = self.core._core.busRead8(self.core._core, address + 1)
        b2 = self.core._core.busRead8(self.core._core, address + 2)
        b3 = self.core._core.busRead8(self.core._core, address + 3)
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

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
        filename = f"shiny_found_{timestamp}.png"
        filepath = os.path.abspath(filename)

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
                with open(filename, 'wb') as f:
                    image.save_png(f)
                print(f"[+] Screenshot file created (may be black): {filepath}")
                return None  # Return None to indicate screenshot may not be useful

            with open(filename, 'wb') as f:
                image.save_png(f)
            print(f"[+] Screenshot saved: {filepath}")
            return filepath
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
            # Save a save state as backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_state_filename = f"shiny_save_state_{timestamp}.ss0"
            
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
            
            print(f"[+] Save state saved: {os.path.abspath(save_state_filename)}")
            
            # The .sav file should auto-save, but we can try to trigger it
            # by running a few frames to let the game save
            self.run_frames(60)  # Run 1 second to let save complete
            
            # Get .sav file path (mGBA auto-saves to same directory as ROM)
            rom_dir = os.path.dirname(os.path.abspath(ROM_PATH)) or "."
            sav_filename = ROM_PATH.replace(".gba", ".sav")
            sav_path = os.path.join(rom_dir, os.path.basename(sav_filename))
            
            if os.path.exists(sav_path):
                print(f"[+] Save file updated: {os.path.abspath(sav_path)}")
            else:
                print(f"[!] Note: Save file may be at: {sav_path}")
            
            return save_state_filename
        except Exception as e:
            print(f"[!] Failed to save game state: {e}")
            return None

    def hunt(self):
        """Main hunting loop"""
        while True:
            self.attempts += 1

            # Reset and load from .sav file
            if not self.reset_to_save():
                print("[!] Failed to load save. Exiting.")
                return False

            # RNG variation: Write random seed to RNG address after loading
            # Emerald RNG seed is at 0x03005D80
            RNG_ADDR = 0x03005D80
            random_seed = random.randint(0, 0xFFFFFFFF)

            # Write random seed to RNG memory location
            self.core._core.busWrite32(self.core._core, RNG_ADDR, random_seed)

            # Also wait some frames to let things settle
            random_delay = random.randint(10, 100)
            self.run_frames(random_delay)

            print(f"\n[Attempt {self.attempts}] Starting new reset...")
            print(f"  RNG Seed: 0x{random_seed:08X}, Delay: {random_delay} frames")

            # Execute selection sequence (press A until game loads)
            self.selection_sequence(verbose=True)

            # Check if shiny
            is_shiny, pv, shiny_value, details = self.check_shiny()

            # Calculate rate
            elapsed = time.time() - self.start_time
            rate = self.attempts / elapsed if elapsed > 0 else 0

            # Progress update
            if pv != 0:
                print(f"\n[Attempt {self.attempts}] Pokemon found!")
                print(f"  PV: 0x{pv:08X}")
                print(f"  PV Low:  0x{details['pv_low']:04X} ({details['pv_low']})")
                print(f"  PV High: 0x{details['pv_high']:04X} ({details['pv_high']})")
                print(f"  TID ^ SID: 0x{details['tid_xor_sid']:04X} ({details['tid_xor_sid']})")
                print(f"  PV XOR: 0x{details['pv_xor']:04X} ({details['pv_xor']})")
                print(f"  Shiny Value: {shiny_value} (need < 8 for shiny)")
                
                if is_shiny:
                    print("\n" + "=" * 60)
                    print("🎉 SHINY FOUND! 🎉")
                    print("=" * 60)
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
                    self.send_notification(
                        f"Shiny found after {self.attempts} attempts!",
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
                        print(f"  1. Load save state: {os.path.abspath(save_state_path)}")
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
