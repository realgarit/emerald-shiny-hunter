"""
Utilities package for Pokemon Emerald Shiny Hunter.

Provides shared helper functions for:
- Logging (Tee, LogManager)
- Memory operations (read/write)
- Pokemon data (decryption, shiny check)
- Notifications (macOS, Discord)
- Save state management
"""

from .logging import Tee, LogManager
from .memory import (
    read_u8,
    read_u16,
    read_u32,
    read_bytes,
    write_u8,
    write_u16,
    write_u32,
    write_bytes,
)
from .pokemon import (
    get_substructure_order,
    decrypt_species,
    decrypt_species_extended,
    calculate_shiny_value,
    check_shiny,
    convert_party_to_box,
    decrypt_ivs,
    format_ivs,
)
from .notifications import (
    play_alert_sound,
    send_macos_notification,
    send_discord_notification,
    open_file,
    notify_shiny_found,
)
from .savestate import (
    save_screenshot,
    save_game_state,
    load_save_state,
)

__all__ = [
    # Logging
    "Tee", "LogManager",
    # Memory
    "read_u8", "read_u16", "read_u32", "read_bytes",
    "write_u8", "write_u16", "write_u32", "write_bytes",
    # Pokemon
    "get_substructure_order", "decrypt_species", "decrypt_species_extended",
    "calculate_shiny_value", "check_shiny", "convert_party_to_box",
    "decrypt_ivs", "format_ivs",
    # Notifications
    "play_alert_sound", "send_macos_notification", "send_discord_notification",
    "open_file", "notify_shiny_found",
    # Save state
    "save_screenshot", "save_game_state", "load_save_state",
]
