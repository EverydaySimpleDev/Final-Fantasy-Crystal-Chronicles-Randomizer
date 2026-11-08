"""
lynarinorth.py - Lynari Desert North Exit (Dungeon Shortcuts option): a
quicksand pit at the north end of Lynari Desert's first area (desert_0) that
drops you into the second area (desert_1).

The game only links the two areas through quicksand: desert_0's jump 2 (the
east pit, 913, -1515) drops you at desert_1 entry 1, and desert_1's jump 0
(a pit near its south edge) drops you back at desert_0 entry 4. The north end
of desert_0 is a dead end between two rock pillars, although desert_1's
entry 0 (-242, -2982) lies just past it in the same coordinates.

Script (dvd/cft/desert_0.cft). A map exit is a MapJump object (director:
createMapJumpQuad(n)) handled by three switch(this.m0) blocks:
  initMapJump    the trigger (addQuad corners from floor y, height) and the
                 line the players sink along (resetLineVertex /
                 addLineVertex, engine line slots 0-15). desert_0 uses
                 slots 0-3 and 11-15, so the new exit uses slot 10.
  onPushMapJump  what happens on contact (quicksand: isFall for every player)
                 and `this.m16 = line`
  mainMapJump    loads the next area with an entry number (G59)
This adds jump 4: the trigger and the sinking are copies of desert_0's
quicksand pit 0 at the new spot, and the load is a copy of its case 2
(desert_1) with entry 1 changed to 0.

Map (dvd/map/stg014/):
  map000_1.mpl   a copy of the quicksand overlay mesh with only one pit
                 above ground (OWN_PAIR)
  map000.otm     the pillars' scene node shows that copy instead
  map000_0.mpl   the pillars' drop shadows are removed
  map000.mid     the invisible wall along the bushes in front of the pit is
                 removed, and the floor under the pit lets a sinking player
                 through (SINK_FACE)
Only the script and map000_1.mpl change size.

    py lynarinorth.py <iso>         # patches the ISO in place (use a copy)
"""

import struct
import sys

import cft
import cftpatch as cp
import gciso
import otm

DESERT_0 = "dvd/cft/desert_0.cft"
MAP = "dvd/map/stg014/map000.otm"
JUMP = 4                  # the new MapJump id
LINE = 10                 # a free engine line slot in desert_0
PIT = (-237.0, -2764.0)   # centre of the new pit, between the pillars
HALF = 11.0               # half the trigger's width (the game's pits use 8)

# desert_0's pit 0 (case 0) -> the new pit: |x|, |z| and the quad's half width
TRIGGER = {436.6: -PIT[0], 1087.3: -PIT[1], 8.0: HALF}
G59_VAR = 0x3b            # permanent var index of G59 (the entry number) in desert_0

MPL = "dvd/map/stg014/map000_0.mpl"
SHADOW_PAIR = 37          # plants and drop shadows of the whole area ...
SHADOW_VERTS = range(16)  # ... whose first 16 vertices (12 triangles, used by nothing else) are the pillars' shadows
SHADOW_BOX = (-275.0, -178.0, -2820.0, -2743.0)   # x0, x1, z0, z1 they lie in

ROCK_NODE = 149           # the two pillars
ROCK_PAIR, SAND_PAIR = 47, 44
# The overlay mesh draws all four pits, so the new pit gets its own copy of
# it (mesh pair 49, appended to the last mesh file) with every vertex outside
# pit 1 sent far underground. Its VSET + DSET are copied whole, with the
# colour table padded by 16 bytes so the display lists stay 32-byte aligned.
MPL_LAST = "dvd/map/stg014/map000_1.mpl"
OWN_PAIR = 49             # = the number of meshes the map had
PIT1_RADIUS = 60.0        # pit 1's vertices (each pit is a separate island of 61)
UNDERGROUND = -3000.0
# The scale has to be the same on every axis: the engine uses the model-view
# matrix itself as the normal matrix (no inverse-transpose, no renormalising),
# so a flattened y would also flatten the normals and leave the overlay unlit.
# At 0.3 the swirl is too faint to see, and at 1.0 it covers the bushes and
# the cactus.
SAND_SCALE = (0.5, 0.5, 0.5)
SAND_CENTRE = (-742.41, 11.75, -1871.63)    # pit 1's overlay (bounding-box centre)
SAND_MID = 12.0           # height of its middle ...
SAND_FLOOR = 0.5          # ... placed just above the sand there (y 0-0.9)

