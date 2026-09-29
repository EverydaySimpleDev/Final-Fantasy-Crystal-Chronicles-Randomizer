"""
cftpatch.py - structural (size-changing) patching of FFCC CFlat script files
(.cft), built on the read-only explorer in cft.py.

Main entry point: transplant_monster(), which makes monster `new_id` work in
a stage that was built for monster `old_id`, by copying `new_id`'s per-ID
switch cases out of a donor stage that natively supports it (miya_0.cft
supports ~163 IDs; a boss's own arena file is the best donor for a boss).
See Documentation/Monster and Boss Swapping.md for the mechanism.

    py cftpatch.py transplant <dst.cft> <donor.cft> <old_id> <new_id> <out.cft>
    py cftpatch.py group      <dst.cft> <donor.cft> <old:new,old:new,...> <out.cft>
                              # boss + helpers, plus the donor's runtime summons
    py cftpatch.py roundtrip  <file.cft>     # sanity check: parse+serialize == original

The output is usually a different size from the input, so inject it with
`gciso.py rebuild`, not `inject`.

Per-ID switch shape (every one the compiler emits looks like this):
    3A DUP; 03 <id> PUSHI; 2C ==; 08 <next> JZ; <body>; ... 07 <join> JMP
All jump args (07/08/09) are absolute code offsets within the function, so
growing or shrinking one case shifts every jump target after it.
"""

import struct
import sys

import cft

CONTAINERS = {b"CFLT", b"FUNC", b"BLCK", b"CLAS"}


# ---------------------------------------------------------------------------
# Chunk tree: lossless parse / serialize
# ---------------------------------------------------------------------------

class Chunk:
    def __init__(self, tag, a0=0, a1=0, payload=b"", children=None):
        self.tag, self.a0, self.a1 = tag, a0, a1
        self.payload = payload
        self.children = children

    def find(self, tag):
        return [c for c in self.children if c.tag == tag]

    def name(self):
        n = self.find(b"NAME")
        return n[0].payload.split(b"\x00")[0].decode("latin1") if n else None


def _pad(n):
    return (n + 15) // 16 * 16


def parse_chunks(data, pos=0, stop=None):
    stop = len(data) if stop is None else stop
    out = []
    while pos + 16 <= stop:
        tag = data[pos:pos + 4]
        length, a0, a1 = struct.unpack(">III", data[pos + 4:pos + 16])
        body = pos + 16
        if tag in CONTAINERS:
            ch = Chunk(tag, a0, a1, children=parse_chunks(data, body, body + length))
        else:
            ch = Chunk(tag, a0, a1, payload=data[body:body + length])
        ch.raw_len = length
        out.append(ch)
        pos = _pad(body + length)
    return out


def serialize(ch):
    if ch.children is not None:
        body = b"".join(_padded(serialize(c)) for c in ch.children)
    else:
        body = ch.payload
    return ch.tag + struct.pack(">III", len(body), ch.a0, ch.a1) + body


def _padded(b):
    return b + b"\x00" * (_pad(len(b)) - len(b))


class Script:
    """A whole .cft file as an editable chunk tree."""

    def __init__(self, path):
        data = open(path, "rb").read()
        self.path = path
        self.root = parse_chunks(data)[0]
        self.funcs = self.root.find(b"FUNC")[0].children
        self.names = [f.name() for f in self.funcs]
        self.str_chunk = self.root.find(b"STR ")[0]
        self.strs = self.str_chunk.payload.split(b"\x00")[:self.str_chunk.a0]

    def code(self, fn):
        return self._code_chunk(fn).payload

    def set_code(self, fn, code):
        self._code_chunk(fn).payload = bytes(code)

    def _code_chunk(self, fn):
        return self.funcs[self.names.index(fn)].find(b"CODE")[0]

    def local_count(self, fn):
        v = self.funcs[self.names.index(fn)].find(b"VAL ")
        return v[0].a0 if v else 0

    def str_index(self, s, add=True):
        if s in self.strs:
            return self.strs.index(s)
        if not add:
            return None
        self.strs.append(s)
        return len(self.strs) - 1

    def to_bytes(self):
        self.str_chunk.payload = b"".join(s + b"\x00" for s in self.strs)
        self.str_chunk.a0 = len(self.strs)
        return _padded(serialize(self.root))

    def save(self, path):
        open(path, "wb").write(self.to_bytes())


