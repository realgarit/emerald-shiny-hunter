#!/usr/bin/env python3
"""
Debug script to find the optimal button sequence for selecting Mudkip
Testing different combinations of A presses, waits, and Right presses
"""

import mgba.core
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
ROM_PATH = str(PROJECT_ROOT / "roms" / "Pokemon - Emerald Version (U).gba")

# Memory addresses
PARTY_PV_ADDR = 0x020244EC  # Personality Value
PARTY_TID_ADDR = 0x020244F0  # Trainer ID

# Button constants (GBA button bits)
KEY_A = 1      # bit 0
KEY_RIGHT = 16  # bit 4

# Pokemon species IDs (Gen III battle structure IDs)
POKEMON_SPECIES = {
    277: "Treecko",
    280: "Torchic",
    283: "Mudkip",
}

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

def press_button(core, button, hold=5, release=5):
    """Press a button (button is the bit value)"""
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
        # Read PV and TID
        pv = read_u32(core, pv_addr)
        tid = read_u16(core, tid_addr)
        
        if pv == 0:
            return 0
        
        # Encrypted data starts at exactly 32 bytes after PV address
        data_start = pv_addr + 32
        
        # Get substructure order
        order = get_substructure_order(pv)
        growth_pos = order.index('G')
        offset = growth_pos * 12
        
        # Read 32 bits from data_start + offset
        encrypted_val = read_u32(core, data_start + offset)
        
        # Decrypt: encrypted_val ^ (tid ^ pv)
        xor_key = (tid & 0xFFFF) ^ pv
        decrypted_val = encrypted_val ^ xor_key
        
        # Extract species ID (lower 16 bits)
        species_id = decrypted_val & 0xFFFF
        
        return species_id
    except Exception as e:
        return 0

def test_sequence(core, a_dialogue, wait_for_bag, right_presses, wait_after_right, a_select, a_additional):
    """Test a specific button sequence
    
    Args:
        a_dialogue: Number of A presses to get through dialogue
        a_bag: Number of A presses to open bag (usually 1)
        wait_after_bag: Frames to wait after opening bag before Right
        right_presses: Number of Right presses
        wait_after_right: Frames to wait after Right before A presses
        a_after_right: Number of A presses after Right
    """
    # Reset and load save
    core.reset()
    core.autoload_save()
    run_frames(core, 60)  # Wait 1 second for save to load
    
    # Step 1: Press A buttons to get through dialogue
    for i in range(a_dialogue):
        press_button(core, KEY_A, hold=5, release=5)
        run_frames(core, 15)  # 0.25s delay between presses
        
        # Check if Pokemon appears early (would be Torchic)
        pv = read_u32(core, PARTY_PV_ADDR)
        if pv != 0:
            species_id = decrypt_party_species(core, PARTY_PV_ADDR, PARTY_TID_ADDR)
            return False, 0, species_id, f"Early after {i+1} A (before bag)"
    
    # Step 2: Wait for bag screen to appear
    run_frames(core, wait_for_bag)
    
    # Step 3: Press Right to move to Mudkip (BEFORE opening bag or RIGHT AFTER)
    # Try pressing Right before opening bag
    for _ in range(right_presses):
        press_button(core, KEY_RIGHT, hold=5, release=5)
        run_frames(core, 15)  # Small delay after each Right
    
    # Step 4: Wait after Right
    run_frames(core, wait_after_right)
    
    # Step 5: Press A to select Mudkip
    pokemon_found = False
    presses_needed = 0
    
    # First A press to select
    for i in range(a_select):
        press_button(core, KEY_A, hold=5, release=5)
        run_frames(core, 15)
        
        # Check if Pokemon appears (should be Mudkip now)
        pv = read_u32(core, PARTY_PV_ADDR)
        if pv != 0:
            pokemon_found = True
            presses_needed = i + 1
            break
    
    # Additional A presses if not found yet
    if not pokemon_found:
        for i in range(a_additional):
            press_button(core, KEY_A, hold=5, release=5)
            run_frames(core, 15)  # 0.25s delay between presses
            
            # Check if Pokemon is found
            pv = read_u32(core, PARTY_PV_ADDR)
            if pv != 0:
                pokemon_found = True
                presses_needed = a_select + i + 1
                break
    
    # Wait a bit more and check again if not found
    if not pokemon_found:
        run_frames(core, 60)
        pv = read_u32(core, PARTY_PV_ADDR)
        if pv != 0:
            pokemon_found = True
            presses_needed = a_select + a_additional
    
    # If Pokemon found, check species
    species_id = 0
    if pokemon_found:
        run_frames(core, 60)  # Wait for data to settle
        species_id = decrypt_party_species(core, PARTY_PV_ADDR, PARTY_TID_ADDR)
    
    return pokemon_found, presses_needed, species_id, None

