"""
chestcolors.py - Gold chests for important items, and AP chests for items
that come from Archipelago instead of out of the chest.

Every dungeon chest is model f034 (dvd/char/fa/f034), loaded by each dungeon
script's initTreasureBox as loadModel(3, 34, 0, -1). The third argument picks
a texture variant: 0 is f034_root.tex, 1 is f034_root_b.tex, 2 is _c, and so
on (the farm cows use this for their coats, loadModel(3, 14, 1-9, -1)). The
chest only ships with the first one, so this adds three as new files:
    1  f034_root_b.tex  gold
    2  f034_root_c.tex  the plain chest with the Archipelago logo
    3  f034_root_d.tex  the gold chest with the Archipelago logo
An AP chest opens empty, because its loot slot holds item 0, just like the
game's own empty chests. The client sees the chest's opened flag and sends
the check.

Which chest looks which way:
A chest's SPAWN_TBOX record [mask, A, 0, B, x, y, z, rot] is shared by all
three cycles, and its loot case is only the low 16 bits of A (bits 0x10000
and 0x20000 are flags the game reads, and no vanilla chest uses a higher
bit).
So A gets two more bits per cycle, the gold bit and the AP bit above it:
    Cycle 1: 0x40000  / 0x80000
    Cycle 2: 0x100000 / 0x200000
    Cycle 3: 0x400000 / 0x800000
that is 0x40000 << slot and 0x80000 << slot, where slot is what getIdxSet()
returns once the AP patch has fixed it to 0 / 2 / 4 (see treasure.py).

SPAWN_TBOX hands A to the new chest through a scratch global that the rest of
the script reuses, and only beginTreasureBox runs while it still holds A. It
keeps the loot case as this.m17 = A & 0xFFFF. initTreasureBox, which loads the
model, runs later. So beginTreasureBox keeps the new bits too
(this.m17 = A & 0xFCFFFF, get_treasure only looks at the low 16 bits), and
initTreasureBox asks for texture variant
    (this.m17 >> (18 + getIdxSet())) & 3
so in each cycle the chest's two bits for that cycle pick its look.

The pictures are assets/chest_gold.png and assets/ap_item.png (the logo).
`build` turns them into assets/chest_gold.tex, chest_ap.tex and
chest_ap_gold.tex, which the patcher copies onto the disc.

Usage:
    py chestcolors.py build  <game.iso>   # rebuild the .tex files from the PNGs
    py chestcolors.py install <game.iso>  # add the chest textures to an ISO
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
ASSETS = os.path.join(HERE, "assets")
PICTURE = os.path.join(ASSETS, "chest_gold.png")
LOGO = os.path.join(ASSETS, "ap_item.png")

CHEST_TEXTURE = "dvd/char/fa/f034/f034_root.tex"
# texture variant -> (file on the disc, asset)
TEXTURES = {
    1: ("dvd/char/fa/f034/f034_root_b.tex", os.path.join(ASSETS, "chest_gold.tex")),
    2: ("dvd/char/fa/f034/f034_root_c.tex", os.path.join(ASSETS, "chest_ap.tex")),
    3: ("dvd/char/fa/f034/f034_root_d.tex", os.path.join(ASSETS, "chest_ap_gold.tex")),
}

# The bits in a chest's A that make it gold, or an AP chest, in each cycle.
GOLD_BITS = {1: 0x40000, 2: 0x100000, 3: 0x400000}
AP_BITS = {cycle: bit << 1 for cycle, bit in GOLD_BITS.items()}
ALL_GOLD_BITS = sum(GOLD_BITS.values())
ALL_BITS = ALL_GOLD_BITS | sum(AP_BITS.values())

# Item classes that get a gold chest. Traps look important too, so players
# open them.
GOLD_CLASSES = {"progression", "useful", "trap"}

# Where the logo goes on the chest texture (256 x 128): (centre x, centre y,
# size, half). Both ends of the chest use the same panel, so one logo there
# shows on the left and the right. The front is drawn from one half of the
# texture mirrored at x = 79 (the middle of the chest), so only the right
# half of the logo is drawn there and the mirror makes it whole.
LOGO_SPOTS = [
    (151.5, 105, 30, False),   # the end panels
    (79, 113, 24, True),       # the front, under the clasp
]

# loadModel(3, 34, 0, -1): the chest model, texture variant 0
_LOAD_CHEST = bytes.fromhex("0300000003" "0300000022" "0300000000" "03ffffffff")
# beginTreasureBox: this.m17 = A & 0xFFFF  (address of this.m17, A, the mask, AND, store)
_CASE_MASK = bytes.fromhex("030000ffff1f0d")
_NEW_MASK = struct.pack(">BI", 0x03, 0xFFFF | ALL_BITS) + bytes.fromhex("1f0d")
_ADD, _OR, _AND, _SHIFT_RIGHT = 0x19, 0x1E, 0x1F, 0x21


def install(iso):
    """Add the chest textures to `iso`. False if they were already there."""
    added = False
    for disc, asset in TEXTURES.values():
        added |= bool(gciso.add_file(iso, disc, open(asset, "rb").read()))
    return added


def gold_bits(cycles):
    """The A bits for a chest that is gold in `cycles`."""
    return sum(GOLD_BITS[c] for c in cycles)


def ap_bits(cycles):
    """The A bits for a chest that is an AP chest in `cycles`."""
    return sum(AP_BITS[c] for c in cycles)


def patch_script(path):
    """Make the chests in the .cft at `path` pick their texture from their
    gold and AP bits. Returns the new file bytes, or None when the script has
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
        return None                             # the texture choice is already there

    # beginTreasureBox: keep the gold and AP bits in this.m17
    begin = bytearray(s.code("beginTreasureBox"))
    mask = begin.find(_CASE_MASK)
    if mask < 10 or begin[mask - 10] != 0x01:
        raise ValueError(f"{os.path.basename(path)}: beginTreasureBox doesn't look as expected")
    member = begin[mask - 9:mask - 5]           # the "address of this.m17" operand
    begin[mask:mask + len(_CASE_MASK)] = _NEW_MASK
    s.set_code("beginTreasureBox", begin)

    call_idxset = bytes([0x0A]) + struct.pack(">I", 0xFFFF0000 | s.names.index("getIdxSet"))
    # stack: 0, this.m17, 18 + getIdxSet()  ->  0, m17 >> it  ->  0, that & 3
    #        ->  0 | that
    expr = (b"\x00" + member + bytes.fromhex("0300000012") + call_idxset
            + bytes([_ADD, _SHIFT_RIGHT]) + bytes.fromhex("0300000003")
            + bytes([_AND, _OR]))
    cftpatch.insert_code(s, "initTreasureBox", variant_end, expr, [])
    return s.to_bytes()


