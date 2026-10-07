"""
worldzones.py - EXPERIMENTAL: shuffle which dungeon each world-map node leads to.

A "node" is a dungeon's spot on the world map (named here by the dungeon that
sits there in vanilla). Putting dungeon D on node N changes, all in place
(same file sizes, NTSC-US, offsets verified against the disc):

  world.cft  mainBasha, node N:
               display block  WM_mapInfoDispOn args (D's name/Myrrh bubble, elements)
               zone block     MJ_SWING_* args (D's stage script, music, ...)
             MJ_SWING_ATTRIB_1/_2, for 1- and 2-element nodes: node N's case
               checks D's "cleared" event flag (200 + D's display index)
  world.cfd  1- and 2-element nodes: the post-clear menu shows D's name
             (name value 0x20 + D's display index)
  D's .cft   every exit, and the boss room's post-boss exit, returns the
             caravan to node N's world param instead of D's own - otherwise the
             map desyncs from where the caravan is and it can't move.

What stays with the node: its MJ_SWING variant, the elements offered after a
Myrrh drop, and anything that gates reaching it (Miasma Streams, Goblin
Wall's Year-2 visibility). So the element progression stays like vanilla;
only which dungeon you enter changes.

Mount Kilanda (entered through several 4-argument MJ_SWING calls, and its
exits work differently) and Mount Vellenge are not included.

See Documentation/Randomizing World Loading Zones.md.
"""

import os
import random
import re
import struct
import tempfile

import gciso

WORLD_CFT = "dvd/cft/world.cft"
WORLD_CFD = "dvd/cft/world.cfd"

# script: (name, world param, display index DD, elements EE,
#          display offset, zone offset, zone values (XX, MM, NN, YY, ZZ),
#          ATTRIB switch offset or None, world.cfd name offset or None)
# Offsets are where the node that this dungeon sits on in vanilla keeps them.
DUNGEONS = {
    "river":  ("River Belle Path",       0x02, 0x00, 0x06, 0x46217, 0x46246, (0x89, 0x96, 0x64, 0x68, 0x0D), 0x33146, 0x13A6B),
    "gob":    ("Goblin Wall",            0x07, 0x01, 0x09, 0x4717B, 0x471AA, (0x8C, 0xA6, 0x74, 0x69, 0x0D), 0x3318D, 0x13AD9),
    "mine":   ("The Mine of Cathuriges", 0x10, 0x02, 0x01, 0x487F7, 0x48826, (0x92, 0xA4, 0x72, 0x6A, 0x6E), 0x334C1, 0x13C56),
    "kinoko": ("The Mushroom Forest",    0x11, 0x03, 0x02, 0x48928, 0x48957, (0x93, 0xAE, 0x7C, 0x6B, 0x6F), 0x33486, 0x13C06),
    "ruin":   ("Tida",                   0x17, 0x04, 0x0C, 0x4A041, 0x4A070, (0x99, 0xB8, 0x86, 0x6C, 0x70), 0x331D4, 0x13B47),
    "gigas":  ("Moschet Manor",          0x1A, 0x05, 0x03, 0x4A877, 0x4A8A6, (0x9B, 0x9F, 0x6D, 0x6D, 0x71), 0x3321B, 0x13BB5),
    "water":  ("Veo Lu Sluice",          0x21, 0x09, 0x00, 0x4B190, 0x4B1BF, (0x9E, 0xB5, 0x83, 0x6E, 0x72), None,    None),
    "cave":   ("Selepation Cave",        0x2B, 0x08, 0x04, 0x4BF2B, 0x4BF5A, (0xA2, 0xB6, 0x84, 0x6F, 0x73), 0x334FC, 0x13CA6),
    "fort":   ("Daemon's Court",         0x2E, 0x07, 0x00, 0x4C7CE, 0x4C7FD, (0xA4, 0xA5, 0x73, 0x70, 0x74), None,    None),
    "swamp":  ("Conall Curach",          0x34, 0x0B, 0x00, 0x4D000, 0x4D02F, (0xA6, 0x9A, 0x68, 0x73, 0x77), None,    None),
    "city":   ("Rebena Te Ra",           0x36, 0x0C, 0x00, 0x4D66E, 0x4D69D, (0xA7, 0xB7, 0x85, 0x74, 0x78), None,    None),
    "desert": ("Lynari Desert",          0x51, 0x0A, 0x08, 0x4E45E, 0x4E48D, (0xAD, 0xAA, 0x78, 0x72, 0x76), 0x33537, 0x13CF7),
}
BY_NAME = {v[0]: k for k, v in DUNGEONS.items()}


