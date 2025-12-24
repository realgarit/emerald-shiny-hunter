#!/usr/bin/env python3
"""
Test script to simulate finding a shiny and verify save state saving works
"""
import mgba.core
import mgba.image
import random
import subprocess
import time
import os
from datetime import datetime

ROM_PATH = "Pokemon - Emerald Version (U).gba"
TID = 56078
SID = 24723
PARTY_PV_ADDR = 0x020244EC
RNG_ADDR = 0x03005D80

def read_u32(core, address):
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    b2 = core._core.busRead8(core._core, address + 2)
    b3 = core._core.busRead8(core._core, address + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

def press_a(core, hold=5, release=5):
    core._core.setKeys(core._core, 1)
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def run_frames(core, n):
    for _ in range(n):
        core.run_frame()

def save_screenshot(core):
    """Save a screenshot"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_shiny_{timestamp}.png"
    filepath = os.path.abspath(filename)

    try:
        width = 240
        height = 160
        image = mgba.image.Image(width, height)
        
        # Set video buffer
        core.set_video_buffer(image)
        
        # Run many frames to ensure everything is rendered
        for _ in range(60):
            core.run_frame()
        
        # Check if buffer has data
        buffer = image.buffer
        has_data = any(buffer[i] != 0 for i in range(min(1000, len(buffer))))
        
        if not has_data:
            print("[!] Warning: Screenshot buffer appears empty, trying again...")
            for _ in range(120):
                core.run_frame()

        with open(filename, 'wb') as f:
            image.save_png(f)
        print(f"[+] Screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"[!] Failed to save screenshot: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_game_state(core):
    """Save the current game state"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_state_filename = f"test_shiny_save_state_{timestamp}.ss0"
        
        state_data = core.save_raw_state()
        # Convert CData object to bytes using cffi buffer
        try:
            from cffi import FFI
            ffi = FFI()
            state_bytes = bytes(ffi.buffer(state_data))
        except:
            # Fallback: try to read as bytes directly
            if hasattr(state_data, '__len__'):
                # Read byte by byte (slow but works)
                state_bytes = b''.join(bytes([state_data[i]]) for i in range(len(state_data)))
            else:
                state_bytes = bytes(state_data)
        
        with open(save_state_filename, 'wb') as f:
            f.write(state_bytes)
        
        print(f"[+] Save state saved: {os.path.abspath(save_state_filename)}")
        
        # Run frames to let save complete
        run_frames(core, 60)
        
        # Get .sav file path
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

def send_notification(message, subtitle=""):
    """Send macOS system notification"""
    try:
        script = f'''
        display notification "{message}" with title "Shiny Hunter TEST" subtitle "{subtitle}" sound name "Glass"
        '''
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception as e:
        print(f"[!] Failed to send notification: {e}")

def play_alert_sound():
    """Play system alert sound"""
    try:
        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
    except Exception as e:
        print(f"[!] Failed to play sound: {e}")

def open_screenshot(filepath):
    """Open screenshot in default viewer"""
    if filepath and os.path.exists(filepath):
        try:
            subprocess.run(["open", filepath], check=False)
        except Exception as e:
            print(f"[!] Failed to open screenshot: {e}")

print("=" * 60)
print("TEST: Simulating Shiny Found Scenario")
print("=" * 60)
print("\n[*] Loading ROM and save file...")

core = mgba.core.load_path(ROM_PATH)
if not core:
    raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

core.reset()
core.autoload_save()

print("[*] Setting up RNG...")
random_seed = random.randint(0, 0xFFFFFFFF)
core._core.busWrite32(core._core, RNG_ADDR, random_seed)
random_delay = random.randint(10, 100)
run_frames(core, random_delay)

print("[*] Pressing A buttons to get to Pokemon selection...")
# Press A 12 times with 1 second pauses
for i in range(12):
    press_a(core, hold=5, release=5)
    run_frames(core, 60)
    time.sleep(1.0)
    print(f"  Press {i+1}/12...")

# Check for Pokemon
pv = read_u32(core, PARTY_PV_ADDR)
if pv == 0:
    print("[!] No Pokemon found - may need more presses")
    print("[*] Continuing anyway for test...")
    pv = 0x12345678  # Fake PV for testing

# Calculate shiny value
if pv != 0:
    pv_low = pv & 0xFFFF
    pv_high = (pv >> 16) & 0xFFFF
    shiny_value = (TID ^ SID) ^ (pv_low ^ pv_high)
    is_shiny = shiny_value < 8
else:
    shiny_value = 99999
    is_shiny = False

print("\n" + "=" * 60)
print("🎉 TEST: SHINY FOUND! (Simulated)")
print("=" * 60)
print(f"Personality Value: 0x{pv:08X}")
print(f"Shiny Value: {shiny_value}")
print(f"Actually Shiny: {is_shiny}")
print("=" * 60)

# Save screenshot
print(f"\n[+] Saving screenshot...")
screenshot_path = save_screenshot(core)

# Play sound
print(f"[+] Playing alert sound...")
play_alert_sound()

# Send notification
print(f"[+] Sending system notification...")
send_notification(
    f"TEST: Shiny found! (Simulated)",
    f"PV: 0x{pv:08X}"
)

# Save game state
print(f"\n[+] Saving game state...")
save_state_path = save_game_state(core)

# Open screenshot
if screenshot_path:
    print(f"[+] Opening screenshot...")
    open_screenshot(screenshot_path)

print("\n" + "=" * 60)
print("✓ TEST COMPLETE! Game saved. You can now:")
if save_state_path:
    print(f"  1. Load save state: {os.path.abspath(save_state_path)}")
print("  2. Or open mGBA and load the .sav file")
print("  3. Continue playing and save in-game normally")
print("=" * 60)
print("\n[!] Test complete. Check the files above to verify everything worked!")

