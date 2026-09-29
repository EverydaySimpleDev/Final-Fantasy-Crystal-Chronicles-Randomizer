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
    --chests-only   randomize only chests, not enemy drops (needs --ref); enemy
                    drops share the get_treasure pool, so this isolates the
                    Game8-identified chest sets and leaves the rest untouched
    --dungeon NAME  restrict to one dungeon script (e.g. river) - repeatable
    --fill-empty    also fill placeholder/empty slots (default: leave them alone)
"""

import argparse
import json
import os
import random
import re
import shutil
import struct
import sys
import tempfile

import gciso
import lootcft
import ffcc_items as items
import items as itemstats          # param.cfd reader/writer (prices live here)

VALID_LO, VALID_HI = 0x001, 0x1ed   # collectible-item ID window

# Item categories a chest can actually hand out (confirmed on emulator).
# Craftable equipment is intentionally absent: chests open but give nothing.
DROPPABLE_CATS = {"Artifact", "Magicite", "PhoenixDown", "Material", "Food", "Recipe"}

# IDs inside the droppable categories that are still Unused / Test / unimple-
# mented and must never be placed (from "FFCC Notes/Inventory Code Lists.txt"
# plus emulator testing).
EXCLUDE = set()
EXCLUDE |= {0x156, 0x160, 0x161, 0x170}                   # unused materials
# (0x162 was here too, but it's now repurposed as the custom "AP Item" - a real,
#  placeable Material with Gold's model; see ffcc_items NAMES[0x162].)
EXCLUDE |= set(range(0x173, 0x17d))                       # Extra 24-33
EXCLUDE |= set(range(0x189, 0x191))                       # unused shards / trade fillers
# Magicite: only these stones are real, droppable drops; the rest of
# 0x100-0x124 are spell internals or unimplemented (e.g. 0x108 "Holy" does NOT
# drop - confirmed in-game).
MAGICITE_OK = {0x100, 0x101, 0x102, 0x105, 0x106, 0x107}
EXCLUDE |= {v for v in range(0x100, 0x125) if v not in MAGICITE_OK}

# Items that are valid/placeable (is_item True, so the JSON import can place them
# and they drop correctly) but must NEVER be chosen by RANDOM modes. The AP Item
# is meant to appear only where a JSON import explicitly puts it.
NO_RANDOM = {0x162}                                       # custom "AP Item"

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
        if v in EXCLUDE or v in NO_RANDOM:
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
        candidates = [i for i, _ in same if is_item(i) and i not in NO_RANDOM] or pool
        return rng.choice(candidates)
    return rng.choice(pool)            # cross


_AREA_RE = re.compile(r"^dvd/cft/(?P<base>[a-z0-9_]+)_(?P<n>\d+)\.cft$", re.I)


def _area_discs(files, script):
    """All area files for a dungeon: dvd/cft/<script>_0.cft, _1, _2 ... (sorted)."""
    out = []
    for path, _, _ in files:
        m = _AREA_RE.match(path)
        if m and m.group("base").lower() == script.lower():
            out.append((int(m.group("n")), path))
    return [p for _, p in sorted(out)]


def _area_no(disc):
    m = _AREA_RE.match(disc.replace("\\", "/"))
    return int(m.group("n")) if m else 0


def dungeons_in_iso(iso):
    """Return [(script, friendly, [disc, ...])] - all area files per dungeon."""
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    found = []
    for script, friendly in lootcft.DUNGEONS:
        discs = _area_discs(files, script)
        if discs:
            found.append((script, friendly, discs))
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


# Bosses that take only 1 damage until hit with Holy. Holy isn't a droppable
# stone (0x108 never drops) - it's cast by fusing Stone of Life (0x107) with
# Fire/Blizzard/Thunder (0x100-0x102). Magicite stones don't carry between
# dungeons, so the stones must be obtainable inside the boss's own dungeon:
# its vanilla all-magicite sets (per-element spawn/drop tables, e.g. city_0
# sets 7-13 = Fire/Blizzard/Thunder/Cure/Life/Clear/mixed) are never
# randomized or used for stage keys. Keyed by the dungeon hosting the boss -
# update if a boss shuffle moves Lich or Zombie Dragon.
HOLY_BOSS_DUNGEONS = {"city": "Lich", "swamp": "Zombie Dragon"}
STONE_OF_LIFE = 0x107
ELEMENT_STONES = {0x100, 0x101, 0x102}


def _is_magicite_set(s):
    return set_kind([v for _, v in s]) == "magicite"


def _randomize_area(iso, disc, rng, mode, pool, nonart, fill_empty, apply, rolls,
                    max_artifacts, art_per_cycle, only_sets, keep_magicite=False):
    """Randomize ONE area file in place. `art_per_cycle` is the dungeon-wide
    artifact tally (shared across the dungeon's areas). `keep_magicite` leaves
    the area's all-magicite sets vanilla (see HOLY_BOSS_DUNGEONS). Returns
    [(area_no, set_index, slot_index, old_id, new_id)]."""
    import collections
    tmp = os.path.join(tempfile.gettempdir(), "rnd_" + os.path.basename(disc))
    size = _extract(iso, disc, tmp)
    sets = lootcft.find_sets(tmp, valid=is_item)
    area = _area_no(disc)
    edits, changes = {}, []
    for si, s in enumerate(sets):
        if only_sets is not None and si not in only_sets:
            continue                              # chests-only: skip drop/pool sets
        if keep_magicite and _is_magicite_set(s):
            continue                              # Holy-boss dungeon: keep stones
        keys = _slot_groups(len(s), rolls)
        cyc = lootcft.slot_cycles(len(s))
        members = collections.defaultdict(list)
        for ci, (off, cur) in enumerate(s):
            if not fill_empty and not is_item(cur):
                continue                       # leave placeholders/sentinels alone
            members[keys[ci]].append(ci)
        for cis in members.values():
            covered = set().union(*(cyc[ci] for ci in cis)) if cis else set()
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
                    changes.append((area, si, ci, cur, new))
    if apply and edits:
        lootcft.apply_edits(tmp, edits)
        data = open(tmp, "rb").read()
        if len(data) != size:
            raise ValueError(f"{disc}: size changed, refusing to inject")
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, disc)[0]
            f.seek(off)
            f.write(data)
    return changes


def randomize_dungeon(iso, script, discs, rng, mode, pool, fill_empty, apply, rolls,
                      max_artifacts=4, only_by_disc=None, holy_dungeons=HOLY_BOSS_DUNGEONS):
    """Randomize all area files of one dungeon, enforcing at most `max_artifacts`
    artifacts per cycle ACROSS the whole dungeon (one shared tally). `only_by_disc`
    (dict disc -> set of chest set indices) restricts to chests; None = everything.
    Dungeons in `holy_dungeons` keep their magicite sets so Holy stays castable.
    Returns [(area_no, set_index, slot_index, old_id, new_id)]."""
    nonart = [v for v in pool if items.category(v) != "Artifact"]
    art_per_cycle = {1: 0, 2: 0, 3: 0}            # shared across the dungeon's areas
    keep = script in holy_dungeons
    changes = []
    for disc in discs:
        only = only_by_disc.get(disc) if only_by_disc is not None else None
        changes += _randomize_area(iso, disc, rng, mode, pool, nonart, fill_empty,
                                   apply, rolls, max_artifacts, art_per_cycle, only,
                                   keep_magicite=keep)
    return changes


def check_holy_access(iso, holy_dungeons=HOLY_BOSS_DUNGEONS):
    """After all patching: for each Holy-boss dungeon, confirm some area still
    has a set that is all Stone of Life and a set with an element stone.
    Returns a list of problem strings (empty = OK)."""
    problems = []
    for script, friendly, discs in dungeons_in_iso(iso):
        if script not in holy_dungeons:
            continue
        life = element = False
        for disc in discs:
            tmp = os.path.join(tempfile.gettempdir(), "holy_" + os.path.basename(disc))
            _extract(iso, disc, tmp)
            for s in lootcft.find_sets(tmp, valid=is_item):
                ids = [v for _, v in s]
                life |= all(v == STONE_OF_LIFE for v in ids)
                element |= any(v in ELEMENT_STONES for v in ids)
        if not (life and element):
            problems.append(f"{friendly} ({script}, {holy_dungeons[script]}): "
                            f"{'no Stone of Life set' if not life else ''}"
                            f"{' and ' if not life and not element else ''}"
                            f"{'no element stone set' if not element else ''} - Holy may be impossible")
    return problems


# ---------------------------------------------------------------------------
# Shop randomization
# ---------------------------------------------------------------------------
# Shop stock lives in each shop cft's shopStart() as push-int item ids (see
# shops.py). Prices auto-derive from the item, so randomizing = swapping ids.
SELLABLE_CATS = ("Material", "Recipe", "Food", "Magicite", "PhoenixDown")


def is_sellable(v):
    """An item a shop can stock: a real item in a class shops sell (so its price
    is defined). Excludes equipment/artifacts (shops never carry them) and the
    unused/test slots in EXCLUDE."""
    return (1 <= v <= 0x1ed and v not in EXCLUDE
            and items.category(v) in SELLABLE_CATS)


def shops_in_iso(iso):
    """[(base, friendly, disc), ...] for each shop cft present in the ISO."""
    import shops as shopmod
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    paths = [p for p, _, _ in files]
    out = []
    for base, name in shopmod.SHOPS.items():
        disc = next((p for p in paths if p.endswith("/" + base + ".cft")), None)
        if disc:
            out.append((base, name, disc))
    return out


def shop_pool(iso):
    """Sellable pool = every item currently stocked by any shop. Drawing only
    from items that already appear in a shop guarantees each has a valid price."""
    import shops as shopmod
    pool = set()
    for base, name, disc in shops_in_iso(iso):
        tmp = os.path.join(tempfile.gettempdir(), "spool_" + base + ".cft")
        _extract(iso, disc, tmp)
        for _, v in shopmod.find_shop_items(tmp, valid=is_sellable):
            pool.add(v)
    return sorted(pool)


def randomize_shop(iso, base, disc, rng, pool, apply=True):
    """Randomize one shop's stock in place. Returns [(slot, old_id, new_id)]."""
    import shops as shopmod
    tmp = os.path.join(tempfile.gettempdir(), "shop_" + base + ".cft")
    size = _extract(iso, disc, tmp)
    slots = shopmod.find_shop_items(tmp, valid=is_sellable)
    edits, changes = {}, []
    for i, (off, cur) in enumerate(slots):
        new = rng.choice(pool)
        if new != cur:
            edits[off] = new
            changes.append((i, cur, new))
    if apply and edits:
        shopmod.apply_edits(tmp, edits)
        data = open(tmp, "rb").read()
        if len(data) != size:
            raise ValueError(f"{disc}: size changed, refusing to inject")
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, disc)[0]
            f.seek(off)
            f.write(data)
    return changes


def randomize_shops(iso, rng, only=None, apply=True, pool=None):
    """Randomize shop stock in `iso`. `only` = iterable of shop bases to limit to
    (None = all shops). Returns {friendly_name: slots_changed}. The pool is built
    from vanilla stock first, so call before other shop edits."""
    if pool is None:
        pool = shop_pool(iso)
    if not pool:
        return {}
    result = {}
    for base, name, disc in shops_in_iso(iso):
        if only is not None and base not in only:
            continue
        result[name] = len(randomize_shop(iso, base, disc, rng, pool, apply))
    return result


# ---------------------------------------------------------------------------
# Bonus-pool ("newbattle.cfd") randomization
# ---------------------------------------------------------------------------
# Post-stage bonus rewards are NOT in any .cft script - they're a flat table
# in dvd/cft/newbattle.cfd of fixed-size CBossArtifactStage structs (one per
# dungeon, 0x168 bytes each, per the real decomp struct in include/ffcc/
# game.h): m_bonusConditions[16] (0x00-0x20, unrelated per-spawn data),
# m_entries (0x20-0x160: 40x 8-byte entries, but only the first 8 -
# m_prefixEntries - are the actual random reward pool CGame::GetBossArtifact
# picks from; the other 32 are unrelated per-food/status data), then
# m_rankThresholds[4] (0x160-0x168, the score-tier cutoffs shown in-game as
# the point requirements). Each of the 8 reward entries holds 4 item ids
# (m_values[4], 2 bytes each) - 32 real item-id slots per dungeon.
# Verified byte-exact against a real ISO's newbattle.cfd this session (see
# project_ffcc_newbattle_bonus_pools memory) - block offsets found by
# locating each dungeon's own m_rankThresholds pattern directly.
NEWBATTLE_ENTRY_COUNT = 8      # m_prefixEntries[8] - the real reward pool
NEWBATTLE_ENTRY_SIZE = 8       # m_values[4], 2 bytes each
NEWBATTLE_BLOCKS = {           # dungeon script -> its CBossArtifactStage file offset
    "river": 0x18c0, "gob": 0x1a28, "mine": 0x1b90, "kinoko": 0x1cf8,
    "ruin": 0x1e60, "gigas": 0x1fc8, "lava": 0x2130, "fort": 0x2298,
    "cave": 0x2400, "water": 0x2568, "desert": 0x26d0, "swamp": 0x2838,
    "city": 0x29a0,
    # "meteo" has NO block - that slot in the real file is all zeros, not a
    # missed offset (checked directly) - left out rather than guessed.
}