# ---------------------------------------------------------------------------
# Switch-case helpers
# ---------------------------------------------------------------------------

JUMPS = (0x07, 0x08, 0x09)
TGT = 0x00FFFFFF  # jump target = low 24 bits; top byte = &&/|| short-circuit flag


def _jumps(code):
    """(offset, opcode, target, flagbits) for every jump in `code`."""
    return [(o, op, a & TGT, a & ~TGT) for o, op, a in cft.disasm(code) if op in JUMPS]


def _is_perm(arg):
    """GET/GETA arg addressing a permanent (file-global) variable."""
    return (arg & 0x08) and not (arg & 0x10) and (arg >> 8) >= 0


def find_case(code, mid):
    """Return (hdr, body_start, end, join) for `case mid`, or None.
    join = the case's `break` target (common exit of the switch)."""
    ins = list(cft.disasm(code))
    for j in range(len(ins) - 3):
        if (ins[j][1] == 0x3A and ins[j + 1][1] == 0x03 and ins[j + 1][2] == mid
                and ins[j + 2][1] == 0x2C and ins[j + 3][1] == 0x08):
            hdr, start, end = ins[j][0], ins[j + 3][0] + 5, ins[j + 3][2] & TGT
            ext = {t for o, op, t, _ in _jumps(code) if start <= o < end and op == 0x07
                   and not (start <= t < end) and not (end <= t <= end + 13)}
            if len(ext) > 1:
                return hdr, start, end, ext  # nested exits; transplant refuses
            return hdr, start, end, (ext.pop() if ext else None)
    return None


def switch_ids(code):
    ins = list(cft.disasm(code))
    return {ins[j + 1][2] for j in range(len(ins) - 3)
            if ins[j][1] == 0x3A and ins[j + 1][1] == 0x03
            and ins[j + 2][1] == 0x2C and ins[j + 3][1] == 0x08}


def learn_var_map(dst, donor):
    """donor permanent-var index -> dst index, learned by aligning code the
    two files share: whole functions with identical opcode streams, and
    per-ID switch cases present in both. Conflicting pairs are dropped."""
    votes = {}

    def align(ca, cb):
        ia, ib = list(cft.disasm(ca)), list(cft.disasm(cb))
        if len(ia) != len(ib) or any(x[1] != y[1] for x, y in zip(ia, ib)):
            return
        for (_, op, a), (_, _, b) in zip(ia, ib):
            if op in (0x00, 0x01) and _is_perm(a) and _is_perm(b) and (a & 0xFF) == (b & 0xFF):
                votes.setdefault(a >> 8, set()).add(b >> 8)

    for fn in set(dst.names) & set(donor.names):
        if fn is None:
            continue
        cd, cs = dst.code(fn), donor.code(fn)
        align(cs, cd)
        for mid in switch_ids(cs) & switch_ids(cd):
            a, b = find_case(cs, mid), find_case(cd, mid)
            align(cs[a[1]:a[2]], cd[b[1]:b[2]])
    var_map = {k: next(iter(v)) for k, v in votes.items() if len(v) == 1}
    # Both files compile the same common headers first, so their permanent
    # VAL tables share an identical prefix; indices inside it map to
    # themselves. (Checked against the aligned votes, which must agree.)
    prefix = _common_val_prefix(dst, donor)
    for i in range(prefix):
        if var_map.setdefault(i, i) != i:
            raise ValueError(f"var {i}: aligned code disagrees with the shared VAL prefix")
    return var_map


def _val_entries(script):
    v = script.root.find(b"VAL ")[0]
    return [v.payload[i * 4:i * 4 + 4] for i in range(v.a0)]


def _common_val_prefix(a, b):
    ea, eb = _val_entries(a), _val_entries(b)
    n = 0
    while n < min(len(ea), len(eb)) and ea[n] == eb[n]:
        n += 1
    return n


# ---------------------------------------------------------------------------
# The transplant
# ---------------------------------------------------------------------------