def _name(s): return DUNGEONS[s][0]
def _param(s): return DUNGEONS[s][1]
def _dd(s): return DUNGEONS[s][2]


def display_bytes(s):
    _, _, dd, ee, *_ = DUNGEONS[s]
    return bytes([3, 0, 0, 0, dd, 3, 0, 0, 0, ee])


def zone_bytes(s):
    xx, mm, nn, yy, zz = DUNGEONS[s][6]
    return bytes([5, 0, 0, 0, xx, 3, 0, 0, 0, 0, 3, 0, 0, 0, mm, 3, 0, 0, 0, nn,
                  3, 0, 0, 1, yy, 3, 0, 0, 0, zz])


def completion_flag(s):
    """The event flag set when dungeon `s` is cleared (checked by the node's
    MJ_SWING_ATTRIB case): 200 + its display index."""
    return 200 + _dd(s)


def name_ref(s):
    """world.cfd stage-name value for dungeon `s`: 0x20 + its display index."""
    return 0x20 + _dd(s)


def call_offset(node):
    """The node's MJ_SWING_* call (right after its zone block and 2 padding pushes)."""
    return DUNGEONS[node][5] + 40


# ---------------------------------------------------------------------------
# Plans: {node script: dungeon script}
# ---------------------------------------------------------------------------

def vanilla_plan():
    return {s: s for s in DUNGEONS}


def complete_plan(fixed):
    """Turn a partial {node: dungeon} into a full one-to-one plan: every
    other node keeps its own dungeon when that dungeon is still free, and
    otherwise gets a leftover one - so each dungeon appears exactly once."""
    plan = dict(fixed)
    used = set(plan.values())
    if len(used) != len(plan):
        raise ValueError("_world_zones: the same dungeon is placed on two nodes")
    free = [s for s in DUNGEONS if s not in used]
    for node in DUNGEONS:
        if node in plan:
            continue
        pick = node if node in free else free[0]
        plan[node] = pick
        free.remove(pick)
    return plan


def random_plan(rng, fixed=None):
    """Shuffle all 12 dungeons over the 12 nodes; `fixed` placements are kept."""
    fixed = dict(fixed or {})
    nodes = [n for n in DUNGEONS if n not in fixed]
    left = [s for s in DUNGEONS if s not in fixed.values()]
    rng.shuffle(left)
    plan = dict(zip(nodes, left))
    plan.update(fixed)
    return plan


def normalize(spec):
    """{node (dungeon name or script): dungeon (name or script)} -> {node script:
    dungeon script}; entries that name the node's own dungeon are dropped."""
    def key(v):
        v = str(v).strip()
        if v.lower() in DUNGEONS:
            return v.lower()
        hit = next((s for s, d in DUNGEONS.items() if d[0].lower() == v.lower()), None)
        if hit is None:
            raise ValueError(f"_world_zones: {v!r} is not one of: {', '.join(d[0] for d in DUNGEONS.values())}")
        return hit
    out = {}
    for k, v in spec.items():
        node, dungeon = key(k), key(v)
        if node != dungeon:
            out[node] = dungeon
    return out


