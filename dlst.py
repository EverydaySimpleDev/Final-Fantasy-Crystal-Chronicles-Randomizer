"""
dlst.py - lossless codec for FFCC display-list (DLST) content + a triangle-list
encoder. This is the piece that lets us WRITE new geometry/topology (faces),
the counterpart to chmio (containers) and objimport (vertices).

A DLST tag's content is:
    u16 matidx                         material index
    then a run of GX primitive batches:
      u8  ltype                        GX draw opcode (low 3 bits = vertex-format/VAT)
                                         0x90/0x91 triangle list, 0x98/0x99 strip,
                                         0x92/0x9a use a 5-index vertex format
      u16 size                         vertex count in this batch
      size * (k * u16)                 per-vertex attribute indices, k = 4 (or 5)
                                         ordered (position, normal, color, uv[, extra])
    bytes < 0x90 are NOP/padding and are preserved verbatim.

parse()/encode() round-trip byte-for-byte. faces_to_dlst() builds a fresh
triangle-list batch from explicit per-vertex index tuples (for new topology).
"""

import struct

# u16 attribute indices per vertex, keyed by GX draw opcode (VAT in low bits)
VFMT = {0x90: 4, 0x91: 4, 0x98: 4, 0x99: 4, 0x92: 5, 0x9a: 5}

TRI_LIST = (0x90, 0x91)
TRI_STRIP = (0x98, 0x99)


def parse(content):
    """content bytes -> (matidx, items) where items is an ordered list of either
    ('nop', byte) or ('prim', ltype, [vertex-tuple, ...])."""
    matidx = struct.unpack(">H", content[:2])[0]
    items, p, n = [], 2, len(content)
    while p < n:
        ltype = content[p]; p += 1
        if ltype < 0x90:
            items.append(("nop", ltype)); continue
        if ltype not in VFMT:
            raise ValueError(f"unknown DLST opcode 0x{ltype:02x} at {p-1}")
        size = struct.unpack(">H", content[p:p + 2])[0]; p += 2
        k = VFMT[ltype]
        verts = []
        for _ in range(size):
            verts.append(struct.unpack(">" + "H" * k, content[p:p + 2 * k]))
            p += 2 * k
        items.append(("prim", ltype, verts))
    return matidx, items


def encode(matidx, items):
    """Inverse of parse(): (matidx, items) -> content bytes (byte-exact)."""
    out = bytearray(struct.pack(">H", matidx))
    for it in items:
        if it[0] == "nop":
            out.append(it[1])
        else:
            _, ltype, verts = it
            out.append(ltype)
            out += struct.pack(">H", len(verts))
            k = VFMT[ltype]
            for v in verts:
                out += struct.pack(">" + "H" * k, *v)
    return bytes(out)


def to_triangles(items):
    """Flatten all batches to a list of triangles, each = (v0, v1, v2) of full
    vertex-index tuples. Handles list and strip (with the GX winding/parity and
    degenerate-skip rules, matching dlhd.to_faces)."""
    tris = []
    for it in items:
        if it[0] != "prim":
            continue
        _, ltype, d = it
        if ltype in TRI_LIST:
            for i in range(0, len(d) - 2, 3):
                a, b, c = d[i], d[i + 1], d[i + 2]
                if len({a[0], b[0], c[0]}) == 3:
                    tris.append((a, b, c))
        else:  # strip (0x98/0x99/0x92/0x9a)
            for i in range(1, len(d) - 1):
                a = d[i - (i % 2)]
                b = d[i - ((i + 1) % 2)]
                c = d[i + 1]
                if len({a[0], b[0], c[0]}) == 3:
                    tris.append((a, b, c))
    return tris


def _pad32(content):
    """Pad display-list content to a 32-byte boundary with NOP (0x00) bytes.
    Stock DLSTs end with NOP padding; without it the GPU FIFO overreads past the
    data and desyncs (the 'Unknown Opcode' crash)."""
    return content + b"\x00" * ((-len(content)) % 32)


def faces_to_dlst(matidx, triangles, opcode=0x90, max_tris=48):
    """Build DLST content from triangles (each = 3 vertex-index tuples) as
    triangle-LIST batches. Vertex tuples must have VFMT[opcode] entries
    (default 4: position, normal, color, uv). The triangles are split into
    batches of at most `max_tris` (the game/GPU mishandles one giant draw - the
    stock models use many small batches), so big meshes stay within a safe
    per-draw vertex count."""
    k = VFMT[opcode]
    items = []
    for start in range(0, len(triangles), max_tris):
        verts = []
        for tri in triangles[start:start + max_tris]:
            for v in tri:
                if len(v) != k:
                    raise ValueError(f"vertex {v} has {len(v)} indices, need {k}")
                verts.append(tuple(v))
        items.append(("prim", opcode, verts))
    return _pad32(encode(matidx, items))


def faces_to_strips(matidx, triangles, opcode=0x98):
    """Each triangle as its own 3-vertex triangle-STRIP (0x98) - matches the
    primary primitive type the stock FFCC models use, in case the engine/GPU is
    configured only for strips."""
    k = VFMT[opcode]
    items = []
    for tri in triangles:
        items.append(("prim", opcode, [tuple(v) for v in tri]))
    return _pad32(encode(matidx, items))


if __name__ == "__main__":
    import sys
    import chmio
    root = chmio.root(chmio.load(sys.argv[1]))
    n_ok = n = 0
    for node in root.find_all(b"DLST"):
        c = node.content()
        n += 1
        mat, items = parse(c)
        ok = encode(mat, items) == c
        n_ok += ok
        prims = [(hex(it[1]), len(it[2])) for it in items if it[0] == "prim"]
        print(f"  DLST mat={mat} prims={prims} tris={len(to_triangles(items))} "
              f"round-trip={'OK' if ok else 'BAD'}")
    print(f"{n_ok}/{n} DLST blocks byte-exact")