# Collision (dvd/map/stg014/map000.mid): the bushes in front of the pit stand
# on a line of wall faces (group 31) from the west cliff to the cactus. Moved
# to group 34, which the area script gives mask 0 (collides with nothing).
MID = "dvd/map/stg014/map000.mid"
WALL_GROUP, OPEN_GROUP = 31, 34
WALL_BOX = (-268.0, -215.0, -2774.0, -2739.0)   # x0, x1, z0, z1 holding the whole faces
WALL_FACES = 8
# The floor triangle under the pit's centre. A sinking player's ground mask is 1
# (setCharaBgMask(1)) and floor group 6's mask has bit 0, so on plain floor
# the player would stay standing. Group 16 (mask 108, the invisible exit
# walls, which only towns change) lacks bit 0. It is solid for anyone
# walking, but a sinking player drops through. The game's own pits also turn
# the player in a circle while sinking, but this one doesn't.
SINK_FACE = ((-241.8, -2760.0), (-198.0, -2760.3), (-224.8, -2800.0))
FLOOR_GROUP, SINK_GROUP = 6, 16


def _read(iso, disc):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, disc)[0]
        f.seek(off)
        return f.read(size)


def _script(data):
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".cft")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    try:
        return cp.Script(path)
    finally:
        os.remove(path)


def _relabel(script, fn, old, new):
    """Give `case old` of `fn` the label `new` (same size)."""
    code = bytearray(script.code(fn))
    hdr = cp.find_case(code, old)[0]
    code[hdr + 2:hdr + 6] = struct.pack(">i", new)
    script.set_code(fn, code)


def _rewrite_case(script, fn, case, floats=None, ints=None, after_var=None):
    """Change constants inside `case` of `fn`: PUSHF values by |value| from
    `floats`, PUSHI values from `ints`, and with after_var=(var, value) the
    PUSHI right after a GETA of that permanent var. Returns what was found."""
    code = bytearray(script.code(fn))
    _, start, end, _ = cp.find_case(code, case)
    ins = list(cft.disasm(code[start:end]))
    seen = set()
    for k, (o, op, a) in enumerate(ins):
        o += start
        if op == 0x04 and floats:
            v = round(struct.unpack(">f", struct.pack(">i", a))[0], 2)
            if v in floats:
                code[o + 1:o + 5] = struct.pack(">f", floats[v])
                seen.add(v)
        elif op == 0x03 and ints and a in ints:
            code[o + 1:o + 5] = struct.pack(">i", ints[a])
            seen.add(("int", a))
        elif op == 0x03 and after_var and k and ins[k - 1][1] == 0x01 and ins[k - 1][2] >> 8 == after_var[0]:
            code[o + 1:o + 5] = struct.pack(">i", after_var[1])
            seen.add("var")
    script.set_code(fn, code)
    return seen


def _clone_case(dst, fn, src, log):
    """Add a copy of dst's own `case src` of `fn` as case JUMP."""
    own = _script(dst.to_bytes())
    _relabel(own, fn, src, JUMP)
    cp.add_case(dst, own, fn, JUMP, {i: i for i in range(4096)}, log)


def build_script(desert_0):
    """desert_0.cft bytes with the north pit's jump added."""
    dst = _script(desert_0)
    if JUMP in cp.switch_ids(dst.code("mainMapJump")):
        return desert_0                                  # already there
    log = []
    _clone_case(dst, "initMapJump", 0, log)
    seen = _rewrite_case(dst, "initMapJump", JUMP, floats=TRIGGER, ints={11: LINE})
    assert seen == set(TRIGGER) | {("int", 11)}, seen
    _clone_case(dst, "onPushMapJump", 0, log)
    assert _rewrite_case(dst, "onPushMapJump", JUMP, ints={11: LINE}) == {("int", 11)}
    _clone_case(dst, "mainMapJump", 2, log)              # desert_1, entry 1 ...
    assert _rewrite_case(dst, "mainMapJump", JUMP, after_var=(G59_VAR, 0)) == {"var"}   # ... entry 0

    # director: createMapJumpQuad(4) after createMapJumpQuad(9)
    code = dst.code("director")
    ins = list(cft.disasm(code))
    k = next(k for k, (o, op, a) in enumerate(ins)
             if op == 0x0A and dst.names[a & 0xFFFF] == "createMapJumpQuad" and ins[k - 1][2] == 9)
    call = b"\x03" + struct.pack(">i", JUMP) + code[ins[k][0]:ins[k + 1][0] + 1]
    cp.insert_code(dst, "director", ins[k + 1][0] + 1, call, log)
    return dst.to_bytes()