def _with_logo(picture):
    """`picture` (a 256 x 128 chest texture) with the Archipelago logo on it."""
    from PIL import Image
    im = picture.convert("RGBA")
    logo = Image.open(LOGO).convert("RGBA")
    for cx, cy, size, half in LOGO_SPOTS:
        part = logo.resize((size, size), Image.LANCZOS)
        left = round(cx - size / 2)
        if half:
            part = part.crop((size // 2, 0, size, size))
            left = round(cx)
        im.alpha_composite(part, (left, round(cy - size / 2)))
    return im


def build(iso):
    """Rebuild the chest textures in assets/ from the chest texture in `iso`,
    assets/chest_gold.png and the logo."""
    import tex
    from PIL import Image
    work = tempfile.mkdtemp()
    src = os.path.join(work, "f034_root.tex")
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, CHEST_TEXTURE)[0]
        f.seek(off)
        open(src, "wb").write(f.read(size))
    plain_dir = os.path.join(work, "plain")
    tex.export_tex(src, plain_dir)
    plain = Image.open(os.path.join(plain_dir, "f034_1.png"))
    gold = Image.open(PICTURE)
    for variant, picture in ((1, gold), (2, _with_logo(plain)), (3, _with_logo(gold))):
        pngs = os.path.join(work, str(variant))
        os.makedirs(pngs)
        picture.save(os.path.join(pngs, "f034_1.png"))      # the texture's own name
        tex.import_tex(src, pngs, TEXTURES[variant][1])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        build(sys.argv[2])
        print("wrote", ", ".join(asset for _, asset in TEXTURES.values()))
    elif len(sys.argv) == 3 and sys.argv[1] == "install":
        print("installed" if install(sys.argv[2]) else "already installed")
    else:
        print(__doc__)
