"""
randomizer.py - Randomize FFCC dungeon chest contents across an entire ISO.

Builds on the existing tooling:
    gciso.py      - extract/inject files inside the .iso (in place, fixed size)
    lootcft.py    - find treasure sets in <dungeon>_0.cft and edit item slots
    ffcc_items.py - item ID <-> name + category tables

WHAT A CHEST RECORD ACTUALLY IS
-------------------------------
Each treasure slot is a 0x5b-byte script record in get_treasure(). The ONLY
per-item field is a single push-int at record+0 holding the item ID; the rest of
the record is identical regardless of the item's category (verified by diffing
Material / Food / Phoenix Down / Artifact / Magicite / Recipe records byte for
byte - they differ only in that one ID and a positional counter). So putting ANY
item in ANY chest is a single 16-bit edit; the "categories must match" rule in
the older tools is a safety convention, not a hard engine constraint.

WHAT ACTUALLY DROPS (confirmed on emulator)
--------------------------------------------
Cross-category never crashes, but only "droppable" item classes are granted by
the chest pickup path. Confirmed by testing River Belle Path:
    DROPPABLE : Artifact (0x9f-0xe7), Magicite (real stones only),
                Phoenix Down (0x125), Material (0x126-0x172),
                Food (0x17d-0x18e), Recipe/Scroll (0x191-0x1ed)
    NOT DROP. : craftable EQUIPMENT - Weapon/Armor/Shield/Gauntlet/Helmet/
                Belt/Accessory (0x01-0x9e). The chest opens but gives nothing.
This is exactly the set vanilla chests ever contain; equipment is obtained by
crafting recipes, so the engine has no path to hand it out from a box. The
chest's *original* category is irrelevant - only the new item's class matters.

Also avoid Unused/Test IDs and anything past 0x01ed (focus attacks, raw spells,
enemy skills); e.g. "Stone of Holy" 0x108 looks like magicite but does not drop.
This randomizer only ever writes IDs from the curated droppable pool below.

USAGE
    # make a copy of your ISO first; this writes in place
    python randomizer.py list    "Hacked Rom.iso"          # show dungeons found
    python randomizer.py preview "Hacked Rom.iso" --seed 1 # dry run, prints diff
    python randomizer.py run     "Hacked Rom.iso" --seed 1 # randomize + inject
                                                           #   (also writes a spoiler log)
    python randomizer.py spoiler "Hacked Rom.iso"          # spoiler for current ISO state
    python randomizer.py export  "Hacked Rom.iso" --ref "Vanilla.iso"  # dump chests -> JSON
    python randomizer.py patch   "Hacked Rom.iso" edits.json           # apply a chest JSON

The JSON (see `export` output) maps dungeon-script -> set-index -> cycle(1-3) ->
item; edit it and `patch` to set exactly those contents. Items may be a name,
"0xID", or "Name [0xID]"; a cycle value can be a list to spread across its slots.

OPTIONS
    --seed N        reproducible result (default: time-based)
    --mode MODE     cross    : any droppable item in any chest (default)
                    category : keep each slot within its original category
    --rolls MODE    cycle    : one item per chest per cycle (default)
                    slot     : every slot rolled independently (most variety)
                    chest    : one item for the whole chest (fully predictable)
    --pool POOL     all (default) | artifact | magicite | consumable | recipe
    --max-artifacts N  cap artifacts per dungeon per cycle (default 4 = the
                    in-game carry limit); excess chests get a non-artifact item
    --dungeon NAME  restrict to one dungeon script (e.g. river) - repeatable
    --fill-empty    also fill placeholder/empty slots (default: leave them alone)
"""

import argparse
import json
import os
import random
import re
import shutil
import sys
import tempfile

import gciso
import lootcft
import ffcc_items as items

VALID_LO, VALID_HI = 0x001, 0x1ed   # collectible-item ID window

# Item categories a chest can actually hand out (confirmed on emulator).
# Craftable equipment is intentionally absent: chests open but give nothing.
DROPPABLE_CATS = {"Artifact", "Magicite", "PhoenixDown", "Material", "Food", "Recipe"}

