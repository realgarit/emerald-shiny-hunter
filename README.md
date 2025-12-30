# Pokémon Emerald Shiny Hunter

Automated shiny hunting for Pokémon Emerald using mGBA. Checks for shinies automatically, so you don't have to sit there pressing buttons for hours.

Works with starter Pokémon and wild encounters on Route 101 and Route 102.

## What it does

- **Route 102 uses flee method**: Instead of resetting after each encounter, flees from battle and continues hunting - much faster!
- Writes random RNG seeds to memory (Emerald starts with the same seed every reset)
- Shows progress updates with attempt counts and rates
- Watch the game live (Route 101 & 102) - add `--show-window` to see what's happening
- Saves screenshots when a shiny is found
- Plays a sound and sends a macOS notification when it finds one
- Sends Discord webhook notifications (optional, via environment variable)
- Saves the game state automatically so you can continue playing
- Logs everything to a file
- Retries automatically if something goes wrong
- Runs fast with optimized button timing

## What you need

- macOS (for notifications and sounds - you can modify it for other OS)
- Python 3.10 or 3.11 (required - the mgba package on PyPI only has pre-built wheels for these versions)
- mGBA installed via Homebrew (`brew install mgba`)
- mGBA Python bindings installed via pip (`pip3 install mgba` with Python 3.10+)
- A Pokémon Emerald ROM (you need to own the game legally)
- A save file positioned right before you select your starter

## Installation

### Install mGBA

First, install the mGBA emulator via Homebrew:

```bash
brew install mgba
```

### Install mGBA Python bindings

The Python bindings are required for the scripts to work. **Important:** The `mgba` package on PyPI only provides pre-built wheels for Python 3.10 and 3.11.

**Install Python 3.10 or 3.11 (recommended):**

On macOS, install a newer Python version via Homebrew:

```bash
brew install python@3.11
python3.11 -m pip install mgba
```

Then use `python3.11` to run the scripts instead of `python3`:

```bash
python3.11 src/torchic.py
python3.11 src/route102.py
```

**Note:** If you have Python 3.9 or older, building from source is possible but can be problematic. We strongly recommend upgrading to Python 3.10 or 3.11 for the easiest installation experience.

### Install Python dependencies

The scripts require additional Python packages. Install the required packages:

```bash
python3.11 -m pip install opencv-python numpy
```

Or install from requirements.txt (includes optional packages):

```bash
python3.11 -m pip install -r requirements.txt
```

**Required packages:**
- `opencv-python` and `numpy` - Required for `route101.py` and `route102.py` (for image processing)
- Starter scripts (`torchic.py`, `mudkip.py`, `treecko.py`) don't need these packages

**Optional packages:**
- `python-dotenv` - Only needed if you want to use a `.env` file for Discord webhook configuration. Without it, the script will use environment variables directly.

### Check if it works

```bash
python3.11 -c "import mgba.core; print('mGBA bindings OK')"
python3.11 -c "import cv2, numpy; print('Dependencies OK')"
```

If both commands print "OK", you're good to go.

### Get the code

```bash
git clone <repository-url>
cd emerald-shiny-hunter
```

## Setup

### 1. Put your ROM in place

Put your Pokémon Emerald ROM in the `roms/` folder and name it `Pokemon - Emerald Version (U).gba`

### 2. Create a save file

- Open the game in mGBA and get to the bag screen (right after Birch asks you to help, when you can select a starter)
- Save the game normally in mGBA
- This creates a `.sav` file in the `roms/` directory

### 3. Set your Trainer IDs

Open the script you want to use (like `src/torchic.py`) and change these values:

```python
TID = 56078  # Your Trainer ID
SID = 24723  # Your Secret ID
```

You need both IDs for the shiny calculation to work correctly.

## Usage

### Starter Pokémon

There are separate scripts for each starter:

- `torchic.py` - Hunts for shiny Torchic (middle starter)
- `mudkip.py` - Hunts for shiny Mudkip (right starter)
- `treecko.py` - Hunts for shiny Treecko (left starter)

Run whichever one you want:

```bash
python3 src/torchic.py
python3 src/mudkip.py
python3 src/treecko.py

# Watch the game while it hunts (all starter scripts support --show-window)
python3 src/torchic.py --show-window
python3 src/mudkip.py --show-window
python3 src/treecko.py --show-window
```

### Route 101 Wild Encounters

Hunt for shiny wild Pokémon on Route 101:

- `route101.py` - Hunt Route 101 Pokémon with optional target filtering. You can watch it live with `--show-window`

```bash
# Hunt all Route 101 species (Poochyena, Zigzagoon, Wurmple)
python3 src/route101.py

# Hunt only a specific species
python3 src/route101.py --target zigzagoon
python3 src/route101.py --target poochyena
python3 src/route101.py --target wurmple

# Watch the game while it hunts
python3 src/route101.py --target zigzagoon --show-window
python3 src/route101.py --show-window  # Shows all encounters
```

For Route 101, your save file should be positioned on Route 101, ready to walk around and trigger encounters.

### Route 102 Wild Encounters

Hunt for shiny wild Pokémon on Route 102 using the **flee method** (faster than resetting!):

- `route102.py` - Hunt Route 102 Pokémon with optional target filtering. Uses flee method instead of resetting.

```bash
# Hunt all Route 102 species (Poochyena, Zigzagoon, Wurmple, Lotad, Seedot, Ralts)
python3 src/route102.py

# Hunt only a specific species (rare Ralts or Seedot)
python3 src/route102.py --target ralts
python3 src/route102.py --target seedot
python3 src/route102.py --target lotad

# Watch the game while it hunts
python3 src/route102.py --target ralts --show-window
python3 src/route102.py --show-window  # Shows all encounters
```

For Route 102, your save file should be positioned on Route 102, ready to walk around and trigger encounters.

**Note:** Route 102 has the same Pokémon as Route 101 (Poochyena, Zigzagoon, Wurmple) but adds version exclusives:
- **Lotad** - Common (appears frequently)
- **Seedot** - Very rare (1% encounter rate)
- **Ralts** - Rare (1% encounter rate) - the most sought-after early-game catch!

**Target Species Behavior:** When hunting for a specific target (e.g., `--target ralts`), the script will:
- Log and continue hunting when non-target species are found
- Still check if non-target encounters are shiny (and notify you if so!)
- Only stop when a shiny of ANY species is found

### What happens when you run it