def build_map(map000):
    """map000.otm bytes with the pillars swapped for a small quicksand overlay."""
    root = otm.Chunk.parse(map000, 0)
    nodes = [k for k in root.find(b"SCEN").items if isinstance(k, otm.Chunk) and k.type == b"NODE"]
    sub = {k.type: k for k in nodes[ROCK_NODE].items if isinstance(k, otm.Chunk)}
    pidx = bytearray(sub[b"PIDX"].items[0])
    pair = struct.unpack(">H", pidx[2:4])[0]
    if pair not in (ROCK_PAIR, SAND_PAIR, OWN_PAIR):
        raise ValueError(f"map000.otm node {ROCK_NODE} shows mesh {pair}, not the pillars ({ROCK_PAIR})")
    pidx[2:4] = struct.pack(">H", OWN_PAIR)
    sub[b"PIDX"].set_content(pidx)
    sx, sy, sz = SAND_SCALE
    t = (PIT[0] - sx * SAND_CENTRE[0], SAND_FLOOR - sy * SAND_MID, PIT[1] - sz * SAND_CENTRE[2])
    sub[b"TFRM"].set_content(struct.pack(">9f", *t, 0.0, 0.0, 0.0, sx, sy, sz))
    out = root.serialize()
    assert len(out) == len(map000)
    return out


def build_shadows(mpl):
    """map000_0.mpl bytes with the pillars' drop shadows collapsed to one point
    under the ground (same size)."""
    from stagemap import _chunk_list
    pair, vert = -1, None
    for t, o, s, _ in _chunk_list(mpl, 16, len(mpl)):
        if t == b"VSET":
            vert = next(((oo, ss) for tt, oo, ss, _ in _chunk_list(mpl, o, o + s) if tt == b"VERT"), None)
        elif t == b"DSET":
            pair += 1
            if pair == SHADOW_PAIR:
                break
    else:
        raise ValueError(f"map000_0.mpl has no mesh pair {SHADOW_PAIR}")
    out = bytearray(mpl)
    under = struct.pack(">3f", PIT[0], -50.0, PIT[1])
    x0, x1, z0, z1 = SHADOW_BOX
    for i in SHADOW_VERTS:
        o = vert[0] + 12 * i
        x, y, z = struct.unpack(">3f", out[o:o + 12])
        if bytes(out[o:o + 12]) == under:
            continue                                     # already moved
        if not (x0 < x < x1 and z0 < z < z1):
            raise ValueError(f"mesh {SHADOW_PAIR} vertex {i} ({x:.0f}, {z:.0f}) isn't a pillar shadow")
        out[o:o + 12] = under
    return bytes(out)


def _mesh_records(mpl):
    """[(VSET start, DSET end)] of each mesh in an .mpl file (one MESH
    container of VSET/DSET pairs), offsets of the chunk headers."""
    from stagemap import _chunk_list
    out, vset = [], None
    for t, o, s, _ in _chunk_list(mpl, 16, len(mpl)):
        if t == b"VSET":
            vset = o - 16
        elif t == b"DSET":
            out.append((vset, o + s + (-s % 16)))
    return out


