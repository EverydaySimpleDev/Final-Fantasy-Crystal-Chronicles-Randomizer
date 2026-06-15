"""
chmio.py - byte-exact reader/writer for FFCC's IFF-tag model/texture containers
(CHM/CHA/CHD/TEX ... - the same family tag.py parses, but lossless so we can
WRITE them back). This is the foundation for a Blender -> game model importer:
parse a model into a Node tree, edit it, and serialize byte-for-byte.

Each tag = 16-byte header [4 type][4 big-endian length][8 mystery] then `length`
bytes of content, then zero-padding up to the next 16-byte boundary. Content is
an ordered mix of child tags and raw byte runs; we preserve that order and the
trailing pad so an unmodified tree re-serializes identically.
"""

import struct

VALID = {b"ATRB", b"BANK", b"BINF", b"BUMP", b"CHD ", b"CHM ", b"COLR", b"DGRP",
         b"DLHD", b"DLST", b"DYN ", b"FMT ", b"FUR ", b"IMAG", b"INFO", b"KEY ",
         b"MATL", b"MESH", b"MIDX", b"MNAM", b"MSET", b"MSST", b"NAME", b"NODE",
         b"NORM", b"NSET", b"ONE ", b"PARM", b"QUAN", b"SCEN", b"SEQ ", b"SIZE",
         b"SKIN", b"TANM", b"TAST", b"TEX ", b"TFRM", b"TIDX", b"TSET", b"TXTR",
         b"UV  ", b"VERT", b"NAM2", b"DATA", b"ANIM", b"FRAM"}


def _align16(n):
    """Next 16-byte boundary at or after n (matches tag.py's align)."""
    return n + ((16 - n % 16) % 16)


class Node:
    """One tag. `items` is an ordered list of child Node or raw `bytes` runs."""

    def __init__(self, type_=b"    ", mystery=b"\x00" * 8):
        self.type = type_
        self.mystery = mystery
        self.items = []        # [Node | bytes], in file order
        self.pad = b""         # zero padding after content to the 16-byte boundary
        self._clen = None      # original content length (None for nodes built fresh)

    # ---- parse ----
    @classmethod
    def parse(cls, buf, pos):
        n = cls(buf[pos:pos + 4], buf[pos + 8:pos + 16])
        length = struct.unpack(">I", buf[pos + 4:pos + 8])[0]
        p, end = pos + 16, pos + 16 + length
        while p < end:
            if buf[p:p + 4] in VALID:
                child = Node.parse(buf, p)
                n.items.append(child)
                p = child._end
            else:
                take = min(16, end - p)
                n.items.append(buf[p:p + take])
                p += take
        aligned = _align16(end)
        n.pad = buf[end:aligned]
        n._clen = length        # original content length (to know if an edit resized it)
        n._end = aligned
        return n

    # ---- serialize ----
    def content(self):
        out = bytearray()
        for it in self.items:
            out += it.serialize() if isinstance(it, Node) else it
        return bytes(out)

    def serialize(self):
        body = self.content()
        # Keep the original pad bytes if content size is unchanged (byte-exact
        # round-trip); otherwise recompute zero-padding to the 16-byte boundary.
        # Pad length depends only on content length (each tag starts 16-aligned).
        if len(body) == self._clen:
            pad = self.pad
        else:
            pad = b"\x00" * ((16 - len(body) % 16) % 16)
        return self.type + struct.pack(">I", len(body)) + self.mystery + body + pad

    # ---- convenience ----
    def find(self, type_):
        """First descendant tag of the given 4-byte type (depth-first)."""
        for it in self.items:
            if isinstance(it, Node):
                if it.type == type_:
                    return it
                hit = it.find(type_)
                if hit is not None:
                    return hit
        return None

    def find_all(self, type_):
        out = []
        for it in self.items:
            if isinstance(it, Node):
                if it.type == type_:
                    out.append(it)
                out += it.find_all(type_)
        return out

    def __repr__(self):
        kids = [it.type.decode("ascii", "replace") for it in self.items if isinstance(it, Node)]
        return f"<{self.type.decode('ascii','replace')} {kids}>" if kids \
            else f"<{self.type.decode('ascii','replace')}>"


# --------------------------------------------------------------------------- #
# geometry accessors (VERT / NORM = int16 x,y,z triples; UV = int16 u,v)
# --------------------------------------------------------------------------- #
def set_content(node, data):
    """Replace a leaf tag's raw content (e.g. an edited VERT block)."""
    node.items = [bytes(data)]


def read_triples(node):
    """Decode a VERT/NORM tag's content into [(x, y, z), ...] of signed int16."""
    b = node.content()
    return [struct.unpack(">hhh", b[i:i + 6]) for i in range(0, len(b) - len(b) % 6, 6)]


def write_triples(node, triples):
    """Encode [(x, y, z), ...] back into a VERT/NORM tag (same count = same size)."""
    set_content(node, b"".join(struct.pack(">hhh", *t) for t in triples))


def read_uvs(node):
    """Decode a UV tag's content into [(u, v), ...] of signed int16."""
    b = node.content()
    return [struct.unpack(">hh", b[i:i + 4]) for i in range(0, len(b) - len(b) % 4, 4)]


def write_uvs(node, uvs):
    set_content(node, b"".join(struct.pack(">hh", *uv) for uv in uvs))


def parse_doc(buf):
    """Parse a whole file as a sequence of top-level items (Node | raw bytes).
    Most model files are a single root tag, but a few (e.g. some .tex) hold
    several sibling tags - and a root tag may even declare length 0 with real
    content after it - so we walk top-level until EOF."""
    items, p = [], 0
    while p < len(buf):
        if buf[p:p + 4] in VALID:
            n = Node.parse(buf, p)
            items.append(n)
            p = n._end
        else:
            items.append(buf[p:])           # trailing non-tag bytes
            break
    return items


def serialize_doc(items):
    return b"".join(it.serialize() if isinstance(it, Node) else it for it in items)


def load(path):
    """Return the document (list of top-level items)."""
    with open(path, "rb") as f:
        return parse_doc(f.read())


def save(doc, path):
    with open(path, "wb") as f:
        f.write(serialize_doc(doc))


def root(doc):
    """The first (usually only) top-level Node - the model/texture root tag."""
    return next(it for it in doc if isinstance(it, Node))


if __name__ == "__main__":
    import sys
    data = open(sys.argv[1], "rb").read()
    rebuilt = serialize_doc(parse_doc(data))
    ok = rebuilt == data
    print(f"{sys.argv[1]}: {len(data)} bytes  round-trip {'IDENTICAL' if ok else 'DIFFERS'}")
    if not ok:
        i = next((k for k in range(min(len(data), len(rebuilt))) if data[k] != rebuilt[k]), -1)
        print(f"  len {len(data)} -> {len(rebuilt)}; first diff at {i}")