# IDs inside the droppable categories that are still Unused / Test / unimple-
# mented and must never be placed (from "FFCC Notes/Inventory Code Lists.txt"
# plus emulator testing).
EXCLUDE = set()
EXCLUDE |= {0x156, 0x160, 0x161, 0x162, 0x170}            # unused materials
EXCLUDE |= set(range(0x173, 0x17d))                       # Extra 24-33
EXCLUDE |= set(range(0x189, 0x191))                       # unused shards / trade fillers
# Magicite: only these stones are real, droppable drops; the rest of
# 0x100-0x124 are spell internals or unimplemented (e.g. 0x108 "Holy" does NOT
# drop - confirmed in-game).
MAGICITE_OK = {0x100, 0x101, 0x102, 0x105, 0x106, 0x107}
EXCLUDE |= {v for v in range(0x100, 0x125) if v not in MAGICITE_OK}

# Which categories belong to each named pool.
POOLS = {
    "artifact":   {"Artifact"},
    "magicite":   {"Magicite"},
    "consumable": {"PhoenixDown", "Material", "Food"},
    "recipe":     {"Recipe"},
}


def build_pool(pool_name):
    """Return a sorted list of safe, droppable item IDs for the chosen pool."""
    wanted = DROPPABLE_CATS if pool_name == "all" else POOLS[pool_name]
    out = []
    for v in range(VALID_LO, VALID_HI + 1):
        if v in EXCLUDE:
            continue
        cat = items.category(v)
        if cat in wanted:
            out.append(v)
    return out


def is_item(v):
    """True if v is a real, droppable item we are willing to place."""
    return (VALID_LO <= v <= VALID_HI and v not in EXCLUDE
            and items.category(v) in DROPPABLE_CATS)


# name (lowercase) -> id, preferring droppable ids when a name is ambiguous
# (e.g. "Iron Shield" is both equipment 0x59 and recipe 0x1aa - we want 0x1aa).
_NAME2ID = {}
for _v in range(VALID_LO, 0x4b5):
    _nm = items.NAMES.get(_v)
    if not _nm:
        continue
    _k = _nm.lower()
    if _k not in _NAME2ID or (is_item(_v) and not is_item(_NAME2ID[_k])):
        _NAME2ID[_k] = _v


def resolve_item(s):
    """Resolve a JSON item value to an id. Accepts an int, a '0xNN' string, a
    'Name [0xNN]' label (hex wins), or a bare item name. Returns None if unknown."""
    if isinstance(s, int):
        return s
    s = str(s).strip()
    m = re.search(r"0x([0-9a-fA-F]+)", s)
    if m:
        return int(m.group(1), 16)
    if s.isdigit():
        return int(s)
    return _NAME2ID.get(s.lower())


def pick(rng, slot_value, mode, pool):
    """Choose a replacement ID for one slot given the mode."""
    if mode == "category":
        same = items.all_items_for_category(items.category(slot_value))
        candidates = [i for i, _ in same if is_item(i)] or pool
        return rng.choice(candidates)
    return rng.choice(pool)            # cross


def dungeons_in_iso(iso):
    """Return [(script, friendly, disc_path)] for dungeons whose cft is present."""
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    found = []
    for script, friendly in lootcft.DUNGEONS:
        disc = f"dvd/cft/{script}_0.cft"
        if gciso.find_file(files, disc):
            found.append((script, friendly, disc))
    return found


def _extract(iso, disc, dst):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        m = gciso.find_file(files, disc)
        _, off, size = m[0]
        f.seek(off)
        data = f.read(size)
    with open(dst, "wb") as o:
        o.write(data)
    return size


def _slot_groups(n, rolls):
    """Map each slot index 0..n-1 to a group key. Slots sharing a key all get
    the same randomized item. rolls: 'slot' = every slot its own item;
    'cycle' = one item per cycle (slots grouped by their primary/earliest cycle);
    'chest' = one item for the whole chest."""
    if rolls == "slot":
        return list(range(n))
    if rolls == "chest":
        return [0] * n
    cyc = lootcft.slot_cycles(n)               # 'cycle'
    return [min(cyc[ci]) for ci in range(n)]


