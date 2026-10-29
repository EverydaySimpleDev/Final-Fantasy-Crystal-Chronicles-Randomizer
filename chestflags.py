"""
chestflags.py - which "chest opened" bit belongs to which Game8 chest number,
read from the game files, so the AP client reports the same chest the
patcher wrote the item into.

Every chest is a SPAWN_TBOX record [127, A, 0, B, x, y, z, rot] (see
spawn_map.py):
  A = get_treasure case number in the low 16 bits (get_treasure is a switch
      on it, the case's body holds the chest's loot set, lootcft.find_sets
      order). Some dungeons (Daemon's Court, Veo Lu Sluice) also set a value
      in the high 16 bits - meaning unknown, kept as `extra`.
  B = chest flag + 1. Bit n of the chest-flag words at 0x80926000 is
      byte (3 - n % 32 // 8) + 4 * (n // 32), bit n % 8 - i.e. bit n of
      big-endian 32-bit words.
The patcher maps (area, loot set) -> Game8 chest number with
randomizer.dungeon_chest_map(), so going record -> loot set -> chest number
gives the same numbering the AP locations use.

    py chestflags.py ISO                      # print the flag table per dungeon
    py chestflags.py export ISO chest_table.py  # write the AP world's location table
    py chestflags.py positions ISO chests.json  # chest positions for tracker pins
"""

import os
import sys
import tempfile

import cft
import lootcft
import spawn_map


