#!/usr/bin/env python3
import mgba.core

core = mgba.core.load_path("Pokemon - Emerald Version (U).gba")
core.reset()

# Check write methods
print("busWrite methods:", [m for m in dir(core._core) if 'Write' in m])

def read_u32(core, addr):
    b0 = core._core.busRead8(core._core, addr)
    b1 = core._core.busRead8(core._core, addr + 1)
    b2 = core._core.busRead8(core._core, addr + 2)
    b3 = core._core.busRead8(core._core, addr + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

# Test address (IWRAM - should be writable)
test_addr = 0x03005D80
print(f"\nTesting write to 0x{test_addr:08X}")

before = read_u32(core, test_addr)
print(f"Before: 0x{before:08X}")

print("Writing 0xDEADBEEF...")
core._core.busWrite32(core._core, test_addr, 0xDEADBEEF)

after = read_u32(core, test_addr)
print(f"After: 0x{after:08X}")

if after == 0xDEADBEEF:
    print("Write SUCCESS!")
else:
    print("Write failed or address is protected")
