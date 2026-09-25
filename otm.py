"""
otm.py - byte-exact reader/writer for FFCC's .otm world-map containers.

Same 16-byte chunk header as chmio's CHM family: [4 tag][4 big-endian size]
[4 arg0][4 version], content of `size` bytes, then zero-pad so the WHOLE
header+content span lands on a 16-byte boundary (matches the decomp's
CChunkFile::GetNextChunk / CMapMng::ReadOtm).

Unlike chmio (which guesses "is this a nested tag" by checking a fixed
vocabulary against arbitrary byte offsets, since CHM mixes recognized tags
with raw runs at the same level), .otm chunk nesting is unambiguous: a
chunk's own tag tells you whether its payload is itself a sequence of
sub-chunks (CONTAINER) or raw leaf data (VERT/NORM/UV/DLST/...). So we
recurse only into known containers and keep everything else as an opaque
byte blob - verified byte-exact round-trip on real map000.otm/map002.otm.
"""

import struct

CONTAINER = {b"OTM ", b"SCEN", b"MESH", b"NODE", b"DLHD", b"HIT ", b"TSET", b"MSET"}


def _align16(n):
    return n + ((16 - n % 16) % 16)


class Chunk:
    """One IFF-style chunk. `items` is a list of child Chunk (CONTAINER tags)
    or a single-element list holding the raw `bytes` payload (leaf tags)."""

    def __init__(self, type_=b"    ", arg0=0, version=0):
        self.type = type_
        self.arg0 = arg0
        self.version = version
        self.items = []
        self.pad = b""
        self._clen = None

    @classmethod
    def parse(cls, buf, pos):
        type_ = bytes(buf[pos:pos + 4])
        size, arg0, version = struct.unpack_from(">III", buf, pos + 4)
        n = cls(type_, arg0, version)
        p, end = pos + 16, pos + 16 + size
        if type_ in CONTAINER:
            while p < end:
                child = Chunk.parse(buf, p)
                n.items.append(child)
                p = child._end
        else:
            n.items = [bytes(buf[p:end])]
        aligned = _align16(end)
        n.pad = bytes(buf[end:aligned])
        n._clen = size
        n._end = aligned
        return n

    def content(self):
        if self.type in CONTAINER:
            return b"".join(it.serialize() for it in self.items)
        return self.items[0]

    def serialize(self):
        body = self.content()
        # Keep the original pad bytes if content size is unchanged (byte-exact
        # round-trip); otherwise recompute zero-padding to the 16-byte boundary.
        if len(body) == self._clen:
            pad = self.pad
        else:
            pad = b"\x00" * ((16 - len(body) % 16) % 16)
        return self.type + struct.pack(">III", len(body), self.arg0, self.version) + body + pad

    def find(self, type_):
        """First descendant chunk of the given 4-byte type (depth-first)."""
        for it in self.items:
            if isinstance(it, Chunk):
                if it.type == type_:
                    return it
                hit = it.find(type_)
                if hit is not None:
                    return hit
        return None

    def find_all(self, type_):
        out = []
        for it in self.items:
            if isinstance(it, Chunk):
                if it.type == type_:
                    out.append(it)
                out += it.find_all(type_)
        return out

    def set_content(self, data):
        """Replace a leaf chunk's raw payload (e.g. an edited VERT block)."""
        self.items = [bytes(data)]

    def __repr__(self):
        t = self.type.decode("ascii", "replace")
        if self.type in CONTAINER:
            return f"<{t} {[it.type.decode('ascii','replace') for it in self.items]}>"
        return f"<{t} {len(self.items[0])}b>"


def load(path):
    with open(path, "rb") as f:
        buf = f.read()
    return Chunk.parse(buf, 0)


def save(chunk, path):
    with open(path, "wb") as f:
        f.write(chunk.serialize())


# --------------------------------------------------------------------------- #
# MESH-level geometry accessors
# --------------------------------------------------------------------------- #
def read_verts(node):
    """VERT payload -> [(x, y, z), ...] of float32 (already world-scale)."""
    b = node.content()
    return [struct.unpack(">fff", b[i:i + 12]) for i in range(0, len(b) - len(b) % 12, 12)]


def write_verts(node, verts):
    node.set_content(b"".join(struct.pack(">fff", *v) for v in verts))


def read_norms(node):
    """NORM payload -> [(x, y, z), ...] of signed int16 (signed-normalized: /32767)."""
    b = node.content()
    return [struct.unpack(">hhh", b[i:i + 6]) for i in range(0, len(b) - len(b) % 6, 6)]


def write_norms(node, norms):
    node.set_content(b"".join(struct.pack(">hhh", *n) for n in norms))


def read_colors(node):
    """COLR payload -> [(r, g, b, a), ...] of uint8."""
    b = node.content()
    return [tuple(b[i:i + 4]) for i in range(0, len(b) - len(b) % 4, 4)]


def read_uvs(node):
    """UV payload -> [(u, v), ...] of signed int16. NOTE: the fixed-point
    scale to normalize these hasn't been confirmed yet (unlike CHM's UV,
    which is a known /4096) - treat exported vt values as unverified."""
    b = node.content()
    return [struct.unpack(">hh", b[i:i + 4]) for i in range(0, len(b) - len(b) % 4, 4)]


def write_uvs(node, uvs):
    node.set_content(b"".join(struct.pack(">hh", *uv) for uv in uvs))


def meshes(root):
    scen = root.find(b"SCEN")
    return (scen or root).find_all(b"MESH")


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    data = open(path, "rb").read()
    root = Chunk.parse(data, 0)
    rebuilt = root.serialize()
    ok = rebuilt == data
    print(f"{path}: {len(data)} bytes  round-trip {'IDENTICAL' if ok else 'DIFFERS'}")
    if not ok:
        i = next((k for k in range(min(len(data), len(rebuilt))) if data[k] != rebuilt[k]), -1)
        print(f"  len {len(data)} -> {len(rebuilt)}; first diff at {i} "
              f"(orig len {len(data)}, rebuilt len {len(rebuilt)})")
    else:
        print(f"  MESH chunks found: {len(meshes(root))}")