def plan_text(plan):
    lines = ["World-map loading zones (EXPERIMENTAL):"]
    for node, dungeon in plan.items():
        mark = "" if node == dungeon else "   (moved)"
        lines.append(f"  {_name(node) + ' node':34s} -> {_name(dungeon)}{mark}")
    return lines


# ---------------------------------------------------------------------------
# ISO access
# ---------------------------------------------------------------------------

def _read(iso, disc):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, disc)[0]
        f.seek(off)
        return bytearray(f.read(size))


def _write(iso, disc, data):
    with open(iso, "r+b") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, disc)[0]
        if len(data) != size:
            raise ValueError(f"{disc}: size changed, refusing to write")
        f.seek(off)
        f.write(data)


def _area_discs(iso, script):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    rx = re.compile(rf"^dvd/cft/{script}_(\d+)\.cft$", re.I)
    return sorted((p for p, _, _ in files if rx.match(p)),
                  key=lambda p: int(rx.match(p).group(1)))


def status(iso):
    """{node: dungeon} as the ISO currently has it (by each node's display
    index, which is unique per dungeon). None for a node that isn't recognised."""
    w = _read(iso, WORLD_CFT)
    by_dd = {_dd(s): s for s in DUNGEONS}
    out = {}
    for node, d in DUNGEONS.items():
        off = d[4]
        blk = bytes(w[off:off + 10])
        out[node] = by_dd.get(blk[4]) if blk[:4] == b"\x03\x00\x00\x00" and blk[5:9] == b"\x03\x00\x00\x00" else None
    return out


# Exit patterns in a dungeon's own scripts. `ID` is the world param the exit
# sends the caravan to.
#   stage exit:     01 00 00 3D 09 03 00 00 00 ID 0D 0C 04 00 00 00 00 0A FF FF 00 28 0C
#   post-boss exit: 03 00 00 00 ID 0D 0C 03 00 00 00 1E 0A FF FF 00 01 0C
def _exit_offsets(data, param):
    p = bytes([param])
    exit_rx = re.compile(re.escape(bytes.fromhex("0100003D0903000000") + p +
                                   bytes.fromhex("0D0C04000000000AFFFF00280C")))
    boss_rx = re.compile(re.escape(bytes.fromhex("03000000") + p +
                                   bytes.fromhex("0D0C030000001E0AFFFF00010C")))
    return sorted([m.start() + 9 for m in exit_rx.finditer(data)] +
                  [m.start() + 4 for m in boss_rx.finditer(data)])


def apply_plan(iso, plan, log=None):
    """Write `plan` ({node: dungeon}) into `iso` in place. The ISO's loading
    zones must still be vanilla (re-applying the same plan is a no-op).
    Returns the log."""
    log = [] if log is None else log
    plan = complete_plan(plan)
    cur = status(iso)
    if cur == plan:
        log.append("World zones: already placed as requested - no changes")
        return log
    if cur != vanilla_plan():
        raise ValueError("loading-zone shuffle needs an ISO whose world-map zones are still "
                         "vanilla; start from a fresh copy of the source ISO")
    w = _read(iso, WORLD_CFT)
    cfd = _read(iso, WORLD_CFD)
    # verify every byte we will overwrite is what we expect before touching anything
    for node, d in DUNGEONS.items():
        _, _, _, _, doff, zoff, _, aoff, coff = d
        checks = [(w, doff, display_bytes(node)), (w, zoff, zone_bytes(node))]
        if aoff is not None:
            checks.append((w, aoff, bytes([completion_flag(node)])))
        if coff is not None:
            checks.append((cfd, coff, bytes([name_ref(node)])))
        for buf, off, want in checks:
            if bytes(buf[off:off + len(want)]) != want:
                raise ValueError(f"{node}: unexpected bytes at 0x{off:x} - wrong game version?")
    exit_edits = {}
    for node, dungeon in plan.items():
        if node == dungeon:
            continue
        _, _, _, _, doff, zoff, _, aoff, coff = DUNGEONS[node]
        w[doff:doff + 10] = display_bytes(dungeon)
        w[zoff:zoff + 30] = zone_bytes(dungeon)
        if aoff is not None:
            w[aoff] = completion_flag(dungeon)
        if coff is not None:
            cfd[coff] = name_ref(dungeon)
        # the dungeon's exits now return to this node
        total = 0
        for disc in _area_discs(iso, dungeon):
            data = exit_edits.get(disc) or _read(iso, disc)
            offs = _exit_offsets(data, _param(dungeon))
            for o in offs:
                data[o] = _param(node)
            if offs:
                exit_edits[disc] = data
            total += len(offs)
        if not total:
            raise ValueError(f"{dungeon}: no exits found to redirect")
        log.append(f"{_name(node)} node -> {_name(dungeon)} ({total} exit(s) redirected)")
    _write(iso, WORLD_CFT, w)
    _write(iso, WORLD_CFD, cfd)
    for disc, data in exit_edits.items():
        _write(iso, disc, data)
    return log


