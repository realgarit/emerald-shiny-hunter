"""
Base emulator class for Pokemon Emerald Shiny Hunter.

Provides core mGBA functionality shared across all hunting scripts:
- ROM loading and reset
- Frame advancement
- Button press helpers
- Video buffer management
"""

import mgba.core
import mgba.image
import mgba.log
import cv2
import numpy as np
from cffi import FFI
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants.keys import (
    KEY_A, KEY_B, KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN,
    KEY_START, KEY_SELECT, KEY_NONE,
    DEFAULT_HOLD_FRAMES, DEFAULT_RELEASE_FRAMES,
)
from constants.memory import RNG_SEED_ADDR


class EmulatorBase:
    """
    Base class providing mGBA emulator functionality.

    Handles:
    - ROM loading and core management
    - Frame advancement with optional visualization
    - Button press simulation
    - Video buffer for screenshots
    """

    def __init__(
        self,
        rom_path: str,
        suppress_debug: bool = True,
        show_window: bool = False,
        window_name: str = "Shiny Hunter"
    ):
        """
        Initialize the emulator.

        Args:
            rom_path: Path to the ROM file
            suppress_debug: If True, suppress mGBA debug output
            show_window: If True, show live visualization window
            window_name: Name for the visualization window
        """
        self.rom_path = rom_path
        self.show_window = show_window
        self.window_name = window_name

        # Suppress mGBA debug output
        if suppress_debug:
            mgba.log.silence()

        # Load ROM
        self.core = mgba.core.load_path(rom_path)
        if not self.core:
            raise RuntimeError(f"Failed to load ROM: {rom_path}")

        self.core.reset()
        self.core.autoload_save()

        # Set up video buffer for screenshots
        self.screenshot_image = mgba.image.Image(240, 160)
        self.core.set_video_buffer(self.screenshot_image)

        # Set up visualization window if enabled
        if self.show_window:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, 480, 320)

        self.frame_counter = 0
        self.frame_skip = 5  # Update window every 5th frame

    def cleanup(self):
        """Clean up resources (close windows, etc.)."""
        if self.show_window:
            try:
                cv2.destroyAllWindows()
            except:
                pass

    def __del__(self):
        """Destructor to clean up resources."""
        self.cleanup()

    def reset_to_save(self) -> bool:
        """
        Reset and load from .sav file.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.core.reset()
            self.core.autoload_save()
            # Re-set video buffer after reset
            if hasattr(self, 'screenshot_image'):
                self.core.set_video_buffer(self.screenshot_image)
            return True
        except Exception as e:
            print(f"[!] Error loading save: {e}")
            return False

    def run_frames(self, count: int):
        """
        Advance emulation by specified number of frames.

        Args:
            count: Number of frames to advance
        """
        for _ in range(count):
            self.core.run_frame()
            self.frame_counter += 1

            # Update visualization window (with frame skip for performance)
            if self.show_window and self.frame_counter % self.frame_skip == 0:
                self._update_display_window()
                cv2.waitKey(1)

    def _update_display_window(self):
        """Update the OpenCV display window with current frame buffer."""
        try:
            if not hasattr(self, 'screenshot_image') or not hasattr(self.screenshot_image, 'buffer'):
                return

            raw_buffer = self.screenshot_image.buffer
            expected_size = 240 * 160 * 4

            try:
                ffi = FFI()
                buffer_bytes = bytes(ffi.buffer(raw_buffer, expected_size))
            except Exception:
                try:
                    buffer_bytes = bytes(raw_buffer)
                except:
                    return

            np_buffer = np.frombuffer(buffer_bytes, dtype=np.uint8, count=expected_size)
            rgba_frame = np_buffer.reshape(160, 240, 4)
            bgr_frame = cv2.cvtColor(rgba_frame, cv2.COLOR_RGBA2BGR)
            scaled_frame = cv2.resize(bgr_frame, (480, 320), interpolation=cv2.INTER_NEAREST)
            cv2.imshow(self.window_name, scaled_frame)

        except Exception:
            pass

    def set_keys(self, keys: int):
        """
        Set button state.

        Args:
            keys: Bitmask of buttons to press
        """
        self.core._core.setKeys(self.core._core, keys)

    def press_button(
        self,
        button: int,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """
        Press and release a button.

        Args:
            button: Button constant (KEY_A, KEY_B, etc.)
            hold_frames: Frames to hold the button
            release_frames: Frames to wait after release
        """
        self.set_keys(button)
        self.run_frames(hold_frames)
        self.set_keys(KEY_NONE)
        self.run_frames(release_frames)

    def press_a(
        self,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """Press and release A button."""
        self.press_button(KEY_A, hold_frames, release_frames)

    def press_b(
        self,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """Press and release B button."""
        self.press_button(KEY_B, hold_frames, release_frames)

    def press_left(
        self,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """Press and release Left button."""
        self.press_button(KEY_LEFT, hold_frames, release_frames)

    def press_right(
        self,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """Press and release Right button."""
        self.press_button(KEY_RIGHT, hold_frames, release_frames)

    def press_up(
        self,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """Press and release Up button."""
        self.press_button(KEY_UP, hold_frames, release_frames)

    def press_down(
        self,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """Press and release Down button."""
        self.press_button(KEY_DOWN, hold_frames, release_frames)

    def press_start(
        self,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """Press and release Start button."""
        self.press_button(KEY_START, hold_frames, release_frames)

    def press_select(
        self,
        hold_frames: int = DEFAULT_HOLD_FRAMES,
        release_frames: int = DEFAULT_RELEASE_FRAMES
    ):
        """Press and release Select button."""
        self.press_button(KEY_SELECT, hold_frames, release_frames)

    def write_rng_seed(self, seed: int):
        """
        Write a value to the RNG seed address.

        Args:
            seed: 32-bit seed value
        """
        self.core._core.busWrite32(self.core._core, RNG_SEED_ADDR, seed)

    def read_memory_u32(self, address: int) -> int:
        """
        Read 32-bit value from memory.

        Args:
            address: Memory address

        Returns:
            32-bit unsigned integer
        """
        b0 = self.core._core.busRead8(self.core._core, address)
        b1 = self.core._core.busRead8(self.core._core, address + 1)
        b2 = self.core._core.busRead8(self.core._core, address + 2)
        b3 = self.core._core.busRead8(self.core._core, address + 3)
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

    def read_memory_u16(self, address: int) -> int:
        """
        Read 16-bit value from memory.

        Args:
            address: Memory address

        Returns:
            16-bit unsigned integer
        """
        b0 = self.core._core.busRead8(self.core._core, address)
        b1 = self.core._core.busRead8(self.core._core, address + 1)
        return b0 | (b1 << 8)

    def read_memory_u8(self, address: int) -> int:
        """
        Read 8-bit value from memory.

        Args:
            address: Memory address

        Returns:
            8-bit unsigned integer
        """
        return self.core._core.busRead8(self.core._core, address)
