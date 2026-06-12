"""
cft.py - Parser/explorer for FFCC's compiled script files (.cfd / .cft).

These live in dvd/cft/ (one set per dungeon: cave, city, desert, fort, gigas,
castle, ...). They use the same IFF-style tag container as the texture files,
but with script tags (CFLD/CFLT root, BLCK script blocks, VAL operand tables,
MES messages, NAME strings). This is where gameplay logic lives - including the
TreasureBox block and the item API (SPAWN_TBOX, addItem, putDropItem), i.e. the
chest / drop data.

This is kept separate from tag.py on purpose: adding these tags to tag.py's
valid-tag list could cause false-positive mis-parses in the (verified) texture
pipeline. cft.py reuses the same parsing approach with an extended tag set.

Usage (extract a file first with gciso.py, then point cft.py at it):
    python gciso.py extract "Hacked Rom.iso" dvd/cft/cave_0.cft cave_0.cft

    python cft.py tree    cave_0.cft            # show the tag structure
    python cft.py blocks  cave_0.cft            # list script blocks (functions)
    python cft.py find    cave_0.cft TreasureBox  # locate a symbol + its block
    python cft.py strings cave_0.cft [keyword]  # dump ASCII strings (optionally filtered)
    python cft.py block   cave_0.cft TreasureBox  # hex-dump one block's VAL/code
    python cft.py calls   cave_0.cft initTreasureBox  # disassemble a function's calls

Known opcodes (FFCC script VM, partial): 0x03 push int32, 0x04 push float32,
0x0a call (relative function index). The full opcode set isn't decoded yet.
"""

import struct
import sys
import re

# Tags seen in CFL script containers. Extend here as more are discovered.
CFL_TAGS = {
    b"CFLD", b"CFLT", b"NAME", b"MES ", b"VAL ", b"FUNC",
    b"BLCK", b"INFO", b"DATA",
}


class Node:
    def __init__(self, st):
        self.off = st.tell()
        self.type = st.read(4)
        self.length = struct.unpack(">I", st.read(4))[0]
        self.myst = st.read(8)
        self.subtags = []
        self.bin = b""
        stop = self.off + 16 + self.length
        while st.tell() < stop:
            p = st.tell()
            first = st.read(4)
            st.seek(p)
            if first in CFL_TAGS and (stop - p) >= 16:
                self.subtags.append(Node(st))
            else:
                self.bin += st.read(min(16, stop - st.tell()))
        # 16-byte alignment, same as tag.py
        st.seek(int(st.tell() + 16 - 1 - (st.tell() - 1) % 16))

    def name(self):
        for s in self.subtags:
            if s.type == b"NAME":
                return s.bin.split(b"\x00")[0].decode("ascii", "replace")
        return None

    def walk(self):
        yield self
        for s in self.subtags:
            yield from s.walk()


def parse(path):
    import io
    with open(path, "rb") as f:
        data = f.read()
    return Node(io.BytesIO(data)), data


def blocks(root):
    return [b for b in root.subtags if b.type == b"BLCK"]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_tree(path, maxd=3):
    root, _ = parse(path)
    def show(t, d=0):
        nm = t.name()
        label = f" name={nm!r}" if nm else ""
        print("  " * d + f"{t.type!r} off=0x{t.off:x} len={t.length} "
              f"bin={len(t.bin)} subtags={len(t.subtags)}{label}")
        if d < maxd:
            for k in t.subtags[:40]:
                show(k, d + 1)
    show(root)


def cmd_blocks(path):
    root, _ = parse(path)
    bl = blocks(root)
    print(f"{len(bl)} script block(s):")
    for b in bl:
        val = next((s for s in b.subtags if s.type == b"VAL "), None)
        vlen = val.length if val else 0
        print(f"   0x{b.off:08x}  {b.name() or '?':22s}  VAL={vlen}B  total={b.length}B")


