"""
shops.py - parse and edit FFCC shop inventories.

Each shop's stock lives in its dungeon/town cft script, inside the shopStart()
function, as a run of push-int item IDs - one per shop slot. The slot layout is

    push 1            (03 00 00 00 01)   stock/availability flag
    push <item id>    (03 00 00 hi lo)   the item sold
    push 0  x5        (03 00 00 00 00)   padding/args
    ... call shop-add

Prices are NOT stored here - the engine derives them from the item via
shopRateCalc - so editing a shop is just replacing the 16-bit item id, exactly
like a chest slot in lootcft.py. This module mirrors lootcft's find/apply API.
"""

import re
import struct

import cft

# Shop cft basename -> friendly name (the 7 shops in the GameCube game).
SHOPS = {
    "village_0": "Tipa",
    "castle_0":  "Alfitaria",
    "farm_0":    "Fields of Fum",
    "uma_1":     "Selkie Peddler",
    "magic_0":   "Shella (Magic)",
    "thief_0":   "Leuda (Premium)",
    "weapon_0":  "Smith (Weapons)",
}

# One shop slot: push(1), push(item id, high bytes always 0000), push(0).
# The 2-byte item id is the capture group; its file offset is match.start()+8.
_SLOT_RE = re.compile(rb"\x03\x00\x00\x00\x01\x03\x00\x00(..)\x03\x00\x00\x00\x00", re.DOTALL)


def _shopstart_region(data):
    """(start, end) file offsets of the shopStart function's CODE within `data`,
    or None. We locate the function via the cft parser then find its (unique)
    code bytes in the raw file, so returned offsets are real file offsets."""
    import os
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "shopscan.cft")
    with open(tmp, "wb") as f:
        f.write(data)
    root, _ = cft.parse(tmp)
    func = next((s for s in root.subtags if s.type == b"FUNC"), None)
    if func is None:
        return None
    names = [k.name() for k in func.subtags]
    if "shopStart" not in names:
        return None
    code = cft._code_of(func.subtags[names.index("shopStart")])
    if not code:
        return None
    pos = data.find(code)
    return None if pos < 0 else (pos, pos + len(code))


def find_shop_items(path, valid=None):
    """Return [(file_offset, item_id), ...] for each shop slot in stock order,
    restricted to the shopStart function. file_offset points at the 2-byte
    (big-endian) item id, ready to overwrite. If `valid` is given it filters
    item ids (e.g. to sellable classes), dropping flag/intro/padding matches."""
    with open(path, "rb") as f:
        data = f.read()
    region = _shopstart_region(data)
    if region is None:
        return []
    lo, hi = region
    out = []
    for m in _SLOT_RE.finditer(data, lo, hi):
        item = struct.unpack(">H", m.group(1))[0]
        if valid is None or valid(item):
            out.append((m.start() + 8, item))
    return out


def apply_edits(path, edits):
    """edits: {file_offset: new_item_id}. Overwrites each 16-bit id in place."""
    with open(path, "rb") as f:
        data = bytearray(f.read())
    for off, new in edits.items():
        data[off:off + 2] = struct.pack(">H", new)
    with open(path, "wb") as f:
        f.write(data)
