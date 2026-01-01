# Pokemon Emerald Shiny Hunter

Automated shiny hunting for Pokemon Emerald using mGBA Python bindings. The scripts check for shinies automatically so you don't have to sit there pressing buttons for hours.

Works with starter Pokemon and wild encounters on all Hoenn routes and dungeons.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
  - [Starter Pokemon](#starter-pokemon)
  - [Wild Pokemon](#wild-pokemon)
- [Combining Shinies](#combining-shinies)
  - [Combine Starters](#combine-starters)
  - [Combine Box Shinies](#combine-box-shinies)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)

## Features

- Hunts starters (Torchic, Mudkip, Treecko) and wild Pokemon (17 routes + 14 dungeons)
- Starters use **soft reset method** - resets after each check
- Wild Pokemon use **flee method** - flees instead of resetting, much faster
- Fixes Emerald's RNG bug (game starts with same seed every reset)
- Live window with `--show-window` flag
- Discord webhook notifications with shiny sprite, IVs, nature, and @everyone ping
- macOS notifications and sound when shiny found
- Auto-saves screenshot and game state when shiny found
- Logs everything to file
- Auto-retry on errors

## Requirements

- macOS (notifications and sounds are macOS-specific, but you can modify for other OS)
- Python 3.10 or 3.11 (mgba package only has wheels for these versions)
- mGBA via Homebrew
- Pokemon Emerald ROM (you need to own the game)
- Save file positioned at the right spot

## Installation

### 1. Install mGBA

```bash
brew install mgba
```

### 2. Install Python 3.11 and mGBA bindings

```bash
brew install python@3.11
python3.11 -m pip install mgba
```

### 3. Install dependencies

```bash
python3.11 -m pip install opencv-python numpy
```

Or from requirements.txt:

```bash
python3.11 -m pip install -r requirements.txt
```

**Note:** `opencv-python` and `numpy` are only needed for window display (`--show-window`).

### 4. Verify installation

```bash
python3.11 -c "import mgba.core; print('mGBA OK')"
python3.11 -c "import cv2, numpy; print('Dependencies OK')"
```

### 5. Get the code

```bash
git clone <repository-url>
cd emerald-shiny-hunter
```

## Setup

### 1. Add your ROM

Put your Pokemon Emerald ROM in `roms/` and name it `Pokemon - Emerald Version (U).gba`

### 2. Create a save file

For starters:
- Open the game in mGBA
- Get to the bag screen (when you can select a starter)
- Save the game

For wild encounters:
- Position your character on the route/dungeon you want to hunt
- Save the game

### 3. Set your Trainer IDs

Open `src/hunt.py` and set your IDs:

```python
TID = 56078  # Your Trainer ID
SID = 24723  # Your Secret ID
```

You need both for the shiny calculation to work.

## Usage

All hunting is done through the unified `hunt.py` script.

### Starter Pokemon

Starters use the **soft reset method** - resets the game after each check.

```bash
# Hunt Torchic (center position)
python3 src/hunt.py --starter torchic

# Hunt Mudkip (right position)
python3 src/hunt.py --starter mudkip

# Hunt Treecko (left position)
python3 src/hunt.py --starter treecko

# Watch while hunting
python3 src/hunt.py --starter torchic --show-window
```

### Wild Pokemon

Wild Pokemon use the **flee method** - instead of resetting after each encounter, it flees and keeps hunting. Much faster than soft resetting.

```bash
# Hunt on any route
python3 src/hunt.py --route 101
python3 src/hunt.py --route 102 --target ralts
python3 src/hunt.py --route 117

# Hunt in dungeons
python3 src/hunt.py --location petalburg_woods
python3 src/hunt.py --location granite_cave --target aron
python3 src/hunt.py --location safari_zone

# List all available locations
python3 src/hunt.py --list-routes

# Watch while hunting
python3 src/hunt.py --route 101 --show-window
```

**Available Routes:** 101, 102, 103, 104, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 123

**Available Dungeons:** petalburg_woods, rusturf_tunnel, granite_cave, fiery_path, jagged_pass, mt_pyre_inside, mt_pyre_outside, mt_pyre_summit, meteor_falls, shoal_cave, cave_of_origin, victory_road, sky_pillar, safari_zone

**Target behavior:** When hunting a specific target, the script still checks if non-target encounters are shiny. It stops when ANY shiny is found.

### Output

When a shiny is found:
- Screenshot saved to `screenshots/`
- Save state saved to `save_states/`
- Log file in `logs/`

## Combining Shinies

### Combine Starters

After hunting all three starters, combine them into one save:

```bash
python3 src/combine_starter_shinies.py
```

This scans `save_states/` for starter save states and combines them into one party. Output: `combined_shinies_YYYYMMDD_HHMMSS.ss0`

### Combine Box Shinies

When running multiple hunting instances, each saves a shiny in a battle save state. This script adds them all to your PC boxes.

**First time setup:**

```bash
python3 src/debug/create_base_savestate.py
```

This creates `base_with_boxes.ss0` from your `.sav` file with box data loaded.

**Combine shinies:**

```bash
python3 src/combine_box_shinies.py
```

The script:
1. Loads `base_with_boxes.ss0`
2. Scans boxes to find existing Pokemon
3. Extracts shinies from all save states
4. Adds them starting from first empty slot
5. Never overwrites existing Pokemon
6. Archives processed save states to `save_states/archive/`

Output: `combined_boxes_YYYYMMDD_HHMMSS.ss0` - load in mGBA and save in-game to keep them.

### Select Best Shinies

When you have multiple shinies of the same species, select the best ones by IV total:

```bash
python3 src/debug/select_best_shinies.py
```

The script:
1. Scans all boxes and reads IVs for each Pokemon
2. Groups Pokemon by species
3. For species with more than 3, shows all IVs and marks top 3 to keep
4. Asks confirmation before deleting extras
5. Reorganizes boxes alphabetically by species (best IVs first within each species)

Test IV reading on first box slot:

```bash
python3 src/debug/select_best_shinies.py --test
```

Output: `best_shinies_YYYYMMDD_HHMMSS.ss0`

## Configuration

Edit these in `src/hunt.py`:

| Setting | Description |
|---------|-------------|
| `ROM_PATH` | Path to ROM (default: `roms/Pokemon - Emerald Version (U).gba`) |
| `TID` | Your Trainer ID |
| `SID` | Your Secret ID |

### Discord Notifications

Set up a webhook URL to get notified when a shiny is found:

**Option 1: .env file**

```bash
cp .env.example .env
# Edit .env and add your webhook URL
```

**Option 2: Environment variable**

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

The `.env` file is gitignored so your URL won't be committed.

**Test your webhook:**

```bash
python3 src/debug/test_discord_webhook.py         # Basic test
python3 src/debug/test_discord_webhook.py --shiny  # Test shiny notification format
```

**Notification format:**

When a shiny is found, the Discord notification includes:
- Raw text with @everyone mention: `Encountered a shiny ✨ Ralts ✨!`
- Embed card with:
  - Pokemon sprite (shiny, from PokemonDB)
  - Nature and species: **Bold Ralts** (Lv. 4) at Route 102!
  - Shiny Value
  - IVs table (HP, ATK, DEF, SPE, SPA, SPD, Total)
  - Total encounter count

## How It Works

### Shiny Formula

Generation III shiny calculation:

```python
shiny_value = (TID ^ SID) ^ (PV_low ^ PV_high)
# Shiny if shiny_value < 8
```

### Memory Addresses

All memory addresses are defined in `constants/memory.py`.

### RNG Fix

Emerald has a bug where the RNG starts at the same value every reset. The scripts fix this by writing a random seed to memory.

### Flee Method

Wild Pokemon hunting uses flee method because:
- No need to reload save each attempt
- No loading sequence (15 A presses)
- Battle transitions are faster than resets

### Species ID Mapping

Pokemon Emerald uses internal species IDs that differ from National Dex numbers. Gen I/II Pokemon (1-251) have matching IDs, but Gen III Pokemon use different internal IDs.

All 386 Pokemon mappings are in `constants/species.py`, sourced from pokeemerald's `species.h`. Helper functions `get_national_dex()` and `get_internal_id()` handle conversions automatically.

## Troubleshooting

### mGBA bindings not found

```
ModuleNotFoundError: No module named 'mgba'
```

The mgba package only has wheels for Python 3.10 and 3.11:

```bash
brew install python@3.11
python3.11 -m pip install mgba
```

Use `python3.11` to run scripts.

### Save file won't load

- Check `.sav` file exists in `roms/`
- Verify it's a Pokemon Emerald save
- Make sure save position is correct (bag screen for starters, route for wild)

### No shiny after many attempts

Shiny odds are 1/8192. It can take thousands of attempts. The script shows your current rate and estimated time.

### Script errors

Check the log file in `logs/` for details. Make sure TID and SID are correct.

## Project Structure

```
emerald-shiny-hunter/
├── src/
│   ├── hunt.py                     # Unified hunting (starters + all routes/dungeons)
│   ├── combine_starter_shinies.py  # Combine starters into one party
│   ├── combine_box_shinies.py      # Combine shinies into PC boxes
│   ├── constants/                  # Shared constants
│   │   ├── __init__.py             # Package exports
│   │   ├── species.py              # All 411 species IDs from pokeemerald + National Dex mappings
│   │   ├── routes.py               # Route/dungeon encounter tables
│   │   ├── starters.py             # Starter selection sequences
│   │   ├── memory.py               # Memory addresses (party, enemy, box, RNG)
│   │   └── keys.py                 # GBA button constants and timing
│   ├── utils/                      # Shared utilities
│   │   ├── __init__.py             # Package exports
│   │   ├── memory.py               # Memory read/write functions
│   │   ├── pokemon.py              # Species decryption, shiny checking, IVs, nature
│   │   ├── logging.py              # Tee class, LogManager
│   │   ├── notifications.py        # macOS and Discord notifications
│   │   └── savestate.py            # Screenshot and save state management
│   ├── core/                       # Core components
│   │   ├── __init__.py             # Package exports
│   │   └── emulator.py             # EmulatorBase class
│   └── debug/
│       ├── create_base_savestate.py    # Create base save with box data
│       ├── select_best_shinies.py      # Select best shinies by IV, reorganize boxes
│       └── test_discord_webhook.py     # Test Discord notifications
├── roms/           # ROM and save files (gitignored)
├── screenshots/    # Shiny screenshots (gitignored)
├── save_states/    # Save states (gitignored)
├── logs/           # Log files (gitignored)
└── README.md
```

## License

MIT License - see [LICENSE](LICENSE)

## Credits

- [mGBA](https://mgba.io/) emulator
- [pokeemerald](https://github.com/pret/pokeemerald) decompilation project