def _newbattle_disc(iso):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    return next((p for p, _, _ in files if p.endswith("newbattle.cfd")), None)


def randomize_bonus_pools(iso, rng, mode="cross", pool=None, apply=True):
    """Randomize the post-stage bonus-reward item pool (newbattle.cfd) for
    every dungeon that has one (see NEWBATTLE_BLOCKS). `pool`: candidate item
    ids (from build_pool()); `mode`: 'category' or 'cross', same semantics as
    chest randomization (pick()). Score thresholds are left untouched - only
    which items can be rewarded changes. Returns [(script, entry, value, old,
    new)] for every slot actually changed."""
    disc = _newbattle_disc(iso)
    if disc is None:
        return []
    if pool is None:
        pool = build_pool("all")
    tmp = os.path.join(tempfile.gettempdir(), "nb_" + os.path.basename(disc))
    size = _extract(iso, disc, tmp)
    data = bytearray(open(tmp, "rb").read())
    changes = []
    for script, block_start in NEWBATTLE_BLOCKS.items():
        entries_off = block_start + 0x20
        for ei in range(NEWBATTLE_ENTRY_COUNT):
            for vi in range(4):
                o = entries_off + ei * NEWBATTLE_ENTRY_SIZE + vi * 2
                cur = int.from_bytes(data[o:o + 2], "big")
                if not is_item(cur):
                    continue                  # leave non-item/sentinel values alone
                new = pick(rng, cur, mode, pool)
                if new != cur:
                    data[o:o + 2] = new.to_bytes(2, "big")
                    changes.append((script, ei, vi, cur, new))
    if apply and changes:
        if len(data) != size:
            raise ValueError(f"{disc}: size changed, refusing to inject")
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, disc)[0]
            f.seek(off)
            f.write(bytes(data))
    return changes


def read_bonus_pools(iso):
    """{script: {entry_index: [4 item ids]}} for every dungeon with a bonus-
    pool block (see NEWBATTLE_BLOCKS). Read-only, for inspection/JSON export."""
    disc = _newbattle_disc(iso)
    if disc is None:
        return {}
    tmp = os.path.join(tempfile.gettempdir(), "nb_read_" + os.path.basename(disc))
    _extract(iso, disc, tmp)
    data = open(tmp, "rb").read()
    out = {}
    for script, block_start in NEWBATTLE_BLOCKS.items():
        entries_off = block_start + 0x20
        pools = {}
        for ei in range(NEWBATTLE_ENTRY_COUNT):
            base = entries_off + ei * NEWBATTLE_ENTRY_SIZE
            pools[ei] = [int.from_bytes(data[base + vi * 2:base + vi * 2 + 2], "big")
                        for vi in range(4)]
        out[script] = pools
    return out


def set_bonus_pools(iso, spec, apply=True):
    """Force specific items into one or more dungeons' bonus-reward pools,
    bypassing randomness entirely - the actual mechanism behind
    randomize_bonus_pools() above, generalized to take exact values instead
    of random ones (see project_ffcc_newbattle_bonus_pools memory for how
    entry/value indices map to which score-tier/cycle can reach them).
    `spec`: {script: {entry_index(0-7): [v0,v1,v2,v3]}} - any value may be
    None to leave that one slot untouched. Reads/writes newbattle.cfd once
    regardless of how many dungeons are given. Returns {script: [(entry,
    value_index, old, new), ...]} for dungeons that actually changed."""
    disc = _newbattle_disc(iso)
    if disc is None or not spec:
        return {}
    tmp = os.path.join(tempfile.gettempdir(), "nb_set_" + os.path.basename(disc))
    size = _extract(iso, disc, tmp)
    data = bytearray(open(tmp, "rb").read())
    result = {}
    for script, entries in spec.items():
        if script not in NEWBATTLE_BLOCKS:
            raise ValueError(f"{script!r} has no bonus-pool block "
                             f"(valid: {sorted(NEWBATTLE_BLOCKS)})")
        entries_off = NEWBATTLE_BLOCKS[script] + 0x20
        changes = []
        for ei, values in entries.items():
            ei = int(ei)
            if not (0 <= ei < NEWBATTLE_ENTRY_COUNT):
                raise ValueError(f"entry index {ei} out of range "
                                 f"(0-{NEWBATTLE_ENTRY_COUNT - 1})")
            for vi, new in enumerate(values):
                if new is None:
                    continue
                o = entries_off + ei * NEWBATTLE_ENTRY_SIZE + vi * 2
                old = int.from_bytes(data[o:o + 2], "big")
                new = int(new)
                if new != old:
                    data[o:o + 2] = new.to_bytes(2, "big")
                    changes.append((ei, vi, old, new))
        if changes:
            result[script] = changes
    if apply and result:
        if len(data) != size:
            raise ValueError(f"{disc}: size changed, refusing to inject")
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, disc)[0]
            f.seek(off)
            f.write(bytes(data))
    return result


def set_bonus_pool(iso, script, entries, apply=True):
    """Force specific items into ONE dungeon's bonus-reward pool. `entries`:
    {entry_index(0-7): [v0,v1,v2,v3]}, any value None to leave that slot
    untouched. Convenience wrapper around set_bonus_pools() for a single
    dungeon. Returns [(entry, value_index, old, new)]."""
    return set_bonus_pools(iso, {script: entries}, apply=apply).get(script, [])


def _param_disc(iso):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    return next((p for p, _, _ in files if p.endswith("/param.cfd")), None)


def sellable_ids():
    return [v for v in range(VALID_LO, VALID_HI + 1) if is_sellable(v)]


def read_prices(iso):
    """{item_id: gil} for every sellable item, read from param.cfd."""
    disc = _param_disc(iso)
    if not disc:
        return {}
    tmp = os.path.join(tempfile.gettempdir(), "price_param.cfd")
    _extract(iso, disc, tmp)
    data = open(tmp, "rb").read()
    base = itemstats.find_base(data)
    goff, gsz = itemstats.FIELDS["gil"]
    out = {}
    for v in sellable_ids():
        o = base + v * itemstats.ENTRY + goff
        out[v] = int.from_bytes(data[o:o + gsz], "big")
    return out


def randomize_prices(iso, rng, apply=True, pool=None):
    """Shuffle the price (gil) field among the items shops actually sell - the
    same set of real prices, reassigned to different items (so prices stay
    realistic and valid; the 0xFFFF "not for sale" sentinel and unsold items are
    left alone). `pool` = item ids to shuffle among (default: items currently
    stocked by shops). Returns the number of items whose price changed."""
    disc = _param_disc(iso)
    if not disc:
        return 0
    if pool is None:
        pool = shop_pool(iso)
    tmp = os.path.join(tempfile.gettempdir(), "rprice_param.cfd")
    size = _extract(iso, disc, tmp)
    data = bytearray(open(tmp, "rb").read())
    base = itemstats.find_base(data)
    goff, gsz = itemstats.FIELDS["gil"]

    def gil_off(v):
        return base + v * itemstats.ENTRY + goff

    priced = [(v, int.from_bytes(data[gil_off(v):gil_off(v) + gsz], "big"))
              for v in pool if is_sellable(v)]
    priced = [(v, g) for v, g in priced if 0 < g < 0xFFFF]   # real, buyable prices only
    ids = [v for v, _ in priced]
    prices = [g for _, g in priced]
    shuffled = prices[:]
    rng.shuffle(shuffled)
    changed = 0
    for v, newp in zip(ids, shuffled):
        o = gil_off(v)
        if int.from_bytes(data[o:o + gsz], "big") != newp:
            data[o:o + gsz] = newp.to_bytes(gsz, "big")
            changed += 1
    if apply and changed:
        with open(tmp, "wb") as f:
            f.write(data)
        if len(data) != size:
            raise ValueError("param.cfd size changed, refusing to inject")
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, disc)[0]
            f.seek(off)
            f.write(bytes(data))
    return changed


MOG_PRESSURE_DOL_OFFSET = 0x109bd4
MOG_PRESSURE_ORIG = bytes.fromhex("38800002")     # li r4, 2
MOG_PRESSURE_PATCHED = bytes.fromhex("38800000")  # li r4, 0


def patch_mog_never_tired(iso, apply=True):
    """Patch Start.dol so Mog's stamina ('pressure') never builds up while
    running with the chalice, removing the 'gets tired and drops it' penalty
    entirely. Single-instruction change in `CGPartyObj::gpmMove()`'s
    fast-movement branch (`li r4,2` -> `li r4,0`, so the `+= delta` there adds
    zero instead of 2/frame). Verified against the retail NTSC-US `main.dol`
    (file offset 0x109bd4 = RAM 0x80119e34, cross-checked via the DOL's own
    section headers). Returns True once the patch is present (freshly applied
    or already there); raises if the ISO's bytes there don't match either the
    vanilla original or the patched form (wrong game version)."""
    with open(iso, "r+b" if apply else "rb") as f:
        off, _ = gciso.dol_span(f)
        f.seek(off + MOG_PRESSURE_DOL_OFFSET)
        cur = f.read(4)
        if cur == MOG_PRESSURE_PATCHED:
            return True
        if cur != MOG_PRESSURE_ORIG:
            raise ValueError(f"unexpected bytes at Mog-pressure patch site: {cur.hex()} "
                              f"(expected {MOG_PRESSURE_ORIG.hex()} - wrong game version?)")
        if apply:
            f.seek(off + MOG_PRESSURE_DOL_OFFSET)
            f.write(MOG_PRESSURE_PATCHED)
    return True


# Starting-location patch (user-discovered and byte-verified, 2026-09-11): a
# new game's opening camera focus (farewell_0.cft) and the caravan's actual
# initial spawn point (ffcc_5.cft) each read a dynamic/persisted value that
# currently always resolves to Tipa. Replacing that 5-byte read with a
# hardcoded `PUSHI <id>` forces a specific town instead. Only destinations
# where Year 1 is completable are offered - Tipa needs no patch at all.
FAREWELL_CAMERA_DISC = "dvd/cft/farewell_0.cft"
FAREWELL_CAMERA_OFFSET = 0x7255
FAREWELL_CAMERA_ORIG = bytes.fromhex("0000003d09")   # GET this[0x3d09]

FFCC5_SPAWN_DISC = "dvd/cft/ffcc_5.cft"
FFCC5_SPAWN_OFFSET = 0x2FC3B
FFCC5_SPAWN_ORIG = bytes.fromhex("030000ffff")        # PUSHI 0xffff (sentinel)

# name -> (farewell_0 camera id, ffcc_5 spawn id). Tipa = None (vanilla, no patch).
STARTING_LOCATIONS = {
    "Tipa": None,
    "Marr's Pass": (0x0C, 0x10),
    "Alfitaria": (0x16, 0x11),
    "Fields of Fum": (0x2A, 0x13),
}


def _patch_pushi_id(iso, disc, offset, orig, new_id, apply):
    """Overwrite a 5-byte `<op> <3 zero bytes> <id>` instruction at `offset`
    within `disc` with `PUSHI <new_id>` (`03 00 00 00 <new_id>`). Accepts
    either the true vanilla bytes or an already-applied `PUSHI <anything>` at
    that same site (so re-picking a different location on top of a
    previously patched copy still works); raises on anything else."""
    tmp = os.path.join(tempfile.gettempdir(), "startloc_" + os.path.basename(disc))
    size = _extract(iso, disc, tmp)
    data = bytearray(open(tmp, "rb").read())
    cur = bytes(data[offset:offset + 5])
    already_patched = cur[0] == 0x03 and cur[1:4] == b"\x00\x00\x00"
    if cur != orig and not already_patched:
        raise ValueError(f"{disc}@0x{offset:x}: unexpected bytes {cur.hex()} "
                          f"(expected {orig.hex()} - wrong game version?)")
    if apply:
        data[offset:offset + 5] = bytes([0x03, 0x00, 0x00, 0x00, new_id])
        with open(tmp, "wb") as f:
            f.write(data)
        if len(data) != size:
            raise ValueError(f"{disc}: size changed, refusing to inject")
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, disc)[0]
            f.seek(off)
            f.write(bytes(data))


