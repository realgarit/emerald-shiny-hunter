#!/usr/bin/env python3
"""
XP Farming battle script for Pokemon Emerald.

Automatically battles wild Pokemon to farm experience points.
Uses memory-based state detection for robust operation.

Usage:
    # Farm XP on Route 101
    python3 src/battle.py --route 101

    # Farm XP with verbose logging
    python3 src/battle.py --route 116 --verbose

    # Limited battles with window display
    python3 src/battle.py --location granite_cave --max-battles 50 --show-window

    # List available locations
    python3 src/battle.py --list-routes
"""

import random
import time
import sys
import argparse
from pathlib import Path
from enum import Enum
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    # Memory addresses - general
    PARTY_PV_ADDR, ENEMY_PV_ADDR,
    # Memory addresses - battle state
    G_BATTLE_TYPE_FLAGS, G_BATTLE_OUTCOME, G_ENEMY_BATTLE_MON,
    BATTLE_MON_HP_OFFSET, BATTLE_MON_MAX_HP_OFFSET, G_MOVE_TO_LEARN,
    # Battle outcome constants
    BATTLE_OUTCOME_NONE, BATTLE_OUTCOME_WON,
    BATTLE_OUTCOME_MON_FLED, BATTLE_OUTCOME_PLAYER_TELEPORTED,
    # Keys
    KEY_NONE, KEY_LEFT, KEY_RIGHT, KEY_A, KEY_B,
    # Routes/dungeons
    get_route_species, get_route_name,
    get_available_routes, get_available_dungeons,
)
from utils import LogManager
from utils.healer import heal_party
from core import EmulatorBase

# Try to load dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Configuration
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")

# Timing constants (reuse from hunt.py)
A_PRESSES_LOADING = 15
A_LOADING_DELAY_FRAMES = 20
LEFT_HOLD_FRAMES = 1
LEFT_WAIT_FRAMES = 20
RIGHT_HOLD_FRAMES = 1
RIGHT_WAIT_FRAMES = 20


class BattleState(Enum):
    """State machine states for battle farming."""
    OVERWORLD = "overworld"
    SEEKING_ENCOUNTER = "seeking_encounter"
    BATTLE_INTRO = "battle_intro"
    BATTLE_ACTIVE = "battle_active"
    BATTLE_END = "battle_end"
    MOVE_LEARNING = "move_learning"
    EVOLUTION = "evolution"
    POST_BATTLE = "post_battle"
    ERROR = "error"