def flag_to_byte_bit(n):
    return 4 * (n // 32) + 3 - (n % 32) // 8, n % 8


def _case_ranges(path):
    """{case number: (start, end)} for get_treasure's outer switch (file offsets)."""
    root, data = cft.parse(path)
    func = next(s for s in root.subtags if s.type == b"FUNC")
    names = [k.name() for k in func.subtags]
    if "get_treasure" not in names:
        return {}
    code = cft._code_of(func.subtags[names.index("get_treasure")])
    base = data.find(code)
    ops = list(cft.disasm(code))
    cases = []
    for i in range(len(ops) - 3):
        o0, o1, o2, o3 = ops[i:i + 4]
        if o0[1] == 0x3A and o1[1] == 3 and o2[1] == 0x2C and o3[1] == 8:
            cases.append((o1[2], base + o0[0], base + (o3[2] & 0xFFFFFF)))
    # outer cases are the ones whose body contains inner cases (they're long)
    outer = {}
    for cid, start, end in cases:
        if end - start > 0x200:
            outer[cid] = (start, end)
    return outer


def chest_table(ref_iso, script, discs):
    """[(area, A, flag, game8 chest, world xyz)] for every chest in the dungeon."""
    import randomizer
    chest_no = randomizer.dungeon_chest_map(ref_iso, script, discs)
    out = []
    for disc in discs:
        tmp = os.path.join(tempfile.gettempdir(), "cf_" + os.path.basename(disc))
        randomizer._extract(ref_iso, disc, tmp)
        area = randomizer._area_no(disc)
        ranges = _case_ranges(tmp)
        sets = lootcft.find_sets(tmp, valid=randomizer.is_item)
        set_of_case = {}
        for si, s in enumerate(sets):
            for cid, (lo, hi) in ranges.items():
                if lo <= s[0][0] < hi:
                    set_of_case[cid] = si
        for rec in spawn_map.chests(tmp):
            a, b = rec["A"] & 0xFFFF, rec["B"]
            si = set_of_case.get(a)
            out.append((area, a, b - 1, chest_no.get((area, si)), rec.get("world")))
    return out


CYCLE_BITS = {1: 0x10, 2: 0x20, 3: 0x40}   # SPAWN_TBOX first field

# Chests that can't be reached in some cycles even though their loot isn't
# empty there (the game data doesn't show this): {dungeon script: {chest: [cycles]}}.
UNREACHABLE = {
    "gob": {9: [1], 10: [1]},     # the upper-left ledge of area 2
    "water": {5: [1], 12: [1]},   # under water until it drops in year 5
}

# Chests that can be reached in a cycle whose vanilla loot slot is empty (the
# game data doesn't show this either). The patcher fills that slot like any other.
REACHABLE = {
    "kinoko": {6: [2], 8: [3]},
    "lava": {2: [1], 7: [1, 2], 8: [1]},
}


def _slot_has_loot(data, info):
    """True if a vanilla slot gives anything (item or gil)."""
    import struct
    if not info:
        return False
    offs = ([info["item"]] if info["item"] else []) + info["gil"]
    return any(struct.unpack(">i", data[o:o + 4])[0] for o in offs)


def canonical(iso, script, discs):
    """The dungeon's chests in the game's own order. Records that share a
    chest-opened flag are one chest (the same chest at alternative spots).
    Separate chests that share a loot case in vanilla always gave the same
    item. _area_split() moves all but one of them to a loot case of their own,
    so each is its own location. Returns a list of dicts:
        chest   1..K for the vanilla chests, in order of each chest's lowest
                flag. Chests split off a shared case come after, as K+1...
        area    area file number.  case = get_treasure case (A) the chest uses
                after the split.  set = loot set index of its vanilla case
        flags   chest-opened flag numbers (B - 1)
        cycles  cycles the chest is a location in: it spawns (record cycle
                bits) AND its vanilla loot in that cycle's slot (0/2/4, the
                one AP seeds use) isn't empty, plus the REACHABLE list and
                minus the UNREACHABLE list. Chests a player can't reach in
                a cycle are left empty there in vanilla. This matches the
                Game8 per-cycle chest counts exactly for 10 of 14 dungeons and
                only ever under-counts elsewhere, except Veo Lu Sluice cycle 1
                (2 more than Game8's 5).
        items   True if slots 0/2/4 can hold an item (treasure.py) - every
                chest, gil-only ones included, since gil can be cleared
        gil     True for chests that give only gil in vanilla
        world   position of the first record
        retarget  [(file offset, new A)] - the SPAWN_TBOX edits that move a
                split-off chest to its own case (empty for the others)
    """
    import randomizer
    import treasure
    groups = {}
    for disc in discs:
        tmp = os.path.join(tempfile.gettempdir(), "cf_" + os.path.basename(disc))
        randomizer._extract(iso, disc, tmp)
        area = randomizer._area_no(disc)
        ranges = _case_ranges(tmp)
        sets = lootcft.find_sets(tmp, valid=randomizer.is_item)
        set_of_case = {}
        for si, s in enumerate(sets):
            for cid, (lo, hi) in ranges.items():
                if lo <= s[0][0] < hi:
                    set_of_case[cid] = si
        raw = open(tmp, "rb").read()
        split = _area_split(tmp)
        records = {off: (mask, a, flag) for off, mask, a, flag in _chest_case_pushes(tmp)}
        for addr, r, w in spawn_map._records(tmp, "SPAWN_TBOX"):
            mask, vanilla_case, extra, flag = r[0], r[1] & 0xFFFF, r[1] >> 16, r[3] - 1
            case = split.get(flag, vanilla_case)
            g = groups.setdefault((area, case), {
                "area": area, "case": case, "extra": extra, "set": set_of_case.get(vanilla_case),
                "flags": [], "cycles": set(), "world": tuple(w[4:7]),
                "split": flag in split, "retarget": []})
            if flag not in g["flags"]:
                g["flags"].append(flag)
            if flag in split:
                g["retarget"] = [(off, (a & ~0xFFFF) | case)
                                 for off, (m, a, f) in records.items() if f == flag]
            if "items" not in g:
                sl = treasure.case_slots(raw, *ranges[case])
                g["items"] = all(sl.get(s, {}).get("item") for s in treasure.CYCLE_SLOT.values())
            # cycles follow the vanilla loot (an empty vanilla slot means the
            # chest isn't meant to be found in that cycle)
            vanilla = treasure.case_slots(raw, *ranges[vanilla_case])
            g["cycles"] |= {c for c, bit in CYCLE_BITS.items()
                            if mask & bit and _slot_has_loot(raw, vanilla.get(treasure.CYCLE_SLOT[c]))}
    vanilla_chests = sorted((g for g in groups.values() if not g["split"]), key=lambda g: min(g["flags"]))
    split_chests = sorted((g for g in groups.values() if g["split"]), key=lambda g: (g["area"], min(g["flags"])))
    chests = vanilla_chests + split_chests
    blocked = UNREACHABLE.get(script, {})
    extra = REACHABLE.get(script, {})
    for n, g in enumerate(chests, 1):
        g["chest"] = n
        g["flags"].sort()
        g["cycles"] = sorted((set(g["cycles"]) | set(extra.get(n, []))) - set(blocked.get(n, [])))
        g["gil"] = g["set"] is None
    return chests


ARTIFACT_IDS = range(0x9F, 0xE8)   # artifacts and Spell Rings


def _spawn_calls(path, func_name, nargs):
    """The argument pushes of every `func_name` call in the SPAWN_MONSTER
    block: [[(file offset, opcode, value) per argument], ...]."""
    root, _ = cft.parse(path)
    func = next((s for s in root.subtags if s.type == b"FUNC"), None)
    if func is None:
        return []
    names = [k.name() for k in func.subtags]
    if "SPAWN_MONSTER" not in names or func_name not in names:
        return []
    block = func.subtags[names.index("SPAWN_MONSTER")]
    abs0 = cft.code_abs_offset(path, block)
    target = names.index(func_name)
    out, pushes = [], []
    for off, op, arg in cft.disasm(cft._code_of(block)):
        if op in (0, 1, 2, 3, 4, 5):
            pushes.append((abs0 + off, op, arg))
        elif op == 0x0a:
            if (arg & 0xFFFF) == target and len(pushes) >= nargs:
                out.append(pushes[-nargs:])
            pushes = []
    return out


def _monster_drop_pushes(path):
    """[(file offset of E's PUSHI, E)] for every SPAWN (monster) record. E's
    low 16 bits pick the get_treasure case, and its top 4 bits (if set) mark the
    monster as a door-key carrier and are left alone."""
    return [(args[10][0], args[10][2]) for args in _spawn_calls(path, "SPAWN", 13) if args[10][1] == 3]


def _chest_case_pushes(path):
    """[(file offset of A's PUSHI, mask, A, flag)] for every SPAWN_TBOX
    (chest) record [mask, A, 0, B, x, y, z, rot], with flag = B - 1."""
    return [(args[1][0], args[0][2], args[1][2], args[3][2] - 1)
            for args in _spawn_calls(path, "SPAWN_TBOX", 8) if args[1][1] == 3]


def _sphere_cases(path):
    """get_treasure cases used by SPAWN_SWITCH_SPHERE records (second argument)."""
    return {args[1][2] & 0xFFFF for args in _spawn_calls(path, "SPAWN_SWITCH_SPHERE", 9)}


def _area_split(path):
    """{flag: new case} for the chests of one area file that share a loot case
    with another chest. The chest with the lowest flag keeps the vanilla case,
    and each other one gets a case of its own: first one nobody uses, then one only
    monsters use (separate_monster_drops() moves those monsters away, since
    the case now belongs to a chest). Only cases whose cycle slots (0/2/4) can
    hold an item are used. Chests left over when no case is free stay shared."""
    import collections
    import treasure

    ranges = _case_ranges(path)
    if not ranges:
        return {}
    data = open(path, "rb").read()
    flags_of = collections.defaultdict(set)
    for _, mask, a, flag in _chest_case_pushes(path):
        flags_of[a & 0xFFFF].add(flag)
    chest_cases = set(flags_of)
    monster_uses = collections.Counter(e & 0xFFFF for _, e in _monster_drop_pushes(path))
    spheres = _sphere_cases(path)

    def writable(case):
        sl = treasure.case_slots(data, *ranges[case])
        return all(sl.get(s, {}).get("item") for s in treasure.CYCLE_SLOT.values())

    free = sorted(c for c in ranges if c not in chest_cases and c not in monster_uses
                  and c not in spheres and writable(c))
    free += sorted((c for c in monster_uses if c in ranges and c not in chest_cases
                    and c not in spheres and writable(c)), key=lambda c: (monster_uses[c], c))
    split = {}
    for case in sorted(flags_of):
        for flag in sorted(flags_of[case])[1:]:
            if not free:
                return split
            split[flag] = free.pop(0)
    return split


def split_chest_cases(path):
    """Cases that chests use after _area_split() - for separate_monster_drops()."""
    return set(_area_split(path).values())


def separate_monster_drops(path, buf, extra_chest_cases=()):
    """Point monsters away from loot that belongs to chests.

    Monsters (SPAWN's E) and chests (SPAWN_TBOX's A) pick from the same
    get_treasure cases, so a monster sharing a chest's case drops whatever is
    written into that chest, and some monster-only cases roll artifacts. Each
    monster whose case is a chest case, or rolls an artifact in a cycle slot
    (0/2/4, see treasure.CYCLE_SLOT), is moved to another monster-only case in
    the same file with no artifacts in those slots - one with the same kind of
    loot (gil-only or not) if there is one, preferring the case most monsters
    already use. `path` is the vanilla area file (read for the analysis),
    `buf` its bytes to edit in place. `extra_chest_cases` are cases that
    chests use after a split (see _area_split). Returns [(old E, new E)]."""
    import collections
    import struct
    import treasure

    ranges = _case_ranges(path)
    if not ranges:
        return []
    data = open(path, "rb").read()
    drops = _monster_drop_pushes(path)
    chest_cases = {c["A"] & 0xFFFF for c in spawn_map.chests(path)} | set(extra_chest_cases)

    def values(case):
        """Drops in the cycle slots (0/2/4) - the only ones rolled in AP seeds."""
        sl = treasure.slot_drops(data, *ranges[case])
        return [d for s in treasure.CYCLE_SLOT.values() for d in sl.get(s, [])]

    def gil_only(case):
        vals = values(case)
        return bool(vals) and all(kind == "gil" for kind, _ in vals)

    def has_artifact(case):
        return any(kind == "item" and v in ARTIFACT_IDS for kind, v in values(case))

    uses = collections.Counter(e & 0xFFFF for _, e in drops)
    safe = [c for c in ranges if c not in chest_cases and c in uses
            and not has_artifact(c) and values(c)]
    safe.sort(key=lambda c: (-uses[c], c))

    changes = []
    for off, e in drops:
        case = e & 0xFFFF
        if case not in ranges or (case not in chest_cases and not has_artifact(case)):
            continue
        same_kind = [c for c in safe if gil_only(c) == gil_only(case)]
        pick = (same_kind or safe or [None])[0]
        if pick is None:
            continue
        if buf[off] != 3 or struct.unpack(">i", bytes(buf[off + 1:off + 5]))[0] != e:
            raise ValueError(f"{path}: unexpected bytes at monster drop 0x{off:x}")
        new = (e & ~0xFFFF) | pick
        buf[off + 1:off + 5] = struct.pack(">i", new)
        changes.append((e, new))
    return changes


def dungeon_discs(iso, script):
    import gciso
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    return sorted((p for p, _, _ in files if p.startswith(f"dvd/cft/{script}_") and p.endswith(".cft")),
                  key=lambda p: int(p.rsplit("_", 1)[1].split(".")[0]))


def patch_map(iso, script, discs=None):
    """{(area, loot set): chest} for the patcher - the same numbering as the
    AP locations (gil-only chests have no set and are left out)."""
    discs = discs or dungeon_discs(iso, script)
    return {(c["area"], c["set"]): c["chest"] for c in canonical(iso, script, discs) if c["items"]}


# Dungeons that are only played once (no Cycle 2/3 locations).
SINGLE_CYCLE = {"Mount Vellenge"}
YEARS = range(2, 11)          # "Year N Begins" locations


def _location_rows(iso):
    """Every AP location in table order: (name, dungeon, cycle, chest, flags).
    Chests first (by dungeon, cycle, chest), then "Cycle N Reached" for each
    dungeon's later cycles, then "Year N Begins"."""
    import lootcft as lc
    chests, cycles_of = [], {}
    for script, dungeon in lc.DUNGEONS:
        rows = [c for c in canonical(iso, script, dungeon_discs(iso, script)) if c["items"]]
        cycles = sorted({cy for c in rows for cy in c["cycles"]
                         if not (dungeon in SINGLE_CYCLE and cy != 1)})
        cycles_of[dungeon] = cycles
        for cycle in cycles:
            for c in rows:
                if cycle in c["cycles"]:
                    chests.append((f"{dungeon} - Cycle {cycle} - Chest {c['chest']}",
                                   dungeon, cycle, c["chest"], tuple(c["flags"])))
    events = [(f"{dungeon} - Cycle {cycle} Reached", dungeon, cycle, 0, ())
              for dungeon, cycles in cycles_of.items() for cycle in cycles if cycle > 1]
    years = [(f"Year {y} Begins", "Menu", y, 0, ()) for y in YEARS]
    return chests + events + years


def _previous_codes(path):
    """{location name: AP code} from the chest_table.py at `path`, so codes
    stay the same when the table is written again. The older format (CHESTS,
    numbered in table order) gives the codes it was numbered with."""
    import ast
    if not os.path.exists(path):
        return {}
    tree = ast.parse(open(path, encoding="utf-8").read())
    values = {t.id: n.value for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name)}
    if "LOCATIONS" in values:
        return {name: row[0] for name, row in ast.literal_eval(values["LOCATIONS"]).items()}
    if "CHESTS" not in values:
        return {}
    old, names, cycles_of = ast.literal_eval(values["CHESTS"]), [], {}
    for dungeon, rows in old.items():
        cycles = sorted({cy for _, cys, _ in rows for cy in cys
                         if not (dungeon in SINGLE_CYCLE and cy != 1)})
        cycles_of[dungeon] = cycles
        names += [f"{dungeon} - Cycle {cycle} - Chest {chest}"
                  for cycle in cycles for chest, cys, _ in rows if cycle in cys]
    names += [f"{dungeon} - Cycle {cycle} Reached"
              for dungeon, cycles in cycles_of.items() for cycle in cycles if cycle > 1]
    names += [f"Year {y} Begins" for y in YEARS]
    return {name: code for code, name in enumerate(names)}