def patch_starting_location(iso, location, apply=True):
    """Retarget where a brand-new game begins. `location` must be a key of
    STARTING_LOCATIONS. Returns True if a patch was (or would be) applied,
    False for "Tipa" (vanilla default, nothing to do)."""
    if location not in STARTING_LOCATIONS:
        raise ValueError(f"unknown starting location {location!r} - "
                          f"choose one of {list(STARTING_LOCATIONS)}")
    ids = STARTING_LOCATIONS[location]
    if ids is None:
        return False
    farewell_id, ffcc5_id = ids
    _patch_pushi_id(iso, FAREWELL_CAMERA_DISC, FAREWELL_CAMERA_OFFSET,
                     FAREWELL_CAMERA_ORIG, farewell_id, apply)
    _patch_pushi_id(iso, FFCC5_SPAWN_DISC, FFCC5_SPAWN_OFFSET,
                     FFCC5_SPAWN_ORIG, ffcc5_id, apply)
    return True


def starting_location_status(iso):
    """Return the STARTING_LOCATIONS name matching what's currently in `iso`
    (by reading ffcc_5.cft's own spawn-point byte back), or 'Tipa' if it's
    still vanilla/unrecognized."""
    tmp = os.path.join(tempfile.gettempdir(), "startloc_status_ffcc_5.cft")
    _extract(iso, FFCC5_SPAWN_DISC, tmp)
    data = open(tmp, "rb").read()
    cur_id = data[FFCC5_SPAWN_OFFSET + 4]
    for name, ids in STARTING_LOCATIONS.items():
        if ids is not None and ids[1] == cur_id:
            return name
    return "Tipa"


# Skip Meteor Parasite -> Mio questions -> Raem: a single-character patch in
# meteo_2.cft's own STR pool retargets the post-Meteor-Parasite script name
# from "last_5" (the memory/diary-check gate that leads into the Mio
# questions) to "last_3" (the Raem fight itself). User-discovered and byte-
# verified (2026-09-13). EXPERIMENTAL: unclear whether skipping the Mio
# questions this way leaves any state unset that a later check expects -
# not yet confirmed safe by a full playthrough.
METEO2_SKIP_DISC = "dvd/cft/meteo_2.cft"
METEO2_SKIP_OFFSET = 0x55DC3
METEO2_SKIP_ORIG = bytes.fromhex("35")      # ASCII '5' (of "last_5")
METEO2_SKIP_PATCHED = bytes.fromhex("33")   # ASCII '3' (of "last_3")


