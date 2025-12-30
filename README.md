# Pokemon Emerald Shiny Hunter

Automated shiny hunting for Pokemon Emerald using mGBA Python bindings. The scripts check for shinies automatically so you don't have to sit there pressing buttons for hours.

Works with starter Pokemon and wild encounters on Route 101 and Route 102.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
  - [Starter Pokemon](#starter-pokemon)
  - [Route 101](#route-101)
  - [Route 102](#route-102)
- [Combining Shinies](#combining-shinies)
  - [Combine Starters](#combine-starters)
  - [Combine Box Shinies](#combine-box-shinies)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)

## Features

- Hunts starters (Torchic, Mudkip, Treecko) and wild Pokemon (Route 101, Route 102)
- Route scripts use **flee method** - flees instead of resetting, which is faster
- Fixes Emerald's RNG bug (game starts with same seed every reset)
- Live window with `--show-window` flag
- Discord webhook notifications (optional)
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

**Note:** `opencv-python` and `numpy` are only needed for route scripts. Starter scripts work without them.

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
- Position your character on Route 101 or 102
- Save the game

### 3. Set your Trainer IDs

Open the script you want to use and set your IDs:

```python
TID = 56078  # Your Trainer ID
SID = 24723  # Your Secret ID
```

You need both for the shiny calculation to work.

## Usage

### Starter Pokemon

```bash
# Hunt Torchic (middle)
python3 src/torchic.py

# Hunt Mudkip (right)
python3 src/mudkip.py

# Hunt Treecko (left)
python3 src/treecko.py

# Watch while hunting
python3 src/torchic.py --show-window
```

### Route 101

Route 101 uses the **flee method** - instead of resetting after each encounter, it flees and keeps hunting. Much faster.

```bash
# Hunt all species
python3 src/route101.py

# Hunt specific species
python3 src/route101.py --target zigzagoon
python3 src/route101.py --target poochyena
python3 src/route101.py --target wurmple

# Watch while hunting
python3 src/route101.py --show-window
```

Species: Poochyena, Zigzagoon, Wurmple

### Route 102

Route 102 also uses the **flee method**.

```bash
# Hunt all species
python3 src/route102.py

# Hunt specific species
python3 src/route102.py --target ralts
python3 src/route102.py --target seedot
python3 src/route102.py --target lotad

# Watch while hunting
python3 src/route102.py --show-window
```

Species: Poochyena, Zigzagoon, Wurmple, Lotad, Seedot (rare), Ralts (rare)

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

## Configuration

Edit these in the script you're using:

| Setting | Description |
|---------|-------------|
| `ROM_PATH` | Path to ROM (default: `roms/Pokemon - Emerald Version (U).gba`) |
| `TID` | Your Trainer ID |
| `SID` | Your Secret ID |

### Discord Notifications

Set up a webhook URL:

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

Route 101 and Route 102 use flee method because:
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
│   ├── torchic.py                  # Torchic starter hunt
│   ├── mudkip.py                   # Mudkip starter hunt
│   ├── treecko.py                  # Treecko starter hunt
│   ├── route101.py                 # Route 101 wild encounters (flee method)
│   ├── route102.py                 # Route 102 wild encounters (flee method)
│   ├── combine_starter_shinies.py  # Combine starters into one party
│   ├── combine_box_shinies.py      # Combine shinies into PC boxes
│   ├── constants/                  # Shared constants
│   │   ├── __init__.py             # Package exports
│   │   ├── species.py              # All 411 species IDs from pokeemerald + National Dex mappings
│   │   ├── memory.py               # Memory addresses (party, enemy, box, RNG)
│   │   └── keys.py                 # GBA button constants and timing
│   ├── utils/                      # Shared utilities
│   │   ├── __init__.py             # Package exports
│   │   ├── memory.py               # Memory read/write functions
│   │   ├── pokemon.py              # Species decryption, shiny checking
│   │   ├── logging.py              # Tee class, LogManager
│   │   ├── notifications.py        # macOS and Discord notifications
│   │   └── savestate.py            # Screenshot and save state management
│   ├── core/                       # Core components
│   │   ├── __init__.py             # Package exports
│   │   └── emulator.py             # EmulatorBase class
│   └── debug/
│       ├── create_base_savestate.py    # Create base save with box data
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
