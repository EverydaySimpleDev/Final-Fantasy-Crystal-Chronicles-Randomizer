"""
chest.py - View/edit dungeon chest (treasure) tables in FFCC.

Each dungeon's script `dvd/cft/<dungeon>_0.cft` has a `get_treasure` function
containing a LOOT TABLE: many "treasure sets", each assigning one item to each
of the dungeon's chests. The game rolls a set per cycle. A chest record is a
0x5b-byte struct: item ID is a push-int at offset +0 (bytes `03 00 00 <id16>`),
chest index is the byte at +0x49 (1..N). Sets are runs whose +0x49 goes 1..N.

Each set is category-homogeneous and its load-time setup is category-specific:
swapping an item WITHIN its category is safe; a wrong-category or out-of-range
value can make the chest drop nothing OR crash the level on load. So edit slots
within their category. (Item IDs per your inventory notes.)

Workflow (fixed-size, re-inject in place):
    python gciso.py extract "Hacked Rom.iso" dvd/cft/river_0.cft river_0.cft
    python chest.py table river_0.cft                 # all sets x chests
    python chest.py setslot river_0.cft 0x25a01 0x107 # edit ONE slot by file offset
    python chest.py set river_0.cft 0x105 0x107       # bulk: every Stone of Cure -> Life
    python gciso.py inject "Hacked Rom.iso" dvd/cft/river_0.cft river_0.cft

Note: the 0x5b stride / +0x49 index are confirmed for River Belle Path; other
dungeons may use a different record size (pass --stride / --idxoff to tune).
"""

import sys
import struct
import cft

CAT = [
    (0x001, 0x044, "Weapon"), (0x045, 0x057, "Armor"), (0x058, 0x061, "Shield"),
    (0x062, 0x06a, "Gauntlet"), (0x06b, 0x074, "Helmet"), (0x075, 0x07e, "Belt"),
    (0x07f, 0x09e, "Accessory"), (0x09f, 0x0e7, "Artifact"), (0x100, 0x124, "Magicite/Spell"),
    (0x125, 0x125, "PhoenixDown"), (0x126, 0x172, "Material"), (0x17d, 0x18e, "Food"),
    (0x191, 0x1ed, "Recipe/Scroll"),
]


def category(v):
    for lo, hi, name in CAT:
        if lo <= v <= hi:
            return name
    return "?"


def detect_sets(raw, stride=0x5b, idxoff=0x49):
    """Find treasure sets: 0x5b-stride runs of push-int records whose +0x49 index
    goes 1..N. Returns list of dicts {start, n, slots:[(file_off,item_id)]}."""
    pushes = set(o for o in range(len(raw) - 5) if raw[o] == 0x03)
    sets = []
    used = set()
    for o in sorted(pushes):
        if o in used or raw[o + idxoff] != 1:
            continue
        # walk the run while +0x49 increments and stride lands on a push
        run = [o]
        p = o
        while p + stride in pushes and raw[p + stride + idxoff] == len(run) + 1:
            p += stride
            run.append(p)
        if len(run) >= 2:
            slots = [(r, int.from_bytes(raw[r + 1:r + 5], "big")) for r in run]
            sets.append({"start": o, "n": len(run), "slots": slots})
            used.update(run)
    return sets


def cmd_table(path, stride, idxoff):
    raw = open(path, "rb").read()
    sets = detect_sets(raw, stride, idxoff)
    print(f"{len(sets)} treasure set(s) (record stride 0x{stride:x}):")
    for s in sets:
        items = s["slots"]
        cats = {category(v) for _, v in items}
        catstr = "/".join(sorted(cats))
        ids = " ".join(f"0x{v:04x}" for _, v in items)
        print(f"  set @0x{s['start']:06x}  [{s['n']} chests] {catstr:14s}: {ids}")


def cmd_find(path, item, stride, idxoff):
    item = int(item, 0)
    raw = open(path, "rb").read()
    sets = detect_sets(raw, stride, idxoff)
    print(f"0x{item:04x} ({category(item)}):")
    for si, s in enumerate(sets):
        for chest_i, (off, v) in enumerate(s["slots"], 1):
            if v == item:
                print(f"  set @0x{s['start']:06x} chest#{chest_i}  slot file-offset 0x{off:x}")


def cmd_setslot(path, off, new):
    off = int(off, 0)
    new = int(new, 0)
    data = bytearray(open(path, "rb").read())
    if data[off] != 0x03:
        print(f"0x{off:x} is not a push-int (item slot). Use `table`/`find` to get a slot offset.")
        return
    old = int.from_bytes(data[off + 1:off + 5], "big")
    data[off + 1:off + 5] = struct.pack(">I", new)
    open(path, "wb").write(data)
    print(f"slot 0x{off:x}: 0x{old:04x} ({category(old)}) -> 0x{new:04x} ({category(new)})")
    if category(old) != category(new):
        print("  WARNING: different category. Sets are category-homogeneous; a wrong-category"
              " value may drop nothing or CRASH the level on load. Prefer same-category items.")


def cmd_set(path, old, new, stride, idxoff):
    old = int(old, 0)
    new = int(new, 0)
    raw = bytearray(open(path, "rb").read())
    sets = detect_sets(bytes(raw), stride, idxoff)
    n = 0
    for s in sets:
        for off, v in s["slots"]:
            if v == old:
                raw[off + 1:off + 5] = struct.pack(">I", new)
                n += 1
    open(path, "wb").write(raw)
    print(f"changed {n} slot(s) across all sets: 0x{old:04x} ({category(old)}) -> 0x{new:04x} ({category(new)})")
    if category(old) != category(new):
        print("  WARNING: cross-category bulk change is risky (nothing-drop or crash on load).")


if __name__ == "__main__":
    args = sys.argv[1:]
    stride, idxoff = 0x5b, 0x49
    for opt, default in (("--stride", None), ("--idxoff", None)):
        if opt in args:
            i = args.index(opt)
            val = int(args[i + 1], 0)
            if opt == "--stride":
                stride = val
            else:
                idxoff = val
            args = args[:i] + args[i + 2:]
    if len(args) < 2:
        print(__doc__.strip())
        sys.exit(1)
    cmd, path = args[0].lower(), args[1]
    if cmd == "table":
        cmd_table(path, stride, idxoff)
    elif cmd == "find":
        cmd_find(path, args[2], stride, idxoff)
    elif cmd == "setslot":
        cmd_setslot(path, args[2], args[3])
    elif cmd == "set":
        cmd_set(path, args[2], args[3], stride, idxoff)
    else:
        print(__doc__.strip())
        sys.exit(1)