print("=" * 70)
print("Finding Optimal Button Sequence for Mudkip Selection")
print("=" * 70)
print(f"\n[*] Loading ROM: {ROM_PATH}")

core = mgba.core.load_path(ROM_PATH)
if not core:
    raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

print("[*] Testing different button sequences...\n")

# Test cases based on user's description:
# 1. Press A once to open bag
# 2. Wait a bit
# 3. Press Right
# 4. Press A multiple times until Mudkip appears

# Comprehensive test cases to find optimal sequence
# We know 22+ A dialogue causes early Torchic, so focus on 18-21
test_cases = []

# Test different A dialogue counts (18-21, avoiding 22+ which causes Torchic)
for a_dialogue in [18, 19, 20, 21]:
    # Test different wait times for bag screen
    for wait_bag in [30, 45, 60]:  # 0.5s, 0.75s, 1.0s
        # Test different Right press counts
        for right_count in [1, 2, 3, 5]:
            # Test different wait times after Right
            for wait_right in [12, 15, 20, 30]:  # 0.2s, 0.25s, 0.33s, 0.5s
                # Test different A select counts
                for a_select in [1, 2]:
                    # Test different A additional counts
                    for a_additional in [3, 5, 7]:
                        test_cases.append((a_dialogue, wait_bag, right_count, wait_right, a_select, a_additional))

print(f"[*] Generated {len(test_cases)} test cases to try...")
print("[*] This will take a while. Testing systematically...\n")

successful_sequences = []
failed_sequences = []
early_torchic = []

for i, (a_dialogue, wait_bag, right_count, wait_right, a_select, a_additional) in enumerate(test_cases, 1):
    if i % 50 == 0 or i == 1:
        print(f"[Progress: {i}/{len(test_cases)} ({i/len(test_cases)*100:.1f}%)]")
    
    found, presses, species_id, early_reason = test_sequence(core, a_dialogue, wait_bag, right_count, wait_right, a_select, a_additional)
    
    if found:
        species_name = POKEMON_SPECIES.get(species_id, f"Unknown (ID: {species_id})")
        if species_id == 283:
            successful_sequences.append((a_dialogue, wait_bag, right_count, wait_right, a_select, a_additional, presses, species_id))
            if len(successful_sequences) <= 20:  # Print first 20 successful
                print(f"  ✅ [{i}] {a_dialogue}A -> {wait_bag/60:.1f}s -> {right_count}xR -> {wait_right/60:.1f}s -> {a_select}+{a_additional}A = MUDKIP (after {presses} A)")
        else:
            failed_sequences.append((a_dialogue, wait_bag, right_count, wait_right, a_select, a_additional, species_id))
    elif early_reason:
        early_torchic.append((a_dialogue, wait_bag, right_count, wait_right, a_select, a_additional, early_reason))
    else:
        failed_sequences.append((a_dialogue, wait_bag, right_count, wait_right, a_select, a_additional, 0))

print("\n" + "=" * 70)
print("Results Summary")
print("=" * 70)

print(f"\n[*] Total tests: {len(test_cases)}")
print(f"[*] Successful (Mudkip): {len(successful_sequences)} ({len(successful_sequences)/len(test_cases)*100:.1f}%)")
print(f"[*] Failed (wrong species or no Pokemon): {len(failed_sequences)} ({len(failed_sequences)/len(test_cases)*100:.1f}%)")
print(f"[*] Early Torchic: {len(early_torchic)} ({len(early_torchic)/len(test_cases)*100:.1f}%)")

