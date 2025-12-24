# Pokémon Emerald Shiny Hunter

Automated shiny hunting script for Pokémon Emerald starter Pokémon using mGBA Python bindings. This tool automates the process of resetting and checking for shiny starter Pokémon, saving you countless hours of manual resets.

## Features

- 🎯 **Automated Resets**: Automatically resets and checks for shiny starters
- 🎲 **RNG Manipulation**: Bypasses Emerald's "seed 0" issue by writing random seeds to memory
- 📊 **Progress Tracking**: Real-time progress updates with attempt counts and rates
- 📸 **Screenshot Capture**: Automatically saves screenshots when a shiny is found
- 🔊 **Notifications**: macOS system notifications and sound alerts
- 💾 **Auto-Save**: Saves game state when shiny is found
- 📝 **Logging**: Comprehensive logging to track your hunt
- 🔄 **Error Recovery**: Automatic retry and recovery on errors
- ⚡ **Optimized**: Fast execution with optimized button press timing

## Requirements

- **macOS** (for system notifications and alert sounds; can be modified for other OS)
- **Python 3.7+**
- **mGBA** installed via Homebrew with Python bindings
- **Pokémon Emerald ROM** (legally obtained)
- **Save file** (`.sav`) positioned before starter selection

## Installation

### 1. Install mGBA with Python bindings

```bash
brew install mgba
```

### 2. Verify Python bindings

The mGBA Python bindings should be available after installing via Homebrew. Verify with:

```bash
python3 -c "import mgba.core; print('mGBA bindings OK')"
```

### 3. Clone this repository

```bash
git clone <repository-url>
cd emerald-shiny-hunter
```

## Setup

1. **Place your ROM**: Put your Pokémon Emerald ROM in the `roms/` directory as `Pokemon - Emerald Version (U).gba`

2. **Prepare your save file**: 
   - Create a save file (`.sav`) in the `roms/` directory
   - Position yourself at the bag screen (after Birch asks you to help, when you can select Torchic)
   - Save the game normally in mGBA (this creates/updates the `.sav` file)

3. **Configure Trainer IDs**: Edit the starter script you want to use (`src/torchic.py` or `src/mudkip.py`) and set your Trainer ID (TID) and Secret ID (SID):
   ```python
   TID = 56078  # Your Trainer ID
   SID = 24723  # Your Secret ID
   ```

### Save File Positioning