def cmd_find(path, keyword):
    root, data = parse(path)
    kw = keyword.encode()
    bl = blocks(root)
    def block_of(pos):
        for b in bl:
            if b.off <= pos < b.off + 16 + b.length:
                return b.name()
        return None
    hits = [m.start() for m in re.finditer(re.escape(kw), data)]
    print(f"'{keyword}': {len(hits)} occurrence(s)")
    for h in hits[:60]:
        ctx = data[max(0, h - 8):h + len(kw) + 8]
        ascii_ctx = "".join(chr(c) if 32 <= c < 127 else "." for c in ctx)
        print(f"   0x{h:08x}  block={block_of(h)!r}  ...{ascii_ctx}...")


def cmd_strings(path, keyword=None):
    _, data = parse(path)
    strs = re.findall(rb"[ -~]{4,}", data)
    seen = set()
    for s in strs:
        d = s.decode("ascii", "replace")
        if keyword and keyword.lower() not in d.lower():
            continue
        if d not in seen:
            seen.add(d)
            print("  ", d)


def cmd_block(path, name):
    root, _ = parse(path)
    for b in blocks(root):
        if b.name() == name:
            print(f"BLCK {name!r}  off=0x{b.off:x} len={b.length}")
            for s in b.subtags:
                print(f"  {s.type!r} off=0x{s.off:x} len={s.length} bin={len(s.bin)}")
                if s.type in (b"VAL ", b"INFO", b"DATA"):
                    hexdump(s.bin)
            return
    print(f"No block named {name!r}. Use 'blocks' to list them.")


def _code_of(block):
    """Extract the CODE bytecode out of a FUNC-block's body bytes."""
    b = block.bin
    i = b.find(b"CODE")
    if i < 0:
        return b""
    clen = struct.unpack(">I", b[i + 4:i + 8])[0]
    return b[i + 16:i + 16 + clen]


def cmd_calls(path, funcname):
    """Disassemble one function's calls. Decoded opcodes (FFCC script VM):
       0x03 = push int32, 0x04 = push float32, 0x0a = call (relative func index).
    Calls are resolved against the FUNC table; int/float pushed in the same
    statement are shown as the call's operands (candidate item IDs etc.)."""
    root, _ = parse(path)
    func = next((s for s in root.subtags if s.type == b"FUNC"), None)
    if func is None:
        print("No FUNC section (is this a .cft script file?)")
        return
    kids = func.subtags
    names = [k.name() for k in kids]
    if funcname not in names:
        print(f"No function {funcname!r}. Try: python cft.py blocks {path}")
        return
    fi = names.index(funcname)
    code = _code_of(kids[fi])
    print(f"{funcname} (func #{fi}, {len(code)} code bytes)")
    i = 0
    pushes = []
    while i < len(code) - 2:
        op = code[i]
        if op == 0x03 and i + 5 <= len(code):
            pushes.append(struct.unpack(">i", code[i + 1:i + 5])[0]); i += 5; continue
        if op == 0x04 and i + 5 <= len(code):
            pushes.append(round(struct.unpack(">f", code[i + 1:i + 5])[0], 2)); i += 5; continue
        if op == 0x0a and i + 3 <= len(code):
            rel = struct.unpack(">h", code[i + 1:i + 3])[0]
            tgt = fi + rel
            nm = names[tgt] if 0 <= tgt < len(names) else "?"
            print(f"   @0x{i:04x}  call {nm:24s} operands={pushes[-6:]}")
            pushes = []
            i += 3
            continue
        i += 1


def hexdump(b, width=16, limit=512):
    for i in range(0, min(len(b), limit), width):
        chunk = b[i:i + width]
        hx = " ".join(f"{c:02x}" for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        print(f"      {i:04x}  {hx:<{width*3}}  {asc}")
    if len(b) > limit:
        print(f"      ... ({len(b)-limit} more bytes)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__.strip())
        sys.exit(1)
    cmd, path = sys.argv[1].lower(), sys.argv[2]
    arg = sys.argv[3] if len(sys.argv) > 3 else None
    if cmd == "tree":
        cmd_tree(path)
    elif cmd == "blocks":
        cmd_blocks(path)
    elif cmd == "find":
        cmd_find(path, arg)
    elif cmd == "strings":
        cmd_strings(path, arg)
    elif cmd == "block":
        cmd_block(path, arg)
    elif cmd == "calls":
        cmd_calls(path, arg)
    else:
        print(__doc__.strip())
        sys.exit(1)
