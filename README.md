# Pokémon Emerald Shiny Hunter

Automated shiny hunting script for Pokémon Emerald starter Pokémon using mGBA Python bindings.

## Requirements

- macOS (for the alert sound, but script can be modified for other OS)
- Python 3.7+
- mGBA installed via Homebrew with Python bindings
- Pokémon Emerald ROM
- Save state file positioned before starter selection

## Installation

### 1. Install mGBA with Python bindings

```bash
brew install mgba
```

### 2. Install Python dependencies

The mGBA Python bindings should be available after installing via Homebrew. Verify with:

```bash
python3 -c "import mgba.core; print('mGBA bindings OK')"
```

## Setup

1. Place your Pokémon Emerald ROM in this directory as `Pokemon - Emerald Version (U).gba`
2. Create a save state (`save-state-1.ss0`) positioned at the bag screen (after Birch asks you to help, when you can select Torchic)
3. Verify your Secret ID in the script (currently set to `24723`)

### Save State Positioning

The save state should be created at the moment when:
- Birch has asked you to take a Pokémon from his bag
- The cursor is on the bag (or you're about to open it)
- You haven't selected Torchic yet

**Note:** Your mGBA keyboard bindings don't affect the script. The Python API sends inputs directly to the Game Boy's virtual buttons.

### Testing Your Setup

Run the test script to verify everything works:
```bash
python3 test_mgba.py        # Tests basic functionality
python3 test_single_run.py  # Tests one full iteration
```

If `test_single_run.py` shows PV and TID as 0, you may need to:
- Adjust the wait time in `wait_for_battle()` (increase from 250 frames)
- Verify your save state is positioned correctly

## Usage

Run the script:

```bash
python3 shiny_hunter.py
```

The script will:
- Load the save state (at bag screen)
- Wait a random number of frames (30-500) to vary RNG
- Execute button presses: A (open/select Torchic) → A (confirm) → A (yes)
- Fast-forward ~4 seconds to the battle
- Check if the Pokémon is shiny
- If shiny: save screenshot, play alert sound, and stop
- If not shiny: reload and repeat

### Progress Output

```
[     1] PV: 1A2B3C4D | TID: 12345 | Shiny: 123 | Rate: 2.50/s
```

- **Attempts**: Number of resets attempted
- **PV**: Personality Value of the Pokémon
- **TID**: Trainer ID read from memory
- **Shiny**: Shiny value (< 8 = shiny)
- **Rate**: Resets per second

## How It Works

### Shiny Calculation

The script uses the Generation III shiny formula:

```python
PV_Low = PV & 0xFFFF
PV_High = PV >> 16
Shiny_Check = (TID ^ SID) ^ (PV_Low ^ PV_High)
```

If `Shiny_Check < 8`, the Pokémon is shiny.

### Memory Addresses

- **Party Start**: `0x020244EC`
- **Personality Value**: First 4 bytes of party data
- **Trainer ID**: Offset `+0x04` from party start

### RNG Bypass

Pokémon Emerald has a "seed 0" issue where the RNG starts at the same value each reset. The script waits a random number of frames before any input to vary the RNG state.

## Configuration

Edit these constants in `shiny_hunter.py`:

- `ROM_PATH`: Path to your ROM file
- `SAVE_STATE_PATH`: Path to your save state
- `SECRET_ID`: Your Secret ID (required for accurate shiny detection)

## Troubleshooting

### mGBA bindings not found

If you get `ImportError: No module named 'mgba'`, ensure mGBA was installed via Homebrew with Python support.

### Save state fails to load

Ensure the save state file is in the same directory and named correctly.

### No shiny found after many attempts

The odds of finding a shiny are 1/8192 in Generation III. This could take thousands of resets!

## License

This is a personal automation tool. Use responsibly and only with legally obtained ROM files.
