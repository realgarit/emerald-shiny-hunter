# Pokémon Emerald Shiny Hunter

Automated shiny hunting for Pokémon Emerald using mGBA. Resets the game and checks for shinies automatically, so you don't have to sit there pressing buttons for hours.

Works with starter Pokémon and wild encounters on Route 101.

## What it does

- Resets the game automatically and checks each attempt
- Writes random RNG seeds to memory (Emerald starts with the same seed every reset)
- Shows progress updates with attempt counts and rates
- Watch the game live (Route 101 only) - add `--show-window` to see what's happening
- Saves screenshots when a shiny is found
- Plays a sound and sends a macOS notification when it finds one
- Saves the game state automatically so you can continue playing
- Logs everything to a file
- Retries automatically if something goes wrong
- Runs fast with optimized button timing

## What you need

- macOS (for notifications and sounds - you can modify it for other OS)
- Python 3.7 or newer
- mGBA installed via Homebrew with Python bindings
- A Pokémon Emerald ROM (you need to own the game legally)
- A save file positioned right before you select your starter

## Installation

### Install mGBA

```bash
brew install mgba
```

### Check if it works

```bash
python3 -c "import mgba.core; print('mGBA bindings OK')"
```

If that prints "mGBA bindings OK", you're good to go.

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

### What happens when you run it

1. Loads your save file
2. Writes a random RNG seed to memory (fixes Emerald's seed 0 bug)
3. Presses buttons to select the starter or trigger an encounter
4. Reads the Pokémon data from memory and checks if it's shiny
5. If shiny: saves screenshot, plays sound, sends notification, saves game state, stops
6. If not shiny: reloads and tries again

For Route 101, you can add `--show-window` to watch the game while it hunts. The window updates every 5th frame so it doesn't slow things down, but you can still see what's happening.

### Progress output

You'll see something like this:

```
[Attempt 1] Starting new reset...
  RNG Seed: 0x12345678, Delay: 50 frames

[Attempt 1] Pokemon found!
  PV: 0x1A2B3C4D
  PV Low:  0x3C4D (15437)
  PV High: 0x1A2B (6699)
  TID ^ SID: 0xABCD (43981)
  PV XOR: 0x2676 (9846)
  Shiny Value: 123 (need < 8 for shiny)
  Result: NOT SHINY (shiny value 123 >= 8)
  Rate: 2.50 attempts/sec | Elapsed: 0.4 min
  Estimated time to shiny: ~54.6 minutes (1/8192 odds)
```

Every 10 attempts or 5 minutes, you'll get a status update:

```
[Status] Attempt 100 | Rate: 2.45/s | Elapsed: 40.8 min | Running smoothly...
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

### Wild Pokémon species identification (Route 101)

Reading wild Pokémon species from memory is trickier than party Pokémon. The battle structure stores things differently, so the normal decryption doesn't work.

#### What went wrong

When I tried to decrypt wild Pokémon data using the same method as party Pokémon, I kept getting values that were close but wrong:

- Expected Wurmple (265), got 290 (off by 25)
- Expected Poochyena (261), got 286 (off by 25)
- Expected Zigzagoon (263), got 288 (off by 25)

Always off by 25. That's not a coincidence.

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
4. Applies offset correction - If the decrypted value is in the valid range (1-386) but doesn't match, it tries adding or subtracting small amounts:
   ```python
   for offset_correction in [-30, -25, -20, -15, -10, -5, 5, 10, 15, 20, 25, 30]:
       corrected_id = species_id + offset_correction
       if corrected_id == target_species_id:
           return corrected_id  # Found it!
   ```

5. Checks both halves - Also looks at the upper 16 bits in case of byte order issues

#### Why this works

The offset is always consistent. If you decrypt a Wurmple and get 290, you'll always get 290. So we can just subtract 25 and get the right answer.

The correction range covers the offset we saw (25) plus some wiggle room in case it varies slightly.

#### How it's implemented

The script in `route101.py` tries the most likely combinations first (OT_TID from memory, offset +32, position 2). If that doesn't work, it tries everything else.

It only applies the offset correction if the value is in the valid Pokémon ID range (1-386), so it won't give false positives.

This works for any route - it just checks against the known species for that route.

### RNG bypass

Emerald has a bug where the RNG starts at the same value every reset. The script fixes this by:

1. Waiting a random number of frames (10-100) after loading
2. Writing a random 32-bit seed to the RNG memory address
3. Re-writing the seed after button presses so the game doesn't overwrite it

### Stability

- Automatic retry (up to 3 consecutive errors)
- Status updates every 10 attempts or 5 minutes
- Resets and reloads save on errors
- Core is reset each iteration, file handles closed properly
- Everything is logged to `logs/shiny_hunt_YYYYMMDD_HHMMSS.log`
- Can run indefinitely without memory leaks

## Configuration

Edit these in the script you're using:

- `ROM_PATH`: Path to your ROM file (default: `roms/Pokemon - Emerald Version (U).gba`)
- `TID`: Your Trainer ID
- `SID`: Your Secret ID

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
- Log File: `logs/shiny_hunt_YYYYMMDD_HHMMSS.log` (or `route101_hunt_...` for Route 101)

## Troubleshooting

### mGBA bindings not found

If you get `ImportError: No module named 'mgba'`:

- Make sure mGBA was installed via Homebrew: `brew install mgba`
- Check if Python can import it: `python3 -c "import mgba.core"`

### Save file won't load

- Make sure the `.sav` file exists in the `roms/` directory
- Check that it's actually a Pokémon Emerald save file
- Verify the save is positioned correctly (at bag screen for starters, on Route 101 for wild encounters)

### Screenshot is black

Screenshots might not work if mGBA is running headless (no visible window). The save state has the exact game state - just load it in mGBA GUI to see your shiny.

### No shiny after many attempts

Shiny odds are 1/8192 in Generation III. It can take thousands of resets. The script shows an estimated time based on your current rate.

### Script stops with errors

- Check the log file in `logs/` for details
- Make sure your ROM and save files are valid
- Double-check your TID and SID are correct

## Other tools

### Combine shinies

`combine_shinies.py` - Takes shiny Pokémon from different save states and puts them all in one save file. Useful if you want all three starters shiny in one game.

```bash
python3 src/combine_shinies.py
```

## Project structure

```
emerald-shiny-hunter/
├── src/
│   ├── torchic.py              # Shiny hunt for Torchic
│   ├── mudkip.py               # Shiny hunt for Mudkip
│   ├── treecko.py              # Shiny hunt for Treecko
│   ├── route101.py             # Route 101 wild encounters (with optional target filtering and live window)
│   ├── combine_shinies.py      # Combine shinies from multiple saves
│   └── debug/                  # Debug scripts that found memory addresses
│       ├── find_species_address.py
│       ├── find_enemy_species_address.py
│       ├── scan_enemy_structure.py
│       ├── test_fast_presses.py
│       ├── test_decryption.py
│       └── test_mudkip_sequences_comprehensive.py
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
- Uses the Generation III shiny formula from the Pokémon community
