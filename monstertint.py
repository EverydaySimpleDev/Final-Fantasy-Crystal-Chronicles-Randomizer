"""
monstertint.py - Give single monsters a colour: their model is tinted and
glows in it. The AP client uses it to mark the enemies whose Monster Hunt
check is still to be done, coloured by the kind of item the check holds.

How a monster is drawn
----------------------
CCharaPcs::CHandle::draw (0x80073F78) draws every character model. Right
before it does, it works out a "shade" colour from the map's light and
shadow under the model (4 bytes at 0x88(r1)) and multiplies it into the
model's own ambient and diffuse light, then sets the ambient light with
LightPcs.SetAmbient. Every model sets its light this way, so a change made
here only affects that one model.

The handle's flags (+8) are a copy of the monster object's m_displayFlags
(CGObject +0x60), made every frame. The game only uses the low bits, so bits
28-30 are free and hold the colour here (0 = none, 1-7 = a COLOURS entry).

What this patch does
--------------------
Two calls into new code, in MetroTRK debugger functions the game never
calls (TRKDoSupportMask to TRKDoConnect, 0x801A9EEC-0x801AA088):

    0x80074344 (both shade paths end here, and the replaced `lis r3, 0x802F`
               is done again at the end):
        if colour: shade.rgb = shade.rgb * colour.rgb / 256     (the hue)
    0x80074408 (the call to LightPcs.SetAmbient, r4 = &ambient):
        if colour: ambient.rgb += colour.rgb * colour.glow / 256 (clamped)
        then on to SetAmbient                                    (the glow)

The colour table sits at the start of that space, as (R, G, B, glow) per
entry, so the client can change colours while the game runs.

Usage:
    py monstertint.py apply <game.iso>
"""

import struct
import sys

import gciso
import randomizer

SHADE_HOOK = 0x80074344
AMBIENT_HOOK = 0x80074408
SET_AMBIENT = 0x80049268
CAVE = 0x801A9EEC
CAVE_END = 0x801AA088
COLOUR_SHIFT = 28               # m_displayFlags bits 28-30: the colour, 0 = none
COLOUR_MASK = 7 << COLOUR_SHIFT
COLOUR_COUNT = 7
TABLE = CAVE                    # COLOUR_COUNT x (R, G, B, glow), written by the client
GLOW = 150
DISPLAY_FLAGS = 0x60            # CGObject m_displayFlags

_SHADE_ORIG = 0x3C60802F        # lis r3, -0x7fd1


# PowerPC encodings used below
def _d_form(op, d, a, imm):
    return (op << 26) | (d << 21) | (a << 16) | (imm & 0xFFFF)


def _x_form(d, a, b, xo):
    return (31 << 26) | (d << 21) | (a << 16) | (b << 11) | (xo << 1)


def _rlwinm(a, s, sh, mb, me, rc=0):
    return (21 << 26) | (s << 21) | (a << 16) | (sh << 11) | (mb << 6) | (me << 1) | rc


def _lwz(d, a, off): return _d_form(32, d, a, off)
def _lbz(d, a, off): return _d_form(34, d, a, off)
def _stb(s, a, off): return _d_form(38, s, a, off)
def _addis(d, a, imm): return _d_form(15, d, a, imm)
def _addi(d, a, imm): return _d_form(14, d, a, imm)
def _cmplwi(a, imm): return _d_form(10, 0, a, imm)
def _add(d, a, b): return _x_form(d, a, b, 266)
def _mullw(d, a, b): return _x_form(d, a, b, 235)
def _srwi(a, s, n): return _rlwinm(a, s, 32 - n, n, 31)
def _slwi(a, s, n): return _rlwinm(a, s, n, 0, 31 - n)


def _branch(kind, frm, to):
    """b / bl, or beq / ble (conditional on cr0)."""
    if kind in ("b", "bl"):
        return (18 << 26) | ((to - frm) & 0x3FFFFFC) | (kind == "bl")
    bo, bi = {"beq": (12, 2), "ble": (4, 1)}[kind]
    return (16 << 26) | (bo << 21) | (bi << 16) | ((to - frm) & 0xFFFC)


_BLR = 0x4E800020


def _assemble(start, program):
    """Words from `program`: ints, label names, and (branch kind, label or
    address) pairs."""
    labels, pos = {}, start
    for item in program:
        if isinstance(item, str):
            labels[item] = pos
        else:
            pos += 4
    out, pos = bytearray(), start
    for item in program:
        if isinstance(item, str):
            continue
        if isinstance(item, tuple):
            kind, target = item
            item = _branch(kind, pos, labels.get(target, target))
        out += struct.pack(">I", item)
        pos += 4
    return bytes(out)