def patch_skip_mio_questions(iso, apply=True):
    """Retarget the post-Meteor-Parasite script from `last_5` to `last_3`,
    skipping straight to the Raem fight instead of the Mio question/diary-
    check sequence. Single-byte STR-pool patch. Returns True once present
    (freshly applied or already there); raises if the byte doesn't match
    either the vanilla original or the patched form (wrong game version)."""
    with open(iso, "r+b" if apply else "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, _ = gciso.find_file(files, METEO2_SKIP_DISC)[0]
        f.seek(off + METEO2_SKIP_OFFSET)
        cur = f.read(1)
        if cur == METEO2_SKIP_PATCHED:
            return True
        if cur != METEO2_SKIP_ORIG:
            raise ValueError(f"unexpected byte at meteo_2 skip site: {cur.hex()} "
                              f"(expected {METEO2_SKIP_ORIG.hex()} - wrong game version?)")
        if apply:
            f.seek(off + METEO2_SKIP_OFFSET)
            f.write(METEO2_SKIP_PATCHED)
    return True


def skip_mio_questions_status(iso):
    """True if `iso`'s meteo_2.cft already has the Raem-skip patch applied."""
    tmp = os.path.join(tempfile.gettempdir(), "skipmio_meteo_2.cft")
    _extract(iso, METEO2_SKIP_DISC, tmp)
    data = open(tmp, "rb").read()
    cur = data[METEO2_SKIP_OFFSET:METEO2_SKIP_OFFSET + 1]
    if cur == METEO2_SKIP_PATCHED:
        return True
    if cur == METEO2_SKIP_ORIG:
        return False
    raise ValueError(f"unexpected byte at meteo_2 skip site: {cur.hex()} "
                      f"(expected {METEO2_SKIP_ORIG.hex()} or {METEO2_SKIP_PATCHED.hex()} "
                      f"- wrong game version?)")


# Skip the opening intro cutscene: a 4-byte patch in world.cft's own STR pool
# retargets the boot-time script reference from "ff44_1" to "ffcc_5",
# jumping straight past the cutscene. User-discovered and byte-verified
# (2026-09-23/24, confirmed working in-game). The STR pool has a duplicate
# "ff44_1" entry immediately after this one - only this specific slot is
# patched, leaving the duplicate (and whatever else references it) untouched.
WORLD_INTRO_SKIP_DISC = "dvd/cft/world.cft"
WORLD_INTRO_SKIP_OFFSET = 0x596D0
WORLD_INTRO_SKIP_ORIG = bytes.fromhex("34345f31")     # ASCII "44_1" (of "ff44_1")
WORLD_INTRO_SKIP_PATCHED = bytes.fromhex("63635f35")  # ASCII "cc_5" (of "ffcc_5")


def patch_skip_intro_cutscene(iso, apply=True):
    """Retarget world.cft's boot-time script reference from `ff44_1` to
    `ffcc_5`, skipping the opening intro cutscene entirely. Single STR-pool
    slot patch (4 bytes). Returns True once present (freshly applied or
    already there); raises if the bytes don't match either the vanilla
    original or the patched form (wrong game version)."""
    with open(iso, "r+b" if apply else "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, _ = gciso.find_file(files, WORLD_INTRO_SKIP_DISC)[0]
        f.seek(off + WORLD_INTRO_SKIP_OFFSET)
        cur = f.read(4)
        if cur == WORLD_INTRO_SKIP_PATCHED:
            return True
        if cur != WORLD_INTRO_SKIP_ORIG:
            raise ValueError(f"unexpected bytes at intro-skip site: {cur.hex()} "
                              f"(expected {WORLD_INTRO_SKIP_ORIG.hex()} - wrong game version?)")
        if apply:
            f.seek(off + WORLD_INTRO_SKIP_OFFSET)
            f.write(WORLD_INTRO_SKIP_PATCHED)
    return True


def skip_intro_cutscene_status(iso):
    """True if `iso`'s world.cft already has the intro-cutscene-skip patch
    applied, False if it's still vanilla. Raises the same way
    `patch_skip_intro_cutscene` does if the bytes are neither (wrong game
    version)."""
    tmp = os.path.join(tempfile.gettempdir(), "skipintro_world.cft")
    _extract(iso, WORLD_INTRO_SKIP_DISC, tmp)
    data = open(tmp, "rb").read()
    cur = data[WORLD_INTRO_SKIP_OFFSET:WORLD_INTRO_SKIP_OFFSET + 4]
    if cur == WORLD_INTRO_SKIP_PATCHED:
        return True
    if cur == WORLD_INTRO_SKIP_ORIG:
        return False
    raise ValueError(f"unexpected bytes at intro-skip site: {cur.hex()} "
                      f"(expected {WORLD_INTRO_SKIP_ORIG.hex()} or {WORLD_INTRO_SKIP_PATCHED.hex()} "
                      f"- wrong game version?)")


# mainBasha (world.cft) checks `currentYear >= 2` at two sites before revealing
# Goblin Wall's road/icon on the world map (dispBgModel calls that show the
# extra terrain + map marker). Each site is a PUSHI 2 feeding that comparison,
# immediately after a read of the year global - changing the literal 2 -> 1
# makes the check always pass (year is never < 1), permanently revealing
# Goblin Wall from a Year 1 save without touching the year value itself or
# anything else. Confirmed live in-game (Dolphin memory testing) before being
# turned into this file patch.
WORLD_GOBLIN_WALL_VISIBLE_DISC = "dvd/cft/world.cft"
WORLD_GOBLIN_WALL_VISIBLE_OFFSETS = (0x3DE9D, 0x4193C)
WORLD_GOBLIN_WALL_VISIBLE_ORIG = bytes.fromhex("00000002")
WORLD_GOBLIN_WALL_VISIBLE_PATCHED = bytes.fromhex("00000001")


def patch_goblin_wall_always_visible(iso, apply=True):
    """Change both `currentYear >= 2` checks gating Goblin Wall's world-map
    road/icon reveal to `>= 1`, so it's visible from a Year 1 save. Two 4-byte
    site patches. Returns True once present (freshly applied or already
    there); raises if either site's bytes don't match the vanilla original or
    the patched form (wrong game version)."""
    with open(iso, "r+b" if apply else "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, _ = gciso.find_file(files, WORLD_GOBLIN_WALL_VISIBLE_DISC)[0]
        cur = []
        for site in WORLD_GOBLIN_WALL_VISIBLE_OFFSETS:
            f.seek(off + site)
            cur.append(f.read(4))
        if all(c == WORLD_GOBLIN_WALL_VISIBLE_PATCHED for c in cur):
            return True
        for site, c in zip(WORLD_GOBLIN_WALL_VISIBLE_OFFSETS, cur):
            if c != WORLD_GOBLIN_WALL_VISIBLE_ORIG:
                raise ValueError(f"unexpected bytes at Goblin-Wall-visible site 0x{site:X}: "
                                  f"{c.hex()} (expected {WORLD_GOBLIN_WALL_VISIBLE_ORIG.hex()} "
                                  f"- wrong game version?)")
        if apply:
            for site in WORLD_GOBLIN_WALL_VISIBLE_OFFSETS:
                f.seek(off + site)
                f.write(WORLD_GOBLIN_WALL_VISIBLE_PATCHED)
    return True


# flashStreamAttrib (world.cft) assigns which element (1=Fire,2=Water,4=Wind,
# 8=Earth) each of 4 rotating Miasma Stream slots requires, recomputed once
# per year as `year mod 4`. Each of the 4 (year mod 4) cases writes all 4
# slots as a permutation of {1,2,4,8} - 16 individual 4-byte int literals
# total, grouped here as 4 groups of 4 (one group per `year mod 4` case, in
# slot 0/1/2/3 order). Live-verified in-game: changing a single slot's value
# in isolation does change which element that stream/road requires, and
# doesn't affect anything else. Randomizing this is only safe paired with
# `patch_goblin_wall_always_visible` - see that function's docstring; without
# it, Fire/Earth aren't obtainable until Year 2 (Goblin Wall's own hotspots),
# which could strand a Year-1 save needing either of those from the very
# first stream.
WORLD_MIASMA_ELEMENTS_DISC = "dvd/cft/world.cft"
WORLD_MIASMA_ELEMENTS_GROUPS = (
    (0x180ea, 0x180fb, 0x1810c, 0x1811d),  # year mod 4 == 1
    (0x18145, 0x18156, 0x18167, 0x18178),  # year mod 4 == 2
    (0x181a0, 0x181b1, 0x181c2, 0x181d3),  # year mod 4 == 3
    (0x181fb, 0x1820c, 0x1821d, 0x1822e),  # year mod 4 == 0
)
MIASMA_ELEMENTS = (1, 2, 4, 8)  # Fire, Water, Wind, Earth


def randomize_miasma_elements(iso, rng, apply=True):
    """Shuffle which element each of the 4 rotating Miasma Stream slots
    requires, independently per `year mod 4` case (16 sites total, 4 groups
    of 4). Returns the list of 4 permutations actually written (one per
    group, in slot 0-3 order) - always a permutation of MIASMA_ELEMENTS
    per group, so every element remains reachable via some slot every year."""
    groups = []
    for group in WORLD_MIASMA_ELEMENTS_GROUPS:
        perm = list(MIASMA_ELEMENTS)
        rng.shuffle(perm)
        groups.append(perm)
    if apply:
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, WORLD_MIASMA_ELEMENTS_DISC)[0]
            for group, perm in zip(WORLD_MIASMA_ELEMENTS_GROUPS, groups):
                for site, value in zip(group, perm):
                    f.seek(off + site + 1)  # +1: skip the PUSHI opcode byte
                    f.write(struct.pack(">i", value))
    return groups


def miasma_elements_status(iso):
    """Current element assigned to each of the 4 slots, per `year mod 4`
    group (list of 4 lists of 4 ints - Fire=1/Water=2/Wind=4/Earth=8).
    Raises if any site doesn't hold a value from MIASMA_ELEMENTS (wrong game
    version)."""
    tmp = os.path.join(tempfile.gettempdir(), "miasma_world.cft")
    _extract(iso, WORLD_MIASMA_ELEMENTS_DISC, tmp)
    data = open(tmp, "rb").read()
    groups = []
    for group in WORLD_MIASMA_ELEMENTS_GROUPS:
        values = []
        for site in group:
            v = struct.unpack(">i", data[site + 1:site + 5])[0]
            if v not in MIASMA_ELEMENTS:
                raise ValueError(f"unexpected value at Miasma-element site 0x{site:X}: "
                                  f"{v} (expected one of {MIASMA_ELEMENTS} - wrong game version?)")
            values.append(v)
        groups.append(values)
    return groups


def goblin_wall_always_visible_status(iso):
    """True if `iso`'s world.cft already has the Goblin-Wall-always-visible
    patch applied, False if it's still vanilla. Raises the same way
    `patch_goblin_wall_always_visible` does if either site's bytes are
    neither (wrong game version)."""
    tmp = os.path.join(tempfile.gettempdir(), "goblinwall_world.cft")
    _extract(iso, WORLD_GOBLIN_WALL_VISIBLE_DISC, tmp)
    data = open(tmp, "rb").read()
    cur = [data[site:site + 4] for site in WORLD_GOBLIN_WALL_VISIBLE_OFFSETS]
    if all(c == WORLD_GOBLIN_WALL_VISIBLE_PATCHED for c in cur):
        return True
    if all(c == WORLD_GOBLIN_WALL_VISIBLE_ORIG for c in cur):
        return False
    raise ValueError(f"unexpected bytes at Goblin-Wall-visible sites: "
                      f"{[c.hex() for c in cur]} (expected all "
                      f"{WORLD_GOBLIN_WALL_VISIBLE_ORIG.hex()} or all "
                      f"{WORLD_GOBLIN_WALL_VISIBLE_PATCHED.hex()} - wrong game version?)")


def mog_never_tired_status(iso):
    """True if `iso`'s Start.dol already has the Mog-never-tired patch applied,
    False if it's still vanilla. Raises the same way `patch_mog_never_tired`
    does if the bytes there are neither (wrong game version)."""
    with open(iso, "rb") as f:
        off, _ = gciso.dol_span(f)
        f.seek(off + MOG_PRESSURE_DOL_OFFSET)
        cur = f.read(4)
    if cur == MOG_PRESSURE_PATCHED:
        return True
    if cur == MOG_PRESSURE_ORIG:
        return False
    raise ValueError(f"unexpected bytes at Mog-pressure patch site: {cur.hex()} "
                      f"(expected {MOG_PRESSURE_ORIG.hex()} or {MOG_PRESSURE_PATCHED.hex()} "
                      f"- wrong game version?)")


# "Development Mode" debug menu unlock (community-documented Action Replay
# codes, translated to direct Start.dol patches, 2026-09-16): normally hidden
# behind a retail build-check, this re-enables a real developer debug menu
# (MUTEKI/invincible, COLCHECK, PARTICLE, CHARA INFO, and more) plus a second-
# controller input path for it. All 9 sites verified against the retail
# NTSC-US Start.dol (offsets are DOL-relative, i.e. added to gciso.dol_span()'s
# own offset, not raw ISO offsets - matches this file's other DOL patches).
# Once applied: plug in a second GameCube controller (Port 2). On Port 2,
# A opens the debug menu, B closes it, D-pad Up/Down moves the selection and
# A/B toggles the highlighted entry. This is a QA test-flag menu (invincibility,
# collision, particle/shadow toggles, etc.) - it is NOT confirmed to include a
# working free-roam camera; treat it as an experimental bonus, not a core
# feature, and expect some entries to do nothing or destabilize the game.
DEBUG_MENU_PATCHES = [
    (0x00ed0c, bytes.fromhex("a0040036"), bytes.fromhex("a004005c")),
    (0x00ed10, bytes.fromhex("540005ad"), bytes.fromhex("540006f7")),
    (0x0115ec, bytes.fromhex("a0030036"), bytes.fromhex("a003ff0c")),
    (0x011630, bytes.fromhex("a0630034"), bytes.fromhex("54e0052b")),
    (0x01165c, bytes.fromhex("54e0077b"), bytes.fromhex("54e00529")),
    (0x011668, bytes.fromhex("2c000002"), bytes.fromhex("54e0056b")),
    (0x028104, bytes.fromhex("fc600890"), bytes.fromhex("a003005c")),
    (0x036508, bytes.fromhex("8003003c"), bytes.fromhex("8003001c")),
    (0x03787c, bytes.fromhex("a0630036"), bytes.fromhex("a063ff0c")),
]


def patch_debug_menu(iso, apply=True):
    """Unlock the developer 'Development Mode' debug menu (see DEBUG_MENU_PATCHES
    above) via 9 verified Start.dol patches. Returns True once all sites are in
    the patched state (freshly applied or already there); raises if any site's
    bytes are neither the vanilla original nor the patched form (wrong game
    version), without writing anything partway."""
    with open(iso, "r+b" if apply else "rb") as f:
        off, _ = gciso.dol_span(f)
        current = []
        for rel, orig, patched in DEBUG_MENU_PATCHES:
            f.seek(off + rel)
            cur = f.read(4)
            if cur != orig and cur != patched:
                raise ValueError(f"unexpected bytes at debug-menu patch site 0x{rel:x}: "
                                  f"{cur.hex()} (expected {orig.hex()} - wrong game version?)")
            current.append(cur)
        if all(cur == patched for cur, (_, _, patched) in zip(current, DEBUG_MENU_PATCHES)):
            return True
        if apply:
            for rel, _, patched in DEBUG_MENU_PATCHES:
                f.seek(off + rel)
                f.write(patched)
    return True


def debug_menu_status(iso):
    """True if `iso`'s Start.dol already has the debug-menu patch fully applied,
    False if it's still fully vanilla. Raises the same way `patch_debug_menu`
    does if a site is neither (wrong game version, or partially patched)."""
    with open(iso, "rb") as f:
        off, _ = gciso.dol_span(f)
        current = []
        for rel, orig, patched in DEBUG_MENU_PATCHES:
            f.seek(off + rel)
            cur = f.read(4)
            if cur != orig and cur != patched:
                raise ValueError(f"unexpected bytes at debug-menu patch site 0x{rel:x}: "
                                  f"{cur.hex()} (expected {orig.hex()} or {patched.hex()} "
                                  f"- wrong game version?)")
            current.append(cur == patched)
    if all(current):
        return True
    if not any(current):
        return False
    raise ValueError("debug-menu patch is partially applied (mixed vanilla/patched sites) - "
                      "ISO may be corrupt")


def cmd_shops(iso, args, apply):
    """Randomize shop inventories (all shops, or those named by --shop)."""
    rng = random.Random(args.seed)
    found = shops_in_iso(iso)
    only = set(args.shop) if args.shop else None
    if only:
        bad = only - {b for b, _, _ in found}
        for b in sorted(bad):
            print(f"  (no shop '{b}' in ISO - skipped)")
    pool = shop_pool(iso)
    verb = "Randomized" if apply else "WOULD randomize"
    print(f"{verb} shops in {os.path.basename(iso)}  (seed {args.seed}, "
          f"pool of {len(pool)} sellable items):")
    total = 0
    for base, name, disc in found:
        if only is not None and base not in only:
            continue
        changes = randomize_shop(iso, base, disc, rng, pool, apply)
        total += len(changes)
        print(f"  {name:18s} ({base}): {len(changes)} slot(s)")
    print(f"{verb}: {total} shop slot(s) total.")
    if getattr(args, "prices", False):
        n = randomize_prices(iso, rng, apply, pool=pool)   # pool = vanilla shop stock
        print(f"  prices: {n} item price(s) {'shuffled' if apply else 'would shuffle'}")
    if not apply:
        print("Run `shops` (not `preview-shops`) to apply.")


def cmd_list(iso):
    found = dungeons_in_iso(iso)
    print(f"{len(found)} dungeon(s) in {os.path.basename(iso)}:")
    for script, friendly, discs in found:
        nsets = nslots = 0
        for disc in discs:
            tmp = os.path.join(tempfile.gettempdir(), "lst_" + os.path.basename(disc))
            _extract(iso, disc, tmp)
            sets = lootcft.find_sets(tmp, valid=is_item)
            nsets += len(sets)
            nslots += sum(sum(is_item(v) for _, v in s) for s in sets)
        print(f"  {script:8s} {friendly:24s} {len(discs)} area(s)  "
              f"{nslots:4d} droppable slot(s) in {nsets} chest set(s)")


def chest_set_indices(ref_iso, script, disc):
    """Set indices that map to a Game8 chest (i.e. real chests, not enemy-drop
    or shared pools). Used by 'chests only' mode to leave enemy drops alone."""
    return set(_chest_labels(ref_iso, script, disc)[0].keys())


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


def dungeon_chest_map(ref_iso, script, discs):
    """Dungeon-wide chest numbering (same as the chest editor): one label_sets
    pass across ALL areas so each Game8 chest number is used once per dungeon.
    Returns {(area_no, set_index): chest_number} using the VANILLA ref contents
    (set order/offsets are identical pre/post randomization)."""
    import game8_chests as g8
    dungeon = g8.SCRIPT_TO_DUNGEON.get(script)
    if not dungeon:
        return {}
    flat, combined = [], []
    for disc in discs:
        tmp = os.path.join(tempfile.gettempdir(), "refmap_" + os.path.basename(disc))
        _extract(ref_iso, disc, tmp)
        for si, s in enumerate(lootcft.find_sets(tmp, valid=is_item)):
            flat.append((_area_no(disc), si))
            combined.append([v for _, v in s])
    labels = g8.label_sets(combined, dungeon)
    return {flat[fi]: cn for fi, cn in labels.items()}


def set_kind(item_ids):
    """Classify a NON-chest set by content: 'magicite', 'gathering', or 'monster'.

    Validated against the GameCube set-list sheet's chest()/monster[] tagging
    (River matched exactly): all-magicite sets are element/magicite spawns; sets
    of only food / Phoenix Down / raw '*Seed' materials are gathering nodes; and
    everything else (artifacts, recipes/scrolls, or crafting materials like
    Bronze/Iron/Mythril/ores/monster-parts) is an enemy (monster) drop."""
    reals = [v for v in item_ids if is_item(v)]
    if not reals:
        return "gathering"
    cats = {items.category(v) for v in reals}
    if cats <= {"Magicite"}:
        return "magicite"

    def _gather(v):
        return items.category(v) in ("Food", "PhoenixDown") or items.name(v).endswith("Seed")

    if all(_gather(v) for v in reals):
        return "gathering"
    return "monster"


def _options_header(o):
    """Build the 'options the player chose' block for the top of a spoiler, from
    an args/namespace-like object (CLI args or the GUI's ns). Missing attrs are
    tolerated so it works for both chest runs and the GUI's chest+shop runs."""
    import shops as shopmod
    g = lambda n, d=None: getattr(o, n, d)
    dn = g("dungeon")
    dungeon_txt = "all" if not dn else ", ".join(
        dict(lootcft.DUNGEONS).get(s, s) for s in dn)
    lines = ["Options chosen:",
             f"  Seed                : {g('seed')}",
             f"  Mode                : {g('mode', 'cross')}",
             f"  Rolls               : {g('rolls', 'cycle')}",
             f"  Item pool           : {g('pool', 'all')}",
             f"  Max artifacts/cycle : {g('max_artifacts', 4)}",
             f"  Scope               : {'chests only' if g('chests_only') else 'chests + enemy drops'}",
             f"  Fill empty slots    : {'yes' if g('fill_empty') else 'no'}",
             f"  Dungeons            : {dungeon_txt}"]
    if g("rand_shops"):
        sel = g("shops") or list(shopmod.SHOPS)
        names = ", ".join(shopmod.SHOPS.get(b, b) for b in sel)
        lines.append(f"  Shops randomized    : {names}")
    else:
        lines.append(f"  Shops randomized    : no")
    prices_on = g("rand_prices") or g("prices")
    lines.append(f"  Shop prices         : {'shuffled' if prices_on else 'unchanged'}")
    return lines


def _shop_spoiler_lines(iso):
    """Lines describing each shop's current stock (distinct sellable items),
    annotated with each item's price (gil) from param.cfd."""
    import shops as shopmod
    prices = read_prices(iso)
    out = []
    for base, name, disc in shops_in_iso(iso):
        tmp = os.path.join(tempfile.gettempdir(), "spshop_" + base + ".cft")
        _extract(iso, disc, tmp)
        stock = shopmod.find_shop_items(tmp, valid=is_sellable)
        distinct = list(dict.fromkeys(v for _, v in stock))
        if not distinct:
            continue
        out.append(f"  {name}:")
        labels = [f"{items.name(v)} ({prices.get(v, '?')}g)" for v in distinct]
        # wrap to ~4 items per line for readability
        for i in range(0, len(labels), 4):
            out.append("      " + ", ".join(labels[i:i + 4]))
    return out


def cmd_spoiler(iso, out_path, ref=None, header=None):
    """Read the (already randomized) ISO and write a spoiler log of every chest,
    grouped by level name and cycle, plus shop inventories. If `ref` (a vanilla
    ISO) is given, chests are numbered by their Game8 chest number. `header`, if
    given, is a list of lines (the player's chosen options) written at the top."""
    found = dungeons_in_iso(iso)
    lines = [f"FFCC SPOILER  -  {os.path.basename(iso)}", ""]
    if header:
        lines += list(header) + [""]
    lines += ["Cycles are by slot position (cycle 1 = early game ... cycle 3 = late);"
              " '/' lists the items a chest can give that cycle.", ""]
    for script, friendly, discs in found:
        dungeon_lines = []
        for disc in discs:
            tmp = os.path.join(tempfile.gettempdir(), "spoil_" + os.path.basename(disc))
            _extract(iso, disc, tmp)
            sets = lootcft.find_sets(tmp, valid=is_item)
            if not sets:
                continue
            labels = _chest_labels(ref, script, disc)[0] if ref else {}
            # Game8's matcher can map several sets to one generic chest; keep only
            # the first set per chest number (per area).
            seen_chest, titles = set(), {}
            for si in range(len(sets)):
                cn = labels.get(si)
                if cn is not None and cn not in seen_chest:
                    seen_chest.add(cn)
                    titles[si] = (0, cn, f"Chest {cn}")
                else:
                    titles[si] = (1, si, f"Set {si + 1}")
            order = sorted(range(len(sets)), key=lambda i: titles[i][:2])
            width = max((len(titles[i][2]) for i in order), default=6)
            if len(discs) > 1:
                dungeon_lines.append(f"  -- Area {_area_no(disc)} --")
            for cyc in (1, 2, 3):
                dungeon_lines.append(f"  Cycle {cyc}:")
                for si in order:
                    s = sets[si]
                    cycmap = lootcft.slot_cycles(len(s))
                    names, seen = [], set()
                    for ci, (_, v) in enumerate(s):
                        if cyc in cycmap[ci] and is_item(v) and v not in seen:
                            seen.add(v)
                            names.append(items.name(v))
                    content = " / ".join(names) if names else "-"
                    dungeon_lines.append(f"      {titles[si][2]:<{width}} : {content}")
                dungeon_lines.append("")
        if dungeon_lines:
            lines.append(f"=== {friendly} ===")
            lines += dungeon_lines
    shop_lines = _shop_spoiler_lines(iso)
    if shop_lines:
        lines += ["=== SHOPS (current stock) ===", ""] + shop_lines + [""]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote spoiler log -> {out_path}  ({len(found)} dungeons)")


# ---------------------------------------------------------------------------
# JSON export / patch
# ---------------------------------------------------------------------------
# JSON layout (dungeons span multiple AREA files, so set indices are per area):
#   { "_format": "...",
#     "<script>": { "_name": "<dungeon>",
#                   "<areaIndex>": { "<setIndex>": { "_label": "Chest N"|"Monster N"|...,
#                                    "_chest": <n|null>,
#                                    "1": "<item>", "2": "<item>", "3": "<item>" } } } }
# Set indices are stable per area (find_sets is deterministic). "_label" mirrors
# the chest editor: each Game8 chest is numbered once per dungeon ("Chest N"); every
# other set is classified (validated against the GameCube set-list sheet) as
# "Monster N" (enemy drop), "Magicite N" (stone/element spawn) or "Gathering N"
# (food/seeds), each numbered across areas. "_chest" is the numeric chest id or null.
# Each cycle value is a single item, or a list to spread across that cycle's slots.
# Items may be a name, "0xNN", or a "Name [0xNN]" label (hex wins). "_"-keys are
# metadata, ignored on import.
JSON_FORMAT = ("ffcc-chest-patch v2: dungeon-script -> area-index -> set-index -> "
               "cycle(1-3) -> item (name, 0xID, or 'Name [0xID]'). '_'-keys are notes "
               "('_label' = Chest/Monster/Magicite/Gathering N, '_chest' = number or null).")


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
    """Dump current chest contents to an editable JSON
    (level -> area -> set -> cycle)."""
    data = {"_format": JSON_FORMAT}
    try:
        data["_mog_never_tired"] = mog_never_tired_status(iso)
    except Exception:
        pass  # older/unrecognized dol - leave the key out rather than fail the export
    try:
        data["_starting_location"] = starting_location_status(iso)
    except Exception:
        pass  # older/unrecognized cft - leave the key out rather than fail the export
    try:
        data["_skip_mio_questions"] = skip_mio_questions_status(iso)
    except Exception:
        pass  # older/unrecognized cft - leave the key out rather than fail the export
    try:
        data["_skip_intro_cutscene"] = skip_intro_cutscene_status(iso)
    except Exception:
        pass  # older/unrecognized cft - leave the key out rather than fail the export
    try:
        data["_goblin_wall_always_visible"] = goblin_wall_always_visible_status(iso)
    except Exception:
        pass  # older/unrecognized cft - leave the key out rather than fail the export
    data["_randomize_miasma_elements"] = False    # set true to auto-randomize on patch
    try:
        data["_miasma_elements"] = miasma_elements_status(iso)
    except Exception:
        pass  # older/unrecognized cft - leave the key out rather than fail the export
    try:
        data["_enable_debug_menu"] = debug_menu_status(iso)
    except Exception:
        pass  # older/unrecognized dol - leave the key out rather than fail the export
    data["_stage_key_locks"] = False    # set true to create/place keys + apply locks on patch
    # EXPERIMENTAL boss shuffle. `_randomize_bosses: true` shuffles bosses on
    # patch (Goblin King and Lich stay home); `_bosses` places them explicitly
    # (dungeon -> boss, any boss in any dungeon) and wins over the shuffle for
    # every dungeon it lists. Needs a copy whose bosses haven't been moved yet.
    data["_randomize_bosses"] = False
    try:
        import bossshuffle
        status = bossshuffle.boss_status(iso)
        friendly = dict(lootcft.DUNGEONS)
        data["_bosses"] = {friendly[s]: n for s, n in status.items() if n}
        data["_boss_choices"] = [n for _, _, n, _ in bossshuffle.BOSSES]
    except Exception:
        pass  # older/unrecognized arena files - leave the keys out rather than fail
    data["_randomize_bonus_pools"] = False    # set true to auto-randomize on patch
    try:
        pools = read_bonus_pools(iso)
        if pools:
            # explicit overrides applied AFTER _randomize_bonus_pools (if both are
            # set) - edit specific entries here for exact control, leave others
            # alone. See project_ffcc_newbattle_bonus_pools memory for which entry
            # indices (0-7) a given cycle/score-tier can actually reach.
            data["_bonus_pools"] = {
                script: {str(ei): [items.label(v) for v in vals]
                        for ei, vals in entries.items()}
                for script, entries in pools.items()
            }
    except Exception:
        pass  # older/unrecognized newbattle.cfd - leave the key out rather than fail
    for script, friendly, discs in dungeons_in_iso(iso):
        dd = {"_name": friendly}
        # dungeon-wide numbering (each Game8 chest once); every other set is
        # classified Monster / Magicite / Gathering - identical to the chest
        # editor. (Labels need --ref to know which sets are chests.)
        cmap = dungeon_chest_map(ref, script, discs) if ref else {}
        kind_n = {"monster": 0, "magicite": 0, "gathering": 0}
        kind_name = {"monster": "Monster", "magicite": "Magicite", "gathering": "Gathering"}
        set_n = 0
        for disc in discs:
            tmp = os.path.join(tempfile.gettempdir(), "exp_" + os.path.basename(disc))
            _extract(iso, disc, tmp)
            sets = lootcft.find_sets(tmp, valid=is_item)
            if not sets:
                continue
            area = _area_no(disc)
            adata = {}
            for si, s in enumerate(sets):
                cn = cmap.get((area, si))
                if cn is not None:
                    label = f"Chest {cn}"
                elif ref:
                    kind = set_kind([it for _, it in s])
                    kind_n[kind] += 1
                    label = f"{kind_name[kind]} {kind_n[kind]}"
                else:
                    # no --ref: can't tell chests from monster loot, stay neutral
                    set_n += 1
                    label = f"Set {set_n}"
                entry = {"_label": label, "_chest": cn}
                for cyc in (1, 2, 3):
                    names = _cycle_items(s, cyc)
                    if names:
                        entry[str(cyc)] = names[0] if len(names) == 1 else names
                adata[str(si)] = entry
            dd[str(area)] = adata
        if len(dd) > 1:
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


# --------------------------------------------------------------------------- #
# Stage-key artifacts: one new key artifact per dungeon, placed in chests only
# (never monster drops - some enemies can drop several candidate artifacts at
# once, which would make key delivery unreliable). See
# Documentation/Artifact-Gated Stage Entrances.md for the in-game gating half
# of this feature (currently only wired up for Goblin Wall as a proof of
# concept - this section is the key-creation/placement half, usable
# independently of how many dungeons the gate check has been extended to).
#
# `river` (River Belle Path) is always left unlocked/keyless - it's the
# game's real starting dungeon. Every other dungeon's key is placed in a
# handful of chests in the PREVIOUS dungeon of a randomized chain that starts
# at `river`. A straight-line chain (not a general dependency graph) is what
# guarantees solvability by construction - no dungeon's key is ever inside
# that same dungeon, and there's no possibility of a cycle with no entry
# point, regardless of shuffle order.
STAGE_KEYS = [
    ("river", 0xE8, "River Key"),
    ("gob", 0xE9, "Gob Key"),
    ("mine", 0xEA, "Mine Key"),
    ("kinoko", 0xEB, "Shroom Key"),
    ("ruin", 0xEC, "Tida Key"),
    ("gigas", 0xED, "Manor Key"),
    ("lava", 0xEE, "Lava Key"),
    ("fort", 0xEF, "Fort Key"),
    ("cave", 0xF0, "Selep Key"),
    ("water", 0xF1, "Sluice Key"),
    ("desert", 0xF2, "Lynari Key"),
    ("swamp", 0xF3, "Conall Key"),
    ("city", 0xF4, "Rebena Key"),
    ("meteo", 0xF5, "Vellen Key"),
]
STAGE_KEY_DONOR = "Earth Pendant"     # real, valid artifact record to clone from
STAGE_KEY_ALWAYS_OPEN = "river"       # never locked, never holds a key requirement
STAGE_KEY_CHESTS_PER_DUNGEON = 3      # redundant copies so one missed chest isn't a softlock

# --- The actual in-game LOCKS, all 13 gated dungeons (see Documentation/
# Artifact-Gated Stage Entrances.md for the full byte-level writeup of what
# these edits do and why, using Goblin Wall as the worked example). Each
# dungeon always needs its OWN fixed key from STAGE_KEYS (`gob` always needs
# 0xE9 "Gob Key") - only WHERE that key is found is randomized by
# place_stage_keys(), so these locks stay correct no matter how the chain
# shuffles.
#
# All 13 dungeon entrances share ONE repurposed function (`encountKaido`,
# freed by neutralizing WM_MoveEnd's only call to it) rather than needing 13
# separate dead functions. This works because every mainBasha entrance call
# already pushes a unique per-site "stage id" as its own first argument
# (a plain vanilla implementation detail, not something we added) - so
# encountKaido's body can switch on that existing value to tell which
# dungeon's check applies, then forward the same 8 original arguments to
# that dungeon's own original MJ_SWING variant if the key is owned.
WORLD_CFT_DISC = "dvd/cft/world.cft"
_STAGE_LOCK_ENCOUNTER_CALL_OFF = 0x387C0                      # WM_MoveEnd -> encountKaido
_STAGE_LOCK_ENCOUNTER_CALL_ORIG = bytes.fromhex("0affff0256")
_STAGE_LOCK_ENCOUNTER_CALL_PATCHED = bytes.fromhex("0300000000")
_STAGE_LOCK_ENCOUNTKAIDO_INFO_OFF = 0x33e60                   # encountKaido INFO argCount (4B)
_STAGE_LOCK_ENCOUNTKAIDO_VAL_ARG0_OFF = 0x33e88               # encountKaido VAL header arg0 (localCount)
_STAGE_LOCK_ENCOUNTKAIDO_CODE_OFF = 0x33ec0                   # encountKaido CODE start

# (dungeon script, mainBasha call-site file offset, stage id, forward func idx)
# stage id / forward func idx / call-site bytes all independently verified
# against a real extracted world.cft before use (not assumed from memory).
# `lava` (Mount Kilanda) was NOT in the original hand-written proposal list -
# located this session by its stage id (172) sitting in an otherwise unbroken
# numeric sequence between Mount Vellenge (171) and Lynari Desert (173);
# high confidence from the real call-site structure matching every other
# entry exactly, but the dungeon-name identification itself isn't from an
# external source the way the other 12 were.
_STAGE_LOCK_SITES = [
    ("gob",    0x471D2, 140, 594),
    ("mine",   0x4884E, 146, 595),
    ("kinoko", 0x4897F, 147, 595),
    ("ruin",   0x4A098, 153, 594),
    ("gigas",  0x4A8CE, 155, 594),
    ("water",  0x4B1E7, 158, 593),
    ("cave",   0x4BF82, 162, 595),
    ("fort",   0x4C825, 164, 593),
    ("swamp",  0x4D057, 166, 593),
    ("city",   0x4D6C5, 167, 593),
    ("meteo",  0x4E1E5, 171, 593),
    ("lava",   0x4E33A, 172, 593),
    ("desert", 0x4E4B5, 173, 595),
]

# Start.dol: checkCaravanItem's compiled inventory search only scanned 8
# passes x 8 items = 64 slots (kInventoryCapacity) - structurally too short to
# ever see a permanent artifact (which start at slot 64). One instruction,
# main.dol file offset 0x913fc: li r0,8 -> li r0,20 (20*8=160, covering every
# regular item AND all 96 permanent artifact slots, safely within the array's
# own 164-slot bound).
_STAGE_LOCK_DOL_OFF = 0x913fc
_STAGE_LOCK_DOL_ORIG = bytes.fromhex("38000008")
_STAGE_LOCK_DOL_PATCHED = bytes.fromhex("38000014")


def _stage_lock_dispatcher_body(cases, check_func_idx=234):
    """Build encountKaido's replacement CFlat bytecode as a switch over the
    incoming local[0] ("stage id", see the module comment above `_STAGE_LOCK_
    SITES`). `cases`: [(stage_id, item_id, forward_func_idx), ...]. For each,
    if local[0]==stage_id: check item_id via the native checkCaravanItem
    (func idx `check_func_idx`), forward all 8 original arguments to
    forward_func_idx if owned, else silently deny. Falls through to a silent
    deny if local[0] doesn't match any case (should never happen - every
    redirected mainBasha call site pushes a stage id covered by exactly one
    case here)."""
    def op1(b):
        return bytes([b])

    def op5(b, arg):
        return bytes([b]) + struct.pack(">I", arg & 0xffffffff)

    prog = bytearray()
    for stage_id, item_id, forward_func_idx in cases:
        prog += op5(0x00, 1)                                   # GET local[0]
        prog += op5(0x03, stage_id)                            # PUSHI stage_id
        prog += op1(0x2c)                                      # int ==
        jz_next = len(prog)
        prog += op5(0x08, 0)                                   # JZ <next case> (patched below)

        prog += op5(0x03, 0)                                   # PUSHI 0   caravanIndex
        prog += op5(0x03, 2)                                   # PUSHI 2   flags
        prog += op5(0x03, item_id)                             # PUSHI itemId
        prog += op5(0x0a, (0xFFFF << 16) | check_func_idx)      # CALL checkCaravanItem
        prog += op5(0x03, 2)
        prog += op1(0x2c)
        jz_deny = len(prog)
        prog += op5(0x08, 0)                                   # JZ <deny> (patched below)
        for i in range(8):
            prog += op5(0x00, (i << 8) | 1)                    # GET local[i]
        prog += op5(0x0a, (0xFFFF << 16) | forward_func_idx)    # CALL <this dungeon's MJ_SWING variant>
        prog += op1(0x3c)                                      # RET
        deny_off = len(prog)
        prog += op1(0x3f)                                      # PUSH0
        prog += op1(0x3c)                                      # RET
        prog[jz_deny:jz_deny + 5] = op5(0x08, deny_off)

        next_case_off = len(prog)
        prog[jz_next:jz_next + 5] = op5(0x08, next_case_off)
    prog += op1(0x3f)   # default (should never be reached): silent deny
    prog += op1(0x3c)
    return bytes(prog)


def patch_stage_key_locks(iso, apply=True, sites=None):
    """Apply the in-game locks for every dungeon in `sites` (default: all 13
    in _STAGE_LOCK_SITES). Redirects each dungeon's own mainBasha entrance
    call to the shared encountKaido dispatcher, rewrites encountKaido's body
    to the switch built by _stage_lock_dispatcher_body(), and applies the one
    Start.dol fix needed for the check to see permanent artifacts at all.
    Same-size edits throughout - no ISO resizing needed. Returns True once
    present (freshly applied or already there); raises if any site's bytes
    are neither vanilla nor already-patched (wrong game version, a
    conflicting prior edit, or an already-modified `mainBasha`)."""
    sites = sites if sites is not None else _STAGE_LOCK_SITES
    key_by_dungeon = {s: kid for s, kid, _ in STAGE_KEYS}
    cases = [(stage_id, key_by_dungeon[script], forward_idx)
             for script, _, stage_id, forward_idx in sites]
    body = _stage_lock_dispatcher_body(cases)
    if len(body) > 18000:
        raise ValueError(f"dispatcher body ({len(body)}B) exceeds encountKaido's "
                          f"18000B budget - split across more than one repurposed function")

    tmp = os.path.join(tempfile.gettempdir(), "stagelock_world.cft")
    _extract(iso, WORLD_CFT_DISC, tmp)
    data = bytearray(open(tmp, "rb").read())

    site_patched = {}
    for script, call_off, _, forward_idx in sites:
        cur = bytes(data[call_off:call_off + 5])
        patched = bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | 598)
        orig = bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | forward_idx)
        if cur == patched:
            site_patched[script] = True
        elif cur == orig:
            site_patched[script] = False
        else:
            raise ValueError(f"{script}: unexpected bytes at call site 0x{call_off:x}: "
                              f"{cur.hex()} (expected {orig.hex()} or {patched.hex()} - "
                              f"wrong game version, or a conflicting prior edit?)")

    if not all(site_patched.values()):
        cur = data[_STAGE_LOCK_ENCOUNTER_CALL_OFF:_STAGE_LOCK_ENCOUNTER_CALL_OFF + 5]
        if cur not in (_STAGE_LOCK_ENCOUNTER_CALL_ORIG, _STAGE_LOCK_ENCOUNTER_CALL_PATCHED):
            raise ValueError(f"unexpected bytes at encounter-call site: {cur.hex()}")
        if apply:
            data[_STAGE_LOCK_ENCOUNTER_CALL_OFF:_STAGE_LOCK_ENCOUNTER_CALL_OFF + 5] = \
                _STAGE_LOCK_ENCOUNTER_CALL_PATCHED
            data[_STAGE_LOCK_ENCOUNTKAIDO_INFO_OFF:_STAGE_LOCK_ENCOUNTKAIDO_INFO_OFF + 4] = \
                struct.pack(">I", 8)
            data[_STAGE_LOCK_ENCOUNTKAIDO_VAL_ARG0_OFF:_STAGE_LOCK_ENCOUNTKAIDO_VAL_ARG0_OFF + 4] = \
                struct.pack(">I", 8)
            data[_STAGE_LOCK_ENCOUNTKAIDO_CODE_OFF:_STAGE_LOCK_ENCOUNTKAIDO_CODE_OFF + len(body)] = body
            for script, call_off, _, _fidx in sites:
                if not site_patched[script]:
                    data[call_off:call_off + 5] = bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | 598)
            open(tmp, "wb").write(data)
            with open(iso, "r+b") as f:
                _, files = gciso.parse_fst(f)
                _, off, _ = gciso.find_file(files, WORLD_CFT_DISC)[0]
                f.seek(off)
                f.write(data)

    with open(iso, "r+b" if apply else "rb") as f:
        off, _ = gciso.dol_span(f)
        f.seek(off + _STAGE_LOCK_DOL_OFF)
        cur = f.read(4)
        if cur != _STAGE_LOCK_DOL_PATCHED:
            if cur != _STAGE_LOCK_DOL_ORIG:
                raise ValueError(f"unexpected bytes at Start.dol offset 0x{_STAGE_LOCK_DOL_OFF:x}: "
                                  f"{cur.hex()} (expected {_STAGE_LOCK_DOL_ORIG.hex()})")
            if apply:
                f.seek(off + _STAGE_LOCK_DOL_OFF)
                f.write(_STAGE_LOCK_DOL_PATCHED)
    return True


