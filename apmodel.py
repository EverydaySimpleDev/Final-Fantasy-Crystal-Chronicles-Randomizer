"""
Item models are dvd/char/fa/fNNN/fNNN_root.chm plus a texture file
fNNN_root.tex, and an item's param.cfd record names its model by that number.
The AP Item uses model 131: f131 is an unused orb that no item, and no .mrg
archive, refers to, so the game loads it from the loose files and replacing
them changes nothing else.

A .chm is a tree of chunks, each a 16-byte header (tag, size, two counts)
followed by its data padded to 16 bytes. The new model is the Gold pouch's
f055_root.chm with only its MESH chunk rebuilt:
    VERT  positions, 3 x s16, scaled by 2^-8 (the QUAN chunk's first value)
    NORM  normals, 3 x s16, scaled by 2^-12
    COLR  one white vertex colour
    UV    texture coordinates, 2 x s16, scaled by 2^-12
    DLHD  one DLST: a 32-byte header (material 0) and a GX display list of
          triangles, each corner being four u16 indices (position, normal,
          colour, uv), counter-clockwise seen from outside.
The texture is f055_root.tex (64x64 CMPR) renamed, holding one patch of each
logo colour. Every ball maps to the middle of its patch.

The balls stand upright in the X/Y plane, facing +Z, with the bottom ball
resting on y = 0 like the pouch does.

Usage:
    py apmodel.py build <game.iso>      (writes assets/ap_model.chm and .tex)
    py apmodel.py install <game.iso>
"""

import math
import os
import struct
import sys

import gciso

MODEL = 131
DISC_CHM = "dvd/char/fa/f131/f131_root.chm"
DISC_TEX = "dvd/char/fa/f131/f131_root.tex"
TEMPLATE_CHM = "dvd/char/fa/f055/f055_root.chm"
TEMPLATE_TEX = "dvd/char/fa/f055/f055_root.tex"
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
ASSET_CHM = os.path.join(ASSETS, "ap_model.chm")
ASSET_TEX = os.path.join(ASSETS, "ap_model.tex")

# (x, y) of each ball's centre on the logo and its colour, going round from
# the top.
BALLS = [
    ((0.0, 1.0), (0xF5, 0xC2, 0xC9)),     # top, red
    ((0.866, 0.5), (0xC5, 0xF1, 0xBF)),   # top right, green
    ((0.866, -0.5), (0xED, 0xC1, 0xF3)),  # bottom right, purple
    ((0.0, -1.0), (0xF5, 0xD8, 0xC2)),    # bottom, orange
    ((-0.866, -0.5), (0xBA, 0xC3, 0xF4)), # bottom left, blue
    ((-0.866, 0.5), (0xF5, 0xEF, 0xC4)),  # top left, yellow
]
RING = 2.5          # distance from the logo's centre to each ball's centre
RADIUS = 0.9        # ball radius
SEGMENTS = 12       # around each ball
RINGS = 8           # pole to pole

VERT_SCALE = 1 << 8
NORM_SCALE = 1 << 12
UV_SCALE = 1 << 12
GX_TRIANGLES = 0x90
TEXTURE_SIZE = 64
CELL_W, CELL_H = 16, 32      # 4 x 2 colour patches on the texture


def _chunk(tag, payload, count=0):
    """One chunk: header plus payload padded to 16 bytes."""
    data = tag + struct.pack(">III", len(payload), count, 0) + payload
    return data + bytes(-len(data) % 16)


def _walk(data, start, end):
    """(tag, header offset, payload size) of each chunk between two offsets."""
    at = start
    while at + 16 <= end:
        tag = data[at:at + 4]
        if not all(0x20 <= c < 0x7F for c in tag):
            break
        size = struct.unpack_from(">I", data, at + 4)[0]
        yield tag, at, size
        at += (16 + size + 15) & ~15


def _find(data, start, end, tag):
    for t, at, size in _walk(data, start, end):
        if t == tag:
            return at, size
    raise ValueError(f"{tag!r} chunk not found")


def _ball(cx, cy):
    """Positions, normals and triangles of one ball centred at (cx, cy)."""
    points = [(0.0, 1.0, 0.0)]
    for r in range(1, RINGS):
        lat = math.pi * r / RINGS
        for s in range(SEGMENTS):
            lon = 2 * math.pi * s / SEGMENTS
            points.append((math.sin(lat) * math.cos(lon), math.cos(lat), math.sin(lat) * math.sin(lon)))
    points.append((0.0, -1.0, 0.0))
    last = len(points) - 1

    def ring_vertex(r, s):
        return 1 + (r - 1) * SEGMENTS + s % SEGMENTS

    triangles = []
    for s in range(SEGMENTS):
        triangles.append((0, ring_vertex(1, s + 1), ring_vertex(1, s)))
        triangles.append((last, ring_vertex(RINGS - 1, s), ring_vertex(RINGS - 1, s + 1)))
    for r in range(1, RINGS - 1):
        for s in range(SEGMENTS):
            a, b = ring_vertex(r, s), ring_vertex(r, s + 1)
            c, d = ring_vertex(r + 1, s), ring_vertex(r + 1, s + 1)
            triangles += [(a, b, d), (a, d, c)]
    positions = [(cx + RADIUS * x, cy + RADIUS * y, RADIUS * z) for x, y, z in points]
    return positions, points, triangles


