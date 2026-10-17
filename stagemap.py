"""
stagemap.py - top-down map images of the dungeons, drawn from the game's own
stage geometry and textures, with the pixel position of every chest.

Each dungeon area loads dvd/map/stgSSS/mapMMM (see Documentation/Map Folders
by Stage.md):

  mapMMM_K.mpl  geometry; the files read as one chunk stream in K order: VSET
                (VERT f32 x/y/z, COLR RGBA8, UV f32 or s16/1024) and DSET
                (DLHD > DLST display lists) pairs, a DSET using the most
                recent VSET. A DLST starts with a u16 material index; its GX
                draw stream is the last `field1` bytes of the chunk. A vertex
                is four u16 indices (position, normal, colour, UV), or five
                when its material has two textures.
  mapMMM.otm    scene graph and materials. SCEN > NODE: PIDX (parent, pair
                index, flags) and TFRM (translation, rotation in degrees with
                R = Rz.Ry.Rx, scale); world = parent world . T.R.S, parents
                first. SCEN > MSET > MATL: TIDX (texture indices, count in
                field1).
  mapMMM_K.mtx  textures, one list in K order: TSET > TXTR (NAME, FMT, SIZE
                width/height, IMAG). Formats 0 (RGBA8) and 6 (CMPR).

Vertex positions are in the same world coordinates as the SPAWN_TBOX
records, so a chest's pixel position comes straight from its spawn position.

The map is drawn from above (x to the right, z down) with a height buffer, so
the highest surface at each pixel wins: textures, multiplied by the vertex
colours (the baked lighting), darkened a little by slope. Dark areas are
brightened afterwards so every map is easy to read. Faces that point
down (the inside of the sky dome) are left out, and so is anything well above
the highest chest or monster (ceilings, roofs, tall overhanging props), so
indoor rooms show their floor. Black occluder planes (materials named
black* / kuro*) that hide what's outside a room are left out too. The image is
cropped to where the area's chests and monsters are.

Drawn on top of each area:
  exits      a box at each exit saying where it leads. Exits come from the
             area script: each MapJump case in onPushMapJump points the camera
             at the exit (cam_mode 102, x, y, z), and the same case in
             mainMapJump loads the next script with an entry number (G59).
             A passage between two areas gets the same letter at both ends
             ("a -> Area 2" here, "a -> Area 1" there): the exits from A to B
             and from B to A are paired in order of their entry numbers.
             Exits to the boss and the world map have no letter.
             Reading them needs the CFlat decompiler (tools/cflat/cflat.py in
             the decomp project, found next to this repo or via FFCC_CFLAT);
             without it the exits are left off.
  hotspots   a diamond in the element's colour (SPAWN_HOT_SPOT type
             1 Fire, 2 Water, 3 Wind, 4 Earth, 5 Unknown)
  monsters   a letter per monster type at each spawn, with a legend
For the tracker, each dungeon is drawn in several variants (VARIANTS: with or
without hotspot icons, and with no enemy letters, all of them or one cycle's),
so the pack can switch between them.

    py stagemap.py render ISO SCRIPT AREA out.png    # one area, chests marked
    py stagemap.py tracker ISO OUT_DIR               # every dungeon + stagemaps.json

stagemaps.json: {dungeon: {"img": plain image, "variants": {suffix: image},
                           "size": [w, h], "pins": {chest number: [[x, y], ...]}}}
(a chest with several possible spots has several pins; a monster's cycles
come from its SPAWN record's cycle bits, the same bits chests use).
"""

import collections
import importlib.util
import itertools
import json
import math
import os
import re
import struct
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import chestflags
import gciso
import otm
import randomizer
import spawn_map

# dungeon script -> dvd/map/stgSSS folder; area N loads mapN unless listed here
STAGES = {"river": 23, "gob": 24, "mine": 3, "kinoko": 16, "ruin": 25, "gigas": 26,
          "lava": 15, "fort": 28, "cave": 27, "water": 29, "desert": 14, "swamp": 2,
          "city": 30, "meteo": 31}
AREA_MAPS = {("water", 0): [0, 2]}       # Veo Lu Sluice's field loads two maps
ROTATE = {("gigas", 2): 1}               # quarter turns clockwise, so the throne faces down
SKIP_PAIRS = {("gigas", 1): {1}}         # the copy of the room seen in its mirror

TILE = 1100           # longest side of one area's image, in pixels
TRACKER_SCALE = 0.75  # tracker images are saved at this size, to keep the pack small
TRACKER_QUALITY = 72  # JPEG quality of the tracker images
MARGIN = 0.12         # extra space around the chests and monsters, per side
MIN_SPAN = 500        # smallest area width shown, in world units
CEILING = 90          # faces starting this far above the highest spawn are left out
BACKGROUND = (14, 16, 22)
LIGHT = 1 / 160       # vertex colour scale: 160 is full brightness
TARGET_BRIGHTNESS = 200   # dark maps are brightened until most of them is below this
MAX_GAIN = 2.5
GLOW = 2              # material blend mode of lights, light beams and mist (left out)
OCCLUDER = re.compile(r"^(black|kuro)", re.I)   # black planes that hide the outside of a room

CFLAT = os.environ.get("FFCC_CFLAT") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Decomp", "reference-decomp", "tools", "cflat")
ELEMENTS = {1: ("Fire", (235, 75, 55)), 2: ("Water", (60, 145, 245)), 3: ("Wind", (80, 205, 115)),
            4: ("Earth", (215, 175, 60)), 5: ("Unknown", (185, 115, 235))}

GX_TRIANGLES = (0x90, 0x91, 0x92)
GX_STRIPS = (0x98, 0x99, 0x9A)


def _chunk_list(data, start, end):
    """[(tag, payload offset, size, field1)] for the 16-byte-header chunks in data[start:end]."""
    out, p = [], start
    while p + 16 <= end:
        tag = bytes(data[p:p + 4])
        size, field1 = struct.unpack(">II", data[p + 4:p + 12])
        if tag != b"\0\0\0\0":
            out.append((tag, p + 16, size, field1))
        p += 16 + size
        p += (16 - p % 16) % 16
    return out


