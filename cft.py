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
    python cft.py sysvals cave_0.cft mainTreasureBox  # find literal "system value" get/set

Opcode table (FFCC CFlat script VM), reverse-engineered from the decompiled
VM interpreter (CFlatRuntime::objectFrame / CFlatRuntime2::onSystemVal /
onSetSystemVal in zcanann/FFCC-Decomp's reference-decomp, src/cflat_runtime.cpp
and src/cflat_r2system.cpp). The interpreter's own opcode-length rule
(cflat_runtime.cpp:1145): every opcode < 0x0C is 5 bytes (1 opcode byte + a
4-byte big-endian argument word); every opcode >= 0x0C is a bare 1 byte, no
operand. Earlier hand-guessed decoding only special-cased 0x03/0x04 (push
int32/float32) and 0x0a (call, wrongly assumed 3 bytes) as having operands,
silently desyncing the byte stream the first time any other <0x0C opcode
(0x00-0x02, 0x05-0x09, 0x0b) appeared - that's `disasm()` below, fixed.

  0x00 GET   value-by-index (local/global/"this"/system-value per arg flags)
  0x01 GETA  address-of same (paired with 0x0d/0x0e/0x0f "store" for assignment)
  0x02 SELV  push packed system-value selector (index<<13 | classId), consumed
             by 0x13/0x14/0x15 (or their 0x16/0x17/0x18 twins) to set a system
             value/event-flag bit. The "index" is the same literal constant
             CFlatRuntime2::onSystemVal/onSetSystemVal switch on.
  0x03 PUSHI push int32       0x04 PUSHF push float32       0x05 PUSHI (alt)
  0x06 CTX   context switch (dynamic call frame rebind)
  0x07 JMP   unconditional jump (24-bit relative codeOffset)
  0x08 JZ    pop; jump if zero          0x09 JNZ  pop; jump if nonzero
  0x0a CALL  call (arg: low16=func index, high16=dispatch flag)
  0x0b NEW   createObject(classIndex)
  0x0c POP   0x0d STORE   0x0e ADDSTORE   0x0f SUBSTORE
  0x10 FSTORE  0x11 FADDSTORE  0x12 FSUBSTORE
  0x13/0x16 SETSYS=   0x14/0x17 SETSYS+=   0x15/0x18 SETSYS-=
     (pop value + packed selector from 0x02; setMode 0/1/-1 into
      CFlatRuntime2::onSetSystemVal - this is how a chest-open flag or
      m_chaliceElement actually gets written)
  0x2c-0x37 comparisons (==, !=, <, <=, >, >=, int/float)
  0x39 RESTORECTX   0x3a DUP   0x3c RET   0x3d F2I   0x3e I2F
  0x3f PUSH0

For a negative system-value index in (-1000, -500], CFlatRuntime2's handler
treats it as a bit in `CGameWork::m_eventFlags[256]` (game.h, offset 0x10CC):
    bitIndex = index + 0x9F3 ; byte = bitIndex // 8 ; bit = bitIndex % 8
This is the same generic flag bank `m_chaliceElement` (index -0x66) lives
next to - almost certainly the backing store for the AP client's per-dungeon
chest-open flags. See `sysval_desc()` / `cmd_sysvals` below.
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


def code_abs_offset(path, block):
    """Return the absolute file offset of `block`'s CODE data (i.e. offset 0 of
    what disasm()/_code_of() operate on). NOTE: `block.bin`'s own byte content
    is NOT contiguous with `block.off + 16` - recognized child subtags (NAME/
    INFO/VAL/...) are parsed out as proper Nodes first and are NOT included in
    `.bin`, so an index within `.bin` does not correspond to `block.off + 16 +
    index`. This re-walks the block's raw byte range the same way Node.__init__
    does (skipping each recognized subtag, 16-byte aligned) to find where the
    unrecognized tail (RET/CODE/...) actually starts in the file, then locates
    the literal b"CODE" tag within that tail."""
    with open(path, "rb") as f:
        data = f.read()
    stop = block.off + 16 + block.length
    pos = block.off + 16
    for sub in block.subtags:
        pos = sub.off + 16 + sub.length
        pos = pos + (16 - 1 - (pos - 1) % 16)  # same 16-byte alignment as the parser
    i = data[pos:stop].find(b"CODE")
    if i < 0:
        raise ValueError("no CODE tag found in this block's raw tail")
    return pos + i + 16