def randomize_stage_key_chain(rng):
    """Return a random permutation of all 14 dungeon scripts with
    `STAGE_KEY_ALWAYS_OPEN` fixed first. For i>=1, chain[i]'s key must be
    placed in chain[i-1]'s chests (chain[0] needs no key). Guaranteed
    acyclic/solvable for ANY shuffle of the remaining 13, since it's a single
    straight chain rather than an arbitrary dependency graph."""
    others = [s for s, _, _ in STAGE_KEYS if s != STAGE_KEY_ALWAYS_OPEN]
    rng.shuffle(others)
    return [STAGE_KEY_ALWAYS_OPEN] + others


def stage_key_requirements(chain):
    """{dungeon_script: (key_id, key_name)} for every dungeon that needs a
    key to enter (all except chain[0], the always-open one)."""
    by_script = {s: (kid, name) for s, kid, name in STAGE_KEYS}
    return {chain[i]: by_script[chain[i]] for i in range(1, len(chain))}


STAGE_KEY_DESC_TEXT = {
    "mine": "Cathurige Key",     # shortened (1 char short of even "Cathuriges Key") - needed to fit
    "lava": "Kilanda Key",       # dropped "Mount " - needed to fit
    "cave": "Selepation Key",    # dropped "Cave" - needed to fit
    "swamp": "Conall Key",       # dropped "Curach" - needed to fit
}
# For a few IDs, the nearest "Help Message" placeholder(s) don't have enough
# spare room for set_item_description()'s default nearby auto-search - found
# by trial against a real ISO's c_system.cfd, not guessed. Explicit farther
# donor slot per Documentation/Adding Custom Items and Artifacts.md's own
# description recipe.
STAGE_KEY_DESC_DONOR = {
    "lava": 0xFB,
    "cave": 0xFC,   # distinct from lava's 0xFB - sharing one donor starved the second edit
    "mine": 0x110,
    "swamp": 0x162,
}