def _remap_body(dst, donor, fn, dcode, dstart, dend, djoin, start, new_end,
                join_target, fall_target, var_map):
    """Re-encode donor code[dstart:dend] for placement at dst offset `start`,
    ending at `new_end`. Returns (bytes, list of strings added to dst).
    `fall_target` replaces the donor's (dead) fall-through jump: its offset
    depends on what follows the case - +13 before another case header, less
    before the default block - so it comes from the dst position."""
    body = bytearray()
    added = []
    for o, op, a in cft.disasm(dcode[dstart:dend]):
        o += dstart
        if op >= 0x0C:
            body.append(op)
            continue
        if op == 0x05:
            s = donor.strs[a]
            if s not in dst.strs:
                added.append(s.decode("latin1"))
            a = dst.str_index(s)
        elif op == 0x0A:
            nm = donor.names[a & 0xFFFF]
            if nm not in dst.names:
                raise ValueError(f"{fn}: donor calls {nm!r}, which dst lacks")
            a = (a & ~0xFFFF) | dst.names.index(nm)
        elif op in JUMPS:
            flags, a = a & ~TGT, a & TGT
            if dstart <= a < dend:
                a = start + (a - dstart)
            elif a == dend:
                a = new_end
            elif dend < a <= dend + 13:  # fall-through into next case / default body
                a = fall_target
            elif a == djoin and join_target is not None:
                a = join_target
            else:
                raise ValueError(f"{fn}: donor jump @0x{o:x} leaves the case (0x{a:x})")
            a |= flags
        elif op in (0x00, 0x01) and _is_perm(a):
            if (a >> 8) not in var_map:
                raise ValueError(f"{fn}: no dst equivalent for donor permanent var {a >> 8}")
            a = (var_map[a >> 8] << 8) | (a & 0xFF)
        elif op == 0x0B:
            raise ValueError(f"{fn}: donor case creates objects (NEW); not supported")
        body += bytes([op]) + struct.pack(">i", a)
    return body, added


def _check_case_pair(dst, donor, fn, join, djoin, code, start, dcode, dstart):
    if isinstance(join, set) or isinstance(djoin, set):
        raise ValueError(f"{fn}: case has more than one exit target; not supported")
    if (join is None) != (djoin is None):
        raise ValueError(f"{fn}: case exit structure differs between files")
    if donor.local_count(fn) > dst.local_count(fn):
        raise ValueError(f"{fn}: donor uses more locals than dst")
    if code[start] != 0x0C or dcode[dstart] != 0x0C:
        raise ValueError(f"{fn}: case body doesn't start with POP")


def add_case(dst, donor, fn, new_id, var_map, log):
    """Insert donor's `case new_id` into dst's switch in `fn`, as a new case
    placed in front of dst's first case. Used for monsters a boss summons
    at runtime, which need a ParamSet entry but have no case to replace."""
    code = bytearray(dst.code(fn))
    dcode = donor.code(fn)
    ids = switch_ids(code)
    if not ids:
        raise ValueError(f"{fn}: dst has no switch to add to")
    if new_id in ids:
        log.append(f"{fn}: case {new_id} already present")
        return
    H, start0, _, join = min((find_case(code, i) for i in ids), key=lambda c: c[0])
    _, dstart, dend, djoin = find_case(dcode, new_id)
    _check_case_pair(dst, donor, fn, join, djoin, code, start0, dcode, dstart)

    L = 12 + (dend - dstart)

    def reloc(t):  # jumps TO H now enter the new case first
        return t + L if t > H else t

    # The new case sits in front of the old first case header: fall-through
    # goes past that header and its POP, as for any mid-switch case.
    body, added = _remap_body(dst, donor, fn, dcode, dstart, dend, djoin,
                              H + 12, H + L, reloc(join) if join is not None else None,
                              H + L + 13, var_map)
    hdr = (bytes([0x3A, 0x03]) + struct.pack(">i", new_id) + bytes([0x2C, 0x08])
           + struct.pack(">i", H + L))
    out = bytearray()
    for o, op, a in cft.disasm(code):
        if o == H:
            out += hdr + body
        if op in JUMPS:
            a = reloc(a & TGT) | (a & ~TGT)
        out += bytes([op]) + (struct.pack(">i", a) if op < 0x0C else b"")
    assert len(out) == len(code) + L
    dst.set_code(fn, out)
    log.append(f"{fn}: added case {new_id} from donor (+{L} bytes)"
               + (f", added strings {added}" if added else ""))