def disasm(code):
    """Yield (offset, opcode, arg) for one function's raw CODE bytes, using the
    real CFlat VM's fixed-width encoding (see module docstring / cft.py's
    opcode table): opcode < 0x0C carries a 4-byte big-endian signed argument
    (5 bytes total); opcode >= 0x0C is a bare 1-byte opcode, arg=None.
    This replaces the old ad-hoc 0x03/0x04/0x0a-only decoding, which
    desynced on any other <0x0C opcode (0x00-0x02, 0x05-0x09, 0x0b)."""
    i, n = 0, len(code)
    while i < n:
        op = code[i]
        if op < 0x0C:
            if i + 5 > n:
                break
            arg = struct.unpack(">i", code[i + 1:i + 5])[0]
            yield i, op, arg
            i += 5
        else:
            yield i, op, None
            i += 1


def sysval_desc(index):
    """Describe a literal CFlat 'system value' index, per the decompiled
    CFlatRuntime2::onSystemVal/onSetSystemVal switch (cflat_r2system.cpp)."""
    if -1000 < index <= -500:
        bit = index + 0x9F3
        return f"eventFlags byte={bit // 8} bit={bit % 8}"
    if index == -0x66:
        return "m_chaliceElement (1=fire,2=water,4=wind,8=earth,16=holy)"
    if -200 >= index > -0x1000:
        # handled by other named CGameWork fields (timerA, frameCounter, ...)
        # or the -200..-999 m_eventWork[] table; not a boolean flag.
        return "(non-flag system value)"
    return "?"


def cmd_calls(path, funcname):
    """Disassemble one function's calls using the corrected opcode widths
    (see disasm()). Calls are resolved against the FUNC table by relative
    index; int/float pushed beforehand are shown as candidate operands."""
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
    pushes = []
    for off, op, arg in disasm(code):
        if op == 0x03 or op == 0x05:
            pushes.append(arg)
        elif op == 0x04:
            pushes.append(round(struct.unpack(">f", struct.pack(">i", arg))[0], 2))
        elif op == 0x0a:
            # arg & 0xFFFF is an absolute index into the FUNC table (not
            # relative to the calling function) - CFlatRuntime::objectFrame
            # case 0x0A: `func = m_funcs + (arg & 0xFFFF)`. High 16 bits >= 0
            # (as signed) means it's virtually redirected per-class at
            # runtime, so the printed name is the compile-time target only.
            tgt = arg & 0xFFFF
            nm = names[tgt] if 0 <= tgt < len(names) else "?"
            virt = " (virtual)" if (arg >> 16) >= 0 else ""
            print(f"   @0x{off:04x}  call {nm:24s}{virt} operands={pushes[-6:]}")
            pushes = []


def cmd_sysvals(path, funcname):
    """Find literal CFlat 'system value' get/set indices in one function -
    e.g. the literal chest-open-flag index a TreasureBox instance's script
    reads/writes, or an element index a HotSpot writes to m_chaliceElement.
    See sysval_desc() / the module docstring's opcode table for how the
    literal index maps to a concrete game-memory byte/bit."""
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
    ops = list(disasm(code))
    for i, (off, op, arg) in enumerate(ops):
        if op in (0x00, 0x01) and arg is not None:
            index = arg >> 8
            mode = arg & 0xFF
            # (mode & 1): direct literal index. (mode & 2): index + a runtime
            # stack offset (not statically resolvable - the literal alone
            # isn't the real value, so it's flagged as such).
            if index < 0 and (mode & 0x10):
                what = "GETA" if op == 0x01 else "GET "
                dyn = "" if (mode & 1) else "  [+ runtime offset, not static]"
                print(f"   @0x{off:04x}  {what} sysval index={index:<6d} {sysval_desc(index)}{dyn}")
        elif op == 0x02 and arg is not None:
            index = arg >> 8
            setop = next((o for (_, o, _) in ops[i + 1:i + 6]
                          if o in (0x13, 0x14, 0x15, 0x16, 0x17, 0x18)), None)
            modestr = {0x13: '=', 0x16: '=', 0x14: '+=', 0x17: '+=',
                       0x15: '-=', 0x18: '-='}.get(setop, '? (no set op found nearby)')
            print(f"   @0x{off:04x}  SET{modestr:<4s} sysval index={index:<6d} {sysval_desc(index)}")


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
    elif cmd == "sysvals":
        cmd_sysvals(path, arg)
    else:
        print(__doc__.strip())
        sys.exit(1)
