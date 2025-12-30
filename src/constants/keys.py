"""
GBA Button/Key Constants for mGBA.

These are the bit positions for GBA controller buttons.
Used with core._core.setKeys() to simulate button presses.
"""

# =============================================================================
# GBA Button Bit Constants
# =============================================================================
# Each button is represented by a single bit
# Multiple buttons can be pressed by OR-ing their values

KEY_A = 1           # bit 0 - A button
KEY_B = 2           # bit 1 - B button
KEY_SELECT = 4      # bit 2 - Select button
KEY_START = 8       # bit 3 - Start button
KEY_RIGHT = 16      # bit 4 - D-pad Right
KEY_LEFT = 32       # bit 5 - D-pad Left
KEY_UP = 64         # bit 6 - D-pad Up
KEY_DOWN = 128      # bit 7 - D-pad Down
KEY_R = 256         # bit 8 - R shoulder button
KEY_L = 512         # bit 9 - L shoulder button

# No keys pressed
KEY_NONE = 0

# =============================================================================
# Common Key Combinations
# =============================================================================
# Soft reset: A + B + Start + Select
KEY_SOFT_RESET = KEY_A | KEY_B | KEY_START | KEY_SELECT

# =============================================================================
# Timing Constants (in frames, 60 FPS)
# =============================================================================
# Standard button press timings

DEFAULT_HOLD_FRAMES = 5         # How long to hold a button
DEFAULT_RELEASE_FRAMES = 5      # How long to wait after release

# A button press delays for different scenarios
A_PRESS_DELAY_FRAMES = 15       # Standard delay between A presses (~0.25s)
A_LOADING_DELAY_FRAMES = 20     # Delay during loading screens (~0.33s)

# Direction button timings
TURN_HOLD_FRAMES = 8            # Hold time for turning in place (no walk)
TURN_WAIT_FRAMES = 8            # Wait time after turn

# Walk vs turn threshold
# 1-2 frames = walk one tile
# 5-10 frames = turn in place
# 10+ frames = continuous walk
WALK_FRAMES = 2                 # Minimum frames to walk
TURN_MIN_FRAMES = 5             # Minimum frames for turn (no walk)
TURN_MAX_FRAMES = 10            # Maximum frames for turn (before walking)


# =============================================================================
# Helper Functions
# =============================================================================

def keys_to_string(keys: int) -> str:
    """
    Convert a key bitmask to a human-readable string.

    Args:
        keys: Bitmask of pressed keys

    Returns:
        String representation like "A+B+START"
    """
    if keys == 0:
        return "NONE"

    pressed = []
    if keys & KEY_A:
        pressed.append("A")
    if keys & KEY_B:
        pressed.append("B")
    if keys & KEY_SELECT:
        pressed.append("SELECT")
    if keys & KEY_START:
        pressed.append("START")
    if keys & KEY_RIGHT:
        pressed.append("RIGHT")
    if keys & KEY_LEFT:
        pressed.append("LEFT")
    if keys & KEY_UP:
        pressed.append("UP")
    if keys & KEY_DOWN:
        pressed.append("DOWN")
    if keys & KEY_R:
        pressed.append("R")
    if keys & KEY_L:
        pressed.append("L")

    return "+".join(pressed)