def transplant_case(dst, donor, fn, old_id, new_id, var_map, log):
    """Replace dst's `case old_id` in function `fn` with donor's `case new_id`
    (remapped for dst), retargeting the case label to new_id."""
    code = bytearray(dst.code(fn))
    dcode = donor.code(fn)
    hdr, start, end, join = find_case(code, old_id)
    _, dstart, dend, djoin = find_case(dcode, new_id)
    _check_case_pair(dst, donor, fn, join, djoin, code, start, dcode, dstart)

    # Nothing outside the old body may jump into it, except the previous
    # case's fall-through to start+1 (just past the body's leading POP),
    # which stays valid because the body start doesn't move.
    for o, op, a, _ in _jumps(code):
        if not (start <= o < end) and start + 1 < a < end:
            raise ValueError(f"{fn}: outside jump @0x{o:x} into case {old_id}")

    new_len = dend - dstart
    delta = new_len - (end - start)
    new_end = end + delta

    def reloc_dst(t):  # dst targets after the old case move by delta
        return t + delta if t >= end else t

    falls = {t for o, op, t, _ in _jumps(code) if start <= o < end and end < t <= end + 13}
    if len(falls) > 1:
        raise ValueError(f"{fn}: case {old_id} has several fall-through targets")
    fall = reloc_dst(falls.pop()) if falls else new_end + 13
    body, added = _remap_body(dst, donor, fn, dcode, dstart, dend, djoin,
                              start, new_end, reloc_dst(join) if join is not None else None,
                              fall, var_map)
    assert len(body) == new_len

    # Relocate every jump outside the case, then splice.
    out = bytearray()
    for o, op, a in cft.disasm(code):
        if start <= o < end:
            continue
        if o == hdr + 1:
            a = new_id
        if op in JUMPS:
            a = reloc_dst(a & TGT) | (a & ~TGT)
        out += bytes([op]) + (struct.pack(">i", a) if op < 0x0C else b"")
        if o == start - 5:  # the case's own JZ is the last header op
            out += body
    dst.set_code(fn, out)
    log.append(f"{fn}: case {old_id} -> donor case {new_id} ({delta:+d} bytes)"
               + (f", added strings {added}" if added else ""))


def disable_case(dst, fn, old_id, log, sentinel=-0x7FFF):
    """Relabel a case so it never matches; the new monster then takes the
    switch's default path, as it does in its donor stage."""
    code = bytearray(dst.code(fn))
    hdr = find_case(code, old_id)[0]
    code[hdr + 2:hdr + 6] = struct.pack(">i", sentinel)
    dst.set_code(fn, code)
    log.append(f"{fn}: case {old_id} disabled (donor has no case {'{new}'}; default path)")


def swap_spawns(dst, old_id, new_id, log, fn="SPAWN_MONSTER", call="SPAWN"):
    code = bytearray(dst.code(fn))
    target = dst.names.index(call)
    pushes, n = [], 0
    for o, op, a in cft.disasm(code):
        if op in (0x03, 0x04, 0x05):
            pushes.append((o, op, a))
        elif op in (0x00, 0x01, 0x02):
            pushes.append((o, op, None))
        elif op == 0x0A and (a & 0xFFFF) == target:
            o0, op0, a0 = pushes[-13]
            if op0 == 0x03 and a0 == old_id:
                code[o0 + 1:o0 + 5] = struct.pack(">i", new_id)
                n += 1
            pushes = []
    dst.set_code(fn, code)
    log.append(f"{fn}: {n} {call} record(s) {old_id} -> {new_id}")
    return n


# Functions whose top-level switch is confirmed to be on monster ID. Other
# functions also contain `case <n>` labels that merely coincide with a
# monster ID (item numbers, event states, ...), so they are never touched.
MONSTER_SWITCHES = ("ParamSet", "setAttackCollision", "setDamageCollision")


