#!/usr/bin/env python3
"""
Test script to find minimum A presses needed with fast button presses
"""
import mgba.core
import random
import time

ROM_PATH = "Pokemon - Emerald Version (U).gba"
TID = 56078
SID = 24723

def read_u32(core, address):
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    b2 = core._core.busRead8(core._core, address + 2)
    b3 = core._core.busRead8(core._core, address + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

def press_a(core, hold=5, release=5):
    core._core.setKeys(core._core, 1)
    for _ in range(hold):
        core.run_frame()
    core._core.setKeys(core._core, 0)
    for _ in range(release):
        core.run_frame()

def run_frames(core, n):
    for _ in range(n):
        core.run_frame()

print("=" * 60)
print("Testing Fast A Presses - Finding Minimum Needed")
print("=" * 60)
print("\n[*] Loading ROM and save file...")

core = mgba.core.load_path(ROM_PATH)
if not core:
    raise RuntimeError(f"Failed to load ROM: {ROM_PATH}")

core.reset()
core.autoload_save()

print("[*] Setting up RNG...")
random_seed = random.randint(0, 0xFFFFFFFF)
core._core.busWrite32(core._core, 0x03005D80, random_seed)
random_delay = random.randint(10, 100)
run_frames(core, random_delay)

print("[*] Testing different delay times between presses...")
print("[*] We'll test: no delay, 30 frames (0.5s), 60 frames (1s), 90 frames (1.5s)\n")

test_delays = [
    (0, "No delay"),
    (15, "15 frames (0.25s)"),
    (30, "30 frames (0.5s)"),
    (45, "45 frames (0.75s)"),
    (60, "60 frames (1s)"),
]

results = []

for delay_frames, delay_name in test_delays:
    print(f"\n--- Testing with {delay_name} ---")
    
    # Test 5 times to get average
    press_counts = []
    for test_run in range(5):
        # Reset for each test
        core.reset()
        core.autoload_save()
        random_seed = random.randint(0, 0xFFFFFFFF)
        core._core.busWrite32(core._core, 0x03005D80, random_seed)
        random_delay = random.randint(10, 100)
        run_frames(core, random_delay)
        
        found = False
        for press_num in range(1, 25):  # Increased to 25 presses
            press_a(core, hold=5, release=5)
            
            # Add delay between presses
            if delay_frames > 0:
                run_frames(core, delay_frames)
            
            # Check for Pokemon
            pv = read_u32(core, 0x020244EC)
            
            if pv != 0:
                press_counts.append(press_num)
                found = True
                break
        
        if not found:
            print(f"  Test {test_run + 1}: No Pokemon found after 25 presses")
    
    if press_counts:
        avg_presses = sum(press_counts) / len(press_counts)
        max_presses = max(press_counts)
        total_time = avg_presses * (delay_frames / 60.0) if delay_frames > 0 else avg_presses * 0.1
        print(f"  Results: {press_counts}")
        print(f"  Average: {avg_presses:.1f} presses | Max: {max_presses} | Est. time: {total_time:.1f}s")
        results.append((delay_frames, delay_name, avg_presses, max_presses, total_time))
    else:
        print(f"  ✗ No Pokemon found in any test with {delay_name}")

print("\n" + "=" * 60)
print("SUMMARY - Fastest Option:")
print("=" * 60)
if results:
    # Sort by total time
    results.sort(key=lambda x: x[4])
    best = results[0]
    print(f"Best: {best[1]} - {best[2]:.1f} avg presses, {best[3]} max, ~{best[4]:.1f}s per attempt")
    print(f"\nRecommended: Use {best[0]} frames delay, {int(best[3]) + 2} max presses")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)

