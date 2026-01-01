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


def format_ivs_table(ivs: dict) -> str:
    """
    Format IVs as a compact ASCII table for Discord display.

    Args:
        ivs: Dict with IV values

    Returns:
        ASCII table string for Discord code block
    """
    lines = [
        f"HP  ATK DEF SPE SPA SPD │ TOT",
        f"{ivs['hp']:>2}  {ivs['atk']:>2}  {ivs['def']:>2}  {ivs['spe']:>2}  {ivs['spa']:>2}  {ivs['spd']:>2}  │ {ivs['total']:>3}",
    ]
    return "\n".join(lines)


def get_sprite_url(species_name: str) -> str:
    """
    Get the PokemonDB shiny sprite URL for a species.

    Args:
        species_name: Pokemon species name

    Returns:
        URL to the shiny sprite image
    """
    # Normalize species name for URL (lowercase, no special chars)
    url_name = species_name.lower().replace(" ", "-").replace(".", "").replace("'", "")
    return f"https://img.pokemondb.net/sprites/ruby-sapphire/shiny/{url_name}.png"


def notify_shiny_found(
    species_name: str,
    attempts: int,
    pv: int,
    shiny_value: int,
    elapsed_minutes: float,
    is_target: bool = True,
    ivs: Optional[dict] = None,
    level: int = 0,
    location: str = "",
    nature: str = ""
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
        ivs: Dict with IV values (hp, atk, def, spe, spa, spd, total)
        level: Pokemon level
        location: Location name where encountered
        nature: Pokemon nature (e.g., "Adamant", "Jolly")
    """
    # Play sound
    play_alert_sound()

    # macOS notification
    send_macos_notification(
        f"Shiny {species_name} found after {attempts} attempts!",
        subtitle=f"PV: 0x{pv:08X} | Time: {elapsed_minutes:.1f} min"
    )

    # Discord notification with new format
    send_discord_shiny_notification(
        species_name=species_name,
        attempts=attempts,
        shiny_value=shiny_value,
        is_target=is_target,
        ivs=ivs,
        level=level,
        location=location,
        nature=nature
    )


def send_discord_shiny_notification(
    species_name: str,
    attempts: int,
    shiny_value: int,
    is_target: bool = True,
    ivs: Optional[dict] = None,
    level: int = 0,
    location: str = "",
    nature: str = "",
    webhook_url: Optional[str] = None
):
    """
    Send Discord webhook notification for shiny find with enhanced formatting.

    Args:
        species_name: Name of the Pokemon
        attempts: Number of attempts
        shiny_value: Calculated shiny value
        is_target: Whether this is the target species
        ivs: Dict with IV values
        level: Pokemon level
        location: Location name
        nature: Pokemon nature (e.g., "Adamant", "Jolly")
        webhook_url: Discord webhook URL (defaults to DISCORD_WEBHOOK_URL env var)
    """
    if webhook_url is None:
        webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        return  # No webhook configured, skip silently

    try:
        # Build the raw text content with @everyone mention
        content = f"Encountered a shiny ✨ {species_name} ✨!\n📢 @everyone"

        # Build embed title
        if is_target:
            embed_title = "Shiny encountered!"
        else:
            embed_title = "Shiny encountered! (non-target)"

        # Build description: "Bold Ralts (Lv. 4) at Route 102!"
        level_str = f"Lv. {level}" if level > 0 else ""
        location_str = location if location else "Unknown"
        nature_str = nature if nature else ""

        pokemon_info = f"**{nature_str} {species_name}**" if nature_str else f"**{species_name}**"
        if level_str:
            pokemon_info += f" ({level_str})"
        pokemon_info += f" at {location_str}!"

        # Build IV table if available
        iv_table = ""
        if ivs:
            iv_table = f"```\n{format_ivs_table(ivs)}\n```"

        # Build embed description
        description = pokemon_info

        # Build fields for the embed
        fields = [
            {
                "name": "Shiny Value",
                "value": str(shiny_value),
                "inline": True
            }
        ]

        if ivs:
            fields.append({
                "name": "IVs",
                "value": iv_table,
                "inline": False
            })

        fields.append({
            "name": "Total Encounters",
            "value": str(attempts),
            "inline": True
        })

        # Get sprite URL
        sprite_url = get_sprite_url(species_name)

        embed = {
            "title": embed_title,
            "description": description,
            "color": 0x00ff00 if is_target else 0xffff00,
            "fields": fields,
            "thumbnail": {
                "url": sprite_url
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {
            "content": content,
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