def _pick_nonart(rng, base, mode, nonart):
    """Pick a non-artifact item (used when a cycle already has its artifact cap)."""
    if mode == "category" and base is not None and items.category(base) != "Artifact":
        return pick(rng, base, "category", nonart)
    return rng.choice(nonart)


def randomize_dungeon(iso, script, disc, rng, mode, pool, fill_empty, apply, rolls,
                      max_artifacts=4):
    """Compute (and optionally inject) randomized contents for one dungeon.
    Enforces at most `max_artifacts` artifacts per cycle (the player can only
    pick up a limited number of artifacts each cycle). Returns a list of
    (set_index, slot_index, old_id, new_id)."""
    import collections
    tmp = os.path.join(tempfile.gettempdir(), f"rnd_{script}_0.cft")
    size = _extract(iso, disc, tmp)
    # Chest-accurate, layout-independent set detection. When not filling empties
    # we only touch slots that already hold a real droppable item.
    sets = lootcft.find_sets(tmp, valid=is_item)
    nonart = [v for v in pool if items.category(v) != "Artifact"]
    art_per_cycle = {1: 0, 2: 0, 3: 0}            # per-dungeon artifact tally
    edits, changes = {}, []
    for si, s in enumerate(sets):
        keys = _slot_groups(len(s), rolls)
        cyc = lootcft.slot_cycles(len(s))
        members = collections.defaultdict(list)
        for ci, (off, cur) in enumerate(s):
            if not fill_empty and not is_item(cur):
                continue                       # leave placeholders/sentinels alone
            members[keys[ci]].append(ci)
        for cis in members.values():
            covered = set().union(*(cyc[ci] for ci in cis)) if cis else set()
            # category mode keys off a real item in the group; one pick per group
            base = next((s[ci][1] for ci in cis if is_item(s[ci][1])), None)
            room = all(art_per_cycle[c] < max_artifacts for c in covered)
            if room or not nonart:
                new = pick(rng, base if base is not None else rng.choice(pool), mode, pool)
                if items.category(new) == "Artifact" and not room and nonart:
                    new = _pick_nonart(rng, base, mode, nonart)
            else:
                new = _pick_nonart(rng, base, mode, nonart)
            if items.category(new) == "Artifact":
                for c in covered:
                    art_per_cycle[c] += 1
            for ci in cis:
                off, cur = s[ci]
                if new != cur:
                    edits[off] = new
                    changes.append((si, ci, cur, new))
    if apply and edits:
        lootcft.apply_edits(tmp, edits)
        data = open(tmp, "rb").read()
        if len(data) != size:
            raise ValueError(f"{script}: size changed, refusing to inject")
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, disc)[0]
            f.seek(off)
            f.write(data)
    return changes


def cmd_list(iso):
    found = dungeons_in_iso(iso)
    print(f"{len(found)} dungeon treasure file(s) in {os.path.basename(iso)}:")
    for script, friendly, _ in found:
        tmp = os.path.join(tempfile.gettempdir(), f"rnd_{script}_0.cft")
        _extract(iso, f"dvd/cft/{script}_0.cft", tmp)
        sets = lootcft.find_sets(tmp, valid=is_item)
        slots = sum(sum(is_item(v) for _, v in s) for s in sets)
        print(f"  {script:8s} {friendly:32s} {slots:4d} droppable slot(s) in {len(sets)} chest set(s)")


def _chest_labels(ref_iso, script, disc):
    """Map set_index -> Game8 chest number using the VANILLA contents in ref_iso
    (set order/offsets are identical pre/post randomization)."""
    import game8_chests as g8
    tmp = os.path.join(tempfile.gettempdir(), f"ref_{script}_0.cft")
    _extract(ref_iso, disc, tmp)
    sets = lootcft.find_sets(tmp, valid=is_item)
    ids = [[v for _, v in s] for s in sets]
    dungeon = g8.SCRIPT_TO_DUNGEON.get(script)
    if not dungeon:
        dn, sc = g8.match_dungeon(ids)
        dungeon = dn if sc >= 3 else None
    return (g8.label_sets(ids, dungeon) if dungeon else {}), dungeon