def create_stage_key_items(iso, donor=STAGE_KEY_DONOR):
    """Create all 14 stage-key artifacts as real, valid items (cloned from
    `donor`). An empty-placeholder artifact record silently fails to drop
    from chests at all - see Documentation/Artifact-Gated Stage
    Entrances.md, step 1, for why cloning a real donor is required rather
    than just naming the slot. Each also gets an in-game description naming
    the dungeon it unlocks."""
    import customitem
    friendly = dict(lootcft.DUNGEONS)
    for script, key_id, name in STAGE_KEYS:
        customitem.add_custom_item(iso, key_id, name, donor, article="the")
        desc = STAGE_KEY_DESC_TEXT.get(script, f"{friendly.get(script, script)} Key")
        customitem.set_item_description(iso, key_id, desc,
                                         donor_id=STAGE_KEY_DESC_DONOR.get(script))


def place_stage_keys(iso, chain, rng, chests_per_dungeon=STAGE_KEY_CHESTS_PER_DUNGEON,
                     holy_dungeons=HOLY_BOSS_DUNGEONS):
    """Place each dungeon's required key into `chests_per_dungeon` chests
    (chosen at random, all 7 cycle-slots of each so the key doesn't depend on
    which year the player finds it in) of the PREVIOUS dungeon in `chain` -
    only ever the dungeon the player must already be ABLE to enter, never the
    gated dungeon itself. Chests only, never monster/spawn drop tables. In a
    `holy_dungeons` dungeon the magicite sets are never used, so a key can't
    overwrite the Life/element stones the boss needs.
    Returns {dungeon_script: [chest_set_index, ...]} actually used."""
    by_script = dict((s, kid) for s, kid, _ in STAGE_KEYS)
    discs_by_script = {script: discs for script, _, discs in dungeons_in_iso(iso)}
    placements = {}
    for i in range(1, len(chain)):
        source_script = chain[i - 1]
        needed_key = by_script[chain[i]]
        discs = discs_by_script.get(source_script)
        if not discs:
            print(f"WARNING: no area files found for {source_script!r} in this ISO - "
                  f"{chain[i]!r}'s key could not be placed")
            continue
        disc = discs[0]
        tmp = os.path.join(tempfile.gettempdir(), "stagekey_" + os.path.basename(disc))
        size = _extract(iso, disc, tmp)
        sets = lootcft.find_sets(tmp, valid=lootcft._valid_item)
        if not sets:
            print(f"WARNING: no chests found in {disc!r} - {chain[i]!r}'s key could not be placed")
            continue
        candidates = [si for si, s in enumerate(sets)
                      if not (source_script in holy_dungeons and _is_magicite_set(s))]
        chosen_idx = sorted(rng.sample(candidates, k=min(chests_per_dungeon, len(candidates))))
        edits = {}
        for si in chosen_idx:
            for off, _ in sets[si]:
                edits[off] = needed_key
        lootcft.apply_edits(tmp, edits)
        data = open(tmp, "rb").read()
        if len(data) != size:
            raise ValueError(f"{disc}: size changed, refusing to inject")
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, disc)[0]
            f.seek(off)
            f.write(data)
        placements[chain[i]] = chosen_idx
    return placements


