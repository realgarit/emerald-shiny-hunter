"""
Memory read/write utilities for Pokemon Emerald Shiny Hunter.

Provides functions to read and write values from mGBA core memory.
"""


def read_u8(core, address: int) -> int:
    """Read 8-bit unsigned integer from memory."""
    return core._core.busRead8(core._core, address)


def read_u16(core, address: int) -> int:
    """Read 16-bit unsigned integer from memory (little-endian)."""
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    return b0 | (b1 << 8)


def read_u32(core, address: int) -> int:
    """Read 32-bit unsigned integer from memory (little-endian)."""
    b0 = core._core.busRead8(core._core, address)
    b1 = core._core.busRead8(core._core, address + 1)
    b2 = core._core.busRead8(core._core, address + 2)
    b3 = core._core.busRead8(core._core, address + 3)
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)


def read_bytes(core, address: int, length: int) -> bytes:
    """Read multiple bytes from memory."""
    return bytes([core._core.busRead8(core._core, address + i) for i in range(length)])


def write_u8(core, address: int, value: int):
    """Write 8-bit unsigned integer to memory."""
    core._core.busWrite8(core._core, address, value & 0xFF)


def write_u16(core, address: int, value: int):
    """Write 16-bit unsigned integer to memory (little-endian)."""
    core._core.busWrite8(core._core, address, value & 0xFF)
    core._core.busWrite8(core._core, address + 1, (value >> 8) & 0xFF)


def write_u32(core, address: int, value: int):
    """Write 32-bit unsigned integer to memory (little-endian)."""
    core._core.busWrite32(core._core, address, value)


def write_bytes(core, address: int, data: bytes):
    """Write multiple bytes to memory."""
    for i, byte in enumerate(data):
        core._core.busWrite8(core._core, address + i, byte)