def _gx_triangles(stream, k):
    """Triangles [(v0, v1, v2)] of index tuples from a GX draw stream whose
    vertices have k u16 indices, or None if the stream doesn't fit k."""
    tris, p, n = [], 0, len(stream)
    while p < n:
        op = stream[p]
        if op == 0:                       # padding at the end
            if any(stream[p:]):
                return None
            break
        if op not in GX_TRIANGLES + GX_STRIPS or p + 3 > n:
            return None
        count = struct.unpack(">H", stream[p + 1:p + 3])[0]
        p += 3
        if p + count * 2 * k > n:
            return None
        v = [struct.unpack(">" + "H" * k, stream[p + 2 * k * i:p + 2 * k * (i + 1)]) for i in range(count)]
        p += count * 2 * k
        if op in GX_TRIANGLES:
            tris += [(v[i], v[i + 1], v[i + 2]) for i in range(0, count - 2, 3)]
        else:
            tris += [(v[i - (i % 2)], v[i - ((i + 1) % 2)], v[i + 1]) for i in range(1, count - 1)]
    return [t for t in tris if len({t[0][0], t[1][0], t[2][0]}) == 3]


def _decode_rgba8(raw, w, h):
    img = np.zeros((h, w, 4), np.uint8)
    p = 0
    for ty in range(0, h, 4):
        for tx in range(0, w, 4):
            ar = np.frombuffer(raw[p:p + 32], np.uint8).reshape(16, 2)
            gb = np.frombuffer(raw[p + 32:p + 64], np.uint8).reshape(16, 2)
            block = np.stack([ar[:, 1], gb[:, 0], gb[:, 1], ar[:, 0]], 1).reshape(4, 4, 4)
            img[ty:ty + 4, tx:tx + 4] = block[:min(4, h - ty), :min(4, w - tx)]
            p += 64
    return img


def _rgb565(c):
    return np.array([(c >> 11) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31, 255], np.int32)


