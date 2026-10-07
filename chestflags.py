"""
chestflags.py - which "chest opened" bit belongs to which Game8 chest number,
read from the game files, so the AP client reports the same chest the
patcher wrote the item into.

Every chest is a SPAWN_TBOX record [127, A, 0, B, x, y, z, rot] (see
spawn_map.py):
  A = get_treasure case number in the low 16 bits (get_treasure is a switch
      on it; the case's body holds the chest's loot set, lootcft.find_sets
      order). Some dungeons (Daemon's Court, Veo Lu Sluice) also set a value
      in the high 16 bits - meaning unknown, kept as `extra`.
  B = chest flag + 1. Bit n of the chest-flag words at 0x80926000 is
      byte (3 - n % 32 // 8) + 4 * (n // 32), bit n % 8 - i.e. bit n of
      big-endian 32-bit words. (Verified against River Belle Path's
      hand-checked client table.)
The patcher maps (area, loot set) -> Game8 chest number with
randomizer.dungeon_chest_map(), so going record -> loot set -> chest number
gives the same numbering the AP locations use.

    py chestflags.py ISO                      # print the flag table per dungeon
    py chestflags.py export ISO chest_table.py  # write the AP world's chest table
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

# Chests players have confirmed can't be reached in some cycles even though
# their loot isn't empty there: {dungeon script: {chest: [cycles]}}.
UNREACHABLE = {
    "gob": {2: [1], 3: [1], 13: [1]},     # Game8 chests 2, 1 and 10 (2026-10-07)
}


def _slot_has_loot(data, info):
    """True if a vanilla slot gives anything (item or gil)."""
    import struct
    if not info:
        return False
    offs = ([info["item"]] if info["item"] else []) + info["gil"]
    return any(struct.unpack(">i", data[o:o + 4])[0] for o in offs)


def canonical(iso, script, discs):
    """The dungeon's chests in the game's own order, one per (area, loot
    case): chests in the same area that share a loot case always give the
    same item (and include alternative spots for one chest), so they're one
    location whose flags all count. Returns a list of dicts:
        chest   1..K, in order of each chest's lowest flag
        area    area file number;  case = get_treasure case (A);  set = loot set index
        flags   chest-opened flag numbers (B - 1)
        cycles  cycles the chest is a location in: it spawns (record cycle
                bits) AND its vanilla loot in that cycle's slot (0/2/4, the
                one AP seeds use) isn't empty, minus the UNREACHABLE list. Chests a player can't reach in
                a cycle are left empty there in vanilla; this matches the
                Game8 per-cycle chest counts exactly for 10 of 14 dungeons and
                only ever under-counts elsewhere, except Veo Lu Sluice cycle 1
                (2 more than Game8's 5 - needs an in-game check).
        items   True if slots 0/2/4 can hold an item (treasure.py) - every
                chest, gil-only ones included, since gil can be cleared
        gil     True for chests that give only gil in vanilla
        world   position of the first record
    """
    import randomizer
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
        for addr, r, w in spawn_map._records(tmp, "SPAWN_TBOX"):
            mask, case, extra, flag = r[0], r[1] & 0xFFFF, r[1] >> 16, r[3] - 1
            g = groups.setdefault((area, case), {
                "area": area, "case": case, "extra": extra, "set": set_of_case.get(case),
                "flags": [], "cycles": set(), "world": tuple(w[4:7])})
            if flag not in g["flags"]:
                g["flags"].append(flag)
            import treasure
            lo, hi = ranges[case]
            raw = open(tmp, "rb").read()
            sl = treasure.case_slots(raw, lo, hi)
            if "items" not in g:
                g["items"] = all(sl.get(s, {}).get("item") for s in treasure.CYCLE_SLOT.values())
            g["cycles"] |= {c for c, bit in CYCLE_BITS.items()
                            if mask & bit and _slot_has_loot(raw, sl.get(treasure.CYCLE_SLOT[c]))}
    chests = sorted(groups.values(), key=lambda g: min(g["flags"]))
    blocked = UNREACHABLE.get(script, {})
    for n, g in enumerate(chests, 1):
        g["chest"] = n
        g["flags"].sort()
        g["cycles"] = sorted(set(g["cycles"]) - set(blocked.get(n, [])))
        g["gil"] = g["set"] is None
    return chests


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


def export(iso, out_path):
    """Write the AP world's chest_table.py from the game files."""
    import lootcft as lc
    lines = ['"""',
             "Generated by chestflags.py (Final-Fantasy-Crystal-Chronicles-Randomizer) from the",
             "game files - regenerate instead of editing by hand.",
             "",
             "Chests are numbered in the game's own order (1..K per dungeon, by each",
             "chest's lowest flag). Chests in the same area that share a loot case are one",
             "chest (they always give the same item; several flags may then count).",
             "",
             "CHESTS[dungeon] = [(chest, cycles, flags), ...]",
             "    flag n = bit n of the big-endian u32 chest-flag words at 0x80926000:",
             "    byte 4*(n//32) + 3 - (n%32)//8, bit n%8",
             "GIL_ONLY: chests that only give gil in vanilla (also locations; the",
             "patcher clears their gil when it puts an item in).",
             '"""', "", "CHESTS = {"]
    gil_lines = ["", "GIL_ONLY = {"]
    for script, name in lc.DUNGEONS:
        rows = canonical(iso, script, dungeon_discs(iso, script))
        lines.append(f"    {name!r}: [")
        gil_lines.append(f"    {name!r}: [")
        for c in rows:
            row = f"        ({c['chest']}, {tuple(c['cycles'])}, {tuple(c['flags'])}),"
            if c["items"]:
                lines.append(row)
            if c["gil"]:
                gil_lines.append(f"        {c['chest']},")
        lines.append("    ],")
        gil_lines.append("    ],")
    lines.append("}")
    gil_lines.append("}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines + gil_lines) + "\n")


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