def cmd_spoiler(iso, out_path, ref=None):
    """Read the (already randomized) ISO and write a spoiler log of every chest,
    grouped by level name and cycle. If `ref` (a vanilla ISO) is given, chests
    are numbered by their Game8 chest number instead of by set order."""
    found = dungeons_in_iso(iso)
    lines = [f"FFCC CHEST SPOILER  -  {os.path.basename(iso)}",
             "Cycles are by slot position (cycle 1 = early game ... cycle 3 = late);"
             " '/' lists the items a chest can give that cycle.", ""]
    for script, friendly, disc in found:
        tmp = os.path.join(tempfile.gettempdir(), f"spoil_{script}_0.cft")
        _extract(iso, disc, tmp)
        sets = lootcft.find_sets(tmp, valid=is_item)
        if not sets:
            continue
        labels = _chest_labels(ref, script, disc)[0] if ref else {}
        # Game8's matcher can map several sets to one generic chest (e.g. every
        # magicite set matches "Cure"); keep only the first set per chest number.
        seen_chest, titles = set(), {}
        for si in range(len(sets)):
            cn = labels.get(si)
            if cn is not None and cn not in seen_chest:
                seen_chest.add(cn)
                titles[si] = (0, cn, f"Chest {cn}")
            else:
                titles[si] = (1, si, f"Set {si + 1}")
        # chest-numbered sets first (by chest number), then unmapped sets
        order = sorted(range(len(sets)), key=lambda i: titles[i][:2])
        width = max((len(titles[i][2]) for i in order), default=6)
        lines.append(f"=== {friendly} ===")
        for cyc in (1, 2, 3):
            lines.append(f"  Cycle {cyc}:")
            for si in order:
                s = sets[si]
                cycmap = lootcft.slot_cycles(len(s))
                names, seen = [], set()
                for ci, (_, v) in enumerate(s):
                    if cyc in cycmap[ci] and is_item(v) and v not in seen:
                        seen.add(v)
                        names.append(items.name(v))
                content = " / ".join(names) if names else "-"
                lines.append(f"      {titles[si][2]:<{width}} : {content}")
            lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote spoiler log -> {out_path}  ({len(found)} dungeons)")


# ---------------------------------------------------------------------------
# JSON export / patch
# ---------------------------------------------------------------------------
# JSON layout:
#   { "_format": "...",
#     "<script>": { "_name": "<dungeon>",
#                   "<setIndex>": { "_chest": <n|null>,
#                                   "1": "<item>", "2": "<item>", "3": "<item>" } } }
# Set indices are stable (find_sets is deterministic). Each cycle value is a
# single item, or a list to spread across that cycle's slots. Items may be a
# name, "0xNN", or a "Name [0xNN]" label (hex wins). "_"-keys are metadata.
JSON_FORMAT = ("ffcc-chest-patch v1: dungeon-script -> set-index -> cycle(1-3) -> "
               "item (name, 0xID, or 'Name [0xID]'). '_'-prefixed keys are notes.")


def _cycle_items(s, cyc):
    """Distinct droppable item names in cycle `cyc` of set s, in slot order."""
    cm = lootcft.slot_cycles(len(s))
    out, seen = [], set()
    for ci, (_, v) in enumerate(s):
        if cyc in cm[ci] and is_item(v) and v not in seen:
            seen.add(v)
            out.append(items.label(v))
    return out