def _find_colour(none_label):
    """r12 = &TABLE[colour - 1] for the handle in r26, or go to none_label."""
    base = TABLE - 4
    return [_lwz(0, 26, 8),
            _rlwinm(12, 0, 32 - COLOUR_SHIFT, 29, 31, rc=1),
            ("beq", none_label),
            _slwi(12, 12, 2),
            _addis(11, 0, (base + 0x8000) >> 16),
            _addi(11, 11, base & 0xFFFF),
            _add(12, 11, 12)]


def _shade_code(start):
    program = _find_colour("done")
    for i in range(3):
        program += [_lbz(0, 1, 0x88 + i), _lbz(11, 12, i), _mullw(0, 0, 11), _srwi(0, 0, 8),
                    _stb(0, 1, 0x88 + i)]
    program += ["done", _SHADE_ORIG, _BLR]
    return _assemble(start, program)


def _ambient_code(start):
    program = _find_colour("set") + [_lbz(9, 12, 3)]
    for i in range(3):
        program += [_lbz(0, 12, i), _mullw(0, 0, 9), _srwi(0, 0, 8),
                    _lbz(10, 4, i), _add(0, 0, 10),
                    _cmplwi(0, 255), ("ble", f"keep{i}"), _addi(0, 0, 255),
                    f"keep{i}", _stb(0, 4, i)]
    program += ["set", ("b", SET_AMBIENT)]
    return _assemble(start, program)


def table_bytes(colours):
    """The colour table for `colours`, a list of up to COLOUR_COUNT (R, G, B)
    or None (no tint)."""
    out = bytearray()
    for colour in (list(colours) + [None] * COLOUR_COUNT)[:COLOUR_COUNT]:
        out += bytes((*colour, GLOW)) if colour else bytes((255, 255, 255, 0))
    return bytes(out)


def _code():
    """(the new code with an empty colour table, shade routine address,
    ambient routine address)."""
    table = table_bytes([])
    shade_at = CAVE + len(table)
    shade = _shade_code(shade_at)
    ambient_at = shade_at + len(shade)
    ambient = _ambient_code(ambient_at)
    blob = table + shade + ambient
    if CAVE + len(blob) > CAVE_END:
        raise ValueError("the monster tint code doesn't fit its space")
    return blob, shade_at, ambient_at


def _dol_offsets(iso, *addrs):
    """Offsets in Start.dol of the given addresses."""
    with open(iso, "rb") as f:
        dol_off, _ = gciso.dol_span(f)
        f.seek(dol_off)
        header = f.read(0xE4)
    offsets = struct.unpack(">18I", header[0:72])
    starts = struct.unpack(">18I", header[72:144])
    sizes = struct.unpack(">18I", header[144:216])
    out = []
    for addr in addrs:
        for off, start, size in zip(offsets, starts, sizes):
            if size and start <= addr < start + size:
                out.append(off + addr - start)
                break
        else:
            raise ValueError(f"0x{addr:08x} isn't in Start.dol")
    return out


def _read_dol(iso, offset, size):
    with open(iso, "rb") as f:
        dol_off, _ = gciso.dol_span(f)
        f.seek(dol_off + offset)
        return f.read(size)


# TRKDoSupportMask starts with `li r3, 0` and `blr` in the game
_CAVE_START = bytes.fromhex("386000004e800020")


def apply(iso, apply=True):
    """Install the monster tint (see the module docstring). Returns True once
    it is in place. Raises if the hooked code or the debugger functions
    aren't the game's own (wrong game version, or another patch uses them)."""
    blob, shade_at, ambient_at = _code()
    cave, shade, ambient = _dol_offsets(iso, CAVE, SHADE_HOOK, AMBIENT_HOOK)
    hooks = [
        (shade, struct.pack(">I", _SHADE_ORIG), struct.pack(">I", _branch("bl", SHADE_HOOK, shade_at))),
        (ambient, struct.pack(">I", _branch("bl", AMBIENT_HOOK, SET_AMBIENT)),
         struct.pack(">I", _branch("bl", AMBIENT_HOOK, ambient_at))),
    ]
    if all(_read_dol(iso, at, 4) == new for at, _, new in hooks):
        return True
    current = _read_dol(iso, cave, len(blob))
    if not current.startswith(_CAVE_START):
        raise ValueError("the MetroTRK functions the monster tint uses are already patched")
    # The table is data the client writes, so the cave is written as a whole.
    return randomizer._dol_patch(iso, [(cave, current, blob)] + hooks, "monster-tint", apply)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "apply":
        apply(sys.argv[2])
        print("monster tint installed")
    else:
        print(__doc__)
