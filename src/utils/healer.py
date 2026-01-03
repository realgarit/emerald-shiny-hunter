"""
Healing utilities for Pokemon Emerald.
Implements Dual-Sync healing (Active + SaveBlock) with correct Decrypted Checksum.
"""

from typing import List
from .memory import read_u8, read_u16, read_u32, write_u8, write_u16, write_u32
from constants.memory import (
    POKEMON_ENCRYPTED_OFFSET, SUBSTRUCTURE_SIZE, SUBSTRUCTURE_ORDERS,
    POKEMON_HP_OFFSET, POKEMON_MAX_HP_OFFSET, POKEMON_STATUS_OFFSET,
    G_SAVE_BLOCK_1_PTR, PARTY_SLOT_1_ADDR, SB1_PARTY_OFFSET
)

# Found via scan
MOVE_TABLE_ADDR = 0x0831C898
MOVE_ENTRY_SIZE = 12

def _get_max_pp(core, move_id: int, pp_ups: int) -> int:
    if move_id == 0: return 0
    addr = MOVE_TABLE_ADDR + (move_id * MOVE_ENTRY_SIZE) + 4
    base_pp = read_u8(core, addr)
    return int(base_pp * (1 + 0.2 * pp_ups))

def heal_pokemon_at_address(core, base_addr: int) -> List[str]:
    pv = read_u32(core, base_addr)
    otid = read_u32(core, base_addr + 4)
    if pv == 0: return []

    actions = []
    
    # 1. HP & Status (Unencrypted)
    max_hp = read_u16(core, base_addr + POKEMON_MAX_HP_OFFSET)
    if max_hp > 0:
        write_u16(core, base_addr + POKEMON_HP_OFFSET, max_hp)
        write_u32(core, base_addr + POKEMON_STATUS_OFFSET, 0)

    # 2. PP & Checksum (Decrypted Sum)
    xor_key = otid ^ pv
    order = SUBSTRUCTURE_ORDERS[pv % 24]
    
    dec_data = [] 
    for i in range(4):
        sub_addr = base_addr + POKEMON_ENCRYPTED_OFFSET + (i * SUBSTRUCTURE_SIZE)
        for j in range(3):
            enc_word = read_u32(core, sub_addr + (j * 4))
            dec_data.append(enc_word ^ xor_key)

    a_pos = order.index('A') * 3
    g_pos = order.index('G') * 3
    
    pp_ups_byte = dec_data[g_pos + 2] & 0xFF
    pp_ups = [(pp_ups_byte >> (i*2)) & 3 for i in range(4)]
    
    moves = [
        dec_data[a_pos] & 0xFFFF,
        (dec_data[a_pos] >> 16) & 0xFFFF,
        (dec_data[a_pos + 1]) & 0xFFFF,
        (dec_data[a_pos + 1] >> 16) & 0xFFFF
    ]
    
    new_pp = []
    for i in range(4):
        if moves[i] == 0: new_pp.append(0)
        else: new_pp.append(_get_max_pp(core, moves[i], pp_ups[i]))
    
    dec_data[a_pos + 2] = new_pp[0] | (new_pp[1] << 8) | (new_pp[2] << 16) | (new_pp[3] << 24)

    # Calculate Checksum on DECRYPTED data
    new_checksum = 0
    for word32 in dec_data:
        new_checksum = (new_checksum + (word32 & 0xFFFF) + ((word32 >> 16) & 0xFFFF)) & 0xFFFF
    
    # Write Back
    for i in range(4):
        sub_addr = base_addr + POKEMON_ENCRYPTED_OFFSET + (i * SUBSTRUCTURE_SIZE)
        for j in range(3):
            write_u32(core, sub_addr + (j * 4), dec_data[i*3 + j] ^ xor_key)
            
    write_u16(core, base_addr + 0x1C, new_checksum)
    return ["Healed"]

def heal_party(core):
    """Dual-Sync Heal: Modifies both active and save memory."""
    # 1. Active Gameplay Party
    heal_pokemon_at_address(core, PARTY_SLOT_1_ADDR)
    
    # 2. Save Block 1 Party
    sb1 = read_u32(core, G_SAVE_BLOCK_1_PTR)
    if sb1 and 0x02000000 <= sb1 <= 0x03000000:
        heal_pokemon_at_address(core, sb1 + SB1_PARTY_OFFSET)
        
    return ["Full Sync Heal Applied"]