def cmd_export(iso, out_path, ref=None):
    """Dump current chest contents to an editable JSON (level -> set -> cycle)."""
    data = {"_format": JSON_FORMAT}
    for script, friendly, disc in dungeons_in_iso(iso):
        tmp = os.path.join(tempfile.gettempdir(), f"exp_{script}_0.cft")
        _extract(iso, disc, tmp)
        sets = lootcft.find_sets(tmp, valid=is_item)
        if not sets:
            continue
        labels = _chest_labels(ref, script, disc)[0] if ref else {}
        dd = {"_name": friendly}
        for si, s in enumerate(sets):
            entry = {"_chest": labels.get(si)}
            for cyc in (1, 2, 3):
                names = _cycle_items(s, cyc)
                if names:
                    entry[str(cyc)] = names[0] if len(names) == 1 else names
            dd[str(si)] = entry
        data[script] = dd
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote chest JSON -> {out_path}  ({len(data) - 1} dungeons)")


def _artifacts_per_cycle(sets):
    """Count, per cycle (1-3), how many chests yield an artifact across `sets`."""
    pc = {1: 0, 2: 0, 3: 0}
    for s in sets:
        cm = lootcft.slot_cycles(len(s))
        for c in (1, 2, 3):
            ids = {v for ci, (_, v) in enumerate(s) if c in cm[ci]}
            if any(items.category(v) == "Artifact" for v in ids):
                pc[c] += 1
    return pc


def cmd_patch(iso, json_path, max_artifacts=4):
    """Apply a chest JSON to the ISO: set each level/set/cycle to the given item.
    Warns if the result exceeds `max_artifacts` artifacts per cycle (carry cap)."""
    with open(json_path, encoding="utf-8") as f:
        spec = json.load(f)
    present = {script: disc for script, _, disc in dungeons_in_iso(iso)}
    total, warns = 0, []
    for script, dd in spec.items():
        if script.startswith("_"):
            continue
        if script not in present:
            warns.append(f"dungeon '{script}' not in ISO - skipped")
            continue
        disc = present[script]
        tmp = os.path.join(tempfile.gettempdir(), f"patch_{script}_0.cft")
        size = _extract(iso, disc, tmp)
        sets = lootcft.find_sets(tmp, valid=is_item)
        edits = {}
        for set_key, entry in dd.items():
            if set_key.startswith("_"):
                continue
            si = int(set_key)
            if si >= len(sets):
                warns.append(f"{script}: set {si} out of range - skipped")
                continue
            s = sets[si]
            cm = lootcft.slot_cycles(len(s))
            for cyc in (1, 2, 3):
                if str(cyc) not in entry:
                    continue
                val = entry[str(cyc)]
                vals = val if isinstance(val, list) else [val]
                ids = [resolve_item(x) for x in vals]
                if any(i is None for i in ids):
                    warns.append(f"{script} set{si} c{cyc}: unresolved item {vals}")
                    continue
                bad = [i for i in ids if not is_item(i)]
                if bad:
                    warns.append(f"{script} set{si} c{cyc}: not droppable "
                                 f"{[items.name(i) for i in bad]} - skipped (won't drop)")
                    continue
                # slots of this cycle that currently hold a real item
                cyc_slots = [ci for ci, (_, cur) in enumerate(s)
                             if cyc in cm[ci] and is_item(cur)]
                for k, ci in enumerate(cyc_slots):
                    off = s[ci][0]
                    edits[off] = ids[k % len(ids)]
        if edits:
            lootcft.apply_edits(tmp, edits)
            # artifact carry-cap check on the resulting (edited + untouched) state
            pc = _artifacts_per_cycle(lootcft.find_sets(tmp, valid=is_item))
            for c in (1, 2, 3):
                if pc[c] > max_artifacts:
                    warns.append(f"{script}: cycle {c} now has {pc[c]} artifacts "
                                 f"(max {max_artifacts}) - the player can only carry "
                                 f"{max_artifacts} per cycle")
            buf = open(tmp, "rb").read()
            if len(buf) != size:
                raise ValueError(f"{script}: size changed, refusing to inject")
            with open(iso, "r+b") as f:
                _, files = gciso.parse_fst(f)
                _, off, _ = gciso.find_file(files, disc)[0]
                f.seek(off)
                f.write(buf)
            total += len(edits)
            print(f"  {script:8s}: {len(edits)} slot(s) patched")
    for w in warns:
        print("  ! " + w)
    print(f"Patched {total} slot(s) into {os.path.basename(iso)}.")