class XPFarmer(EmulatorBase):
    """XP farming bot that battles wild Pokemon to gain experience."""

    def __init__(self, location_id, suppress_debug=True, show_window=False, verbose=False):
        """
        Initialize the XP farmer.

        Args:
            location_id: Route number (int) or dungeon key (str)
            suppress_debug: Whether to suppress mGBA debug output
            show_window: Whether to show live game window
            verbose: Enable verbose debug logging
        """
        self.location_id = location_id
        self.location_name = get_route_name(location_id)
        self.verbose = verbose

        # Get species for this location (for display purposes)
        base_species = get_route_species(location_id)
        if not base_species:
            raise ValueError(f"Unknown location: {location_id}")

        # Set up logging
        self.log_dir = PROJECT_ROOT / "logs"
        location_slug = str(location_id).replace(" ", "_").lower()
        self.log_manager = LogManager(self.log_dir, f"xp_{location_slug}")

        # Initialize base emulator
        super().__init__(
            rom_path=ROM_PATH,
            suppress_debug=suppress_debug,
            show_window=show_window,
            window_name=f"XP Farmer - {self.location_name}"
        )

        # Run a few frames to populate the buffer
        for _ in range(10):
            self.core.run_frame()

        # State tracking
        self.last_battle_pv = None
        self.last_direction = None
        self.current_state = BattleState.OVERWORLD
        self.handled_moves_this_battle = set()  # Track move IDs handled in current battle
        
        # Memory location for gMain (auto-detected)
        self.g_main_addr = None
        self.battle_cb2 = None
        self.overworld_cb2 = None

        # Statistics
        self.battles_completed = 0
        self.pokemon_fled_count = 0
        self.evolutions_count = 0
        self.moves_declined_count = 0
        self.start_time = time.time()

        # Find gMain address
        self.g_main_addr = self.find_gmain_candidate()
        if self.g_main_addr:
            print(f"[*] Found gMain candidate at 0x{self.g_main_addr:08X}")
        else:
            print("[!] Could not find gMain address (some features limited)")

        # Print startup info
        print(f"[*] XP Farmer - Pokemon Emerald")
        print(f"[*] Logging to: {self.log_manager.get_log_path()}")
        print(f"[*] Loaded ROM: {ROM_PATH}")
        print(f"[*] Location: {self.location_name}")
        print(f"[*] Verbose logging: {'Enabled' if verbose else 'Disabled'}")
        species_list = ', '.join(sorted(set(base_species.values())))
        print(f"[*] Available Pokemon: {species_list}")
        print(f"[*] Starting XP farming...\n")

    def cleanup(self):
        """Clean up resources."""
        super().cleanup()
        if hasattr(self, 'log_manager'):
            self.log_manager.cleanup()

    def debug_log(self, message, level="INFO"):
        """Log debug message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_msg = f"[{timestamp}] [{level}] {message}"

        # LogManager redirects stdout to both console and file
        # So we just print, but only if verbose or it's a warning/error
        if self.verbose or level in ("WARN", "ERROR"):
            print(log_msg)

    # =========================================================================
    # State Detection Methods (Memory-Based)
    # =========================================================================

    def find_gmain_candidate(self):
        """Scan IWRAM for gMain struct signature (two function pointers)."""
        # Scan 0x03000000 - 0x03006000 (common area for globals)
        # We look for two consecutive values that look like ROM pointers (0x08xxxxxx)
        # gMain is usually one of the first globals.
        for addr in range(0x03000000, 0x03006000, 4):
            val1 = self.read_memory_u32(addr)
            if 0x08000000 <= val1 <= 0x08FFFFFF:
                val2 = self.read_memory_u32(addr + 4)
                if 0x08000000 <= val2 <= 0x08FFFFFF:
                    return addr
        return None

    def read_callback2(self):
        """Read the current main callback function address."""
        if not self.g_main_addr:
            return 0
        return self.read_memory_u32(self.g_main_addr + 4)

    def is_in_battle(self):
        """Check if currently in battle using gBattleTypeFlags."""
        battle_flags = self.read_memory_u32(G_BATTLE_TYPE_FLAGS)
        return battle_flags != 0

    def get_battle_outcome(self):
        """Read gBattleOutcome to detect battle end state."""
        return self.read_memory_u8(G_BATTLE_OUTCOME)

    def get_enemy_hp(self):
        """Read current enemy HP from battle structure."""
        hp_addr = G_ENEMY_BATTLE_MON + BATTLE_MON_HP_OFFSET
        return self.read_memory_u16(hp_addr)

    def get_enemy_max_hp(self):
        """Read enemy max HP from battle structure."""
        hp_addr = G_ENEMY_BATTLE_MON + BATTLE_MON_MAX_HP_OFFSET
        return self.read_memory_u16(hp_addr)

    def is_enemy_fainted(self):
        """Check if enemy HP is 0."""
        return self.get_enemy_hp() == 0

    def is_move_learning_prompt(self):
        """Detect move learning dialog state."""
        move_to_learn = self.read_memory_u16(G_MOVE_TO_LEARN)
        return move_to_learn != 0

    def check_battle_ended_early(self):
        """
        Check if wild Pokemon fled or teleported.
        Returns True if battle ended via flee/teleport.
        """
        outcome = self.get_battle_outcome()
        return outcome in (BATTLE_OUTCOME_MON_FLED, BATTLE_OUTCOME_PLAYER_TELEPORTED)

    # =========================================================================
    # Action Methods
    # =========================================================================

    def loading_sequence(self, verbose=False):
        """Execute the loading sequence: Press A 15 times with 20-frame delay."""
        if verbose:
            self.debug_log(f"Pressing {A_PRESSES_LOADING} A buttons (loading screens)")

        for i in range(A_PRESSES_LOADING):
            self.press_a(hold_frames=5, release_frames=5)
            self.run_frames(A_LOADING_DELAY_FRAMES)

        if verbose:
            self.debug_log("Loading sequence complete")

    def encounter_sequence(self, max_turns=1000, timeout_seconds=60):
        """
        Turn in place to trigger wild encounters.
        Returns True if encounter found, False if timeout.
        """
        self.debug_log("Seeking encounter - turning in place")
        self.current_state = BattleState.SEEKING_ENCOUNTER

        # Capture Overworld CB2 if known
        if not self.overworld_cb2:
            self.overworld_cb2 = self.read_callback2()
            if self.overworld_cb2:
                self.debug_log(f"Overworld CB2: 0x{self.overworld_cb2:08X}")

        # Clear all keys before starting
        self.set_keys(KEY_NONE)
        self.run_frames(10)

        turn_count = 0
        start_with_right = (self.last_direction == 'left')
        sequence_start = time.time()

        while turn_count < max_turns:
            # Timeout check
            if time.time() - sequence_start > timeout_seconds:
                self.debug_log(f"Encounter timeout after {timeout_seconds}s", "WARN")
                return False

            if start_with_right:
                self.press_right(hold_frames=RIGHT_HOLD_FRAMES, release_frames=0)
                self.run_frames(RIGHT_WAIT_FRAMES)
                self.last_direction = 'right'

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    self.debug_log(f"Encounter found! (PV: 0x{pv:08X})")
                    return True

                self.press_left(hold_frames=LEFT_HOLD_FRAMES, release_frames=0)
                self.run_frames(LEFT_WAIT_FRAMES)
                self.last_direction = 'left'

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    self.debug_log(f"Encounter found! (PV: 0x{pv:08X})")
                    return True
            else:
                self.press_left(hold_frames=LEFT_HOLD_FRAMES, release_frames=0)
                self.run_frames(LEFT_WAIT_FRAMES)
                self.last_direction = 'left'

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    self.debug_log(f"Encounter found! (PV: 0x{pv:08X})")
                    return True

                self.press_right(hold_frames=RIGHT_HOLD_FRAMES, release_frames=0)
                self.run_frames(RIGHT_WAIT_FRAMES)
                self.last_direction = 'right'

                pv = self.read_memory_u32(ENEMY_PV_ADDR)
                if pv != 0 and pv != self.last_battle_pv:
                    self.debug_log(f"Encounter found! (PV: 0x{pv:08X})")
                    return True

            turn_count += 1

        self.debug_log(f"Max turns reached ({max_turns})", "WARN")
        return False

    def attack_sequence(self):
        """
        Navigate battle menu to use Move 1.
        Presses A to select FIGHT, then A to select Move 1.
        """
        self.debug_log("Using Move 1")

        # Wait for battle menu to be ready
        self.run_frames(30)

        # Select FIGHT (A button - FIGHT is default selected)
        self.press_a(hold_frames=10, release_frames=0)
        self.run_frames(30)

        # Select Move 1 (A button - Move 1 is default selected)
        self.press_a(hold_frames=10, release_frames=0)
        self.run_frames(20)

    def wait_for_turn_end(self, max_frames=2000):
        """
        Wait for turn to complete by polling battle state.
        Returns True if turn completed normally, False if timeout.
        """
        frames_waited = 0

        while frames_waited < max_frames:
            self.run_frames(30)
            frames_waited += 30

            # Check if enemy fainted
            if self.is_enemy_fainted():
                self.debug_log("Enemy fainted during turn")
                return True

            # Check if battle ended early (flee/teleport)
            if self.check_battle_ended_early():
                self.debug_log("Battle ended early (flee/teleport)")
                return True

            # Check if we're back at battle menu (simple heuristic)
            # In real battles, we'd be back at menu after ~300-600 frames
            if frames_waited >= 600:
                # Assume we're back at menu
                return True

        self.debug_log("Turn wait timeout", "WARN")
        return False

    def run_frames_with_watchdog(self, frames, check_move_learning=True):
        """
        Run frames while continuously checking for move learning.
        Returns True if move learning was detected, False otherwise.
        """
        frames_run = 0
        while frames_run < frames:
            # Run small chunks at a time
            chunk = min(5, frames - frames_run)
            for _ in range(chunk):
                self.core.run_frame()
            frames_run += chunk

            # Check for move learning after each chunk
            if check_move_learning and self.read_memory_u16(G_MOVE_TO_LEARN) != 0:
                return True
        return False

    def skip_move_learning(self):
        """
        Decline learning a new move. Handles multiple scenarios:

        Universal Sequence (works for both normal and stuck states):
        1. Press B:
           - If at "Teach [Move]?": Declines -> Goes to "Stop learning?"
           - If at "Forget which move?" (Accidental A): Exits -> Goes to "Stop learning?"
           - If at "Stop learning?": selects "No" -> Goes back to "Forget which move?" (Risk!)
             *Wait, if we are at "Stop learning?", B acts as "No". So we must follow B with A.*

        2. Press UP + A:
           - Ensures "Yes" is selected on "Stop learning?" screen.
           - Confirms "Yes" -> Goes to "Did not learn [Move]" text.

        3. Press A:
           - Clears "Did not learn" text -> Done.

        Returns:
            True if flag cleared successfully, False if stuck.
        """
        move_to_learn = self.read_memory_u16(G_MOVE_TO_LEARN)
        if move_to_learn == 0:
            return True

        # Check if we already handled this move ID in this battle
        if move_to_learn in self.handled_moves_this_battle:
            self.debug_log(f"Ignoring stuck move learning flag (Move ID: {move_to_learn} already handled)")
            # Return True so the caller thinks it's handled and doesn't panic
            return True

        self.debug_log(f"Move learning prompt detected (move ID: {move_to_learn})")
        self.current_state = BattleState.MOVE_LEARNING

        # Try the sequence fewer times to avoid blocking evolution
        # 2 attempts is enough to catch missed inputs without spamming for 10s
        for attempt in range(2):
            # Critical check: if battle ended while we are trying to skip, STOP.
            # This prevents B spam during evolution transition.
            if not self.is_in_battle():
                self.debug_log("Battle ended during move skip - aborting")
                return True

            self.debug_log(f"Skip move learning attempt {attempt + 1}")

            # Step 1: Press B to decline or exit move list
            # Hold longer to ensure registration
            self.press_b(hold_frames=10, release_frames=0)
            
            # Wait for dialog transition (B -> Yes/No prompt takes a moment)
            self.run_frames(60)

            # Check if cleared (unlikely here, but possible)
            if self.read_memory_u16(G_MOVE_TO_LEARN) == 0:
                self.debug_log("Flag cleared after B press")
                self.moves_declined_count += 1
                self.handled_moves_this_battle.add(move_to_learn)
                return True

            # Step 2: Press UP to ensure "Yes" is selected, then A to confirm
            self.press_up(hold_frames=5, release_frames=5)
            self.press_a(hold_frames=10, release_frames=0)
            
            # Wait for text to print "Did not learn..."
            self.run_frames(80)

            if self.read_memory_u16(G_MOVE_TO_LEARN) == 0:
                self.debug_log("Flag cleared after UP+A press")
                self.moves_declined_count += 1
                self.handled_moves_this_battle.add(move_to_learn)
                return True

            # Step 3: Press A to clear "Did not learn" text
            self.press_a(hold_frames=10, release_frames=0)
            
            # Wait for text to clear and flag to reset
            self.run_frames(80)

            if self.read_memory_u16(G_MOVE_TO_LEARN) == 0:
                self.debug_log("Flag cleared after second A press")
                self.moves_declined_count += 1
                self.handled_moves_this_battle.add(move_to_learn)
                return True

        # If we get here, the flag didn't clear after attempts.
        # It's likely stuck/sticky (phantom flag).
        # To prevent this from haunting us in the NEXT battle, we FORCE CLEAR it.
        self.debug_log(f"Flag persistent for move {move_to_learn} - forcing clear in memory", "WARN")
        
        # Force write 0 to the address to clear the phantom flag
        try:
            self.write_memory_u16(G_MOVE_TO_LEARN, 0)
            self.debug_log("Forced memory clear successful")
        except Exception as e:
            self.debug_log(f"Failed to force clear memory: {e}", "ERROR")

        self.handled_moves_this_battle.add(move_to_learn)
        # Return True because we manually "handled" (deleted) it
        return True

    def handle_evolution(self):
        """
        Handle evolution sequence.
        Wait for evolution to complete, then handle any move learning.
        """
        self.debug_log("Evolution detected - waiting for completion")
        self.current_state = BattleState.EVOLUTION

        # Evolution animation takes ~10-15 seconds
        # Poll every second for up to 20 seconds
        for i in range(20):
            self.run_frames(60)  # 1 second

            # Check if we're back in overworld or battle ended
            # (Simple check: battle flags should be 0 after evolution)
            if not self.is_in_battle():
                self.debug_log("Evolution complete (returned to overworld)")
                break

        # Clear any remaining dialog with A button spam
        for _ in range(10):
            self.press_a(hold_frames=10, release_frames=0)
            self.run_frames(30)

        # Check for move learning after evolution
        if self.is_move_learning_prompt():
            self.skip_move_learning()

        self.evolutions_count += 1
        self.debug_log("Evolution handling complete")

    def safe_advance_text(self, max_frames=60):
        """
        Advance text with A, but abort immediately if move learning is detected.
        Uses frame-by-frame checking to catch move learning ASAP.
        Returns True if move learning was detected, False otherwise.
        """
        # Press A
        self.set_keys(KEY_A)
        for _ in range(10):  # Hold A for 10 frames
            self.core.run_frame()
            if self.read_memory_u16(G_MOVE_TO_LEARN) != 0:
                self.set_keys(KEY_NONE)
                return True
        self.set_keys(KEY_NONE)

        # Wait for text to advance, checking every frame
        for _ in range(max_frames - 10):
            self.core.run_frame()
            if self.read_memory_u16(G_MOVE_TO_LEARN) != 0:
                return True
        return False

    def handle_battle_end(self):
        """
        Process battle end sequence (XP gain, level up text).
        Uses frame-by-frame watchdog to catch move learning immediately.
        Returns True if sequence completed cleanly, False if move learning stuck.
        """
        self.debug_log("Handling battle end sequence")
        self.current_state = BattleState.BATTLE_END
        move_learning_stuck = False

        # Wait for victory/XP screen, checking every frame for move learning
        for _ in range(120):
            self.core.run_frame()
            # If battle finished early (switched to evolution/overworld), stop waiting
            if not self.is_in_battle():
                break
                
            if self.read_memory_u16(G_MOVE_TO_LEARN) != 0:
                self.debug_log("Move learning detected during victory wait!")
                if not self.skip_move_learning():
                    move_learning_stuck = True
                break

        # Clear battle end text carefully with watchdog
        if not move_learning_stuck:
            for i in range(40):
                # 1. Critical Check: Are we still in battle?
                # If battle flags are cleared, we might be transitioning to Evolution.
                if not self.is_in_battle():
                    self.debug_log("Returned to overworld (battle flags cleared) - ending sequence")
                    break

                # 1b. Check CB2 (stronger check)
                # If the main callback changed (e.g. to Overworld or Evolution), we are done.
                current_cb2 = self.read_callback2()
                if self.battle_cb2 and current_cb2 != 0 and current_cb2 != self.battle_cb2:
                    self.debug_log(f"CB2 changed (0x{self.battle_cb2:08X} -> 0x{current_cb2:08X}) - battle ended")
                    break

                # 2. Check move learning
                if self.read_memory_u16(G_MOVE_TO_LEARN) != 0:
                    self.debug_log("Move learning detected!")
                    if not self.skip_move_learning():
                        move_learning_stuck = True
                    break

                # 3. Safe advance with frame-by-frame monitoring
                # We need to be careful: if safe_advance_text returns True,
                # it implies move learning flag was seen.
                # But we should verify we are still in battle before acting on it.
                if self.safe_advance_text(max_frames=40):
                    if not self.is_in_battle():
                        self.debug_log("Move learning flag seen, but battle ended (ignoring)")
                        break
                        
                    self.debug_log("Move learning caught during text advance!")
                    if not self.skip_move_learning():
                        move_learning_stuck = True
                    break

                # Debug log every 10 iterations
                if i > 0 and i % 10 == 0:
                    battle_flags = self.read_memory_u32(G_BATTLE_TYPE_FLAGS)
                    self.debug_log(f"Still clearing battle end text (iteration {i}, battle_flags=0x{battle_flags:08X})")

        # Store this battle's PV for next encounter
        self.last_battle_pv = self.read_memory_u32(ENEMY_PV_ADDR)
        return not move_learning_stuck

    def heal_after_battle(self):
        """Heal party using healer.py utilities."""
        self.debug_log("Healing party (HP and PP)")
        try:
            heal_party(self.core)
            self.debug_log("Party healed successfully")
        except Exception as e:
            self.debug_log(f"Healing error: {e}", "ERROR")

    # =========================================================================
    # Main Farming Loop
    # =========================================================================

    def farm(self, max_battles=None):
        """
        Main XP farming loop.

        Args:
            max_battles: Maximum number of battles to run (None = unlimited)

        Returns:
            True if farming completed successfully
        """
        # Initial setup
        self.debug_log("Initializing - loading save")
        if not self.reset_to_save():
            self.debug_log("Failed to reset to save", "ERROR")
            return False

        self.loading_sequence(verbose=True)
        self.debug_log("Ready to farm XP")

        # Main farming loop
        while max_battles is None or self.battles_completed < max_battles:
            try:
                battle_num = self.battles_completed + 1
                print(f"\n{'='*60}")
                print(f"Battle #{battle_num}")
                print(f"{'='*60}")

                # 1. Find encounter
                self.debug_log(f"Battle {battle_num}: Seeking encounter")
                self.handled_moves_this_battle.clear()  # Reset handled moves for new battle
                if not self.encounter_sequence():
                    self.debug_log("No encounter found, resetting", "WARN")
                    self.reset_to_save()
                    self.loading_sequence()
                    continue

                # 2. Wait for battle intro animation
                self.current_state = BattleState.BATTLE_INTRO
                self.debug_log("Battle starting - waiting for intro")
                self.run_frames(400)  # Wait for "Wild X appeared!" and shiny animation

                # Skip initial text
                for _ in range(3):
                    self.press_a(hold_frames=10, release_frames=0)
                    self.run_frames(40)

                # 3. Battle loop - attack until enemy faints or flees
                self.current_state = BattleState.BATTLE_ACTIVE
                
                # Capture the Battle Callback function address
                # This helps us detect when the battle TRULY ends (even if flags are stuck)
                self.battle_cb2 = self.read_callback2()
                if self.battle_cb2:
                    self.debug_log(f"Battle CB2: 0x{self.battle_cb2:08X}")
                
                turn_count = 0
                max_turns = 50  # Safety limit

                while turn_count < max_turns:
                    turn_count += 1

                    # Check for early battle end (flee/teleport)
                    if self.check_battle_ended_early():
                        outcome = self.get_battle_outcome()
                        self.debug_log(f"Enemy escaped (outcome: {outcome})")
                        self.pokemon_fled_count += 1
                        break

                    # Check if enemy fainted
                    if self.is_in_battle():
                        enemy_hp = self.get_enemy_hp()
                        enemy_max_hp = self.get_enemy_max_hp()

                        if enemy_hp == 0:
                            self.debug_log("Enemy fainted!")
                            break

                        self.debug_log(f"Turn {turn_count}: Enemy HP {enemy_hp}/{enemy_max_hp}")
                    else:
                        # Battle ended
                        self.debug_log("Battle ended (no longer in battle)")
                        break

                    # Use Move 1
                    self.attack_sequence()

                    # Wait for turn to complete
                    self.wait_for_turn_end()

                    # Check for move learning (can happen mid-battle on level up)
                    if self.is_move_learning_prompt():
                        self.skip_move_learning()

                # 4. Handle battle end
                move_learning_stuck = False
                if not self.check_battle_ended_early():
                    if not self.handle_battle_end():
                        move_learning_stuck = True
                        self.debug_log("Warning: Exiting battle end with stuck move learning flag", "WARN")

                # 5. Check for evolution (happens after battle in overworld)
                # Use watchdog approach - check every frame for move learning
                self.debug_log("Checking for post-battle evolution")

                evolution_detected = False
                
                # Wait until we return to Overworld (CB2 == overworld_cb2)
                # This handles the long evolution animation (10-15s) correctly.
                # If gMain wasn't found (cb2=0), fallback to 30s timeout.
                timeout_frames = 3600  # 60 seconds (increased for safety)
                
                for i in range(timeout_frames):
                    self.core.run_frame()

                    # Check if we are back in Overworld
                    curr_cb2 = self.read_callback2()
                    
                    # If we suspect evolution (stuck flag), enforce a grace period (e.g. 5s)
                    # to allow the game to transition Battle -> Overworld -> Evolution.
                    # Otherwise we might exit immediately if the game briefly touches Overworld state.
                    min_frames_if_stuck = 300 # 5 seconds
                    can_exit = not move_learning_stuck or i > min_frames_if_stuck

                    if can_exit and self.overworld_cb2 and curr_cb2 == self.overworld_cb2:
                        self.debug_log("Returned to Overworld (CB2 matched)")
                        break
                    
                    # If we don't know overworld CB2, fallback to shorter wait (original behavior)
                    if not self.overworld_cb2 and i > 200:
                        break

                    # Check for move learning every frame
                    curr_move_id = self.read_memory_u16(G_MOVE_TO_LEARN)
                    if curr_move_id != 0:
                        # If this is a NEW move we haven't seen/handled yet, handle it immediately!
                        if curr_move_id not in self.handled_moves_this_battle:
                            self.debug_log(f"New move detected during evolution (ID: {curr_move_id})")
                            evolution_detected = True
                            if not self.skip_move_learning():
                                move_learning_stuck = True
                        
                        # If it's the old sticky move, just log and wait
                        elif move_learning_stuck:
                            if i % 60 == 0:
                                self.debug_log("Ignoring stuck move learning flag (likely evolution pending)")
                                evolution_detected = True

                    # Every 30 frames (~0.5 sec), press A to advance evolution/text
                    # BUT ONLY if we aren't seeing a NEW move prompt
                    if i > 0 and i % 30 == 0:
                        self.set_keys(KEY_A)
                        for _ in range(5):
                            self.core.run_frame()
                            
                            # Safety Check: Did a NEW move appear while we were pressing A?
                            check_move_id = self.read_memory_u16(G_MOVE_TO_LEARN)
                            if check_move_id != 0 and check_move_id not in self.handled_moves_this_battle:
                                self.set_keys(KEY_NONE)
                                self.debug_log(f"New move caught during A press (ID: {check_move_id})")
                                evolution_detected = True
                                self.skip_move_learning()
                                break
                                
                        self.set_keys(KEY_NONE)

                if evolution_detected:
                    self.evolutions_count += 1
                    self.debug_log("Evolution sequence completed")
                else:
                    self.debug_log("No evolution detected")

                # 6. Heal party
                self.current_state = BattleState.POST_BATTLE
                self.heal_after_battle()

                # 7. Update statistics
                self.battles_completed += 1
                elapsed = time.time() - self.start_time
                battles_per_hour = (self.battles_completed / elapsed) * 3600 if elapsed > 0 else 0

                print(f"\n[+] Battle #{battle_num} complete!")
                print(f"    Total battles: {self.battles_completed}")
                print(f"    Pokemon fled: {self.pokemon_fled_count}")
                print(f"    Evolutions: {self.evolutions_count}")
                print(f"    Moves declined: {self.moves_declined_count}")
                print(f"    Rate: {battles_per_hour:.1f} battles/hour")

                # Reset state for next encounter
                self.current_state = BattleState.OVERWORLD

            except KeyboardInterrupt:
                print("\n[!] Interrupted by user")
                break
            except Exception as e:
                self.debug_log(f"Error in battle loop: {e}", "ERROR")
                # Try to recover
                self.reset_to_save()
                self.loading_sequence()

        # Final statistics
        elapsed = time.time() - self.start_time
        print(f"\n{'='*60}")
        print(f"XP Farming Complete!")
        print(f"{'='*60}")
        print(f"Total battles: {self.battles_completed}")
        print(f"Total time: {elapsed/60:.1f} minutes")
        print(f"Pokemon fled: {self.pokemon_fled_count}")
        print(f"Evolutions: {self.evolutions_count}")
        print(f"Moves declined: {self.moves_declined_count}")
        print(f"Average: {(elapsed/self.battles_completed)/60:.2f} min/battle" if self.battles_completed > 0 else "N/A")

        return True


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Main entry point for XP farming script."""
    parser = argparse.ArgumentParser(
        description="Pokemon Emerald XP Farmer - Automated battle training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 src/battle.py --route 101
  python3 src/battle.py --route 116 --max-battles 100 --verbose
  python3 src/battle.py --location granite_cave --show-window
  python3 src/battle.py --list-routes
        """
    )

    # Location arguments (same as hunt.py)
    location_group = parser.add_mutually_exclusive_group(required=True)
    location_group.add_argument('--route', '-r', type=int,
                                help='Route number to farm (e.g., 101, 116)')
    location_group.add_argument('--location', '-l', type=str,
                                help='Dungeon/location key to farm (e.g., granite_cave)')
    location_group.add_argument('--list-routes', action='store_true',
                                help='List all available routes and dungeons')

    # Farming options
    parser.add_argument('--max-battles', '-n', type=int, default=None,
                        help='Maximum battles to run (default: unlimited)')
    parser.add_argument('--show-window', '-w', action='store_true',
                        help='Show live game window')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose debug output')

    args = parser.parse_args()

    # Handle --list-routes
    if args.list_routes:
        print("Available Routes:")
        for route_id in sorted(get_available_routes()):
            route_name = get_route_name(route_id)
            species = get_route_species(route_id)
            species_list = ', '.join(sorted(set(species.values())))
            print(f"  Route {route_id}: {route_name}")
            print(f"    Pokemon: {species_list}")

        print("\nAvailable Dungeons/Locations:")
        for dungeon_key in sorted(get_available_dungeons()):
            dungeon_name = get_route_name(dungeon_key)
            species = get_route_species(dungeon_key)
            species_list = ', '.join(sorted(set(species.values())))
            print(f"  {dungeon_key}: {dungeon_name}")
            print(f"    Pokemon: {species_list}")
        return

    # Determine location ID
    location_id = args.route if args.route else args.location

    # Create and run farmer
    try:
        farmer = XPFarmer(
            location_id=location_id,
            suppress_debug=True,
            show_window=args.show_window,
            verbose=args.verbose
        )

        try:
            farmer.farm(max_battles=args.max_battles)
        finally:
            farmer.cleanup()

    except ValueError as e:
        print(f"[!] Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