def _decode_cmpr(raw, w, h):
    img = np.zeros((h, w, 4), np.uint8)
    p = 0
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            for sy, sx in ((0, 0), (0, 4), (4, 0), (4, 4)):
                c0, c1 = struct.unpack(">HH", raw[p:p + 4])
                a, b = _rgb565(c0), _rgb565(c1)
                if c0 > c1:
                    pal = [a, b, (2 * a + b) // 3, (a + 2 * b) // 3]
                else:
                    pal = [a, b, (a + b) // 2, np.array([0, 0, 0, 0], np.int32)]
                bits = raw[p + 4:p + 8]
                for row in range(4):
                    for col in range(4):
                        y, x = ty + sy + row, tx + sx + col
                        if y < h and x < w:
                            img[y, x] = pal[(bits[row] >> (6 - col * 2)) & 3]
                p += 8
    return img


class Stage:
    """Read access to one dvd/map/stgSSS folder of an ISO."""

    def __init__(self, iso, stage):
        self.iso, self.stage = iso, stage
        with open(iso, "rb") as f:
            _, files = gciso.parse_fst(f)
        prefix = f"dvd/map/stg{stage:03d}/"
        self.files = {p: (o, s) for p, o, s in files if p.startswith(prefix)}
        self._textures = {}

    def read(self, name):
        o, s = self.files[f"dvd/map/stg{self.stage:03d}/{name}"]
        with open(self.iso, "rb") as f:
            f.seek(o)
            return f.read(s)

    def has(self, name):
        return f"dvd/map/stg{self.stage:03d}/{name}" in self.files

    def materials(self, mp):
        """[[texture index, ...]] by material index, from the .otm's MSET."""
        return [tex for tex, _, _ in self.material_info(mp)]

    def material_info(self, mp):
        """[([texture index, ...], blend mode, name)] by material index. The
        blend mode is ATRB byte 4: 4 = opaque, 2 = additive glow (lights, light
        beams, mist), 0/1/5 = other surfaces."""
        root = otm.Chunk.parse(self.read(f"map{mp:03d}.otm"), 0)
        out = []
        for m in root.find(b"MSET").items:
            if not isinstance(m, otm.Chunk) or m.type != b"MATL":
                continue
            raw = m.items[0] if isinstance(m.items[0], bytes) else m.content()
            sub = {t: (o, s, f1) for t, o, s, f1 in _chunk_list(raw, 0, len(raw))}
            tex = []
            if b"TIDX" in sub:
                o, _, count = sub[b"TIDX"]
                tex = list(struct.unpack(f">{count}I", raw[o:o + 4 * count]))
            mode = raw[sub[b"ATRB"][0] + 4] if b"ATRB" in sub and sub[b"ATRB"][1] > 4 else 4
            name = raw[sub[b"NAME"][0]:sub[b"NAME"][0] + sub[b"NAME"][1]].split(b"\0")[0].decode(
                "latin1") if b"NAME" in sub else ""
            out.append((tex, mode, name))
        return out

    def textures(self, mp):
        """[(rgba array or None)] in texture index order (formats 0 and 6 are decoded)."""
        if mp in self._textures:
            return self._textures[mp]
        out, k = [], 0
        while self.has(f"map{mp:03d}_{k}.mtx"):
            data = self.read(f"map{mp:03d}_{k}.mtx")
            last = False
            for t, o, s, f1 in _chunk_list(data, 0, len(data)):
                if t != b"TSET":
                    continue
                last = f1 == 1
                for t2, o2, s2, _ in _chunk_list(data, o, o + s):
                    if t2 != b"TXTR":
                        continue
                    sub = {x[0]: x for x in _chunk_list(data, o2, o2 + s2)}
                    fmt = data[sub[b"FMT "][1]]
                    w, h = struct.unpack(">II", data[sub[b"SIZE"][1]:sub[b"SIZE"][1] + 8])
                    raw = data[sub[b"IMAG"][1]:sub[b"IMAG"][1] + sub[b"IMAG"][2]]
                    if fmt == 0:
                        out.append(_decode_rgba8(raw, w, h))
                    elif fmt == 6:
                        out.append(_decode_cmpr(raw, w, h))
                    else:
                        out.append(None)
            k += 1
            if last:
                break
        self._textures[mp] = out
        return out

    def pairs(self, mp):
        """[{"verts", "cols", "uvs", "tris": [(material, v0, v1, v2)]}] by pair index."""
        mats = self.materials(mp)
        stream, k = [], 0
        while self.has(f"map{mp:03d}_{k}.mpl"):
            data = self.read(f"map{mp:03d}_{k}.mpl")
            stream += [(data, t, o, s) for t, o, s, _ in _chunk_list(data, 16, len(data))]
            k += 1
        out, vset = [], None
        for data, t, o, s in stream:
            if t == b"VSET":
                sub = {tt: (oo, ss) for tt, oo, ss, _ in _chunk_list(data, o, o + s)}
                vset = {"verts": None, "cols": None, "uv_raw": None}
                if b"VERT" in sub:
                    vo, vs = sub[b"VERT"]
                    vset["verts"] = np.frombuffer(data[vo:vo + vs], ">f4").reshape(-1, 3).astype(float)
                if b"COLR" in sub:
                    co, cs = sub[b"COLR"]
                    vset["cols"] = np.frombuffer(data[co:co + cs], np.uint8).reshape(-1, 4)[:, :3].astype(float)
                if b"UV  " in sub:
                    uo, us = sub[b"UV  "]
                    vset["uv_raw"] = data[uo:uo + us]
            elif t == b"DSET" and vset is not None:
                tris = []
                for t2, o2, s2, _ in _chunk_list(data, o, o + s):
                    if t2 != b"DLHD":
                        continue
                    for t3, o3, s3, f1 in _chunk_list(data, o2, o2 + s2):
                        if t3 != b"DLST":
                            continue
                        mat = struct.unpack(">H", data[o3:o3 + 2])[0]
                        gx = data[o3 + s3 - f1:o3 + s3]
                        k5 = mat < len(mats) and len(mats[mat]) >= 2
                        found = _gx_triangles(gx, 5 if k5 else 4) or _gx_triangles(gx, 4 if k5 else 5) or []
                        tris += [(mat, a, b, c) for a, b, c in found]
                out.append(dict(vset, tris=tris))
        for p in out:
            p["uvs"] = _uvs(p["uv_raw"], max((v[3] for _, *vs in p["tris"] for v in vs), default=-1))
        return out

    def instances(self, mp):
        """[(pair index, 4x4 world matrix)] from the map's scene graph."""
        root = otm.Chunk.parse(self.read(f"map{mp:03d}.otm"), 0)
        nodes = [k for k in root.find(b"SCEN").items if isinstance(k, otm.Chunk) and k.type == b"NODE"]
        world, out = [], []
        for node in nodes:
            sub = {k.type: k.items[0] for k in node.items if isinstance(k, otm.Chunk)}
            pidx = sub.get(b"PIDX", b"\xff\xff\xff\x00")
            parent = struct.unpack(">H", pidx[:2])[0]
            pair = struct.unpack(">H", pidx[2:4])[0] if len(pidx) >= 6 else 0xFFFF
            t = struct.unpack(">9f", sub[b"TFRM"][:36]) if b"TFRM" in sub else (0,) * 6 + (1,) * 3
            m = np.eye(4)
            m[:3, :3] = _rotation(*t[3:6]) @ np.diag(t[6:9])
            m[:3, 3] = t[:3]
            m = world[parent] @ m if parent < len(world) else m
            world.append(m)
            if pair < 0xFFF0:
                out.append((pair, m))
        return out


def _uvs(raw, max_index):
    """The UV array as Nx2 floats: f32 pairs, or s16 pairs / 1024 when the f32
    reading is too short for the indices used or gives unreasonable values."""
    if raw is None:
        return None
    if len(raw) // 8 > max_index:
        f = np.frombuffer(raw[:len(raw) // 8 * 8], ">f4").reshape(-1, 2).astype(float)
        if np.all(np.isfinite(f)) and np.abs(f).max(initial=0) < 256:
            return f
    return np.frombuffer(raw[:len(raw) // 4 * 4], ">i2").reshape(-1, 2) / 1024.0


def _rotation(rx, ry, rz):
    rx, ry, rz = (math.radians(a) for a in (rx, ry, rz))
    x = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    y = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    z = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    return z @ y @ x


class _Canvas:
    """Top-down rasteriser with a height buffer (the highest surface wins)."""

    def __init__(self, width, height):
        self.rgb = np.zeros((height, width, 3), np.float32)
        self.rgb[:] = BACKGROUND
        self.top = np.full((height, width), -np.inf, np.float32)

    def triangle(self, xy, heights, cols, uv=None, tex=None):
        h, w = self.top.shape
        x0, y0 = np.floor(xy.min(0)).astype(int)
        x1, y1 = np.ceil(xy.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w - 1), min(y1, h - 1)
        if x0 > x1 or y0 > y1:
            return
        (ax, ay), (bx, by), (cx, cy) = xy
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-9:
            return
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        l1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        l2 = 1 - l0 - l1
        inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not inside.any():
            return
        z = l0 * heights[0] + l1 * heights[1] + l2 * heights[2]
        region = self.top[y0:y1 + 1, x0:x1 + 1]
        draw = inside & (z > region)
        if not draw.any():
            return
        shade = (l0[..., None] * cols[0] + l1[..., None] * cols[1] + l2[..., None] * cols[2])
        if tex is not None and uv is not None:
            u = l0 * uv[0, 0] + l1 * uv[1, 0] + l2 * uv[2, 0]
            v = l0 * uv[0, 1] + l1 * uv[1, 1] + l2 * uv[2, 1]
            th, tw = tex.shape[:2]
            texel = tex[(np.floor(v * th).astype(int)) % th, (np.floor(u * tw).astype(int)) % tw]
            draw &= texel[..., 3] >= 128
            colour = texel[..., :3].astype(np.float32) * shade * LIGHT
        else:
            colour = shade
        sub = self.rgb[y0:y1 + 1, x0:x1 + 1]
        sub[draw] = colour[draw]
        region[draw] = z[draw]

    def image(self):
        """The finished map, brightened so the brighter part of what was drawn
        sits at a normal level (dark dungeons stay readable)."""
        drawn = np.isfinite(self.top)
        rgb = self.rgb
        if drawn.any():
            bright = np.percentile(rgb[drawn].max(1), 90)
            gain = min(max(TARGET_BRIGHTNESS / max(bright, 1), 1.0), MAX_GAIN)
            rgb = rgb.copy()
            rgb[drawn] *= gain
        return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def _draw(canvas, stage, maps, bounds, ceiling, to_px, skip=None):
    """Draw every upward face inside bounds that starts below `ceiling`.
    `skip` is {map: {pair index, ...}} left out."""
    x0, z0, x1, z1 = bounds
    for mp in maps:
        pairs = stage.pairs(mp)
        info = stage.material_info(mp)
        mats = [tex for tex, _, _ in info]
        hidden = {i for i, (_, mode, name) in enumerate(info) if mode == GLOW or OCCLUDER.match(name)}
        textures = stage.textures(mp)
        for pair, world in stage.instances(mp):
            if pair >= len(pairs) or pair in (skip or {}).get(mp, ()):
                continue
            p = pairs[pair]
            verts, cols, uvs = p["verts"], p["cols"], p["uvs"]
            if verts is None or cols is None or not p["tris"]:
                continue                  # uncoloured: backdrop planes outside the play area
            wv = (np.c_[verts, np.ones(len(verts))] @ world.T)[:, :3]
            for mat, a, b, c in p["tris"]:
                if mat in hidden:
                    continue              # see-through lights and mist, black occluder planes
                idx = [a[0], b[0], c[0]]
                if max(idx) >= len(wv) or max(a[2], b[2], c[2]) >= len(cols):
                    continue
                q = wv[idx]
                if q[:, 0].max() < x0 or q[:, 0].min() > x1 or q[:, 2].max() < z0 or q[:, 2].min() > z1:
                    continue
                if q[:, 1].min() > ceiling:
                    continue
                n = np.cross(q[1] - q[0], q[2] - q[0])
                length = np.linalg.norm(n)
                if length == 0 or n[1] / length < 0.15:
                    continue              # walls, ceilings, the inside of the sky dome
                shade = cols[[a[2], b[2], c[2]]] * (0.75 + 0.25 * n[1] / length)
                tex = uv = None
                tex_ids = mats[mat] if mat < len(mats) else []
                if tex_ids and tex_ids[0] < len(textures) and textures[tex_ids[0]] is not None \
                        and uvs is not None and max(a[3], b[3], c[3]) < len(uvs):
                    tex, uv = textures[tex_ids[0]], uvs[[a[3], b[3], c[3]]]
                else:
                    shade = shade * 160 / 255     # untextured: vertex colour alone
                xy = np.array([to_px(x, z) for x, _, z in q])
                canvas.triangle(xy, q[:, 1], shade, uv, tex)


def render_area(iso, script, disc, area, tile=TILE):
    """(image, to_pixel(x, z)) for one dungeon area file."""
    tmp = os.path.join(tempfile.gettempdir(), "stagemap_" + os.path.basename(disc))
    randomizer._extract(iso, disc, tmp)
    spots = [(c["world"]["x"], c["world"]["y"], c["world"]["z"]) for c in spawn_map.chests(tmp)]
    spots += [(m["world"]["x"], m["world"]["y"], m["world"]["z"]) for m in spawn_map.monsters(tmp)]
    pts = np.array(spots, float)
    ceiling = pts[:, 1].max() + CEILING
    x0, z0 = pts[:, [0, 2]].min(0)
    x1, z1 = pts[:, [0, 2]].max(0)
    grow = [max(0.0, (MIN_SPAN - (x1 - x0)) / 2), max(0.0, (MIN_SPAN - (z1 - z0)) / 2)]
    x0, x1, z0, z1 = x0 - grow[0], x1 + grow[0], z0 - grow[1], z1 + grow[1]
    pad = MARGIN * max(x1 - x0, z1 - z0)
    x0, z0, x1, z1 = x0 - pad, z0 - pad, x1 + pad, z1 + pad
    scale = tile / max(x1 - x0, z1 - z0)
    w, h = int((x1 - x0) * scale), int((z1 - z0) * scale)
    turns = ROTATE.get((script, area), 0) % 4

    def to_px(x, z):
        px, py = (x - x0) * scale, (z - z0) * scale
        return [(px, py), (h - py, px), (w - px, h - py), (py, w - px)][turns]

    canvas = _Canvas(*((h, w) if turns % 2 else (w, h)))
    maps = AREA_MAPS.get((script, area), [area])
    _draw(canvas, Stage(iso, STAGES[script]), maps, (x0, z0, x1, z1), ceiling, to_px,
          {mp: SKIP_PAIRS.get((script, mp), ()) for mp in maps})
    return canvas.image(), to_px


def _decompiler():
    """The decomp project's CFlat decompiler module, or None if it isn't there."""
    path = os.path.join(CFLAT, "cflat.py")
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location("ffcc_cflat", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _number(text):
    """A number as the decompiler writes it (negatives as -.N), or None for an
    expression (an exit placed relative to the player)."""
    text = text.strip()
    try:
        return -float(text[2:]) if text.startswith("-.") else float(text)
    except ValueError:
        return None


def _m0_cases(lines):
    """{case: [lines]} of the first `switch (this.m0)` block in decompiled lines."""
    start = next((i for i, l in enumerate(lines) if "switch (this.m0)" in l), None)
    if start is None:
        return {}
    indent = len(lines[start]) - len(lines[start].lstrip())
    cases, current = {}, None
    for line in lines[start + 1:]:
        depth = len(line) - len(line.lstrip())
        if line.strip() == "}" and depth == indent:
            break
        m = re.match(r"\s*case (\d+):", line)
        if m and depth == indent + 4:
            current = int(m.group(1))
            cases[current] = []
        elif current is not None:
            cases[current].append(line)
    return cases


def exit_quads(stage, maps):
    """[(x, z)] - the centre of every exit trigger in an area's collision
    data: mapMMM.mid > MID > SCEN > HIT holds HITV (f32 x/y/z vertices) and
    HITF (56-byte faces: plane, 8 attribute bytes, two edge vectors, three
    u16 vertex indices). Exit faces have attribute byte 3 = 0x10 and come in
    pairs (one quad per exit)."""
    out = []
    for mp in maps:
        if not stage.has(f"map{mp:03d}.mid"):
            continue
        data = stage.read(f"map{mp:03d}.mid")

        def hits(start=0, end=len(data)):
            """(HITV, HITF) of every HIT block - a map can have several, e.g.
            Moschet Manor's doors each have their own before the room's."""
            found = {}
            for t, o, s, f1 in _chunk_list(data, start, end):
                if t in (b"HITV", b"HITF"):
                    found[t] = (o, f1)
                if t in (b"MID ", b"SCEN", b"HIT "):
                    yield from hits(o, o + s)
            if len(found) == 2:
                yield found[b"HITV"], found[b"HITF"]

        for verts, faces in hits():
            v = np.frombuffer(data[verts[0]:verts[0] + 12 * verts[1]], ">f4").reshape(-1, 3)
            exits = []
            for i in range(faces[1]):
                rec = data[faces[0] + 56 * i:faces[0] + 56 * i + 54]
                if len(rec) == 54 and rec[19] == 0x10:
                    idx = struct.unpack(">3H", rec[48:54])
                    if max(idx) < len(v):
                        exits.append(set(idx))
            quads = []
            for tri in exits:             # the two triangles of a quad share an edge
                quad = next((q for q in quads if len(q & tri) >= 2), None)
                if quad is None:
                    quads.append(set(tri))
                else:
                    quad |= tri
            out += [tuple(v[sorted(q)][:, [0, 2]].mean(0)) for q in quads]
    return out


def _branches(text):
    """[(z bound or None, destination, entry)] of one mainMapJump case. Most
    cases load one script; a case whose trigger covers a whole wall of doors
    (Moschet Manor's hall) picks the room by the player's Z instead:
    `if (posZ < -600) load A else if (posZ < -450) load B ... else load D`."""
    out, bound, entry = [], None, None
    for m in re.finditer(r"posZ <\. ([^)\s]+)\)|G59 = ([^;]+);|loadCFlat\('(\w+)'\)", text):
        if m.group(1):
            bound = _number(m.group(1))
        elif m.group(2):
            entry = _number(m.group(2))
        else:
            out.append((bound, m.group(3), entry))
            bound = None
    if not any(b is not None for b, _, _ in out):
        return out[-1:]
    return [b for b in out if b[0] is not None] + out[-1:]


def _wall_exits(cases, free, rooms):
    """[(x, z, destination, entry)] for jump cases that pick the room by Z.
    Each such case gets the column of triggers (same x) that has one trigger
    per branch and lies nearest the rooms it leads to; other cases then take
    the trigger nearest their room, and a last case leading outside takes
    the one trigger left."""
    out = []

    def near(q, target):
        room = rooms.get(target)
        return math.hypot(q[0] - room[0], q[1] - room[1]) if room else 0.0

    for case in sorted(cases, key=lambda c: -len(cases[c])):
        branches = cases[case]
        if len(branches) < 2:
            continue
        best = None
        for x in {round(q[0] / 40) for q in free}:
            column = [q for q in free if round(q[0] / 40) == x]
            picked = {}
            for q in column:
                i = next((i for i, (b, _, _) in enumerate(branches) if b is None or q[1] < b))
                picked.setdefault(i, q)
            if len(picked) != len(branches):
                continue
            cost = sum(near(q, branches[i][1]) for i, q in picked.items())
            if best is None or cost < best[0]:
                best = (cost, picked)
        if best:
            for i, q in best[1].items():
                out.append((*q, *branches[i][1:]))
                free.remove(q)
    rest = [c for c in cases if len(cases[c]) == 1]
    for case in sorted(rest, key=lambda c: cases[c][0][1] not in rooms):
        _, target, entry = cases[case][0]
        if not free:
            break
        if target in rooms:
            q = min(free, key=lambda q: near(q, target))
        elif len(free) == 1:
            q = free[0]
        else:
            continue
        out.append((*q, target, entry))
        free.remove(q)
    return out


def area_exits(path, quads=(), rooms=None):
    """[(x, z, destination script, entry number)] for the exits of one area
    script, or None when the decompiler isn't available. `quads` are the exit
    triggers from the collision data (exit_quads): an exit whose camera point
    is known goes on the nearest trigger; the triggers left over are given to
    the exits without a camera point when those all lead to the same place.
    `rooms` ({script: (x, z)}) places a hall's wall of doors (_wall_exits)."""
    cflat = _decompiler()
    if cflat is None:
        return None
    script = cflat.Script(path)
    funcs = {f.name: f for f in script.funcs}
    if "onPushMapJump" not in funcs or "mainMapJump" not in funcs:
        return []
    spots = {}
    for case, body in _m0_cases(cflat.decompile(script, funcs["onPushMapJump"])).items():
        m = re.search(r"cam_mode\(102, ([^,]+), [^,]+, ([^,]+),", "\n".join(body))
        if m and _number(m.group(1)) is not None and _number(m.group(2)) is not None:
            spots[case] = (_number(m.group(1)), _number(m.group(2)))
    loads, branches = {}, {}
    own = os.path.basename(script.name).split(".")[0]
    for case, body in _m0_cases(cflat.decompile(script, funcs["mainMapJump"])).items():
        text = "\n".join(body)
        targets = list(re.finditer(r"loadCFlat\('(\w+)'\)", text))
        if not targets:
            continue
        target = targets[-1]
        entries = re.findall(r"G59 = ([^;]+);", text[:target.start()])
        if target.group(1) != own:
            loads[case] = (target.group(1), _number(entries[-1]) if entries else None)
            branches[case] = _branches(text)
    free = list(quads)
    if rooms and not spots and any(len(b) > 1 for b in branches.values()):
        return _wall_exits(branches, free, rooms)
    for case in sorted(spots):
        if case in loads and free:
            x, z = spots[case]
            nearest = min(free, key=lambda q: math.hypot(q[0] - x, q[1] - z))
            if math.hypot(nearest[0] - x, nearest[1] - z) < 150:
                spots[case] = nearest
                free.remove(nearest)
    unplaced = [c for c in loads if c not in spots]
    if unplaced and free and len({loads[c][0] for c in unplaced}) == 1:
        for case, quad in zip(sorted(unplaced), free):
            spots[case] = quad
    return [(*spots[c], *loads[c]) for c in sorted(loads) if c in spots]


def _jumps(path):
    """{jump: (destination script, entry number)} from an area's mainMapJump."""
    cflat = _decompiler()
    script = cflat.Script(path)
    funcs = {f.name: f for f in script.funcs}
    out = {}
    if "mainMapJump" not in funcs:
        return out
    own = os.path.basename(script.name).split(".")[0]
    for case, body in _m0_cases(cflat.decompile(script, funcs["mainMapJump"])).items():
        text = "\n".join(body)
        targets = list(re.finditer(r"loadCFlat\('(\w+)'\)", text))
        if targets and targets[-1].group(1) != own:
            entries = re.findall(r"G59 = ([^;]+);", text[:targets[-1].start()])
            out[case] = (targets[-1].group(1), _number(entries[-1]) if entries else None)
    return out


def door_spots(path):
    """{door: (x, z)} from an area's door_se_pos(door, sound, x, y, z) calls -
    the doors of Moschet Manor, whose exits have no trigger quads."""
    cflat = _decompiler()
    script = cflat.Script(path)
    if not any(f.name == "door_se_pos" for f in script.funcs):
        return {}
    out = {}
    for f in script.funcs:
        if not f.code or f.name == "door_se_pos":
            continue
        for line in cflat.decompile(script, f):
            m = re.search(r"door_se_pos\((\d+), [^,]+, ([^,]+), [^,]+, ([^)]+)\)", line)
            if m and _number(m.group(2)) is not None and _number(m.group(3)) is not None:
                out.setdefault(int(m.group(1)), (_number(m.group(2)), _number(m.group(3))))
    return out


def _door_exits(paths, script):
    """{area: [(x, z, destination, entry)]} for rooms whose exits are doors
    (not the hall they open onto). A room's door i uses its jump i (or its
    only destination), and double doors (two door spots close together with
    the same destination) are one exit."""
    jumps = {area: _jumps(path) for area, path in paths.items()}
    returns = {}                      # (area entered, entry) -> area it came from
    for area, js in jumps.items():
        for target, entry in js.values():
            m = re.match(rf"{script}_(\d+)$", target)
            if m and entry is not None:
                returns[(int(m.group(1)), int(entry))] = area
    out = {}
    for area, path in paths.items():
        doors = door_spots(path)
        if not doors:
            continue
        exits = []
        targets = {t for t, _ in jumps[area].values()}
        if any(entered == area for entered, _ in returns):
            continue                      # the hall: its exit triggers are read instead (_wall_exits)
        for k, (x, z) in sorted(doors.items()):
            if k in jumps[area]:
                dest, passage = jumps[area][k]
            elif len(targets) == 1:
                dest, passage = next(iter(jumps[area].values()))
            else:
                continue
            if any(t == dest and math.hypot(x - ex, z - ez) < 60 for ex, ez, t, _ in exits):
                continue
            exits.append((x, z, dest, passage))
        out[area] = exits
    return out


def dungeon_exits(iso, paths, script, areas):
    """{area: [(x, z, label)]} for every area of a dungeon, with the two ends
    of each passage between areas sharing a letter. `paths` is {area: script
    file}. None when the decompiler isn't available."""
    stage = Stage(iso, STAGES[script])
    quads = {area: exit_quads(stage, AREA_MAPS.get((script, area), [area])) for area in paths}
    # where each area is, for a hall whose triggers pick the room by position
    rooms = {f"{script}_{area}": tuple(np.mean(q, 0)) for area, q in quads.items() if q}
    found = {area: area_exits(path, quads[area], rooms) for area, path in paths.items()}
    if any(v is None for v in found.values()):
        return None
    doors = _door_exits(paths, script)
    found.update(doors)
    boss = max(paths)
    drawn = set(areas)
    areas = set(paths) - {boss}       # every area but the boss room can be named
    letter = {}
    pairs = sorted({tuple(sorted((a, int(m.group(1)))))
                    for a, exits in found.items() for _, _, t, _ in exits
                    if a in drawn and (m := re.match(rf"{script}_(\d+)$", t)) and int(m.group(1)) in drawn})
    next_letter = 0
    for a, b in pairs:
        ab = sorted((e[3] if e[3] is not None else 0, i) for i, e in enumerate(found[a]) if e[2] == f"{script}_{b}")
        ba = sorted((e[3] if e[3] is not None else 0, i) for i, e in enumerate(found[b]) if e[2] == f"{script}_{a}")
        if (a in doors or b in doors) and len(ab) == len(ba) > 1:
            # Moschet Manor's rooms all share one set of coordinates, so the
            # two sides of a door are simply the closest pair
            spot = lambda area, i: found[area][i][:2]
            ba = min(([ba[k] for k in order] for order in itertools.permutations(range(len(ba)))),
                     key=lambda o: sum(math.dist(spot(a, i), spot(b, j)) for (_, i), (_, j) in zip(ab, o)))
        for (_, i), (_, j) in zip(ab, ba):
            name = chr(ord("a") + next_letter) if next_letter < 26 else "?"
            letter[(a, i)] = letter[(b, j)] = name
            next_letter += 1
    out = {}
    for area, exits in found.items():
        out[area] = []
        for i, (x, z, target, _) in enumerate(exits):
            label = _exit_label(target, script, areas)
            if (area, i) in letter:
                label = f"{letter[(area, i)]}  \u2192 {label}"
            else:
                label = f"\u2192 {label}"
            out[area].append((x, z, label))
    return out


def _exit_label(target, script, areas):
    """What an exit box says: "Area N", "Boss", "World Map" or the script name."""
    if target in ("world", "worldmap"):
        return "World Map"
    m = re.match(rf"{script}_(\d+)$", target)
    if m:
        n = int(m.group(1))
        return f"Area {n + 1}" if n in areas else "Boss"
    return target


def _hotspots(path):
    """[(x, z, element)] from SPAWN_HOT_SPOT records [element, x, y, z, ...]."""
    return [(w[1], w[3], r[0]) for _, r, w in spawn_map._records(path, "SPAWN_HOT_SPOT")
            if isinstance(w[1], float) and isinstance(w[3], float)]


def _monster_cycles(c):
    """Cycles a SPAWN record appears in, from its cycle bits (as for chests)."""
    if not isinstance(c, int):
        return [1, 2, 3]
    return [cycle for cycle, bit in chestflags.CYCLE_BITS.items() if c & bit] or [1, 2, 3]


def _chest_spots(iso, disc):
    """{flag: [(x, z), ...]} - every spot a chest can appear at in one area file."""
    tmp = os.path.join(tempfile.gettempdir(), "stagemap_" + os.path.basename(disc))
    randomizer._extract(iso, disc, tmp)
    out = {}
    for _, rec, w in spawn_map._records(tmp, "SPAWN_TBOX"):
        out.setdefault(rec[3] - 1, []).append((w[4], w[6]))
    return out


def _font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _area_markers(path, to_px):
    """(monsters, hotspots) of one area in its image's pixels:
    monsters = [(name, cycles, (px, py))], hotspots = [(element, (px, py))]."""
    monsters = [(m["name"], _monster_cycles(m["C"]), to_px(m["world"]["x"], m["world"]["z"]))
                for m in spawn_map.monsters(path)]
    hotspots = [(element, to_px(x, z)) for x, z, element in _hotspots(path)]
    return monsters, hotspots


def _letters(monsters):
    """{monster name: letter}, A, B, C... in order of first spawn."""
    out = {}
    for name, _, _ in monsters:
        out.setdefault(name, chr(ord("A") + len(out)) if len(out) < 26 else "?")
    return out


def _draw_exits(img, exits, to_px, font):
    draw = ImageDraw.Draw(img, "RGBA")
    placed = []
    for x, z, text in exits:
        px, py = to_px(x, z)
        w = draw.textlength(text, font=font)
        # exits just outside the cropped area go on its nearest edge
        px = min(max(px, w / 2 + 10), img.width - w / 2 - 10)
        py = min(max(py, 18), img.height - 18)
        # boxes of exits close together are stacked instead of overlapping
        for _ in range(8):
            if not any(abs(px - qx) < (w + qw) / 2 + 18 and abs(py - qy) < 36 for qx, qy, qw in placed):
                break
            py = py + 36 if py + 54 < img.height else py - 36
        placed.append((px, py, w))
        draw.rounded_rectangle([px - w / 2 - 8, py - 16, px + w / 2 + 8, py + 16], 6,
                               fill=(20, 22, 30, 225), outline=(255, 215, 80, 255), width=2)
        draw.text((px, py), text, fill=(255, 235, 160), font=font, anchor="mm")


def _hotspot_icon(draw, px, py, element, font, scale=1.0):
    """A map-pin shaped badge in the element's colour with its initial."""
    name, colour = ELEMENTS.get(element, ("?", (200, 200, 200)))
    r = 11 * scale
    draw.polygon([(px - r * 0.7, py - r * 0.9), (px + r * 0.7, py - r * 0.9), (px, py + r * 1.1)],
                 fill=colour + (255,))
    draw.ellipse([px - r, py - 2.2 * r, px + r, py - 0.2 * r], fill=colour + (255,), outline=(255, 255, 255, 255),
                 width=2)
    draw.text((px, py - 1.2 * r), name[0], fill=(255, 255, 255), font=font, anchor="mm")


def _legend_rows(entries, width, font):
    if not entries:
        return 0, 0
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    col_w = max(probe.textlength(t, font=font) for _, t, _ in entries) + 46
    per_row = max(1, int(width // col_w))
    return -(-len(entries) // per_row), col_w


def _marked_tile(base, monsters, hotspots, letters, cycles, show_hotspots, legend_height):
    """A copy of an area image with monster letters (those spawning in any of
    `cycles`; none if cycles is empty) and/or hotspot icons drawn on it, and a
    legend strip of `legend_height` below (the same height for every
    variant, so chest pins stay put)."""
    small, letter_font = _font(15), _font(14)
    img = base.copy()
    draw = ImageDraw.Draw(img, "RGBA")
    counts = collections.Counter()
    for name, spawn_cycles, (px, py) in monsters:
        if cycles and set(spawn_cycles) & set(cycles):
            counts[name] += 1
            draw.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(150, 20, 30, 225), outline=(255, 215, 215, 240))
            draw.text((px, py), letters[name], fill=(255, 255, 255), font=letter_font, anchor="mm")
    elements = set()
    if show_hotspots:
        for element, (px, py) in hotspots:
            elements.add(element)
            _hotspot_icon(draw, px, py, element, letter_font)
    out = Image.new("RGB", (img.width, img.height + legend_height), BACKGROUND)
    out.paste(img, (0, 0))
    entries = [(letters[n], f"{n} ×{c}", None) for n, c in sorted(counts.items(), key=lambda kv: letters[kv[0]])]
    entries += [("", f"{ELEMENTS[e][0]} hotspot", e) for e in sorted(elements) if e in ELEMENTS]
    _, col_w = _legend_rows(entries, img.width, small)
    per_row = max(1, int(img.width // col_w)) if entries else 1
    ld = ImageDraw.Draw(out, "RGBA")
    for i, (letter, text, element) in enumerate(entries):
        x = 10 + (i % per_row) * col_w
        y = img.height + 10 + (i // per_row) * 24
        if element is not None:
            _hotspot_icon(ld, x + 9, y + 15, element, letter_font, 0.75)
        else:
            ld.ellipse([x, y, x + 18, y + 18], fill=(150, 20, 30), outline=(255, 215, 215))
            ld.text((x + 9, y + 9), letter, fill=(255, 255, 255), font=letter_font, anchor="mm")
        ld.text((x + 26, y + 1), text, fill=(230, 230, 230), font=small)
    return out


# Tracker image variants: (suffix, enemy cycles shown, hotspots shown)
VARIANTS = [(f"{h}{e}", cycles, h == "h")
            for h in ("", "h")
            for e, cycles in (("", ()), ("e", (1, 2, 3)), ("e1", (1,)), ("e2", (2,)), ("e3", (3,)))]


def render_dungeon(iso, script, tile=TILE, gap=24, label_height=44, variants=(("he", (1, 2, 3), True),)):
    """({suffix: image}, {chest: [(x, y), ...]}) - the dungeon's areas side by
    side (up to three per row), each labelled, with exit boxes; one image per
    variant (suffix, enemy cycles shown, hotspots shown). Chest pixel spots
    are the same in every variant."""
    discs = chestflags.dungeon_discs(iso, script)
    chests = chestflags.canonical(iso, script, discs)
    chest_of = {(c["area"], f): c["chest"] for c in chests for f in c["flags"]}
    paths = {}
    for disc in discs:
        area = randomizer._area_no(disc)
        paths[area] = os.path.join(tempfile.gettempdir(), "stagemap_" + os.path.basename(disc))
        randomizer._extract(iso, disc, paths[area])
    # areas with chests, and the rooms between them that only have monsters
    # (the areas after the last chest are the boss rooms)
    last = max(c["area"] for c in chests)
    areas = sorted({c["area"] for c in chests} |
                   {a for a, p in paths.items() if a < last and spawn_map.monsters(p)})
    exits = dungeon_exits(iso, paths, script, set(areas))
    if exits is None:
        print(f"  (exits left off: no CFlat decompiler at {CFLAT})")
    small = _font(15)
    tiles = []
    for disc in discs:
        area = randomizer._area_no(disc)
        if area not in areas:
            continue
        img, to_px = render_area(iso, script, disc, area, tile)
        _draw_exits(img, (exits or {}).get(area, []), to_px, _font(20))
        monsters, hotspots = _area_markers(paths[area], to_px)
        letters = _letters(monsters)
        # room for the longest legend any variant can show
        everything = [(letters[n], f"{n} ×{c}", None)
                      for n, c in collections.Counter(n for n, _, _ in monsters).items()]
        everything += [("", f"{ELEMENTS[e][0]} hotspot", e) for e in {e for e, _ in hotspots} if e in ELEMENTS]
        rows, _ = _legend_rows(everything, img.width, small)
        legend = rows * 24 + 12 if rows else 0
        tiles.append((area, img, to_px, _chest_spots(iso, disc), monsters, hotspots, letters, legend))
    cols = min(3, len(tiles))
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    width = max(sum(t[1].width for t in row) + gap * (len(row) - 1) for row in rows)
    row_heights = [max(t[1].height + t[7] for t in row) + label_height for row in rows]
    height = sum(row_heights) + gap * (len(rows) - 1)
    font = _font(28)
    images = {}
    for suffix, cycles, show_hotspots in variants:
        out = Image.new("RGB", (width, height), BACKGROUND)
        draw = ImageDraw.Draw(out)
        y = 0
        for row, row_height in zip(rows, row_heights):
            x = 0
            for area, img, to_px, spots, monsters, hotspots, letters, legend in row:
                draw.text((x + 8, y + 6), f"Area {area + 1}", fill=(235, 235, 235), font=font)
                out.paste(_marked_tile(img, monsters, hotspots, letters, cycles, show_hotspots, legend),
                          (x, y + label_height))
                x += img.width + gap
            y += row_height + gap
        images[suffix] = out
    pins, y = {}, 0
    for row, row_height in zip(rows, row_heights):
        x = 0
        for area, img, to_px, spots, *_ in row:
            for flag, points in spots.items():
                chest = chest_of.get((area, flag))
                if chest is None:
                    continue
                for wx, wz in points:
                    px, py = to_px(wx, wz)
                    pins.setdefault(chest, []).append([int(x + px), int(y + label_height + py)])
            x += img.width + gap
        y += row_height + gap
    return images, pins


def write_tracker_maps(iso, out_dir):
    """Every dungeon's map images (one per VARIANTS entry, named
    <script>_<suffix>.jpg, plain for no suffix) plus stagemaps.json."""
    import lootcft
    os.makedirs(out_dir, exist_ok=True)
    index = {}
    for script, name in lootcft.DUNGEONS:
        images, pins = render_dungeon(iso, script, variants=VARIANTS)
        files = {}
        for suffix, img in images.items():
            files[suffix] = f"{script}_{suffix}.jpg" if suffix else f"{script}.jpg"
            small = img.resize((round(img.width * TRACKER_SCALE), round(img.height * TRACKER_SCALE)),
                               Image.LANCZOS)
            small.save(os.path.join(out_dir, files[suffix]), quality=TRACKER_QUALITY, optimize=True)
        size = (round(images[""].width * TRACKER_SCALE), round(images[""].height * TRACKER_SCALE))
        pins = {k: [[round(x * TRACKER_SCALE), round(y * TRACKER_SCALE)] for x, y in v] for k, v in pins.items()}
        index[name] = {"img": files[""], "variants": files, "size": list(size),
                       "pins": {str(k): v for k, v in sorted(pins.items())}}
        print(f"  {name}: {size[0]}x{size[1]}, {len(pins)} chest(s), {len(images)} variant(s)")
    with open(os.path.join(out_dir, "stagemaps.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1)


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "render":
        iso, script, area, out = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
        disc = next(d for d in chestflags.dungeon_discs(iso, script) if randomizer._area_no(d) == area)
        img, to_px = render_area(iso, script, disc, area)
        draw = ImageDraw.Draw(img)
        chest_of = {(c["area"], f): c["chest"] for c in chestflags.canonical(
            iso, script, chestflags.dungeon_discs(iso, script)) for f in c["flags"]}
        for flag, points in _chest_spots(iso, disc).items():
            for wx, wz in points:
                px, py = to_px(wx, wz)
                draw.ellipse([px - 10, py - 10, px + 10, py + 10], outline=(255, 220, 40), width=4)
                draw.text((px + 12, py - 8), str(chest_of.get((area, flag), "?")), fill=(255, 255, 255))
        img.save(out)
        print("wrote", out)
    elif len(sys.argv) == 4 and sys.argv[1] == "tracker":
        write_tracker_maps(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