def cmd_run(iso, args, apply):
    rng = random.Random(args.seed)
    pool = build_pool(args.pool)
    if not pool:
        sys.exit(f"empty pool for --pool {args.pool}")
    found = dungeons_in_iso(iso)
    if args.dungeon:
        want = set(args.dungeon)
        found = [d for d in found if d[0] in want]
        if not found:
            sys.exit(f"no matching dungeon for {args.dungeon}")
    verb = "Randomizing" if apply else "Preview (no write)"
    print(f"{verb}: seed={args.seed} mode={args.mode} rolls={args.rolls} "
          f"pool={args.pool} pool_size={len(pool)} max_artifacts/cycle="
          f"{getattr(args, 'max_artifacts', 4)} dungeons={len(found)}")
    total = 0
    for script, friendly, disc in found:
        changes = randomize_dungeon(iso, script, disc, rng, args.mode, pool,
                                    args.fill_empty, apply, args.rolls,
                                    getattr(args, "max_artifacts", 4))
        total += len(changes)
        print(f"\n{friendly} ({script})  -  {len(changes)} slot(s) changed")
        for si, ci, old, new in changes[:200]:
            print(f"  set {si:2d} slot {ci+1}: "
                  f"{items.name(old):28s} -> {items.name(new)}  [0x{old:04x}->0x{new:04x}]")
        if len(changes) > 200:
            print(f"  ... ({len(changes)-200} more)")
    print(f"\n{'WROTE' if apply else 'WOULD CHANGE'} {total} slot(s) total.")
    if apply:
        spoiler = os.path.splitext(iso)[0] + " - spoiler.txt"
        cmd_spoiler(iso, spoiler, ref=getattr(args, "ref", None))
    else:
        print("Run the same command with `run` (and the same --seed) to apply.")


def main():
    p = argparse.ArgumentParser(description="Randomize FFCC chest contents in an ISO.")
    p.add_argument("command", choices=["list", "preview", "run", "spoiler", "export", "patch"])
    p.add_argument("iso")
    p.add_argument("json", nargs="?", help="JSON file (for `patch`)")
    p.add_argument("--seed", type=int, default=random.randrange(1 << 30))
    p.add_argument("--mode", choices=["cross", "category"], default="cross")
    p.add_argument("--rolls", choices=["cycle", "slot", "chest"], default="cycle",
                   help="cycle: one item per chest per cycle (default); "
                        "slot: every slot independent (most variety); "
                        "chest: one item for the whole chest")
    p.add_argument("--pool", choices=["all", "artifact", "magicite", "consumable", "recipe"],
                   default="all")
    p.add_argument("--dungeon", action="append", help="restrict to this script name (repeatable)")
    p.add_argument("--max-artifacts", type=int, default=4,
                   help="max artifacts per dungeon per cycle (default 4 = the carry limit)")
    p.add_argument("--fill-empty", action="store_true")
    p.add_argument("--ref", help="vanilla ISO used to label spoiler chests by Game8 chest number")
    args = p.parse_args()

    if not os.path.isfile(args.iso):
        sys.exit(f"ISO not found: {args.iso}")
    if args.command == "list":
        cmd_list(args.iso)
    elif args.command == "preview":
        cmd_run(args.iso, args, apply=False)
    elif args.command == "spoiler":
        cmd_spoiler(args.iso, os.path.splitext(args.iso)[0] + " - spoiler.txt", ref=args.ref)
    elif args.command == "export":
        cmd_export(args.iso, os.path.splitext(args.iso)[0] + " - chests.json", ref=args.ref)
    elif args.command == "patch":
        if not args.json or not os.path.isfile(args.json):
            sys.exit("patch needs a JSON file: randomizer.py patch <iso> <file.json>")
        cmd_patch(args.iso, args.json, args.max_artifacts)
    else:
        cmd_run(args.iso, args, apply=True)


if __name__ == "__main__":
    main()
