"""
Notification utilities for Pokemon Emerald Shiny Hunter.

Provides functions for:
- macOS system notifications
- Discord webhook notifications
- System alert sounds
"""

import os
import json
import subprocess
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from typing import Optional


def play_alert_sound(sound_path: str = "/System/Library/Sounds/Glass.aiff"):
    """
    Play system alert sound (macOS).

    Args:
        sound_path: Path to sound file
    """
    try:
        subprocess.run(["afplay", sound_path], check=False)
    except Exception as e:
        print(f"[!] Failed to play sound: {e}")


def send_macos_notification(message: str, title: str = "Shiny Hunter", subtitle: str = ""):
    """
    Send macOS system notification.

    Args:
        message: Notification message
        title: Notification title
        subtitle: Notification subtitle
    """
    try:
        script = f'''
        display notification "{message}" with title "{title}" subtitle "{subtitle}" sound name "Glass"
        '''
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception as e:
        print(f"[!] Failed to send notification: {e}")


def send_discord_notification(
    message: str,
    title: str = "Shiny Hunter Notification",
    color: int = 0x00ff00,
    webhook_url: Optional[str] = None
):
    """
    Send Discord webhook notification.

    Args:
        message: The message content
        title: The embed title
        color: The embed color (default: green)
        webhook_url: Discord webhook URL (defaults to DISCORD_WEBHOOK_URL env var)
    """
    if webhook_url is None:
        webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        return  # No webhook configured, skip silently

    try:
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {
            "embeds": [embed]
        }

        data = json.dumps(payload).encode('utf-8')
        req = Request(
            webhook_url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'ShinyHunter/1.0'
            }
        )
        urlopen(req, timeout=10)
        print("[+] Discord notification sent!")
    except (URLError, HTTPError) as e:
        print(f"[!] Failed to send Discord notification: {e}")
    except Exception as e:
        print(f"[!] Discord notification error: {e}")


def open_file(filepath: str):
    """
    Open a file with the default application (macOS).

    Args:
        filepath: Path to file to open
    """
    if filepath and os.path.exists(filepath):
        try:
            subprocess.run(["open", filepath], check=False)
        except Exception as e:
            print(f"[!] Failed to open file: {e}")


def notify_shiny_found(
    species_name: str,
    attempts: int,
    pv: int,
    shiny_value: int,
    elapsed_minutes: float,
    is_target: bool = True
):
    """
    Send all notifications for a shiny find.

    Args:
        species_name: Name of the Pokemon
        attempts: Number of attempts
        pv: Personality Value
        shiny_value: Calculated shiny value
        elapsed_minutes: Time elapsed in minutes
        is_target: Whether this is the target species
    """
    # Play sound
    play_alert_sound()

    # macOS notification
    send_macos_notification(
        f"Shiny {species_name} found after {attempts} attempts!",
        subtitle=f"PV: 0x{pv:08X} | Time: {elapsed_minutes:.1f} min"
    )

    # Discord notification
    if is_target:
        discord_message = (
            f"**Pokemon:** {species_name}\n"
            f"**Attempts:** {attempts}\n"
            f"**Personality Value:** `0x{pv:08X}`\n"
            f"**Shiny Value:** {shiny_value}\n"
            f"**Time Elapsed:** {elapsed_minutes:.1f} minutes"
        )
        send_discord_notification(discord_message, title=f"✨ Shiny {species_name} Found! ✨")
    else:
        discord_message = (
            f"✨ **Shiny {species_name} found!** ✨\n\n"
            f"**Note:** Not target species, but shiny!\n"
            f"**Attempts:** {attempts}\n"
            f"**Personality Value:** `0x{pv:08X}`\n"
            f"**Shiny Value:** {shiny_value}\n"
            f"**Time Elapsed:** {elapsed_minutes:.1f} minutes"
        )
        send_discord_notification(discord_message, title="✨ Shiny Found (Non-Target)! ✨", color=0xffff00)
