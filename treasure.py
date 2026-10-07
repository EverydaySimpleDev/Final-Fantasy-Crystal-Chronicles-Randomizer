"""
treasure.py - read and write individual get_treasure slots, and make the
slot a chest rolls deterministic.

get_treasure(case) is a switch on the case number (a chest's SPAWN_TBOX A,
low 16 bits); inside, a switch on a slot 0-7. Each slot assigns four drop
entries var2..var5 (SPAWN_TBOX copies them into the chest's 4 drop codes).
Each entry is an item ID, gil (0x4000 | amount - sometimes a small
expression, e.g. 0x4000 + (25 or 25 * players)) or 0. Which entry holds the
item varies (Goblin Wall uses var3, Mushroom Forest var2).

The slot comes from getIdxSet() in the same script, from the dungeon's cycle:
    cycle 1: rand(4)      -> slots 0-3
    cycle 2: 2 + rand(4)  -> slots 2-5
    cycle 3: 4 + rand(4)  -> slots 4-7
The windows overlap, so a slot can't belong to just one cycle. For AP seeds
patch_getidxset() turns the three rand(4) into rand(1): every chest (and
monster drop) then uses slot 0 / 2 / 4 in cycle 1 / 2 / 3.
"""

import re
import struct

import cft

INNER = re.compile(rb"\x3a\x03\x00\x00\x00(.)\x2c\x08", re.S)
GETA_VAR = re.compile(rb"\x01\x00\x00(.)\x04", re.S)   # GETA local var, address form

CYCLE_SLOT = {1: 0, 2: 2, 3: 4}


def _code(path, func_name):
    root, data = cft.parse(path)
    func = next(s for s in root.subtags if s.type == b"FUNC")
    names = [k.name() for k in func.subtags]
    code = cft._code_of(func.subtags[names.index(func_name)])
    return data, data.find(code), code, names


def case_slots(data, lo, hi):
    """{slot: {"item": offset of var3's 4-byte value (where the AP item goes),
    "gil": [offsets of every literal in var2/var4/var5's assignments, which
    are cleared]}} for the get_treasure case at data[lo:hi]."""
    body = data[lo:hi]
    heads = [(m.group(1)[0], m.start()) for m in INNER.finditer(body)][1:]   # [0] is the case itself
    slots = {}
    for i, (slot, start) in enumerate(heads):
        end = heads[i + 1][1] if i + 1 < len(heads) else len(body)
        seg = body[start:end]
        ops = list(cft.disasm(seg))
        info = {"item": None, "gil": []}
        for j, (off, op, arg) in enumerate(ops):
            if op != 1 or arg is None or (arg & 0xFF) != 0x04:
                continue
            var = arg >> 8
            if var not in (2, 3, 4, 5):
                continue
            # the value pushes between this GETA and its store (opcode 0x0D)
            lits = []
            for off2, op2, arg2 in ops[j + 1:]:
                if op2 == 0x0D:
                    break
                if op2 == 3:
                    lits.append(lo + start + off2 + 1)
            if var == 3 and len(lits) == 1:
                info["item"] = lits[0]
            elif var != 3:
                info["gil"] += lits
        slots[slot] = info
    return slots


def write_slot(buf, info, item_id):
    """Make a slot drop only `item_id`: var3 = item, every other entry 0."""
    buf[info["item"]:info["item"] + 4] = struct.pack(">i", item_id)
    for o in info["gil"]:
        buf[o:o + 4] = b"\0\0\0\0"


def getidxset_sites(path):
    """File offsets of the three `rand(4)` ranges in getIdxSet (the 4-byte value)."""
    data, base, code, names = _code(path, "getIdxSet")
    rand = names.index("rand")
    ops = list(cft.disasm(code))
    sites = []
    for j, (off, op, arg) in enumerate(ops):
        if op == 10 and arg is not None and (arg & 0xFFFF) == rand and ((arg >> 16) & 0xFFFF) == 0xFFFF:
            poff, pop, parg = ops[j - 1]
            if pop == 3 and parg in (4, 1):
                sites.append(base + poff + 1)
    return sites


def patch_getidxset(buf, path):
    """rand(4) -> rand(1) in getIdxSet; returns how many sites are now patched."""
    sites = getidxset_sites(path)
    if len(sites) != 3:
        raise ValueError(f"{path}: expected 3 rand ranges in getIdxSet, found {len(sites)}")
    for o in sites:
        buf[o:o + 4] = struct.pack(">i", 1)
    return len(sites)