# ---------------------------------------------------------------------------
# World-map building icons
#
# Each world-map stop's building is a flat card (picture + ground shadow): one
# mesh part (a VSET/DSET pair) in the world map's mesh file. Its picture is one
# 128x128 cell of a 4x4 "plate" texture (material 4 = w7_plate, material 5 =
# w13_plate2), chosen by the part's UVs: s16, 1024 = one texture width, so a
# cell is 256. v is negative and wraps, so
#   col = (u % 1024) // 256,   row = 3 - (-v // 256)
# Start.dol's crest table (also used by the save screen) holds each place's
# cell as [plate, col, row, 0], indexed by the dungeon's display index DD.
# Changing a stop's building = shifting its part's UVs to another cell (and
# switching the material if the cell is on the other plate). Same file size.
# Confirmed in game 2026-10-06 (Tipa's stop showing River Belle Path's art).
# ---------------------------------------------------------------------------

WORLD_MPL = "dvd/map/stg033/map000_0.mpl"
# node -> mesh part holding that node's building (its vanilla crest = node's DD)
ICON_PART = {"river": 3, "gob": 25, "mine": 7, "kinoko": 5, "ruin": 10, "gigas": 11,
             "water": 12, "cave": 16, "fort": 17, "swamp": 18, "city": 19, "desert": 22}
CREST_TABLE_DOL = 0x1D8214          # 25 x [plate, col, row, 0] (RAM 0x801DB214)
PLATE_MATERIAL = {1: 4, 2: 5}
MATERIAL_PLATE = {4: 1, 5: 2}


def _chunks(data, start, end):
    """[(tag, payload_offset, size)] for the 16-byte-header chunks in data[start:end]."""
    out, p = [], start
    while p + 16 <= end:
        tag = bytes(data[p:p + 4])
        size = struct.unpack(">I", data[p + 4:p + 8])[0]
        if tag != b"\0\0\0\0":
            out.append((tag, p + 16, size))
        p += 16 + size
        p += (16 - p % 16) % 16
    return out


def _icon_layout(mpl, part):
    """(uv_offset, uv_count, [DLST payload offsets]) for mesh part `part`."""
    kids = _chunks(mpl, 16, len(mpl))
    (vtag, voff, vsize), (dtag, doff, dsize) = kids[2 * part], kids[2 * part + 1]
    if vtag != b"VSET" or dtag != b"DSET":
        raise ValueError(f"world-map mesh part {part}: unexpected layout")
    uv = [(o, s) for t, o, s in _chunks(mpl, voff, voff + vsize) if t == b"UV  "]
    dl = [o2 for t, o, s in _chunks(mpl, doff, doff + dsize) if t == b"DLHD"
          for t2, o2, s2 in _chunks(mpl, o, o + s) if t2 == b"DLST"]
    if len(uv) != 1 or not dl:
        raise ValueError(f"world-map mesh part {part}: no UVs or display list")
    return uv[0][0], uv[0][1] // 4, dl