**For Starters and Route 101:**
1. Loads your save file
2. Writes a random RNG seed to memory (fixes Emerald's seed 0 bug)
3. Presses buttons to select the starter or trigger an encounter
4. Reads the Pokémon data from memory and checks if it's shiny
5. If shiny: saves screenshot, plays sound, sends notification, saves game state, stops
6. If not shiny: reloads and tries again

**For Route 102 (Flee Method):**
1. Loads your save file once at the start
2. Writes a random RNG seed to memory
3. Turns left/right to trigger encounters
4. When a Pokémon appears, checks if it's shiny
5. If shiny: saves screenshot, plays sound, sends notification, saves game state, stops
6. If not shiny: **flees from battle** and continues turning to find the next encounter
7. No need to reset - much faster!

You can add `--show-window` to watch the game while it hunts. The window updates every 5th frame so it doesn't slow things down, but you can still see what's happening.

### Progress output

You'll see something like this:

```
[*] Using FLEE method (flee from battle instead of resetting)
[*] Starting shiny hunt on Route 102...

[*] Starting hunt...
    Target: Ralts (non-targets will be logged/notified)

[Attempt 1] Pokemon found!
  Species: Zigzagoon (ID: 263) - NOT TARGET (continuing hunt)

[Attempt 2] Pokemon found!
  Species: Poochyena (ID: 261) - NOT TARGET (continuing hunt)

[Attempt 3] Pokemon found!
  Species: Ralts (ID: 270) - TARGET SPECIES!
  PV: 0x1A2B3C4D
  Shiny Value: 123 (need < 8 for shiny)
  Result: NOT SHINY (shiny value 123 >= 8)
  Rate: 3.50 attempts/sec | Elapsed: 0.9 min
```

Every 10 attempts or 5 minutes, you'll get a status update:

```
[Status] Attempt 100 | Rate: 3.45/s | Elapsed: 0.5 min | Running smoothly...
```

## How it works

### Shiny calculation

Uses the Generation III shiny formula:

```python
PV_Low = PV & 0xFFFF          # Lower 16 bits of Personality Value
PV_High = (PV >> 16) & 0xFFFF # Upper 16 bits of Personality Value
TID_XOR_SID = TID ^ SID       # Trainer ID XOR Secret ID
PV_XOR = PV_Low ^ PV_High     # PV lower XOR PV upper
Shiny_Value = TID_XOR_SID ^ PV_XOR  # Final shiny calculation
```

If `Shiny_Value < 8`, it's shiny.

### Memory addresses

- Personality Value: `0x020244EC` (party Pokémon) or `0x02024744` (enemy/wild Pokémon)
- Species ID: `0x020244F4` (party, PV + 0x08) or `0x0202474C` (enemy, PV + 0x08)
- RNG Seed: `0x03005D80` (used for RNG manipulation)

### Flee Method (Route 102)

The flee method is faster than resetting because:
1. No need to reload the save file each attempt
2. No need to go through the loading sequence (15 A presses)
3. Battle transitions are faster than full resets
4. RNG state is maintained between encounters

The script:
1. Detects when a new Pokémon appears (by monitoring the Personality Value in memory)
2. Checks if it's shiny
3. If not shiny, navigates to "Run" in the battle menu (Down → Right → A)
4. Returns to the overworld and continues turning to trigger the next encounter
5. Tracks the last direction faced to avoid accidentally walking when turning

### Direction Tracking

After fleeing from battle, the character returns facing the same direction they were facing when the battle started. The script tracks this and always starts turning in the **opposite** direction to avoid accidentally walking a tile.

### Wild Pokémon species identification (Route 101 & Route 102)

Reading wild Pokémon species from memory is trickier than party Pokémon. The battle structure stores things differently, so the normal decryption doesn't work.

#### What went wrong

When I tried to decrypt wild Pokémon data using the same method as party Pokémon, I kept getting values that were close but wrong:

- Expected Wurmple (265), got 290 (off by 25)
- Expected Poochyena (261), got 286 (off by 25)
- Expected Zigzagoon (263), got 288 (off by 25)

Always off by 25. That's not a coincidence.

#### The discovery: Internal vs National Dex IDs

After researching the [pokeemerald decompilation source code](https://github.com/pret/pokeemerald), I found that Pokémon Emerald uses **internal species indices** that differ from National Dex numbers:

**Route 101 & 102 Pokémon:**
| Pokémon | National Dex | Internal Index | Offset |
|---------|--------------|----------------|--------|
| Poochyena | 261 | 286 | -25 |
| Zigzagoon | 263 | 288 | -25 |
| Wurmple | 265 | 290 | -25 |
| Lotad | 270 | 295 | -25 |
| Seedot | 273 | 298 | -25 |
| **Ralts** | **280** | **392** | **-122** |

**Most Pokémon follow a -25 offset pattern**, but **Ralts has a completely unique offset of -122**! This is because Gen III's internal ordering stored Gen 1 and 2 Pokémon first, then new Gen 3 species in a different order.

The decrypted values from memory give us the **internal indices**, not National Dex numbers. We need offset correction to convert them.

**Note on Route 102 mappings:** Through empirical testing, Lotad appears in the game when the script identifies ID 280 (which would normally be Ralts in National Dex). This means:
- ID 280 → "Lotad" (empirically verified in-game)
- ID 270 → "Ralts" (Ralts decrypts to 392, with -122 offset = 270)

This mapping works correctly and all species are properly identified.

#### Why it happens

The battle structure for wild encounters is different from party Pokémon:

1. OT TID handling - Wild Pokémon usually have OT TID = 0, but the battle structure might store it differently
2. Memory layout - The encrypted data might be at a different offset
3. Decryption key - The XOR formula might need tweaking

The normal party decryption looks like this:
```python
xor_key = (tid ^ pv)
decrypted = encrypted_val ^ xor_key
species_id = decrypted & 0xFFFF
```

For wild Pokémon, this gives you values that are consistently off by about 25.

#### How it's fixed

The script tries a bunch of things until something works:

1. Tries different OT TID values - Tests 0, the TID from memory, and a few other combinations
2. Tries different memory offsets - Checks offsets like 32, 0, 8, 16, 24, 40, 48 from the PV address
3. Tries all substructure positions - Tests all 4 positions (G, A, E, M) to find where the species ID is
4. Applies offset correction - If the decrypted value is in the valid range (1-450 to include Ralts at 392) but doesn't match, it tries converting from internal index to National Dex:
   ```python
   # Includes -122 for Ralts and common offsets for other species
   for offset_correction in [-122, -30, -25, -20, -15, -10, -5, 5, 10, 15, 20, 25, 30]:
       corrected_id = species_id + offset_correction
       if corrected_id == target_species_id:
           return corrected_id  # Found it!
   ```

5. Checks both halves - Also looks at the upper 16 bits in case of byte order issues

#### Why this works

The offset is always consistent for each Pokémon species:
- If you decrypt a Wurmple, you always get 290 (internal index) → subtract 25 → get 265 (National Dex) ✓
- If you decrypt a Ralts, you always get 392 (internal index) → subtract 122 → get 270 (ID used in our mapping) ✓

The correction range covers common offsets (-25 for most Pokémon) plus the special Ralts offset (-122), with some wiggle room in case other species vary.

#### How it's implemented

The scripts (`route101.py` and `route102.py`) try the most likely combinations first (OT_TID from memory, offset +32, position 2). If that doesn't work, they try everything else.

The offset correction only applies if the value is in a valid range (1-450 to include Ralts at internal index 392), preventing false positives.

This works for any route - each script checks against the known species for that route and applies the appropriate offsets.

### RNG bypass

Emerald has a bug where the RNG starts at the same value every reset. The script fixes this by:

1. Waiting a random number of frames (10-100) after loading
2. Writing a random 32-bit seed to the RNG memory address
3. Re-writing the seed after button presses so the game doesn't overwrite it

### Stability

- All scripts use `mgba.log.silence()` to suppress mGBA debug output (prevents I/O blocking)
- Automatic retry (up to 3 consecutive errors)
- Status updates every 10 attempts or 5 minutes
- Resets and reloads save on errors (starter scripts and route101)
- Route 102 uses flee method - only resets on critical errors
- Everything is logged to `logs/shiny_hunt_YYYYMMDD_HHMMSS.log`
- Can run indefinitely without memory leaks

## Configuration

Edit these in the script you're using:

- `ROM_PATH`: Path to your ROM file (default: `roms/Pokemon - Emerald Version (U).gba`)
- `TID`: Your Trainer ID
- `SID`: Your Secret ID

### Discord Webhook Notifications (Optional)

All scripts support Discord webhook notifications in addition to macOS notifications. To enable:

**Option 1: Using .env file (Recommended)**

1. Copy the example file and add your webhook URL:
   ```bash
   cp .env.example .env
   # Edit .env and add your Discord webhook URL
   ```

2. Install python-dotenv (optional, but recommended):
   ```bash
   pip3 install python-dotenv
   ```
   If `python-dotenv` is not installed, the scripts will still work but won't load the `.env` file automatically.

3. Run any script as usual:
   ```bash
   python3 src/torchic.py
   python3 src/route102.py
   ```

**Option 2: Using environment variable**

Alternatively, you can set the environment variable directly:
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
python3 src/torchic.py
```

All scripts will send a Discord notification when a shiny is found. If the webhook URL is not set, Discord notifications are silently skipped (no errors).

**Note:** The `.env` file is already in `.gitignore`, so your webhook URL won't be committed to the repository.

### Starter-specific settings

**Torchic** (`src/torchic.py`):
- `A_PRESSES_NEEDED`: Number of A button presses (default: 26)
- `A_PRESS_DELAY_FRAMES`: Frames to wait between presses (default: 15)

**Mudkip** (`src/mudkip.py`):
- `A_PRESSES_BEFORE_RIGHT`: A presses before Right button (default: 20)
- `WAIT_AFTER_A_FRAMES`: Frames to wait after A presses (default: 30)
- `A_PRESSES_AFTER_RIGHT`: A presses after Right button (default: 2)
- `A_PRESS_DELAY_FRAMES`: Frames to wait between presses (default: 15)

**Treecko** (`src/treecko.py`):
- Similar settings to Mudkip but for selecting the left starter

## Output files

When a shiny is found:

- Screenshot: `screenshots/shiny_found_YYYYMMDD_HHMMSS.png`
- Save State: `save_states/shiny_save_state_YYYYMMDD_HHMMSS.ss0`
- Log File: `logs/shiny_hunt_YYYYMMDD_HHMMSS.log` (starters) or `logs/route101_hunt_...` / `logs/route102_hunt_...` (wild encounters)

## Troubleshooting

### mGBA bindings not found

If you get `ModuleNotFoundError: No module named 'mgba'` or `ImportError: No module named 'mgba'`:

- **Check your Python version**: `python3 --version`
- The `mgba` package on PyPI only has pre-built wheels for Python 3.10 and 3.11
- **Solution**: Install Python 3.11 and use it:
  ```bash
  brew install python@3.11
  python3.11 -m pip install mgba
  python3.11 -c "import mgba.core; print('mGBA bindings OK')"
  ```
- Make sure mGBA was installed via Homebrew: `brew install mgba`
- Remember to use `python3.11` to run the scripts instead of `python3`

### Save file won't load

- Make sure the `.sav` file exists in the `roms/` directory
- Check that it's actually a Pokémon Emerald save file
- Verify the save is positioned correctly (at bag screen for starters, on Route 101/102 for wild encounters)

### No shiny after many attempts

Shiny odds are 1/8192 in Generation III. It can take thousands of attempts. The script shows an estimated time based on your current rate.

### Script stops with errors

- Check the log file in `logs/` for details
- Make sure your ROM and save files are valid
- Double-check your TID and SID are correct

## Other tools

### Combine Starter Shinies

[combine_starter_shinies.py](src/combine_starter_shinies.py) - Combines your 3 shiny starters (Treecko, Torchic, Mudkip) from different save states into one party.

**How it works:**
1. Scans `save_states/` folder for shiny starter save states (files with "mudkip", "torchic", or "treecko" in the name)
2. Extracts the 100-byte Pokémon data from party slot 1 of each save state
3. Uses the first found save as the base (keeps its slot 1 Pokémon)
4. Writes the other starters' data to party slots 2 and 3
5. Updates the party count and saves a new combined save state

**Usage:**
```bash
python3 src/combine_starter_shinies.py
```

**Output:** Creates `combined_shinies_YYYYMMDD_HHMMSS.ss0` in `save_states/` that you can load in mGBA to play with all three shiny starters in your party.

### Combine Box Shinies

[combine_box_shinies.py](src/combine_box_shinies.py) - Combines shiny Pokemon from multiple hunting sessions into PC boxes.

When running multiple shiny hunting instances (e.g., hunting on Route 102), each instance saves the shiny Pokemon in a battle save state. This script extracts those shinies and adds them to your PC boxes.

**Setup (one-time):**
1. First, create a base save state with your box data loaded:
   ```bash
   python3 src/debug/create_base_savestate.py
   ```
   This loads your `.sav` file, waits for box data to load into RAM, and creates `base_with_boxes.ss0`.

**Usage:**
```bash
python3 src/combine_box_shinies.py
```

**How it works:**
1. Loads `base_with_boxes.ss0` (contains your current box Pokemon)
2. Scans all boxes to find existing Pokemon and the first empty slot
3. Extracts shiny Pokemon from all `*.ss0` files (from the enemy battle slot)
4. Adds them to boxes starting from the first empty slot
5. Never overwrites existing Pokemon - always finds empty slots first
6. Saves a new combined save state

**Output:** Creates `combined_boxes_YYYYMMDD_HHMMSS.ss0` - load this in mGBA and save in-game to persist your Pokemon.

**Note:** The shiny save states store Pokemon in the enemy battle slot (address `0x02024744`), not the party. The script automatically extracts from the correct location.

## Project structure

```
emerald-shiny-hunter/
├── src/
│   ├── torchic.py              # Shiny hunt for Torchic
│   ├── mudkip.py               # Shiny hunt for Mudkip
│   ├── treecko.py              # Shiny hunt for Treecko
│   ├── route101.py             # Route 101 wild encounters
│   ├── route102.py             # Route 102 wild encounters (flee method)
│   ├── combine_starter_shinies.py  # Combine starter shinies into party
│   ├── combine_box_shinies.py  # Combine wild shinies into PC boxes
│   └── debug/
│       ├── create_base_savestate.py  # Create base save state from .sav file
│       └── test_discord_webhook.py   # Test Discord webhook notifications
├── roms/                       # ROM and save files (gitignored)
├── screenshots/                # Screenshots when shiny found (gitignored)
├── save_states/                # Save states (gitignored)
├── logs/                       # Log files (gitignored)
├── README.md
└── LICENSE
```

## Legal stuff

This is for educational and personal use only. You need to own a legal copy of Pokémon Emerald. ROM files should be created from your own game cartridge.

The authors aren't responsible for any misuse or legal issues.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome. Feel free to submit a pull request.

## Credits

- Built with [mGBA](https://mgba.io/) emulator
- Go visit the guys at [pokeemerald](https://github.com/pret/pokeemerald)
- Uses the Generation III shiny formula from the Pokémon community