def cmd_patch(iso, json_path, max_artifacts=4):
    """Apply a chest JSON to the ISO: set each level/set/cycle to the given item.
    Warns if the result exceeds `max_artifacts` artifacts per cycle (carry cap)."""
    # Make sure the custom AP Item exists so a JSON that places it resolves. Safe
    # to call on every ISO (idempotent): users with a fresh, unpatched ISO get it
    # baked in automatically; already-patched ISOs are left untouched.
    try:
        import customitem
        if customitem.ensure_ap_item(iso):
            print("Installed AP Item into ISO (definition + name + icon).")
    except Exception as e:
        print(f"note: could not auto-install AP Item ({e}); JSON placing it may fail")
    with open(json_path, encoding="utf-8") as f:
        spec = json.load(f)
    boss_plan = _boss_plan_from_spec(spec)
    holy = holy_dungeons_for(boss_plan)
    if spec.get("_mog_never_tired"):
        try:
            patch_mog_never_tired(iso, apply=True)
            print("Applied Mog-never-tired Start.dol patch.")
        except Exception as e:
            print(f"note: could not apply Mog-never-tired patch ({e})")
    loc = spec.get("_starting_location")
    if loc and loc != "Tipa":
        try:
            patch_starting_location(iso, loc, apply=True)
            print(f"Applied starting-location patch: {loc}.")
            if loc == "Fields of Fum":
                print("  WARNING: do not change your chalice element away from Fire "
                      "before you're ready to cross back - the Miasma Stream there is "
                      "Fire, and switching away (e.g. to Wind in Selepation Cave) can "
                      "soft-lock your only way home, forcing a new save file.")
        except Exception as e:
            print(f"note: could not apply starting-location patch ({e})")
    if spec.get("_skip_mio_questions"):
        try:
            patch_skip_mio_questions(iso, apply=True)
            print("Applied Meteor Parasite -> Raem skip patch (Mio questions skipped).")
        except Exception as e:
            print(f"note: could not apply Mio-questions-skip patch ({e})")
    if spec.get("_skip_intro_cutscene"):
        try:
            patch_skip_intro_cutscene(iso, apply=True)
            print("Applied intro-cutscene-skip patch.")
        except Exception as e:
            print(f"note: could not apply intro-cutscene-skip patch ({e})")
    if spec.get("_goblin_wall_always_visible"):
        try:
            patch_goblin_wall_always_visible(iso, apply=True)
            print("Applied Goblin-Wall-always-visible patch.")
        except Exception as e:
            print(f"note: could not apply Goblin-Wall-always-visible patch ({e})")
    if spec.get("_randomize_miasma_elements"):
        if not spec.get("_goblin_wall_always_visible"):
            print("WARNING: _randomize_miasma_elements requires _goblin_wall_always_visible "
                  "to also be set (it's what guarantees Fire and Earth are obtainable from "
                  "Year 1 - without it, a shuffled stream could demand an element you have no "
                  "way to get yet). Skipping Miasma Stream randomization.")
        else:
            try:
                groups = randomize_miasma_elements(iso, random.Random(), apply=True)
                print(f"Randomized Miasma Stream elements (4 groups of 4): {groups}")
            except Exception as e:
                print(f"note: could not randomize Miasma Stream elements ({e})")
    if spec.get("_stage_key_locks"):
        try:
            create_stage_key_items(iso)
            chain = randomize_stage_key_chain(random.Random())
            reqs = stage_key_requirements(chain)
            placements = place_stage_keys(iso, chain, random.Random(), holy_dungeons=holy)
            patch_stage_key_locks(iso, apply=True)
            print("Stage-key artifacts: created all 14, placed via a randomized "
                  f"solvable chain starting at {STAGE_KEY_ALWAYS_OPEN!r}: {chain}")
            print("  All 13 gated dungeons now check for their key on entry.")
        except Exception as e:
            print(f"note: could not apply stage-key locks ({e})")
    if spec.get("_enable_debug_menu"):
        try:
            patch_debug_menu(iso, apply=True)
            print("Applied debug-menu unlock patch. Plug in a second GameCube "
                  "controller (Port 2): A opens the debug menu, B closes it, "
                  "D-pad Up/Down selects an entry, A/B toggles it.")
        except Exception as e:
            print(f"note: could not apply debug-menu unlock patch ({e})")
    if spec.get("_randomize_bonus_pools"):
        try:
            n = len(randomize_bonus_pools(iso, random.Random(), mode="cross",
                                          pool=build_pool("all"), apply=True))
            print(f"Randomized bonus pools: {n} slot(s) across "
                  f"{len(NEWBATTLE_BLOCKS)} dungeon(s).")
        except Exception as e:
            print(f"note: could not randomize bonus pools ({e})")
    bonus_overrides = spec.get("_bonus_pools")
    if bonus_overrides:
        try:
            parsed = {script: {int(ei): [resolve_item(v) if v is not None else None
                                        for v in vals]
                               for ei, vals in entries.items()}
                     for script, entries in bonus_overrides.items()
                     if script in NEWBATTLE_BLOCKS}
            skipped = sorted(set(bonus_overrides) - set(parsed))
            result = set_bonus_pools(iso, parsed, apply=True)
            total_bp = sum(len(v) for v in result.values())
            print(f"Applied explicit bonus-pool overrides: {total_bp} slot(s) "
                  f"across {len(result)} dungeon(s).")
            if skipped:
                print(f"  note: no bonus-pool block for {skipped} - skipped")
        except Exception as e:
            print(f"note: could not apply bonus-pool overrides ({e})")
    present = {script: discs for script, _, discs in dungeons_in_iso(iso)}
    total, warns = 0, []
    for script, dd in spec.items():
        if script.startswith("_"):
            continue
        if script not in present:
            warns.append(f"dungeon '{script}' not in ISO - skipped")
            continue
        by_area = {_area_no(d): d for d in present[script]}
        # per-dungeon artifact tally across areas for the cap check
        dungeon_after = []
        for area_key, adata in dd.items():
            if area_key.startswith("_") or not area_key.isdigit():
                continue
            area = int(area_key)
            if area not in by_area:
                warns.append(f"{script}: area {area} not in ISO - skipped")
                continue
            disc = by_area[area]
            tmp = os.path.join(tempfile.gettempdir(), "patch_" + os.path.basename(disc))
            size = _extract(iso, disc, tmp)
            sets = lootcft.find_sets(tmp, valid=is_item)
            edits = {}
            for set_key, entry in adata.items():
                if set_key.startswith("_") or not set_key.isdigit():
                    continue
                si = int(set_key)
                if si >= len(sets):
                    warns.append(f"{script} a{area}: set {si} out of range - skipped")
                    continue
                s = sets[si]
                cm = lootcft.slot_cycles(len(s))
                for cyc in (1, 2, 3):
                    if str(cyc) not in entry:
                        continue
                    vals = entry[str(cyc)]
                    vals = vals if isinstance(vals, list) else [vals]
                    ids = [resolve_item(x) for x in vals]
                    if any(i is None for i in ids):
                        warns.append(f"{script} a{area} set{si} c{cyc}: unresolved {vals}")
                        continue
                    bad = [i for i in ids if not is_item(i)]
                    if bad:
                        warns.append(f"{script} a{area} set{si} c{cyc}: not droppable "
                                     f"{[items.name(i) for i in bad]} - skipped (won't drop)")
                        continue
                    cyc_slots = [ci for ci, (_, cur) in enumerate(s)
                                 if cyc in cm[ci] and is_item(cur)]
                    for k, ci in enumerate(cyc_slots):
                        edits[s[ci][0]] = ids[k % len(ids)]
            if edits:
                lootcft.apply_edits(tmp, edits)
                buf = open(tmp, "rb").read()
                if len(buf) != size:
                    raise ValueError(f"{disc}: size changed, refusing to inject")
                with open(iso, "r+b") as f:
                    _, files = gciso.parse_fst(f)
                    _, off, _ = gciso.find_file(files, disc)[0]
                    f.seek(off)
                    f.write(buf)
                total += len(edits)
                print(f"  {script:8s} a{area}: {len(edits)} slot(s) patched")
            dungeon_after += lootcft.find_sets(tmp, valid=is_item)
        # artifact carry-cap check across the whole dungeon (all its areas)
        pc = _artifacts_per_cycle(dungeon_after)
        for c in (1, 2, 3):
            if pc[c] > max_artifacts:
                warns.append(f"{script}: cycle {c} now has {pc[c]} artifacts "
                             f"(max {max_artifacts}) - the player can only carry "
                             f"{max_artifacts} per cycle")
    for w in warns:
        print("  ! " + w)
    print(f"Patched {total} slot(s) into {os.path.basename(iso)}.")
    if boss_plan is not None:
        apply_bosses(iso, boss_plan)
    for problem in check_holy_access(iso, holy):
        print(f"WARNING: {problem}")


def _boss_plan_from_spec(spec):
    """Boss plan from a patch JSON, or None to leave bosses alone.

    `_bosses` ({dungeon: boss}) places bosses explicitly. With
    `_randomize_bosses: true` the rest are shuffled (Goblin King and Lich stay
    home), and an entry naming a dungeon's own original boss counts as "no
    preference" - so an exported `_bosses` block left unedited doesn't cancel
    the shuffle. A boss placed explicitly is taken out of the shuffle."""
    import bossshuffle
    explicit = {}
    if spec.get("_bosses"):
        full = bossshuffle.normalize_plan(spec["_bosses"])
        vanilla = bossshuffle.vanilla_plan()
        explicit = {s: b for s, b in full.items() if b != vanilla[s]}
    if not spec.get("_randomize_bosses"):
        if not explicit:
            return None
        plan = bossshuffle.vanilla_plan()
        plan.update(explicit)
        return plan
    return bossshuffle.random_plan(random.Random(), fixed=explicit)


def holy_dungeons_for(boss_plan):
    """Dungeons whose magicite must stay vanilla: wherever Lich and Zombie
    Dragon are (their home dungeons when bosses aren't moved)."""
    if boss_plan is None:
        return HOLY_BOSS_DUNGEONS
    import bossshuffle
    return bossshuffle.holy_dungeons(boss_plan)


def apply_bosses(iso, boss_plan, spoiler=None):
    """Apply a boss plan (EXPERIMENTAL) and print what moved. Appends the
    placement to `spoiler` if given."""
    import bossshuffle
    try:
        log = bossshuffle.apply_boss_plan(iso, boss_plan)
    except Exception as e:
        print(f"note: could not place bosses ({e})")
        return False
    moved = [l for l in log if not l.startswith("    ")]
    print("Bosses (EXPERIMENTAL): " + ("; ".join(moved) if moved else "no changes"))
    if spoiler:
        with open(spoiler, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(bossshuffle.plan_text(boss_plan)) + "\n")
    return True