def transplant_monster(dst_path, donor_path, old_id, new_id, out_path,
                       spawns=True, functions=MONSTER_SWITCHES):
    """Make `new_id` fully work in dst in place of `old_id`. For each
    monster-ID switch in `functions`:
      - dst has case old_id, donor has case new_id -> transplant donor's case
      - dst has case old_id, donor has none        -> disable it, so new_id
        takes the default path (as it does in the donor)
      - dst has no case old_id, donor has case new_id -> can't be done in
        place; reported as NOT HANDLED
    then retargets the SPAWN records. Raises before writing anything if a
    case can't be transplanted safely. Returns a log."""
    dst, donor = Script(dst_path), Script(donor_path)
    var_map = learn_var_map(dst, donor)
    log = []
    for fn in functions:
        if fn not in dst.names or fn not in donor.names:
            log.append(f"NOT HANDLED: {fn} missing from dst or donor")
            continue
        have_old = old_id in switch_ids(dst.code(fn))
        have_new = new_id in switch_ids(donor.code(fn))
        if have_old and have_new:
            transplant_case(dst, donor, fn, old_id, new_id, var_map, log)
        elif have_old:
            disable_case(dst, fn, old_id, log)
            log[-1] = log[-1].replace("{new}", str(new_id))
        elif have_new:
            log.append(f"NOT HANDLED: {fn} (donor has case {new_id}, dst has no case {old_id})")
    if spawns:
        swap_spawns(dst, old_id, new_id, log)
    dst.save(out_path)
    return log



# ---------------------------------------------------------------------------
# Whole functions and classes (arena mechanics: e.g. Lich's orbs)
# ---------------------------------------------------------------------------

import copy


def _classes(script):
    return script.root.find(b"CLAS")[0].children


def class_names(script):
    return [c.name() for c in _classes(script)]


def remap_code(dst, donor, code, var_map, where=""):
    """Re-encode a whole donor function body for dst: strings by content,
    calls by function name, permanent vars via var_map, NEW by class name.
    Jumps are function-relative, so a whole function needs no relocation."""
    dcls, dstcls = class_names(donor), class_names(dst)
    out = bytearray()
    for o, op, a in cft.disasm(code):
        if op >= 0x0C:
            out.append(op)
            continue
        if op == 0x05:
            a = dst.str_index(donor.strs[a])
        elif op == 0x0A:
            nm = donor.names[a & 0xFFFF]
            if nm not in dst.names:
                raise ValueError(f"{where}: calls {nm!r}, which dst lacks")
            a = (a & ~0xFFFF) | dst.names.index(nm)
        elif op in (0x00, 0x01) and _is_perm(a):
            if (a >> 8) not in var_map:
                raise ValueError(f"{where}: no dst equivalent for donor permanent var {a >> 8}")
            a = (var_map[a >> 8] << 8) | (a & 0xFF)
        elif op == 0x0B:
            nm = dcls[a]
            if nm not in dstcls:
                raise ValueError(f"{where}: creates class {nm!r}, which dst lacks")
            a = dstcls.index(nm)
        out += bytes([op]) + struct.pack(">i", a)
    return bytes(out)


def import_functions(dst, donor, names, log):
    """Append donor functions that dst lacks (names only; bodies are
    remapped later by finish_functions, once every name is resolvable)."""
    func_chunk = dst.root.find(b"FUNC")[0]
    for nm in names:
        if nm in dst.names:
            raise ValueError(f"import: dst already has {nm!r}")
        blk = copy.deepcopy(donor.funcs[donor.names.index(nm)])
        func_chunk.children.append(blk)
        dst.names.append(nm)
    func_chunk.a0 = len(func_chunk.children)
    dst.funcs = func_chunk.children
    log.append(f"FUNC: appended {len(names)} function(s): {names}")


def replace_function(dst, donor, nm, log):
    """Overwrite dst's function `nm` with the donor's version (locals, return
    info and code). Body remapped later by finish_functions."""
    i = dst.names.index(nm)
    dst.funcs[i].children = copy.deepcopy(donor.funcs[donor.names.index(nm)].children)
    log.append(f"FUNC: replaced {nm!r} with donor version")


def finish_functions(dst, donor, names, var_map):
    for nm in names:
        blk = dst.funcs[dst.names.index(nm)]
        code = blk.find(b"CODE")[0]
        code.payload = remap_code(dst, donor, donor.code(nm), var_map, nm)