def _cell_centre(index):
    col, row = index % (TEXTURE_SIZE // CELL_W), index // (TEXTURE_SIZE // CELL_W)
    return ((col + 0.5) * CELL_W / TEXTURE_SIZE, (row + 0.5) * CELL_H / TEXTURE_SIZE)


def mesh_arrays():
    """Every ball's positions, normals and (position, normal, colour, uv)
    index triangles, ready to pack."""
    positions, normals, corners = [], [], []
    lift = RING + RADIUS
    for index, ((x, y), _) in enumerate(BALLS):
        p, n, tris = _ball(x * RING, y * RING + lift)
        base = len(positions)
        positions += p
        normals += n
        for tri in tris:
            corners += [(base + v, base + v, 0, index) for v in tri]
    return positions, normals, corners


def _check_winding(positions, normals, corners):
    for i in range(0, len(corners), 3):
        p = [positions[c[0]] for c in corners[i:i + 3]]
        e1 = [p[1][k] - p[0][k] for k in range(3)]
        e2 = [p[2][k] - p[0][k] for k in range(3)]
        cross = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
        n = [sum(normals[c[1]][k] for c in corners[i:i + 3]) for k in range(3)]
        if sum(cross[k] * n[k] for k in range(3)) <= 0:
            raise AssertionError("a triangle faces inwards")


def build_chm(template):
    """The AP model as .chm bytes, built on the Gold pouch's model."""
    positions, normals, corners = mesh_arrays()
    _check_winding(positions, normals, corners)

    vert = b"".join(struct.pack(">3h", *(round(c * VERT_SCALE) for c in p)) for p in positions)
    norm = b"".join(struct.pack(">3h", *(round(c * NORM_SCALE) for c in n)) for n in normals)
    uv = b"".join(struct.pack(">2h", round(u * UV_SCALE), round(v * UV_SCALE))
                  for u, v in (_cell_centre(i) for i in range(len(BALLS))))
    gx = struct.pack(">BH", GX_TRIANGLES, len(corners)) + b"".join(struct.pack(">4H", *c) for c in corners)
    gx += bytes(-len(gx) % 32)
    dlst = b"DLST" + struct.pack(">III", 32 + len(gx), len(gx), 0) + bytes(32) + gx

    chm_end = 16 + struct.unpack_from(">I", template, 4)[0]
    msst_at, msst_size = _find(template, 16, chm_end, b"MSST")
    mesh_at, mesh_size = _find(template, msst_at + 16, msst_at + 16 + msst_size, b"MESH")
    info_at, info_size = _find(template, mesh_at + 16, mesh_at + 16 + mesh_size, b"INFO")
    info = template[info_at + 16:info_at + 16 + info_size]

    mesh = b"".join([
        _chunk(b"INFO", info),
        _chunk(b"MNAM", b"obj\0"),
        _chunk(b"VERT", vert),
        _chunk(b"NORM", norm),
        _chunk(b"COLR", b"\xff\xff\xff\xff"),
        _chunk(b"UV  ", uv),
        _chunk(b"DLHD", dlst, count=1),
    ])
    msst = _chunk(b"MSST", _chunk(b"MESH", mesh), count=1)
    old_end = msst_at + ((16 + msst_size + 15) & ~15)
    body = template[16:msst_at] + msst + template[old_end:chm_end]
    header = template[:4] + struct.pack(">I", len(body)) + template[8:16]
    return (header + body).replace(b"f055_root", b"f131_root")


def build_tex(template):
    """The colour-patch texture as .tex bytes, built on the pouch's texture."""
    import tex
    pixels = []
    for y in range(TEXTURE_SIZE):
        for x in range(TEXTURE_SIZE):
            index = (y // CELL_H) * (TEXTURE_SIZE // CELL_W) + x // CELL_W
            colour = BALLS[index][1] if index < len(BALLS) else (0xFF, 0xFF, 0xFF)
            pixels.append(colour + (0xFF,))
    image = tex.encode_cmpr(pixels, TEXTURE_SIZE, TEXTURE_SIZE)
    at = template.find(b"IMAG")
    size = struct.unpack_from(">I", template, at + 4)[0]
    if size != len(image) or template.count(b"f055_1") != 1:
        raise ValueError("unexpected Gold pouch texture")
    data = template[:at + 16] + image + template[at + 16 + size:]
    return data.replace(b"f055_1", b"f131_1")


def _read(iso, disc):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, disc)[0]
        f.seek(off)
        return f.read(size)


def build(iso):
    """Rebuild assets/ap_model.chm and assets/ap_model.tex from `iso`."""
    open(ASSET_CHM, "wb").write(build_chm(_read(iso, TEMPLATE_CHM)))
    open(ASSET_TEX, "wb").write(build_tex(_read(iso, TEMPLATE_TEX)))


def install(iso, item_id=None):
    """Put the AP model in place of f131 and, if `item_id` is given, point
    that item at it. Returns False if the model was already there."""
    chm = open(ASSET_CHM, "rb").read()
    texture = open(ASSET_TEX, "rb").read()
    changed = _read(iso, DISC_CHM) != chm
    if changed:
        gciso.put_file(iso, DISC_CHM, chm)
        gciso.put_file(iso, DISC_TEX, texture)
    if item_id is not None:
        import customitem
        customitem.set_item_model(iso, item_id, MODEL)
    return changed


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        build(sys.argv[2])
        print("wrote", ASSET_CHM, "and", ASSET_TEX)
    elif len(sys.argv) == 3 and sys.argv[1] == "install":
        import customitem
        install(sys.argv[2], customitem.AP_SLOT)
        print("installed")
    else:
        print(__doc__)