def cmd_hybrid_patch(iso, ref_iso, ffcc_file):
    """Hybrid AP patch: own-player chests get the real item; others get AP Item.

    Reads the .ffcc placement file produced by Archipelago generation to decide
    which item belongs in each chest.  For this player's own items the game
    engine gives the item naturally on chest open, so the AP client skips the
    memory-write for those locations (preventing a double-give).

    Usage:
        py randomizer.py ap-hybrid "Hacked Rom.iso" --ref "Vanilla.iso" --ffcc "seed.ffcc"
    """
    import json, zipfile as _zipfile

    AP_ITEM_ID = 0x162

    # ── 1. Read placement from .ffcc file ──────────────────────────────────────
    # Accepts either a raw .ffcc JSON file (the one sitting in the output folder)
    # or the .zip container that wraps it — both contain the same placement data.
    placement_json = None
    try:
        with _zipfile.ZipFile(ffcc_file) as zf:
            for name in zf.namelist():
                if name.endswith(".ffcc"):
                    placement_json = json.loads(zf.read(name))
                    break
        if placement_json is None:
            sys.exit(f"No .ffcc entry found inside {ffcc_file}")
    except _zipfile.BadZipFile:
        # The user selected the raw .ffcc JSON file rather than the .zip wrapper —
        # both are valid and carry identical placement data; read it directly.
        try:
            with open(ffcc_file, "r", encoding="utf-8") as fh:
                placement_json = json.load(fh)
            print(f"Note: reading {os.path.basename(ffcc_file)} as plain JSON "
                  f"(not a ZIP — both formats are accepted).")
        except Exception as e2:
            sys.exit(f"Could not read {ffcc_file} as ZIP or JSON: {e2}")
    except Exception as e:
        sys.exit(f"Could not open {ffcc_file}: {e}")

    self_player = placement_json.get("player", "")
    raw_locs    = placement_json.get("locations", {})
    print(f"Loaded placement for player '{self_player}' — {len(raw_locs)} location(s).")

    # Build lookup: (dungeon, cycle, game8_chest_no) -> item_id to write in binary
    chest_items = {}  # (dungeon:str, cycle:int, chest:int) -> int
    real_count  = 0
    for loc_name, loc_data in raw_locs.items():
        dungeon  = loc_data.get("dungeon", "")
        cycle    = int(loc_data.get("cycle", 1))
        chest_no = int(loc_data.get("game8_chest", 0))
        is_self  = loc_data.get("player") == self_player

        if is_self:
            # Use the item_id written directly into the .ffcc file — no name
            # resolution needed and guaranteed to match the in-game ID exactly.
            raw_id = loc_data.get("item_id")
            item_id = int(raw_id) if raw_id is not None else None
            if item_id is not None and is_item(item_id):
                chest_items[(dungeon, cycle, chest_no)] = item_id
                real_count += 1
            else:
                # Trap / Progressive Artifact / item_id absent → AP Item placeholder
                chest_items[(dungeon, cycle, chest_no)] = AP_ITEM_ID
        else:
            chest_items[(dungeon, cycle, chest_no)] = AP_ITEM_ID

    other_count = len(raw_locs) - real_count
    print(f"  {real_count} own real items → real model in chest"
          f",  {other_count} other/trap → AP Item placeholder.")

    # ── 2. Install AP Item definition ─────────────────────────────────────────
    try:
        import customitem
        if customitem.ensure_ap_item(iso):
            print("Installed AP Item into ISO (definition + name + icon).")
    except Exception as e:
        print(f"Note: could not auto-install AP Item ({e}); 0x162 must already be present.")

    # ── 3. Apply per-cycle item assignments ────────────────────────────────────
    found = dungeons_in_iso(iso)
    total_slots = 0

    for script, friendly, discs in found:
        chest_map = dungeon_chest_map(ref_iso, script, discs)
        if not chest_map:
            print(f"  {friendly}: no game8 chest data — skipped")
            continue

        for disc in discs:
            area = _area_no(disc)
            area_chest_map = {si: cn for (a, si), cn in chest_map.items() if a == area}
            if not area_chest_map:
                continue

            tmp  = os.path.join(tempfile.gettempdir(), "hybrid_" + os.path.basename(disc))
            size = _extract(iso, disc, tmp)
            sets = lootcft.find_sets(tmp, valid=is_item)

            edits = {}
            for si, chest_no in area_chest_map.items():
                if si >= len(sets):
                    continue
                slots      = sets[si]
                cycle_map  = lootcft.slot_cycles(len(slots))  # list of {cycle_int} per slot
                for k, (off, cur) in enumerate(slots):
                    if not is_item(cur):
                        continue
                    cycle   = next(iter(cycle_map[k]))         # extract int from single-element set
                    item_id = chest_items.get((friendly, cycle, chest_no), AP_ITEM_ID)
                    edits[off] = item_id

            if edits:
                lootcft.apply_edits(tmp, edits)
                buf = open(tmp, "rb").read()
                if len(buf) != size:
                    raise ValueError(f"{disc}: size changed, refusing to inject")
                with open(iso, "r+b") as f:
                    _, files = gciso.parse_fst(f)
                    _, off, _ = gciso.find_file(files, disc)[0]
                    f.seek(off)
                    f.write(buf)
                total_slots += len(edits)
                print(f"  {script:8s} a{area}: {len(edits)} slot(s) patched (hybrid)")

    print(f"Hybrid AP patch complete: {total_slots} slot(s) written into {os.path.basename(iso)}.")


def cmd_ap_patch(iso, ref_iso):
    """Replace every game8-matched chest set in `iso` with AP Item (0x162).

    `ref_iso` must be the unmodified vanilla ISO so the chest-set matcher can
    identify which loot sets are game8-tracked chests (vs. enemy/gathering drops).

    After running this command, every game8 chest gives the custom AP Item when
    opened. The Archipelago client then intercepts the pickup and delivers the
    real randomized item via memory writes.

    Usage:
        py randomizer.py ap-patch "Hacked Rom.iso" --ref "Vanilla.iso"
    """
    AP_ITEM_ID = 0x162

    try:
        import customitem
        if customitem.ensure_ap_item(iso):
            print("Installed AP Item into ISO (definition + name + icon).")
    except Exception as e:
        print(f"Note: could not auto-install AP Item ({e}); 0x162 must already be present.")

    found = dungeons_in_iso(iso)
    total_slots = 0

    for script, friendly, discs in found:
        chest_map = dungeon_chest_map(ref_iso, script, discs)
        if not chest_map:
            print(f"  {friendly}: no game8 chest data — skipped")
            continue

        for disc in discs:
            area = _area_no(disc)
            # Set indices in this area that are game8-identified chests
            chest_sets = {si for (a, si), _cn in chest_map.items() if a == area}
            if not chest_sets:
                continue

            tmp = os.path.join(tempfile.gettempdir(), "ap_" + os.path.basename(disc))
            size = _extract(iso, disc, tmp)
            sets = lootcft.find_sets(tmp, valid=is_item)

            edits = {}
            for si in sorted(chest_sets):
                if si >= len(sets):
                    continue
                for off, cur in sets[si]:
                    if is_item(cur):
                        edits[off] = AP_ITEM_ID

            if edits:
                lootcft.apply_edits(tmp, edits)
                buf = open(tmp, "rb").read()
                if len(buf) != size:
                    raise ValueError(f"{disc}: size changed, refusing to inject")
                with open(iso, "r+b") as f:
                    _, files = gciso.parse_fst(f)
                    _, off, _ = gciso.find_file(files, disc)[0]
                    f.seek(off)
                    f.write(buf)
                total_slots += len(edits)
                print(f"  {script:8s} a{area}: {len(edits)} slot(s) -> AP Item")

    print(f"AP patch complete: {total_slots} slot(s) replaced in {os.path.basename(iso)}.")


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
    chests_only = getattr(args, "chests_only", False)
    ref = getattr(args, "ref", None)
    if chests_only and not ref:
        sys.exit("--chests-only needs --ref <vanilla.iso> to identify which sets are chests")
    verb = "Randomizing" if apply else "Preview (no write)"
    print(f"{verb}: seed={args.seed} mode={args.mode} rolls={args.rolls} "
          f"pool={args.pool} pool_size={len(pool)} max_artifacts/cycle="
          f"{getattr(args, 'max_artifacts', 4)} "
          f"scope={'chests-only' if chests_only else 'chests+drops'} dungeons={len(found)}")
    boss_plan = None
    if getattr(args, "randomize_bosses", False):
        import bossshuffle
        boss_plan = bossshuffle.random_plan(random.Random(f"{args.seed}-bosses"))
    holy = holy_dungeons_for(boss_plan)
    total = 0
    for script, friendly, discs in found:
        only_by_disc = None
        if chests_only:
            only_by_disc = {disc: chest_set_indices(ref, script, disc) for disc in discs}
            if not any(only_by_disc.values()):
                print(f"\n{friendly} ({script})  -  skipped (no Game8 chest data to isolate chests)")
                continue
        changes = randomize_dungeon(iso, script, discs, rng, args.mode, pool,
                                    args.fill_empty, apply, args.rolls,
                                    getattr(args, "max_artifacts", 4), only_by_disc,
                                    holy_dungeons=holy)
        total += len(changes)
        na = len(discs)
        print(f"\n{friendly} ({script})  -  {len(changes)} slot(s) changed across {na} area(s)")
        for area, si, ci, old, new in changes[:120]:
            print(f"  a{area} set {si:2d} slot {ci+1}: "
                  f"{items.name(old):26s} -> {items.name(new)}  [0x{old:04x}->0x{new:04x}]")
        if len(changes) > 120:
            print(f"  ... ({len(changes)-120} more)")
    print(f"\n{'WROTE' if apply else 'WOULD CHANGE'} {total} slot(s) total.")
    if apply:
        spoiler = os.path.splitext(iso)[0] + " - spoiler.txt"
        cmd_spoiler(iso, spoiler, ref=getattr(args, "ref", None),
                    header=_options_header(args))
        if boss_plan is not None:
            apply_bosses(iso, boss_plan, spoiler)
        for problem in check_holy_access(iso, holy):
            print(f"WARNING: {problem}")
    else:
        print("Run the same command with `run` (and the same --seed) to apply.")


def main():
    p = argparse.ArgumentParser(description="Randomize FFCC chest contents in an ISO.")
    p.add_argument("command", choices=["list", "preview", "run", "spoiler", "export",
                                        "patch", "ap-patch", "ap-hybrid", "shops", "preview-shops",
                                        "list-shops", "prices"])
    p.add_argument("iso")
    p.add_argument("json", nargs="?", help="JSON file (for `patch`)")
    p.add_argument("--shop", action="append",
                   help="limit shop randomization to this shop base name (repeatable; "
                        "default = all shops). Names come from `list-shops`")
    p.add_argument("--prices", action="store_true",
                   help="also shuffle item prices (with `shops`); or use the `prices` "
                        "command to shuffle prices only")
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
    p.add_argument("--chests-only", action="store_true",
                   help="randomize only Game8-identified chests, leaving enemy-drop / "
                        "shared sets alone (needs --ref; dungeons without Game8 data are skipped)")
    p.add_argument("--ref", help="vanilla ISO used to label spoiler chests by Game8 chest number")
    p.add_argument("--randomize-bosses", action="store_true",
                   help="EXPERIMENTAL: shuffle dungeon bosses between arenas (with `run`; "
                        "Goblin King and Lich stay home). Needs a copy whose bosses "
                        "haven't been moved yet")
    p.add_argument("--ffcc", help=".ffcc placement file (for `ap-hybrid`)")
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
    elif args.command == "ap-patch":
        if not args.ref or not os.path.isfile(args.ref):
            sys.exit("ap-patch needs --ref <vanilla.iso> to identify which sets are chests")
        cmd_ap_patch(args.iso, args.ref)
    elif args.command == "ap-hybrid":
        if not args.ref or not os.path.isfile(args.ref):
            sys.exit("ap-hybrid needs --ref <vanilla.iso>")
        if not args.ffcc or not os.path.isfile(args.ffcc):
            sys.exit("ap-hybrid needs --ffcc <seed.ffcc> (the Archipelago output file)")
        cmd_hybrid_patch(args.iso, args.ref, args.ffcc)
    elif args.command == "list-shops":
        for base, name, _ in shops_in_iso(args.iso):
            print(f"  {base:12s} {name}")
    elif args.command == "shops":
        cmd_shops(args.iso, args, apply=True)
    elif args.command == "preview-shops":
        cmd_shops(args.iso, args, apply=False)
    elif args.command == "prices":
        n = randomize_prices(args.iso, random.Random(args.seed), apply=True)
        print(f"Shuffled {n} item price(s) in {os.path.basename(args.iso)} (seed {args.seed}).")
    else:
        cmd_run(args.iso, args, apply=True)


if __name__ == "__main__":
    main()