def _icon_cell(mpl, part):
    uvo, n, dl = _icon_layout(mpl, part)
    uvs = [struct.unpack(">hh", mpl[uvo + 4 * k:uvo + 4 * k + 4]) for k in range(n)]
    mat = struct.unpack(">H", mpl[dl[0]:dl[0] + 2])[0]
    if mat not in MATERIAL_PLATE:
        raise ValueError(f"world-map mesh part {part}: material {mat} is not a plate")
    col = (min(u for u, _ in uvs) % 1024) // 256
    row = 3 - (((-max(v for _, v in uvs)) // 256) % 4)
    return MATERIAL_PLATE[mat], col, row


def crest_cells(iso):
    """[(plate, col, row)] for crest table entries 0-24, from the ISO's Start.dol."""
    with open(iso, "rb") as f:
        off, _ = gciso.dol_span(f)
        f.seek(off + CREST_TABLE_DOL)
        raw = f.read(100)
    return [tuple(raw[4 * i:4 * i + 3]) for i in range(25)]


def icon_status(iso):
    """{node: dungeon whose building the node shows} (None if unrecognised)."""
    mpl = _read(iso, WORLD_MPL)
    cells = crest_cells(iso)
    by_cell = {cells[_dd(s)]: s for s in DUNGEONS}
    return {node: by_cell.get(_icon_cell(mpl, part)) for node, part in ICON_PART.items()}


def apply_icons(iso, plan, log=None):
    """Make each node's world-map building show the dungeon `plan` puts there.
    Works from each part's current cell, so re-applying is a no-op."""
    log = [] if log is None else log
    plan = complete_plan(plan)
    mpl = _read(iso, WORLD_MPL)
    cells = crest_cells(iso)
    changed = 0
    for node, dungeon in plan.items():
        part = ICON_PART[node]
        uvo, n, dl = _icon_layout(mpl, part)
        cplate, ccol, crow = _icon_cell(mpl, part)
        tplate, tcol, trow = cells[_dd(dungeon)]
        if tplate not in PLATE_MATERIAL:
            raise ValueError(f"crest table entry {_dd(dungeon)}: bad plate {tplate} - wrong game version?")
        if (cplate, ccol, crow) == (tplate, tcol, trow):
            continue
        du = (tcol - ccol) * 256 + (tplate - cplate) * 1024
        dv = (trow - crow) * 256           # higher row = less negative v
        for k in range(n):
            u, v = struct.unpack(">hh", mpl[uvo + 4 * k:uvo + 4 * k + 4])
            mpl[uvo + 4 * k:uvo + 4 * k + 4] = struct.pack(">hh", u + du, v + dv)
        for o in dl:
            mpl[o:o + 2] = struct.pack(">H", PLATE_MATERIAL[tplate])
        changed += 1
    if changed:
        _write(iso, WORLD_MPL, mpl)
    log.append(f"World-map icons: {changed} stop building(s) updated")
    return log


def stage_lock_sites(plan, base_sites):
    """Stage-key call sites for a shuffled map. `base_sites` is randomizer's
    _STAGE_LOCK_SITES ((script, call offset, stage id, forward func), keyed by
    the dungeon that gets locked). Each shuffled dungeon is locked at the node
    it now sits on: that node's call, D's stage id (its zone STR index), and
    the node's own MJ_SWING variant."""
    plan = complete_plan(plan)
    node_of = {d: n for n, d in plan.items()}
    out = []
    for script, off, stage_id, fwd in base_sites:
        if script in DUNGEONS:
            node = node_of[script]
            node_fwd = next((f for s, o, _, f in base_sites if s == node), None)
            if node_fwd is None:            # the always-open river node isn't in the list
                node_fwd = 594
            out.append((script, call_offset(node), DUNGEONS[script][6][0], node_fwd))
        else:
            out.append((script, off, stage_id, fwd))
    return out