def import_class(dst, donor, cname, log):
    """Append a donor class (NAME/INFO/VTBL/VAL). VTBL slots hold function
    indices, remapped by name - so import the methods first."""
    clas = dst.root.find(b"CLAS")[0]
    if cname in class_names(dst):
        raise ValueError(f"import: dst already has class {cname!r}")
    c = copy.deepcopy(_classes(donor)[class_names(donor).index(cname)])
    vt = c.find(b"VTBL")[0]
    slots = bytearray(vt.payload)
    for k in range(len(slots) // 4):
        fi = struct.unpack(">i", slots[k * 4:k * 4 + 4])[0]
        if fi >= 0:
            nm = donor.names[fi]
            if nm not in dst.names:
                raise ValueError(f"class {cname}: method {nm!r} not in dst")
            slots[k * 4:k * 4 + 4] = struct.pack(">i", dst.names.index(nm))
    vt.payload = bytes(slots)
    clas.children.append(c)
    clas.a0 = len(clas.children)
    log.append(f"CLAS: appended class {cname!r} as index {len(clas.children) - 1}")


def extend_class_members(dst, donor, cname, log):
    """Make sure dst's class has at least as many members as the donor's, so
    donor methods copied into it can address every member they use. Missing
    members are appended from the donor's table. Members are raw 4-byte slots
    (each load/store opcode picks int or float), so a type difference in an
    existing slot doesn't matter to copied code."""
    dv = _classes(donor)[class_names(donor).index(cname)].find(b"VAL ")[0]
    tv = _classes(dst)[class_names(dst).index(cname)].find(b"VAL ")[0]
    if dv.a0 > tv.a0:
        log.append(f"CLAS: {cname} members {tv.a0} -> {dv.a0}")
        tv.payload = tv.payload + dv.payload[tv.a0 * 4:dv.a0 * 4]
        tv.a0 = dv.a0


def append_before_return(dst, fn, code_bytes, log):
    """Insert code at the end of `fn`, before its final PUSH0/RET, provided
    nothing jumps to that tail."""
    code = dst.code(fn)
    if code[-2:] != b"\x3f\x3c":
        raise ValueError(f"{fn}: doesn't end with PUSH0/RET")
    L = len(code) - 2
    if any(t >= L for _, _, t, _ in _jumps(code)):
        raise ValueError(f"{fn}: something jumps to the tail; can't append safely")
    dst.set_code(fn, code[:L] + code_bytes + code[L:])
    log.append(f"{fn}: appended {len(code_bytes)} bytes before return")


def encode_call(dst, fn, args):
    """Bytecode for `fn(*args); POP`. Ints -> PUSHI, floats -> PUSHF (negative
    floats use PUSHF |x| + NEG, as the compiler emits them)."""
    out = bytearray()
    for v in args:
        if isinstance(v, float):
            out += b"\x04" + struct.pack(">f", abs(v))
            if v < 0:
                out.append(0x2B)
        else:
            out += b"\x03" + struct.pack(">i", v)
    out += b"\x0a" + struct.pack(">I", (0xFFFF << 16) | dst.names.index(fn)) + b"\x0c"
    return bytes(out)


def import_lich_orbs(dst, donor, var_map, orb_positions, log):
    """Bring Lich's orb/shield mechanic from its arena (city_2) into dst:
      - SwitchSphere class + its methods and helpers (resInit/resLoop/resFunc)
      - SPAWN_SWITCH_SPHERE (dst has an empty stub from the common header)
      - JochuSE's init/main, which drive sysControl(3, ...) = the boss state
        the engine reads for Lich's shield (bit0) and phase (bit1)
      - two SPAWN_SWITCH_SPHERE calls inserted at the start of SPAWN_MONSTER"""
    methods = [n for n in donor.names if n and n.endswith("SwitchSphere")
               and n != "SPAWN_SWITCH_SPHERE"]
    helpers = ["resInit", "resLoop", "resFunc"]
    new_fns = [n for n in helpers + methods if n not in dst.names]
    import_functions(dst, donor, new_fns, log)
    for nm in ("SPAWN_SWITCH_SPHERE", "initJochuSE", "mainJochuSE"):
        replace_function(dst, donor, nm, log)
    import_class(dst, donor, "SwitchSphere", log)
    extend_class_members(dst, donor, "JochuSE", log)
    finish_functions(dst, donor, new_fns + ["SPAWN_SWITCH_SPHERE", "initJochuSE", "mainJochuSE"],
                     var_map)
    calls = b"".join(encode_call(dst, "SPAWN_SWITCH_SPHERE",
                                 [30200 + i, 0, float(x), float(y), float(z), 5.0, 10.0, 5.0, 6145])
                     for i, (x, y, z) in enumerate(orb_positions))
    # At the start, not the end: some arenas' SPAWN_MONSTER has early-return
    # paths, and the start is the one point every path runs.
    insert_code(dst, "SPAWN_MONSTER", 0, calls, log)



def insert_code(dst, fn, at, code_bytes, log):
    """Insert raw bytecode into `fn` at instruction offset `at`. Jumps to
    targets after `at` shift by the inserted length; jumps to `at` itself
    now land on the inserted code (so a loop's `continue` still runs it).
    `code_bytes` must already use final (post-insertion) jump targets."""
    code = dst.code(fn)
    if at not in {o for o, _, _ in cft.disasm(code)}:
        raise ValueError(f"{fn}: 0x{at:x} is not an instruction boundary")
    L = len(code_bytes)
    out = bytearray()
    for o, op, a in cft.disasm(code):
        if o == at:
            out += code_bytes
        if op in JUMPS:
            t = a & TGT
            a = (t + L if t > at else t) | (a & ~TGT)
        out += bytes([op]) + (struct.pack(">i", a) if op < 0x0C else b"")
    dst.set_code(fn, out)
    log.append(f"{fn}: inserted {L} bytes at 0x{at:x}")


def add_class_member(dst, cname, log, kind=1):
    """Append one member to a class (VAL entry = type, flags, name-index;
    the name index is debug-only, so the last member of that type's is
    reused). Returns the new member's `this[]` index."""
    v = _classes(dst)[class_names(dst).index(cname)].find(b"VAL ")[0]
    ents = [v.payload[i * 4:i * 4 + 4] for i in range(v.a0)]
    tmpl = next(e for e in reversed(ents) if e[0] == kind)
    v.payload += tmpl
    v.a0 += 1
    log.append(f"CLAS: {cname} gained member this[{v.a0 - 1}]")
    return v.a0 - 1


def _sys_call(dst, name, high16):
    # high16: 0xFFFF for script-level functions; for engine class functions
    # it is the engine command number (e.g. setDamageColMask = 0xFFD0 = -0x30).
    return b"\x0a" + struct.pack(">I", (high16 << 16) | dst.names.index(name))


def loop_body_start(dst, fn):
    """Offset of a `while (1)` body: `fn` must open with PUSHI 1; JZ <end>
    and jump back to 0 at the bottom."""
    code = dst.code(fn)
    ins = list(cft.disasm(code))
    if not (ins[0][1] == 0x03 and ins[0][2] == 1 and ins[1][1] == 0x08):
        raise ValueError(f"{fn}: doesn't start with while(1)")
    if not any(t == 0 for _, op, t, _ in _jumps(code) if op == 0x07):
        raise ValueError(f"{fn}: no back-jump to the loop head")
    return ins[2][0]


def add_orb_shield(dst, boss_id, log, fn="mainMonster_Logic", monster_id_member=18):
    """Make any boss invulnerable while the orb boss state (sysControl 3,
    bit 0 - kept by JochuSE from the SwitchSphere orbs) is set, the same way
    the engine's CGMonObj::enableDamageCol() does it: damage colliders 0 and
    1 get hit mask 0 (off) / 1 (on). Runs at the top of the monster's main
    loop and acts only when the state changes, so it never fights the
    engine's own enable/disable calls in between:

        if (this[18] == boss_id) {
            s = getSysControl(3) & 1;
            if (s != this[last]) {
                this[last] = s;
                if (s) { setDamageColMask(0,0); setDamageColMask(1,0); }
                else   { setDamageColMask(0,1); setDamageColMask(1,1); }
            }
        }
    """
    last = add_class_member(dst, "Monster_Logic", log)
    at = loop_body_start(dst, fn)
    THIS = 0x19

    def get(i):
        return b"\x00" + struct.pack(">i", (i << 8) | THIS)

    def geta(i):
        return b"\x01" + struct.pack(">i", (i << 8) | THIS)

    def pushi(v):
        return b"\x03" + struct.pack(">i", v)

    shield_bit = pushi(3) + _sys_call(dst, "getSysControl", 0xFFFF) + pushi(1) + b"\x1f"

    def mask(idx, m):
        return pushi(idx) + pushi(m) + _sys_call(dst, "setDamageColMask", 0xFFD0) + b"\x0c"

    parts = [
        get(monster_id_member) + pushi(boss_id) + b"\x2c",   # this[18] == boss
        ("JZ", "SKIP"),
        shield_bit + get(last) + b"\x2d",                    # s != this[last]
        ("JZ", "SKIP"),
        geta(last) + shield_bit + b"\x0d\x0c",               # this[last] = s
        get(last),
        ("JZ", "RESTORE"),
        mask(0, 0) + mask(1, 0),                              # shield up
        ("JMP", "SKIP"),
        "RESTORE",
        mask(0, 1) + mask(1, 1),                              # shield down
        "SKIP",
    ]
    labels, pos = {}, at
    for p in parts:
        if isinstance(p, str):
            labels[p] = pos
        else:
            pos += 5 if isinstance(p, tuple) else len(p)
    out = bytearray()
    for p in parts:
        if isinstance(p, tuple):
            out += (b"\x08" if p[0] == "JZ" else b"\x07") + struct.pack(">i", labels[p[1]])
        elif isinstance(p, bytes):
            out += p
    insert_code(dst, fn, at, bytes(out), log)
    log.append(f"{fn}: orb shield for monster {boss_id} (state member this[{last}])")
    return last


def spawned_ids(script, fn="SPAWN_MONSTER", call="SPAWN"):
    target = script.names.index(call)
    pushes, ids = [], []
    for o, op, a in cft.disasm(script.code(fn)):
        if op in (0x03, 0x04, 0x05):
            pushes.append((op, a))
        elif op in (0x00, 0x01, 0x02):
            pushes.append((op, None))
        elif op == 0x0A and (a & 0xFFFF) == target and len(pushes) >= 13:
            ids.append(pushes[-13][1])
            pushes = []
    return ids


def runtime_ids(donor):
    """Monster IDs the donor's ParamSet supports but its SPAWN_MONSTER never
    spawns directly - i.e. monsters summoned at runtime (boss adds)."""
    return sorted(switch_ids(donor.code("ParamSet")) - set(spawned_ids(donor)))


def transplant_group(dst_path, donor_path, pairs, out_path, add_ids=None,
                     functions=MONSTER_SWITCHES):
    """Boss version of transplant_monster: apply several old->new swaps
    (e.g. boss and its helpers) in one pass, then add cases for `add_ids`
    (default: the donor's runtime-summoned IDs)."""
    dst, donor = Script(dst_path), Script(donor_path)
    var_map = learn_var_map(dst, donor)
    add_ids = runtime_ids(donor) if add_ids is None else add_ids
    log = []
    for old_id, new_id in pairs:
        for fn in functions:
            have_old = old_id in switch_ids(dst.code(fn))
            have_new = new_id in switch_ids(donor.code(fn))
            if have_old and have_new:
                transplant_case(dst, donor, fn, old_id, new_id, var_map, log)
            elif have_old:
                disable_case(dst, fn, old_id, log)
                log[-1] = log[-1].replace("{new}", str(new_id))
            elif have_new:
                add_case(dst, donor, fn, new_id, var_map, log)
        swap_spawns(dst, old_id, new_id, log)
    for new_id in add_ids:
        for fn in functions:
            if new_id in switch_ids(donor.code(fn)):
                add_case(dst, donor, fn, new_id, var_map, log)
    dst.save(out_path)
    return log


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "roundtrip":
        orig = open(sys.argv[2], "rb").read()
        print("roundtrip identical:", Script(sys.argv[2]).to_bytes() == orig)
    elif len(sys.argv) == 6 and sys.argv[1] == "group":
        pairs = [tuple(map(int, p.split(":"))) for p in sys.argv[4].split(",")]
        for line in transplant_group(sys.argv[2], sys.argv[3], pairs, sys.argv[5]):
            print(line)
    elif len(sys.argv) == 7 and sys.argv[1] == "transplant":
        for line in transplant_monster(sys.argv[2], sys.argv[3], int(sys.argv[4]),
                                       int(sys.argv[5]), sys.argv[6]):
            print(line)
    else:
        print(__doc__.strip())