if successful_sequences:
    print(f"\n[*] All {len(successful_sequences)} sequences that correctly select MUDKIP:")
    print("    (Showing first 30, sorted by total button presses)")
    
    # Sort by total button presses (fewest first)
    sorted_sequences = sorted(successful_sequences, key=lambda x: x[0] + x[2] + x[4] + x[5])
    
    for seq in sorted_sequences[:30]:
        a_dialogue, wait_bag, right_count, wait_right, a_select, a_additional, presses, species_id = seq
        total_presses = a_dialogue + right_count + a_select + a_additional
        print(f"  ✅ {a_dialogue}A -> wait {wait_bag/60:.1f}s -> {right_count}xR -> wait {wait_right/60:.1f}s -> {a_select}+{a_additional}A = MUDKIP (after {presses} A, {total_presses} total)")
    
    if len(sorted_sequences) > 30:
        print(f"  ... and {len(sorted_sequences) - 30} more successful sequences")
    
    # Find best sequences by different criteria
    best_fewest_presses = min(successful_sequences, key=lambda x: x[0] + x[2] + x[4] + x[5])
    best_fastest = min(successful_sequences, key=lambda x: x[1] + x[3])  # Shortest wait times
    best_most_reliable = max(successful_sequences, key=lambda x: x[6])  # Most A presses before finding (more margin)
    
    print(f"\n[*] Top recommendations:")
    print(f"\n  1. Fewest button presses ({best_fewest_presses[0] + best_fewest_presses[2] + best_fewest_presses[4] + best_fewest_presses[5]} total):")
    print(f"     {best_fewest_presses[0]} A dialogue -> wait {best_fewest_presses[1]/60:.1f}s -> {best_fewest_presses[2]}x Right -> wait {best_fewest_presses[3]/60:.1f}s -> {best_fewest_presses[4]} A select -> {best_fewest_presses[5]} A more")
    print(f"     (Found after {best_fewest_presses[6]} A presses)")
    
    print(f"\n  2. Fastest timing ({(best_fastest[1] + best_fastest[3])/60:.2f}s total wait):")
    print(f"     {best_fastest[0]} A dialogue -> wait {best_fastest[1]/60:.1f}s -> {best_fastest[2]}x Right -> wait {best_fastest[3]/60:.1f}s -> {best_fastest[4]} A select -> {best_fastest[5]} A more")
    print(f"     (Found after {best_fastest[6]} A presses)")
    
    print(f"\n  3. Most reliable margin ({best_most_reliable[6]} A presses before finding):")
    print(f"     {best_most_reliable[0]} A dialogue -> wait {best_most_reliable[1]/60:.1f}s -> {best_most_reliable[2]}x Right -> wait {best_most_reliable[3]/60:.1f}s -> {best_most_reliable[4]} A select -> {best_most_reliable[5]} A more")
    print(f"     (Found after {best_most_reliable[6]} A presses)")
    
    # Analyze patterns
    print(f"\n[*] Pattern analysis:")
    dialogue_counts = {}
    right_counts = {}
    wait_bag_counts = {}
    wait_right_counts = {}
    
    for seq in successful_sequences:
        dialogue_counts[seq[0]] = dialogue_counts.get(seq[0], 0) + 1
        right_counts[seq[2]] = right_counts.get(seq[2], 0) + 1
        wait_bag_counts[seq[1]] = wait_bag_counts.get(seq[1], 0) + 1
        wait_right_counts[seq[3]] = wait_right_counts.get(seq[3], 0) + 1
    
    print(f"  Most common A dialogue: {max(dialogue_counts.items(), key=lambda x: x[1])}")
    print(f"  Most common Right presses: {max(right_counts.items(), key=lambda x: x[1])}")
    print(f"  Most common wait_bag: {max(wait_bag_counts.items(), key=lambda x: x[1])[0]/60:.1f}s")
    print(f"  Most common wait_right: {max(wait_right_counts.items(), key=lambda x: x[1])[0]/60:.1f}s")
else:
    print("\n[!] No sequences correctly selected Mudkip!")
    print("[!] May need to adjust test cases or timing")

if early_torchic:
    print(f"\n[!] {len(early_torchic)} sequences caused early Torchic selection")
    print("    (These sequences selected Torchic before Right button sequence)")

print("\nTest complete!")