def build_own_mesh(mpl0, mpl1):
    """map000_1.mpl bytes with a pit-1-only copy of the overlay mesh appended."""
    import numpy as np
    from stagemap import _chunk_list
    first = len(_mesh_records(mpl0))
    last = _mesh_records(mpl1)
    if first + len(last) > OWN_PAIR:
        return mpl1                                      # already there
    assert first + len(last) == OWN_PAIR and first > SAND_PAIR, (first, len(last))
    start, end = _mesh_records(mpl0)[SAND_PAIR]
    rec = bytearray(mpl0[start:end])
    vsize = struct.unpack_from(">I", rec, 4)[0]
    subs = {t: (o - start, s) for t, o, s, _ in _chunk_list(mpl0, start + 16, start + 16 + vsize)}

    vo, vs = subs[b"VERT"]
    v = np.frombuffer(bytes(rec[vo:vo + vs]), ">f4").reshape(-1, 3).copy()
    far = np.hypot(v[:, 0] - SAND_CENTRE[0], v[:, 2] - SAND_CENTRE[2]) > PIT1_RADIUS
    v[far, 1] = UNDERGROUND
    rec[vo:vo + vs] = v.astype(">f4").tobytes()

    # 16 more bytes of colour (unused entries) so the copy's display lists keep
    # their 32-byte alignment at the new offset
    pad = (start - len(mpl1)) % 32
    if pad:
        co, cs = subs[b"COLR"]
        hdr = co - 16
        old = cs + (-cs % 16)
        grown = rec[co:co + cs] + rec[co + cs - 4:co + cs] * 4
        chunk = rec[hdr:hdr + 4] + struct.pack(">I", len(grown)) + rec[hdr + 8:hdr + 16] + grown
        chunk += b"\x00" * (-len(chunk) % 16)
        assert len(chunk) - 16 - old == pad == 16
        rec[hdr:co + old] = chunk
        struct.pack_into(">I", rec, 4, vsize + pad)
    out = bytearray(mpl1) + rec
    struct.pack_into(">I", out, 4, len(out) - 16)        # the MESH container
    return bytes(out)


def build_walls(mid):
    """map000.mid bytes with the bush wall in front of the pit made passable
    (same size). File faces are 56 bytes: ..., group at +19, vertex indices
    (u16 x3) at +48."""
    from stagemap import _chunk_list

    def hits(start, end):
        found = {}
        for t, o, s, n in _chunk_list(mid, start, end):
            if t in (b"HITV", b"HITF"):
                found[t] = (o, n)
            if t in (b"MID ", b"SCEN", b"HIT "):
                yield from hits(o, o + s)
        if len(found) == 2:
            yield found[b"HITV"], found[b"HITF"]

    out = bytearray(mid)
    x0, x1, z0, z1 = WALL_BOX
    sink = sorted(SINK_FACE)
    found = sunk = 0
    for (vo, vn), (fo, fn) in hits(0, len(mid)):
        verts = [struct.unpack_from(">3f", mid, vo + 12 * i) for i in range(vn)]
        for i in range(fn):
            o = fo + 56 * i
            p = [verts[k] for k in struct.unpack_from(">3H", mid, o + 48)]
            if out[o + 19] in (FLOOR_GROUP, SINK_GROUP) and \
                    sorted((round(v[0], 1), round(v[2], 1)) for v in p) == sink:
                out[o + 19] = SINK_GROUP
                sunk += 1
            if out[o + 19] not in (WALL_GROUP, OPEN_GROUP):
                continue
            if (x0 < min(v[0] for v in p) and max(v[0] for v in p) < x1
                    and z0 < min(v[2] for v in p) and max(v[2] for v in p) < z1):
                out[o + 19] = OPEN_GROUP
                found += 1
    if found != WALL_FACES:
        raise ValueError(f"map000.mid: found {found} bush wall faces, expected {WALL_FACES}")
    if sunk != 1:
        raise ValueError(f"map000.mid: found {sunk} floor faces under the pit, expected 1")
    return bytes(out)


def patch(iso):
    done = False
    mpl0 = _read(iso, MPL)
    steps = ((DESERT_0, build_script), (MPL_LAST, lambda data: build_own_mesh(mpl0, data)),
             (MAP, build_map), (MPL, build_shadows), (MID, build_walls))
    for disc, build in steps:
        data = _read(iso, disc)
        new = build(data)
        if new != data:
            gciso.put_file(iso, disc, new)
            done = True
    return done


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print("north pit added" if patch(sys.argv[1]) else "already patched")
