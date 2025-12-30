"""
Save state management utilities for Pokemon Emerald Shiny Hunter.

Provides functions for:
- Saving and loading save states
- Screenshot capture
"""

import mgba.image
from datetime import datetime
from pathlib import Path
from typing import Optional


def save_screenshot(
    core,
    screenshot_dir: Path,
    prefix: str = "shiny_found"
) -> Optional[str]:
    """
    Save a screenshot of the current game state.

    Note: Screenshots may not work in headless mode (when mGBA has no visible window).
    The save state will contain the exact game state, so you can load it in mGBA GUI.

    Args:
        core: mGBA core instance
        screenshot_dir: Directory to save screenshots
        prefix: Filename prefix

    Returns:
        Path to screenshot file, or None if failed
    """
    screenshot_dir = Path(screenshot_dir)
    screenshot_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    filepath = screenshot_dir / filename

    try:
        # Create a fresh image for the screenshot
        width = 240
        height = 160
        image = mgba.image.Image(width, height)

        # Set video buffer
        core.set_video_buffer(image)

        # Run many frames to ensure everything is rendered
        for _ in range(120):
            core.run_frame()

        # Check if buffer has data (not all zeros/black)
        try:
            buffer = image.buffer
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


def save_game_state(
    core,
    save_state_dir: Path,
    species_name: str = "unknown",
    run_frames_func=None
) -> Optional[str]:
    """
    Save the current game state (save state file).

    Args:
        core: mGBA core instance
        save_state_dir: Directory to save state files
        species_name: Pokemon species name for filename
        run_frames_func: Optional function to run frames (for letting save complete)

    Returns:
        Path to save state file, or None if failed
    """
    try:
        save_state_dir = Path(save_state_dir)
        save_state_dir.mkdir(exist_ok=True)

        species_safe = species_name.lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_state_filename = save_state_dir / f"{species_safe}_shiny_save_state_{timestamp}.ss0"

        state_data = core.save_raw_state()

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

        # Run frames to let save complete if function provided
        if run_frames_func:
            run_frames_func(60)

        return str(save_state_filename)

    except Exception as e:
        print(f"[!] Failed to save game state: {e}")
        return None


def load_save_state(core, save_state_path: Path) -> bool:
    """
    Load a save state file.

    Args:
        core: mGBA core instance
        save_state_path: Path to save state file

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(save_state_path, 'rb') as f:
            state_data = f.read()
        core.load_raw_state(state_data)
        return True
    except Exception as e:
        print(f"[!] Failed to load save state: {e}")
        return False