def export(iso, out_path):
    """Write the AP world's chest_table.py: every AP location, one per line.
    A location already in the file keeps its code, and a new one gets the next
    unused code, so adding a chest never changes the other locations' IDs."""
    rows = _location_rows(iso)
    codes = _previous_codes(out_path)
    next_code = max(codes.values(), default=-1) + 1
    for name, *_ in rows:
        if name not in codes:
            codes[name] = next_code
            next_code += 1
    width = max(len(repr(name)) for name, *_ in rows) + 1
    lines = ['"""',
             "Written by chestflags.py (Final-Fantasy-Crystal-Chronicles-Randomizer) from the",
             "game files - regenerate instead of editing by hand:",
             "    py chestflags.py export <clean.iso> <this file>",
             "",
             "Every AP location, one per line:",
             "    name: (code, dungeon, cycle, chest, flags)",
             "",
             "code     the location's AP code (AP id = 2326528 + code). Regenerating keeps",
             "         each location's code. New locations get the next unused one.",
             "dungeon  the region it is in (\"Menu\" for the Year locations).",
             "cycle    1-3 (for a \"Year N Begins\" location, the year).",
             "chest    the chest's number in the game's own order: 1..K per dungeon by",
             "         each chest's lowest flag, then chests that shared a loot case in",
             "         vanilla and get their own from the patcher (K+1...). 0 = not a chest.",
             "flags    the chest's \"opened\" flags: flag n is bit n of the big-endian",
             "         32-bit words at 0x80926000, i.e. byte 4*(n//32) + 3 - (n%32)//8,",
             "         bit n%8. Several flags are the same chest at alternative spots.",
             '"""',
             "",
             "LOCATIONS = {"]
    section = None
    for name, dungeon, cycle, chest, flags in rows:
        title = (dungeon if chest else
                 "Cycle reached" if dungeon != "Menu" else "Year begins")
        if title != section:
            lines.append(f"    # {title}")
            section = title
        lines.append(f"    {repr(name) + ':':{width}} ({codes[name]}, {dungeon!r}, {cycle}, {chest}, {flags!r}),")
    lines.append("}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def export_positions(iso, out_path):
    """Write {dungeon: [{chest, area, cycles, flags, items, world: [x, y, z]}]}
    as JSON, for tracker pin placement."""
    import json
    import lootcft as lc
    data = {}
    for script, name in lc.DUNGEONS:
        data[name] = [{"chest": c["chest"], "area": c["area"], "cycles": c["cycles"],
                       "flags": c["flags"], "items": c["items"], "gil": c["gil"],
                       "world": [round(v, 1) for v in c["world"]]}
                      for c in canonical(iso, script, dungeon_discs(iso, script))]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "positions":
        export_positions(sys.argv[2], sys.argv[3])
        print("wrote", sys.argv[3])
        sys.exit(0)
    if len(sys.argv) > 2 and sys.argv[1] == "export":
        export(sys.argv[2], sys.argv[3])
        print("wrote", sys.argv[3])
        sys.exit(0)
    import gciso
    import lootcft as lc
    iso = sys.argv[1]
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    for script, friendly in lc.DUNGEONS:
        discs = sorted(p for p, _, _ in files
                       if p.startswith(f"dvd/cft/{script}_") and p.endswith(".cft"))
        rows = chest_table(iso, script, discs)
        flags = {f: c for _, _, f, c, _ in rows if c is not None}
        print(f"{friendly}: " + ", ".join(f"chest {c} = {flag_to_byte_bit(f)}"
                                         for f, c in sorted(flags.items(), key=lambda x: x[1])))
