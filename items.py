"""
items.py - Read/edit FFCC's item-definition table (dvd/cft/param.cfd).

Each item is a 72-byte (0x48) record; the table holds 1205 entries (IDs
0x0000-0x04B4). Field layout is from FFCC Notes/Structures.txt. IDs are the
ones in FFCC Notes/Inventory Code Lists.txt (e.g. 0x0001 Copper Sword,
0x0125 Phoenix Down, 0x0100 Stone of Fire).

Workflow (param.cfd is fixed-size, so edits re-inject in place):
    python gciso.py extract "Hacked Rom.iso" dvd/cft/param.cfd param.cfd
    python items.py show param.cfd 0x0001
    python items.py set  param.cfd 0x0001 damage 99
    python gciso.py inject "Hacked Rom.iso" dvd/cft/param.cfd param.cfd

Commands:
    python items.py show <param.cfd> <id>
    python items.py list <param.cfd> [start] [count]
    python items.py set  <param.cfd> <id> <field|0xOFF[:1|2]> <value>

Named fields (offset,size): type(0,2) model(2,2) equiptype(4,1)
    equipability(5,1) value(6,2) status(8,2) focus(10,2) gfxsize(16,2)
    gil(32,2)  - or address any byte with 0xOFF[:size], e.g. 0x06:2
"""

import sys
import struct

ENTRY = 0x48
# Item table base as a file offset within param.cfd (id 0 / Null entry).
TABLE_BASE = 0x175f0
# Stable signature for the start of Copper Sword (id 1): type+model+equip bytes
# only (no editable stats), used as a fallback to locate the table.
SIG = bytes.fromhex("000100010101")

FIELDS = {
    "type": (0, 2), "model": (2, 2), "equiptype": (4, 1), "equipability": (5, 1),
    "value": (6, 2), "damage": (6, 2), "defense": (6, 2), "status": (8, 2),
    "focus": (10, 2), "spell": (10, 2), "gfxsize": (16, 2), "gil": (32, 2),
}


def find_base(data):
    # Primary: fixed file offset (stable for param.cfd). Sanity-check that the
    # Copper Sword slot still looks like a weapon record.
    cs = TABLE_BASE + ENTRY
    if data[cs + 4] == 0x01 and int.from_bytes(data[cs:cs + 2], "big") == 0x0001:
        return TABLE_BASE
    # Fallback: search a stable (non-editable) signature.
    i = data.find(SIG)
    if i >= 0:
        return i - ENTRY  # id 0 (Null) is one entry before Copper Sword (id 1)
    return TABLE_BASE  # last resort: trust the known offset


def rec(data, base, item_id):
    off = base + item_id * ENTRY
    return off, data[off:off + ENTRY]


def cmd_show(path, item_id):
    data = open(path, "rb").read()
    base = find_base(data)
    off, e = rec(data, base, item_id)
    print(f"item 0x{item_id:04x}  file-offset 0x{off:x}")
    print("  raw:", e.hex())
    for nm in ("type", "model", "equiptype", "equipability", "value", "status", "focus", "gfxsize", "gil"):
        o, sz = FIELDS[nm]
        v = int.from_bytes(e[o:o + sz], "big")
        print(f"    {nm:13s} @0x{o:02x}:{sz} = 0x{v:0{sz*2}x} ({v})")


def cmd_list(path, start=0, count=32):
    data = open(path, "rb").read()
    base = find_base(data)
    for i in range(start, start + count):
        _, e = rec(data, base, i)
        t = int.from_bytes(e[0:2], "big")
        m = int.from_bytes(e[2:4], "big")
        eq = e[4]
        v = int.from_bytes(e[6:8], "big")
        print(f"  0x{i:04x}  type=0x{t:04x} model=0x{m:04x} equipType=0x{eq:02x} value={v}")


def parse_field(spec):
    if spec in FIELDS:
        return FIELDS[spec]
    if spec.startswith("0x"):
        if ":" in spec:
            o, s = spec.split(":")
            return int(o, 16), int(s)
        return int(spec, 16), 2
    raise SystemExit(f"Unknown field {spec!r}. Named: {', '.join(FIELDS)} or 0xOFF[:size].")


def cmd_set(path, item_id, field, value):
    o, sz = parse_field(field)
    val = int(value, 0)
    data = bytearray(open(path, "rb").read())
    base = find_base(data)
    off = base + item_id * ENTRY + o
    old = int.from_bytes(data[off:off + sz], "big")
    data[off:off + sz] = val.to_bytes(sz, "big")
    open(path, "wb").write(data)
    print(f"item 0x{item_id:04x} {field} @0x{off:x}: 0x{old:0{sz*2}x} -> 0x{val:0{sz*2}x}  (wrote {path})")


def parse_id(s):
    return int(s, 0)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__.strip()); sys.exit(1)
    cmd, path = sys.argv[1].lower(), sys.argv[2]
    if cmd == "show":
        cmd_show(path, parse_id(sys.argv[3]))
    elif cmd == "list":
        start = parse_id(sys.argv[3]) if len(sys.argv) > 3 else 0
        count = int(sys.argv[4]) if len(sys.argv) > 4 else 32
        cmd_list(path, start, count)
    elif cmd == "set":
        cmd_set(path, parse_id(sys.argv[3]), sys.argv[4], sys.argv[5])
    else:
        print(__doc__.strip()); sys.exit(1)
