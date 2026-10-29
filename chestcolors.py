"""
chestcolors.py - Gold treasure chests for important items.

Every dungeon chest is model f034 (dvd/char/fa/f034), loaded by each dungeon
script's initTreasureBox as loadModel(3, 34, 0, -1). The third argument picks
a texture variant: 0 is f034_root.tex, 1 is f034_root_b.tex, 2 is _c, and so
on (the farm cows use this for their coats, loadModel(3, 14, 1-9, -1)). The
chest only ships with the first one, so this adds f034_root_b.tex, a gold
version of the chest, as a new file on the disc.

Which chests are gold:
A chest's SPAWN_TBOX record [mask, A, 0, B, x, y, z, rot] is shared by all
three cycles, and its loot case is only the low 16 bits of A (bits 0x10000
and 0x20000 are flags the game reads). So A gets one more bit per cycle:
    Cycle 1: 0x40000   Cycle 2: 0x100000   Cycle 3: 0x400000
that is 0x40000 << slot, where slot is what getIdxSet() returns once the AP
patch has fixed it to 0 / 2 / 4 (see treasure.py).

SPAWN_TBOX hands A to the new chest through a scratch global that the rest of
the script reuses, and only beginTreasureBox runs while it still holds A. It
keeps the loot case as this.m17 = A & 0xFFFF. initTreasureBox, which loads the
model, runs later. So beginTreasureBox keeps the gold bits too
(this.m17 = A & 0x54FFFF, get_treasure only looks at the low 16 bits), and
initTreasureBox asks for texture variant
    0 != (this.m17 & (0x40000 << getIdxSet()))
so a chest is gold in exactly the cycles where its item is important.

The gold picture is assets/chest_gold.png. `build` turns it into
assets/chest_gold.tex (the chest texture with that picture), which the
patcher copies onto the disc.

Usage:
    py chestcolors.py build  <game.iso>   # rebuild assets/chest_gold.tex from the PNG
    py chestcolors.py install <game.iso>  # add the gold texture to an ISO
"""

import os
import struct
import sys
import tempfile

import cftpatch
import gciso

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    HERE = getattr(sys, "_MEIPASS", HERE)
ASSET = os.path.join(HERE, "assets", "chest_gold.tex")
PICTURE = os.path.join(HERE, "assets", "chest_gold.png")

CHEST_TEXTURE = "dvd/char/fa/f034/f034_root.tex"
GOLD_TEXTURE = "dvd/char/fa/f034/f034_root_b.tex"

# The bit in a chest's A that makes it gold in each cycle.
GOLD_BITS = {1: 0x40000, 2: 0x100000, 3: 0x400000}
ALL_GOLD_BITS = sum(GOLD_BITS.values())

# Item classes that get a gold chest. Traps look important too, so players
# open them.
GOLD_CLASSES = {"progression", "useful", "trap"}

# loadModel(3, 34, 0, -1): the chest model, texture variant 0
_LOAD_CHEST = bytes.fromhex("0300000003" "0300000022" "0300000000" "03ffffffff")
# beginTreasureBox: this.m17 = A & 0xFFFF  (address of this.m17, A, the mask, AND, store)
_CASE_MASK = bytes.fromhex("030000ffff1f0d")
_GOLD_MASK = struct.pack(">BI", 0x03, 0xFFFF | ALL_GOLD_BITS) + bytes.fromhex("1f0d")
_AND, _SHIFT_LEFT, _NOT_EQUAL = 0x1F, 0x22, 0x2D


def install(iso):
    """Add the gold chest texture to `iso`. False if it was already there."""
    return gciso.add_file(iso, GOLD_TEXTURE, open(ASSET, "rb").read())


def gold_bits(cycles):
    """The A bits for a chest that is gold in `cycles`."""
    return sum(GOLD_BITS[c] for c in cycles)


def patch_script(path):
    """Make the chests in the .cft at `path` pick the gold texture when their
    gold bit is set. Returns the new file bytes, or None when the script has
    no chests or is already patched."""
    s = cftpatch.Script(path)
    if "initTreasureBox" not in s.names or "getIdxSet" not in s.names:
        return None
    code = s.code("initTreasureBox")
    at = code.find(_LOAD_CHEST)
    if at < 0:
        return None
    variant_end = at + 15                       # just after "push 0" (the variant)
    if code[variant_end:variant_end + 1] == b"\x00":
        return None                             # the gold check is already there

    # beginTreasureBox: keep the gold bits in this.m17
    begin = bytearray(s.code("beginTreasureBox"))
    mask = begin.find(_CASE_MASK)
    if mask < 10 or begin[mask - 10] != 0x01:
        raise ValueError(f"{os.path.basename(path)}: beginTreasureBox doesn't look as expected")
    member = begin[mask - 9:mask - 5]           # the "address of this.m17" operand
    begin[mask:mask + len(_CASE_MASK)] = _GOLD_MASK
    s.set_code("beginTreasureBox", begin)

    call_idxset = bytes([0x0A]) + struct.pack(">I", 0xFFFF0000 | s.names.index("getIdxSet"))
    # stack: 0, this.m17, 0x40000 << getIdxSet()  ->  0, m17 & bit  ->  0 != (m17 & bit)
    expr = (b"\x00" + member + bytes.fromhex("0300040000") + call_idxset
            + bytes([_SHIFT_LEFT, _AND, _NOT_EQUAL]))
    cftpatch.insert_code(s, "initTreasureBox", variant_end, expr, [])
    return s.to_bytes()


def build(iso):
    """Rebuild assets/chest_gold.tex: the chest texture from `iso` with the
    picture in assets/chest_gold.png."""
    import shutil
    import tex
    work = tempfile.mkdtemp()
    src = os.path.join(work, "f034_root.tex")
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, CHEST_TEXTURE)[0]
        f.seek(off)
        open(src, "wb").write(f.read(size))
    pngs = os.path.join(work, "png")
    os.makedirs(pngs)
    shutil.copy(PICTURE, os.path.join(pngs, "f034_1.png"))   # the texture's own name
    tex.import_tex(src, pngs, ASSET)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        build(sys.argv[2])
        print("wrote", ASSET)
    elif len(sys.argv) == 3 and sys.argv[1] == "install":
        print("installed" if install(sys.argv[2]) else "already installed")
    else:
        print(__doc__)