Your save file should be positioned at the moment when:
- Birch has asked you to take a Pokémon from his bag
- The cursor is on the bag (or you're about to open it)
- You haven't selected Torchic yet

**Note:** Your mGBA keyboard bindings don't affect the script. The Python API sends inputs directly to the Game Boy's virtual buttons.

## Usage

### Starter Scripts

This project includes separate scripts for each starter Pokémon:

- **`torchic.py`**: Hunts for shiny Torchic (middle starter)
- **`mudkip.py`**: Hunts for shiny Mudkip (right starter)

### Running the Scripts

Run the script for your desired starter:

```bash
# For Torchic
python3 src/torchic.py

# For Mudkip
python3 src/mudkip.py
```

### Suppressing GBA Debug Output

mGBA may output debug messages that clutter the console. To suppress them, pipe the output through `grep`:

```bash
# For Torchic
python3 src/torchic.py 2>&1 | grep -v "^GBA"

# For Mudkip
python3 src/mudkip.py 2>&1 | grep -v "^GBA"
```

This filters out lines starting with "GBA" while keeping all other output (including errors and progress updates).

### What the Script Does

The script will:
1. Load the save file from `roms/Pokemon - Emerald Version (U).sav`
2. Write a random RNG seed to memory (to bypass Emerald's seed 0 issue)
3. Execute button presses to select the starter (sequence varies by starter)
4. Decrypt and identify the Pokémon species from memory
5. Check if the Pokémon is shiny using the Generation III formula
6. If shiny: save screenshot, play alert sound, send notification, save game state, and stop
7. If not shiny: reload save and repeat

### Progress Output

The script provides detailed progress information:

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

### Status Updates

Every 10 attempts or 5 minutes, you'll see a status update:

```
[Status] Attempt 100 | Rate: 2.45/s | Elapsed: 40.8 min | Running smoothly...
```

## How It Works

### Shiny Calculation

The script uses the Generation III shiny formula:

```python
PV_Low = PV & 0xFFFF          # Lower 16 bits of Personality Value
PV_High = (PV >> 16) & 0xFFFF # Upper 16 bits of Personality Value
TID_XOR_SID = TID ^ SID       # Trainer ID XOR Secret ID
PV_XOR = PV_Low ^ PV_High     # PV lower XOR PV upper
Shiny_Value = TID_XOR_SID ^ PV_XOR  # Final shiny calculation
```

If `Shiny_Value < 8`, the Pokémon is shiny.

### Memory Addresses

- **Personality Value**: `0x020244EC` (first 4 bytes of party data)
- **RNG Seed**: `0x03005D80` (used for RNG manipulation)

### RNG Bypass

Pokémon Emerald has a "seed 0" issue where the RNG starts at the same value each reset. The script:
1. Waits a random number of frames (10-100) after loading
2. Writes a random 32-bit seed to the RNG memory address
3. Re-writes the seed after button presses to prevent overwrite

### Stability Features

- **Error Handling**: Automatic retry (up to 3 consecutive errors)
- **Periodic Status Updates**: Every 10 attempts or 5 minutes
- **Automatic Recovery**: Resets core and reloads save on errors
- **Memory Management**: Core is reset each iteration, file handles properly closed
- **Logging**: All output is logged to `logs/shiny_hunt_YYYYMMDD_HHMMSS.log`
- **Long-Running**: Can run indefinitely without memory leaks

## Configuration

Edit these constants in the starter script you're using (`src/torchic.py` or `src/mudkip.py`):

- `ROM_PATH`: Path to your ROM file (default: `roms/Pokemon - Emerald Version (U).gba`)
- `TID`: Your Trainer ID (required for accurate shiny detection)
- `SID`: Your Secret ID (required for accurate shiny detection)

### Torchic-specific (`src/torchic.py`):
- `A_PRESSES_NEEDED`: Number of A button presses (default: 26)
- `A_PRESS_DELAY_FRAMES`: Frames to wait between presses (default: 15)

### Mudkip-specific (`src/mudkip.py`):
- `A_PRESSES_BEFORE_RIGHT`: A presses before Right button (default: 20)
- `WAIT_AFTER_A_FRAMES`: Frames to wait after A presses (default: 30)
- `A_PRESSES_AFTER_RIGHT`: A presses after Right button (default: 2)
- `A_PRESS_DELAY_FRAMES`: Frames to wait between presses (default: 15)

## Output Files

When a shiny is found, the script creates:

- **Screenshot**: `screenshots/shiny_found_YYYYMMDD_HHMMSS.png`
- **Save State**: `save_states/shiny_save_state_YYYYMMDD_HHMMSS.ss0`
- **Log File**: `logs/shiny_hunt_YYYYMMDD_HHMMSS.log`

## Troubleshooting

### mGBA bindings not found

If you get `ImportError: No module named 'mgba'`:
- Ensure mGBA was installed via Homebrew: `brew install mgba`
- Verify Python can import it: `python3 -c "import mgba.core"`

### Save file fails to load

- Ensure the `.sav` file exists in the `roms/` directory
- Verify the save file is from Pokémon Emerald
- Make sure the save is positioned correctly (at bag screen)

### Screenshot appears black

Screenshots may not work in headless mode (when mGBA has no visible window). The save state contains the exact game state - load it in mGBA GUI to see your shiny!

### No shiny found after many attempts

The odds of finding a shiny are **1/8192** in Generation III. This could take thousands of resets! The script will show estimated time based on your current rate.

### Script stops with errors

- Check the log file in `logs/` for detailed error messages
- Ensure your ROM and save files are valid
- Verify your TID and SID are correct

## Project Structure

```
emerald-shiny-hunter/
├── src/
│   ├── torchic.py           # Shiny hunting script for Torchic
│   ├── mudkip.py            # Shiny hunting script for Mudkip
│   ├── debug/               # Debug and test scripts
│   │   ├── test_mudkip_sequence.py
│   │   └── ...
│   └── ...                  # Other test scripts
├── roms/                     # ROM and save files (gitignored)
├── screenshots/              # Screenshots when shiny found (gitignored)
├── save_states/             # Save states (gitignored)
├── logs/                    # Log files (gitignored)
├── README.md                # This file
└── LICENSE                  # MIT License
```

## Legal Disclaimer

This software is for **educational and personal use only**. Users are responsible for ensuring they have legal rights to use any ROM files with this software. The authors and contributors are not responsible for any misuse of this software or any legal issues arising from its use.

**You must own a legal copy of Pokémon Emerald** to use this software ethically. ROM files should be created from your own legally purchased game cartridge.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Built with [mGBA](https://mgba.io/) emulator
- Uses the Generation III shiny formula documented by the Pokémon community
