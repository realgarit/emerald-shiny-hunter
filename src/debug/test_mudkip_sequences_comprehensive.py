#!/usr/bin/env python3
"""
Comprehensive test script to find the optimal button sequence for selecting Mudkip
Tests multiple sequences with different parameters and runs each multiple times for reliability.

Goals:
- Eliminate "No Pokemon found" errors
- Avoid mistakenly selecting Torchic
- Find the most reliable sequence
"""

import mgba.core
from pathlib import Path
from collections import defaultdict
import time
import os
import sys
import random

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")

# Memory addresses
PARTY_PV_ADDR = 0x020244EC  # Personality Value
PARTY_TID_ADDR = 0x020244F0  # Trainer ID

# Pokemon species IDs (Gen III battle structure IDs)
POKEMON_SPECIES = {
    277: "Treecko",
    280: "Torchic",
    283: "Mudkip",
}

# Button constants (GBA button bits)
KEY_A = 1      # bit 0
KEY_RIGHT = 16  # bit 4

def read_u32(core, address):
    """Read 32-bit unsigned integer from memory"""
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    b2 = core._core.busRead8(core._core, address + 2)
    b3 = core._core.busRead8(core._core, address + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

def read_u16(core, address):
    """Read 16-bit unsigned integer from memory"""
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    return b0 | (b1 << 8)

def get_substructure_order(pv):
    """Get the order of substructures based on PV"""
    order_index = pv % 24
    orders = [
        "GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA",
        "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG",
        "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG",
        "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG"
    ]
    return orders[order_index]

def decrypt_party_species(core, pv_addr, tid_addr):
    """Decrypt and extract species ID from encrypted party data"""
    try:
        pv = read_u32(core, pv_addr)
        tid = read_u16(core, tid_addr)
        
        data_start = pv_addr + 32
        order = get_substructure_order(pv)
        growth_pos = order.index('G')
        offset = growth_pos * 12
        
        encrypted_val = read_u32(core, data_start + offset)
        xor_key = (tid & 0xFFFF) ^ pv
        decrypted_val = encrypted_val ^ xor_key
        species_id = decrypted_val & 0xFFFF
        
        return species_id
    except Exception as e:
        return 0

def press_button(core, button, hold=5, release=5):
    """Press a button"""
    core._core.setKeys(core._core, button)
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def run_frames(core, n):
    """Advance emulation by n frames"""
    for _ in range(n):
        core.run_frame()

def test_sequence(core, a_dialogue, wait_bag, right_presses, wait_after_right, a_select, 
                  a_delay=15, right_delay=15, a_select_delay=15, max_retry_a=10, verbose=False):
    """Test a specific button sequence with configurable delays
    
    Args:
        a_dialogue: Number of A presses for dialogue
        wait_bag: Frames to wait for bag screen
        right_presses: Number of Right button presses
        wait_after_right: Frames to wait after Right presses
        a_select: Number of A presses to select
        a_delay: Frames to wait between A presses in dialogue
        right_delay: Frames to wait after each Right press
        a_select_delay: Frames to wait between A presses when selecting
        max_retry_a: Maximum additional A presses if Pokemon not found
        verbose: Print detailed progress
    
    Returns:
        (found, species_id, species_name, presses_needed)
    """
    # Reset and load save
    core.reset()
    core.autoload_save()
    run_frames(core, 60)  # Wait 1 second for save to load
    
    # RNG manipulation (same as in actual hunt)
    RNG_ADDR = 0x03005D80
    random_seed = random.randint(0, 0xFFFFFFFF)
    random_delay = random.randint(10, 100)
    run_frames(core, random_delay)
    core._core.busWrite32(core._core, RNG_ADDR, random_seed)
    run_frames(core, random.randint(5, 20))
    
    if verbose:
        print(f"    Sequence: {a_dialogue}A -> wait{wait_bag/60:.1f}s -> {right_presses}xRight -> wait{wait_after_right/60:.1f}s -> {a_select}A (RNG: 0x{random_seed:08X}, delay: {random_delay})")
    
    # Step 1: A presses for dialogue (with configurable delay)
    for i in range(a_dialogue):
        press_button(core, KEY_A, hold=5, release=5)
        run_frames(core, a_delay)  # Configurable delay between presses
    
    # Step 2: Wait for bag screen
    run_frames(core, wait_bag)
    
    # Step 3: Press Right (with configurable delay)
    for _ in range(right_presses):
        press_button(core, KEY_RIGHT, hold=5, release=5)
        run_frames(core, right_delay)  # Configurable delay after each Right
    
    # Step 4: Wait after Right
    run_frames(core, wait_after_right)
    
    # Step 5: Press A to select (with configurable delay)
    pokemon_found = False
    presses_needed = 0
    
    for i in range(a_select):
        press_button(core, KEY_A, hold=5, release=5)
        run_frames(core, a_select_delay)  # Configurable delay between presses
        
        # Check if Pokemon found
        pv = read_u32(core, PARTY_PV_ADDR)
        if pv != 0:
            pokemon_found = True
            presses_needed = i + 1
            break
    
    # Retry with additional A presses if not found
    if not pokemon_found:
        for i in range(max_retry_a):
            press_button(core, KEY_A, hold=5, release=5)
            run_frames(core, 30)  # Longer delay for retries (0.5s)
            
            pv = read_u32(core, PARTY_PV_ADDR)
            if pv != 0:
                pokemon_found = True
                presses_needed = a_select + i + 1
                break
    
    # Final check after additional wait
    if not pokemon_found:
        run_frames(core, 90)  # Wait 1.5s
        pv = read_u32(core, PARTY_PV_ADDR)
        if pv != 0:
            pokemon_found = True
            presses_needed = a_select + max_retry_a
    
    # Get species if found
    species_id = 0
    species_name = "None"
    if pokemon_found:
        run_frames(core, 60)  # Wait for data to settle
        species_id = decrypt_party_species(core, PARTY_PV_ADDR, PARTY_TID_ADDR)
        species_name = POKEMON_SPECIES.get(species_id, f"Unknown({species_id})")
    
    return pokemon_found, species_id, species_name, presses_needed

def run_test_suite(core, test_cases, runs_per_test=5):
    """Run a suite of tests and collect statistics"""
    results = []
    
    total_tests = len(test_cases) * runs_per_test
    current_test = 0
    
    for test_idx, test_case in enumerate(test_cases, 1):
        # Support both old format (5 params) and new format (8 params with delays)
        if len(test_case) == 5:
            a_dialogue, wait_bag, right_presses, wait_after_right, a_select = test_case
            a_delay, right_delay, a_select_delay = 15, 15, 15  # Default delays
        else:
            a_dialogue, wait_bag, right_presses, wait_after_right, a_select, a_delay, right_delay, a_select_delay = test_case
        
        print(f"\n[Test {test_idx}/{len(test_cases)}] Testing sequence:")
        print(f"  {a_dialogue}A (delay {a_delay}) -> wait{wait_bag/60:.1f}s -> {right_presses}xRight (delay {right_delay}) -> wait{wait_after_right/60:.1f}s -> {a_select}A (delay {a_select_delay})")
        
        stats = {
            'mudkip': 0,
            'torchic': 0,
            'treecko': 0,
            'none': 0,
            'total_presses': []
        }
        
        for run in range(runs_per_test):
            current_test += 1
            if current_test % 5 == 0:
                print(f"    Run {run+1}/{runs_per_test}...", end='', flush=True)
            
            found, species_id, species_name, presses = test_sequence(
                core, a_dialogue, wait_bag, right_presses, wait_after_right, a_select,
                a_delay=a_delay, right_delay=right_delay, a_select_delay=a_select_delay,
                verbose=(run == 0)  # Only verbose for first run
            )
            
            if not found:
                stats['none'] += 1
            elif species_id == 283:
                stats['mudkip'] += 1
                stats['total_presses'].append(presses)
            elif species_id == 280:
                stats['torchic'] += 1
            elif species_id == 277:
                stats['treecko'] += 1
            
            # Small delay between runs
            time.sleep(0.1)
        
        if current_test % 5 == 0:
            print()  # Newline after progress
        
        # Calculate success rate
        mudkip_rate = stats['mudkip'] / runs_per_test * 100
        error_rate = (stats['none'] + stats['torchic'] + stats['treecko']) / runs_per_test * 100
        avg_presses = sum(stats['total_presses']) / len(stats['total_presses']) if stats['total_presses'] else 0
        
        result = {
            'sequence': (a_dialogue, wait_bag, right_presses, wait_after_right, a_select, a_delay, right_delay, a_select_delay),
            'stats': stats,
            'mudkip_rate': mudkip_rate,
            'error_rate': error_rate,
            'avg_presses': avg_presses
        }
        results.append(result)
        
        print(f"  Results: Mudkip={stats['mudkip']}/{runs_per_test} ({mudkip_rate:.0f}%), "
              f"Torchic={stats['torchic']}, Treecko={stats['treecko']}, None={stats['none']}")
        if stats['total_presses']:
            print(f"  Avg presses needed: {avg_presses:.1f}")
    
    return results

def main():
    # Suppress GBA debug output
    original_stderr = sys.stderr
    null_file = open(os.devnull, 'w')
    sys.stderr = null_file
    
    try:
        print("=" * 80)
        print("Comprehensive Mudkip Selection Sequence Tester")
        print("=" * 80)
        print(f"\n[*] Loading ROM: {ROM_PATH}")
        
        core = mgba.core.load_path(ROM_PATH)
        if not core:
            raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")
        
        print("[*] Testing sequences with multiple runs each for reliability...\n")
        
        # Define comprehensive test cases WITH RNG manipulation
        # Format: (A_dialogue, wait_bag_frames, right_presses, wait_after_right_frames, A_select, A_delay, Right_delay, A_select_delay)
        # Or old format: (A_dialogue, wait_bag_frames, right_presses, wait_after_right_frames, A_select) - uses default delays
        test_cases = []
        
        # First, test the best sequences from before with increased delays
        base_sequences = [
            (19, 30, 1, 12, 6),   # Best from previous test
            (19, 30, 2, 12, 6),   # Best with 2x Right
            (18, 30, 1, 12, 6),   # Try 18 A
            (18, 30, 2, 12, 6),   # 18 A with 2x Right
        ]
        
        # Test each base sequence with different delay combinations
        delay_combos = [
            (15, 15, 15),   # Default
            (20, 20, 20),   # Slightly longer
            (30, 30, 30),   # Longer delays
            (15, 30, 30),   # Longer after Right and select
            (20, 30, 30),   # Even longer
            (30, 30, 45),   # Very long select delay
            (20, 45, 45),   # Very long Right and select delays
        ]
        
        for seq in base_sequences:
            for a_delay, right_delay, a_select_delay in delay_combos:
                test_cases.append(seq + (a_delay, right_delay, a_select_delay))
        
        # Add more comprehensive combinations to find 100% success
        promising_sequences = [
            # Best from previous test: 19A with 2xRight and delays
            (19, 30, 2, 12, 6, 15, 30, 30),   # Best so far (70%)
            (19, 30, 2, 18, 6, 15, 30, 30),   # Longer wait after Right
            (19, 30, 2, 24, 6, 15, 30, 30),   # Even longer wait
            (19, 30, 2, 12, 8, 15, 30, 30),   # More A presses
            (19, 30, 2, 18, 8, 15, 30, 30),   # Both longer wait and more A
            (19, 30, 2, 24, 8, 15, 30, 30),   # Maximum wait and more A
            
            # Try 17 A dialogue (even earlier to avoid Torchic)
            (17, 30, 2, 12, 6, 15, 30, 30),
            (17, 30, 2, 18, 6, 15, 30, 30),
            (17, 30, 2, 24, 6, 15, 30, 30),
            (17, 30, 2, 12, 8, 15, 30, 30),
            (17, 30, 2, 18, 8, 15, 30, 30),
            (17, 45, 2, 24, 8, 20, 35, 40),
            (17, 60, 2, 30, 10, 25, 40, 45),
            
            # Try 16 A dialogue (very early)
            (16, 30, 2, 12, 6, 15, 30, 30),
            (16, 30, 2, 18, 6, 15, 30, 30),
            (16, 30, 2, 24, 6, 15, 30, 30),
            (16, 45, 2, 24, 8, 20, 35, 40),
            (16, 60, 2, 30, 10, 25, 40, 45),
            
            # Try 15 A dialogue (very very early)
            (15, 30, 2, 12, 6, 15, 30, 30),
            (15, 30, 2, 18, 6, 15, 30, 30),
            (15, 30, 2, 24, 6, 15, 30, 30),
            (15, 45, 2, 24, 8, 20, 35, 40),
            (15, 60, 2, 30, 10, 25, 40, 45),
            
            # Try 14 A dialogue (extremely early)
            (14, 45, 2, 24, 8, 20, 35, 40),
            (14, 60, 2, 30, 10, 25, 40, 45),
            
            # Very conservative: Maximum waits and delays
            (17, 90, 2, 48, 12, 30, 45, 60),  # 1.5s bag, 0.8s after Right, very long delays
            (16, 90, 2, 48, 12, 30, 45, 60),
            (19, 90, 2, 48, 12, 30, 45, 60),
            
            # Extreme: Best patterns with maximum waits
            (18, 90, 2, 60, 12, 30, 45, 60),  # 18A with extreme waits
            (17, 90, 2, 60, 12, 30, 45, 60),  # 17A with extreme waits
            (18, 120, 2, 60, 15, 30, 45, 60), # 18A with 2s bag wait
            (17, 120, 2, 60, 15, 30, 45, 60), # 17A with 2s bag wait
        ]
        
        test_cases.extend(promising_sequences)
        
        # First pass: test all sequences with 10 runs
        print(f"[*] Testing {len(test_cases)} different sequences, {10} runs each (with RNG manipulation)")
        print(f"[*] Total: {len(test_cases) * 10} test runs\n")
        
        start_time = time.time()
        results = run_test_suite(core, test_cases, runs_per_test=10)
        
        # Second pass: test top sequences with 20 runs for better accuracy
        results.sort(key=lambda x: (-x['mudkip_rate'], x['error_rate']))
        top_sequences = [r for r in results[:5] if r['mudkip_rate'] >= 60]
        
        if top_sequences:
            print("\n" + "=" * 80)
            print("SECOND PASS: Testing Top Sequences with 20 Runs")
            print("=" * 80)
            top_test_cases = [r['sequence'] for r in top_sequences]
            top_results = run_test_suite(core, top_test_cases, runs_per_test=20)
            
            # Merge results - replace original with more accurate top results
            for top_result in top_results:
                for i, result in enumerate(results):
                    if result['sequence'] == top_result['sequence']:
                        results[i] = top_result
                        break
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 80)
        print("RESULTS SUMMARY")
        print("=" * 80)
        
        # Sort by mudkip success rate (descending), then by error rate (ascending)
        results.sort(key=lambda x: (-x['mudkip_rate'], x['error_rate']))
        
        # Show top 10 sequences
        print("\n[*] Top 10 Sequences (by Mudkip success rate):")
        print("-" * 80)
        print(f"{'Sequence':<50} {'Mudkip':<10} {'Errors':<10} {'Avg Presses':<12}")
        print("-" * 80)
        
        for i, result in enumerate(results[:10], 1):
            seq = result['sequence']
            if len(seq) == 8:
                a_d, w_b, r_p, w_ar, a_s, a_del, r_del, a_s_del = seq
                seq_str = f"{a_d}A(d{a_del}) -> {w_b/60:.1f}s -> {r_p}xR(d{r_del}) -> {w_ar/60:.1f}s -> {a_s}A(d{a_s_del})"
            else:
                a_d, w_b, r_p, w_ar, a_s = seq
                seq_str = f"{a_d}A -> {w_b/60:.1f}s -> {r_p}xR -> {w_ar/60:.1f}s -> {a_s}A"
            print(f"{i:2}. {seq_str:<55} {result['mudkip_rate']:>6.0f}%     "
                  f"{result['error_rate']:>6.0f}%     {result['avg_presses']:>6.1f}")
        
        # Find perfect sequences (100% Mudkip, 0% errors)
        perfect = [r for r in results if r['mudkip_rate'] == 100 and r['error_rate'] == 0]
        
        if perfect:
            print("\n" + "=" * 80)
            print("PERFECT SEQUENCES (100% Mudkip, 0% Errors)")
            print("=" * 80)
            for i, result in enumerate(perfect, 1):
                seq = result['sequence']
                stats = result['stats']
                if len(seq) == 8:
                    a_d, w_b, r_p, w_ar, a_s, a_del, r_del, a_s_del = seq
                    print(f"\n{i}. {a_d}A(delay {a_del}) -> wait{w_b/60:.1f}s -> {r_p}xRight(delay {r_del}) -> wait{w_ar/60:.1f}s -> {a_s}A(delay {a_s_del})")
                    print(f"   Success: {stats['mudkip']}/10 (100%)")
                    print(f"   Avg presses: {result['avg_presses']:.1f}")
                    print(f"   Total button presses: {a_d + r_p + a_s}")
                else:
                    a_d, w_b, r_p, w_ar, a_s = seq
                    print(f"\n{i}. {a_d}A -> wait{w_b/60:.1f}s -> {r_p}xRight -> wait{w_ar/60:.1f}s -> {a_s}A")
                    print(f"   Success: {stats['mudkip']}/10 (100%)")
                    print(f"   Avg presses: {result['avg_presses']:.1f}")
                    print(f"   Total button presses: {a_d + r_p + a_s}")
            
            # Recommend the fastest perfect sequence
            best = min(perfect, key=lambda x: x['sequence'][0] + x['sequence'][2] + x['sequence'][4])
            seq = best['sequence']
            if len(seq) == 8:
                a_d, w_b, r_p, w_ar, a_s, a_del, r_del, a_s_del = seq
                print("\n" + "=" * 80)
                print("RECOMMENDED SEQUENCE (Fastest Perfect)")
                print("=" * 80)
                print(f"A_PRESSES_DIALOGUE: {a_d}")
                print(f"A_PRESS_DELAY_FRAMES: {a_del}  # {a_del/60:.2f}s between A presses")
                print(f"WAIT_FOR_BAG_FRAMES: {int(w_b)}  # {w_b/60:.2f}s")
                print(f"RIGHT_PRESS_COUNT: {r_p}")
                print(f"RIGHT_PRESS_DELAY_FRAMES: {r_del}  # {r_del/60:.2f}s after each Right")
                print(f"WAIT_AFTER_RIGHT_FRAMES: {int(w_ar)}  # {w_ar/60:.2f}s")
                print(f"A_PRESSES_SELECT: {a_s}")
                print(f"A_SELECT_DELAY_FRAMES: {a_s_del}  # {a_s_del/60:.2f}s between A presses")
            else:
                a_d, w_b, r_p, w_ar, a_s = seq
                print("\n" + "=" * 80)
                print("RECOMMENDED SEQUENCE (Fastest Perfect)")
                print("=" * 80)
                print(f"A_PRESSES_DIALOGUE: {a_d}")
                print(f"WAIT_FOR_BAG_FRAMES: {int(w_b)}  # {w_b/60:.2f}s")
                print(f"RIGHT_PRESS_COUNT: {r_p}")
                print(f"WAIT_AFTER_RIGHT_FRAMES: {int(w_ar)}  # {w_ar/60:.2f}s")
                print(f"A_PRESSES_SELECT: {a_s}")
            print(f"\nTotal presses: {a_d + r_p + a_s}")
        else:
            print("\n[!] No perfect sequences found. Showing best options:")
            best = results[0]
            seq = best['sequence']
            if len(seq) == 8:
                a_d, w_b, r_p, w_ar, a_s, a_del, r_del, a_s_del = seq
                print(f"\nBest sequence: {a_d}A(delay {a_del}) -> wait{w_b/60:.1f}s -> {r_p}xRight(delay {r_del}) -> wait{w_ar/60:.1f}s -> {a_s}A(delay {a_s_del})")
            else:
                a_d, w_b, r_p, w_ar, a_s = seq
                print(f"\nBest sequence: {a_d}A -> wait{w_b/60:.1f}s -> {r_p}xRight -> wait{w_ar/60:.1f}s -> {a_s}A")
            print(f"Success rate: {best['mudkip_rate']:.0f}%")
            print(f"Error rate: {best['error_rate']:.0f}%")
        
        # Show sequences that got Torchic (to avoid)
        torchic_sequences = [r for r in results if r['stats']['torchic'] > 0]
        if torchic_sequences:
            print("\n" + "=" * 80)
            print("SEQUENCES THAT SELECTED TORCHIC (AVOID THESE)")
            print("=" * 80)
        for result in torchic_sequences[:5]:
            seq = result['sequence']
            if len(seq) == 8:
                a_d, w_b, r_p, w_ar, a_s, a_del, r_del, a_s_del = seq
                print(f"  {a_d}A(d{a_del}) -> {w_b/60:.1f}s -> {r_p}xR(d{r_del}) -> {w_ar/60:.1f}s -> {a_s}A(d{a_s_del}): "
                      f"Torchic={result['stats']['torchic']}/10")
            else:
                a_d, w_b, r_p, w_ar, a_s = seq
                print(f"  {a_d}A -> {w_b/60:.1f}s -> {r_p}xR -> {w_ar/60:.1f}s -> {a_s}A: "
                      f"Torchic={result['stats']['torchic']}/10")
        
        print(f"\n[*] Total test time: {elapsed:.1f} seconds")
        print("\nTest complete!")
    finally:
        # Restore stderr
        sys.stderr = original_stderr
        null_file.close()

if __name__ == "__main__":
    main()

