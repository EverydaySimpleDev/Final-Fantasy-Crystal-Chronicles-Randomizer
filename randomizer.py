"""
randomizer.py - Randomize FFCC dungeon chest contents across an entire ISO.

Builds on the existing tooling:
    gciso.py      - extract/inject files inside the .iso (in place, fixed size)
    lootcft.py    - find treasure sets in <dungeon>_0.cft and edit item slots
    ffcc_items.py - item ID <-> name + category tables

WHAT A CHEST RECORD ACTUALLY IS
-------------------------------
Each treasure slot is a 0x5b-byte script record in get_treasure(). The ONLY
per-item field is a single push-int at record+0 holding the item ID. The rest of
the record is identical regardless of the item's category (Material / Food /
Phoenix Down / Artifact / Magicite / Recipe records differ only in that one ID
and a positional counter). So putting ANY
item in ANY chest is a single 16-bit edit. The "categories must match" rule in
the older tools is a safety convention, not a hard engine constraint.

WHAT ACTUALLY DROPS
-------------------
Cross-category never crashes, but only "droppable" item classes are granted by
the chest pickup path:
    DROPPABLE : Artifact (0x9f-0xe7), Magicite (real stones only),
                Phoenix Down (0x125), Material (0x126-0x172),
                Food (0x17d-0x18e), Recipe/Scroll (0x191-0x1ed)
    NOT DROP. : craftable EQUIPMENT - Weapon/Armor/Shield/Gauntlet/Helmet/
                Belt/Accessory (0x01-0x9e). The chest opens but gives nothing.
This is exactly the set vanilla chests ever contain. Equipment is obtained by
crafting recipes, so the engine has no path to hand it out from a box. The
chest's *original* category is irrelevant - only the new item's class matters.

Also avoid Unused/Test IDs and anything past 0x01ed (focus attacks, raw spells,
enemy skills). For example, "Stone of Holy" 0x108 looks like magicite but does not drop.
This randomizer only ever writes IDs from the curated droppable pool below.

USAGE
    # make a copy of your ISO first, this writes in place
    python randomizer.py list    "Hacked Rom.iso"          # show dungeons found
    python randomizer.py preview "Hacked Rom.iso" --seed 1 # dry run, prints diff
    python randomizer.py run     "Hacked Rom.iso" --seed 1 # randomize + inject
                                                           #   (also writes a spoiler log)
    python randomizer.py spoiler "Hacked Rom.iso"          # spoiler for current ISO state
    python randomizer.py export  "Hacked Rom.iso" --ref "Vanilla.iso"  # dump chests -> JSON
    python randomizer.py patch   "Hacked Rom.iso" edits.json           # apply a chest JSON

The JSON (see `export` output) maps dungeon-script -> set-index -> cycle(1-3) ->
item. Edit it and `patch` to set exactly those contents. Items may be a name,
"0xID", or "Name [0xID]". A cycle value can be a list to spread across its slots.

OPTIONS
    --seed N        reproducible result (default: time-based)
    --mode MODE     cross    : any droppable item in any chest (default)
                    category : keep each slot within its original category
    --rolls MODE    cycle    : one item per chest per cycle (default)
                    slot     : every slot rolled independently (most variety)
                    chest    : one item for the whole chest (fully predictable)
    --pool POOL     all (default) | artifact | magicite | consumable | recipe
    --max-artifacts N  cap artifacts per dungeon per cycle (default 4 = the
                    in-game carry limit). Excess chests get a non-artifact item
    --chests-only   randomize only chests, not enemy drops (needs --ref). Enemy
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

# Item categories a chest can actually hand out.
# Craftable equipment is intentionally absent: chests open but give nothing.
DROPPABLE_CATS = {"Artifact", "Magicite", "PhoenixDown", "Material", "Food", "Recipe"}

# IDs inside the droppable categories that are still Unused / Test / unimple-
# mented and must never be placed.
EXCLUDE = set()
EXCLUDE |= {0x156, 0x160, 0x161, 0x170}                   # unused materials
# (0x162 was here too, but it's now repurposed as the custom "AP Item" - a real,
#  placeable Material with Gold's model. See ffcc_items NAMES[0x162].)
EXCLUDE |= set(range(0x173, 0x17d))                       # Extra 24-33
EXCLUDE |= set(range(0x189, 0x191))                       # unused shards / trade fillers
# Magicite: only these stones are real, droppable drops. The rest of
# 0x100-0x124 are spell internals or unimplemented (e.g. 0x108 "Holy" does NOT
# drop).
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
    the same randomized item. rolls: 'slot' = every slot its own item,
    'cycle' = one item per cycle (slots grouped by their primary/earliest cycle),
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


# Dungeons that need one of their OWN magicite stones to be completed.
# Magicite stones don't carry between dungeons, so the stone must come from
# that dungeon: its vanilla all-magicite sets (per-element spawn/drop tables,
# e.g. city_0 sets 7-13 = Fire/Blizzard/Thunder/Cure/Life/Clear/mixed) are
# never randomized or used for stage keys. Every dungeon has these sets.
#  - "holy": the boss takes 1 damage until hit with Holy. Holy isn't a
#    droppable stone (0x108 never drops). It's cast by fusing Fire/Blizzard/
#    Thunder THEN Stone of Life (Start.dol fusion table - Life first gives
#    Slow). Follows Lich / Zombie Dragon when the boss shuffle moves them.
#  - "fire": the path is blocked by something only Fire clears (Tida's
#    spider webs).
HOLY_BOSS_DUNGEONS = {"city": "Lich", "swamp": "Zombie Dragon"}
FIRE_DUNGEONS = {"ruin": "Tida's spider webs"}
# script -> (need, reason), the default when bosses aren't moved
STONE_DUNGEONS = {**{k: ("holy", v) for k, v in HOLY_BOSS_DUNGEONS.items()},
                  **{k: ("fire", v) for k, v in FIRE_DUNGEONS.items()}}
STONE_OF_FIRE = 0x100
STONE_OF_LIFE = 0x107
ELEMENT_STONES = {0x100, 0x101, 0x102}


def _is_magicite_set(s):
    return set_kind([v for _, v in s]) == "magicite"


def _randomize_area(iso, disc, rng, mode, pool, nonart, fill_empty, apply, rolls,
                    max_artifacts, art_per_cycle, only_sets, keep_magicite=False):
    """Randomize ONE area file in place. `art_per_cycle` is the dungeon-wide
    artifact tally (shared across the dungeon's areas). `keep_magicite` leaves
    the area's all-magicite sets vanilla (see STONE_DUNGEONS). Returns
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
                      max_artifacts=4, only_by_disc=None, holy_dungeons=STONE_DUNGEONS):
    """Randomize all area files of one dungeon, enforcing at most `max_artifacts`
    artifacts per cycle ACROSS the whole dungeon (one shared tally). `only_by_disc`
    (dict disc -> set of chest set indices) restricts to chests, None = everything.
    Dungeons in `holy_dungeons` (see STONE_DUNGEONS) keep their magicite sets,
    so the stones they need stay obtainable.
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


def check_stone_access(iso, stone_dungeons=STONE_DUNGEONS):
    """After all patching: for each dungeon in `stone_dungeons` ({script:
    (need, reason)}), confirm its areas still have the stones it needs -
    "holy": a set that is all Stone of Life plus a set with an element stone, and
    "fire": a set with a Stone of Fire. Returns problem strings (empty = OK)."""
    problems = []
    for script, friendly, discs in dungeons_in_iso(iso):
        if script not in stone_dungeons:
            continue
        need, reason = stone_dungeons[script]
        life = element = fire = False
        for disc in discs:
            tmp = os.path.join(tempfile.gettempdir(), "stones_" + os.path.basename(disc))
            _extract(iso, disc, tmp)
            for s in lootcft.find_sets(tmp, valid=is_item):
                ids = [v for _, v in s]
                life |= all(v == STONE_OF_LIFE for v in ids)
                element |= any(v in ELEMENT_STONES for v in ids)
                fire |= any(v == STONE_OF_FIRE for v in ids)
        if need == "holy" and not (life and element):
            missing = " and ".join(x for x, ok in (("no Stone of Life set", life),
                                                   ("no element stone set", element)) if not ok)
            problems.append(f"{friendly} ({reason} needs Holy): {missing} - Holy may be impossible")
        elif need == "fire" and not fire:
            problems.append(f"{friendly} ({reason} need Fire): no Stone of Fire set - "
                            f"the dungeon may be impossible to finish")
    return problems


check_holy_access = check_stone_access      # older name


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
    """Randomize one shop's stock in place. Returns [(slot, old_id, new_id)].

    A shop's stock comes in tiers that the game switches between as the story
    progresses (e.g. Tipa's 4 tiers follow the village's house-growth level,
    Leuda's follow its event state) - never randomly and never cyclically.
    In vanilla each later tier keeps the earlier tier's items and adds more.
    So each vanilla item is replaced by ONE random item, used in every tier
    of this shop: the randomized shop keeps that structure, and an item seen
    in an early year stays on sale later."""
    import shops as shopmod
    tmp = os.path.join(tempfile.gettempdir(), "shop_" + base + ".cft")
    size = _extract(iso, disc, tmp)
    slots = shopmod.find_shop_items(tmp, valid=is_sellable)
    originals = list(dict.fromkeys(cur for _, cur in slots))
    if len(pool) >= len(originals):
        picks = rng.sample(pool, len(originals))        # no two items collapse into one
    else:
        picks = [rng.choice(pool) for _ in originals]
    substitute = dict(zip(originals, picks))
    edits, changes = {}, []
    for i, (off, cur) in enumerate(slots):
        new = substitute[cur]
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
# dungeon, 0x168 bytes each, per the decomp struct in include/ffcc/
# game.h): m_bonusConditions[16] (0x00-0x20, unrelated per-spawn data),
# m_entries (0x20-0x160: 40x 8-byte entries, but only the first 8 -
# m_prefixEntries - are the actual random reward pool CGame::GetBossArtifact
# picks from, the other 32 are unrelated per-food/status data), then
# m_rankThresholds[4] (0x160-0x168, the score-tier cutoffs shown in-game as
# the point requirements). Each of the 8 reward entries holds 4 item ids
# (m_values[4], 2 bytes each) - 32 real item-id slots per dungeon.
# Block offsets are for the retail newbattle.cfd, found via each dungeon's
# m_rankThresholds pattern.
NEWBATTLE_ENTRY_COUNT = 8      # m_prefixEntries[8] - the real reward pool
NEWBATTLE_ENTRY_SIZE = 8       # m_values[4], 2 bytes each
NEWBATTLE_BLOCKS = {           # dungeon script -> its CBossArtifactStage file offset
    "river": 0x18c0, "gob": 0x1a28, "mine": 0x1b90, "kinoko": 0x1cf8,
    "ruin": 0x1e60, "gigas": 0x1fc8, "lava": 0x2130, "fort": 0x2298,
    "cave": 0x2400, "water": 0x2568, "desert": 0x26d0, "swamp": 0x2838,
    "city": 0x29a0,
    # "meteo" has no block: its slot in the file is all zeros.
}


def _newbattle_disc(iso):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    return next((p for p, _, _ in files if p.endswith("newbattle.cfd")), None)


def randomize_bonus_pools(iso, rng, mode="cross", pool=None, apply=True):
    """Randomize the post-stage bonus-reward item pool (newbattle.cfd) for
    every dungeon that has one (see NEWBATTLE_BLOCKS). `pool`: candidate item
    ids (from build_pool()). `mode`: 'category' or 'cross', same semantics as
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
    of random ones (see "Boss Reward Sets (GameCube guide).md" for how entry/value
    indices map to which score-tier/cycle can reach them).
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


def read_bonus_thresholds(iso):
    """{script: (4 score thresholds)} for every dungeon with a bonus-pool block.
    The game compares the party's bonus points, scaled by player count (x1.35
    solo, x1.25, x1.1, x1.0 for 2-4 players), against these."""
    disc = _newbattle_disc(iso)
    if disc is None:
        return {}
    tmp = os.path.join(tempfile.gettempdir(), "nb_thr_" + os.path.basename(disc))
    _extract(iso, disc, tmp)
    data = open(tmp, "rb").read()
    return {script: tuple(int.from_bytes(data[start + 0x160 + 2 * i:start + 0x162 + 2 * i], "big")
                          for i in range(4))
            for script, start in NEWBATTLE_BLOCKS.items()}


def export_bonus_table(iso, out_path):
    """Write the AP world's bonus_table.py: each dungeon's bonus thresholds and
    vanilla bonus pool, the items a randomized slot can get, and item names."""
    import lootcft
    pools, thresholds = read_bonus_pools(iso), read_bonus_thresholds(iso)
    names = dict(lootcft.DUNGEONS)
    candidates = build_pool("all")
    used = set(candidates)
    lines = ['"""',
             "Written by randomizer.py (Final-Fantasy-Crystal-Chronicles-Randomizer) from the",
             "game files - regenerate instead of editing by hand:",
             "    py randomizer.py export-bonus <clean.iso> <this file>",
             "",
             "The end-of-dungeon bonus (newbattle.cfd). Each dungeon has 8 reward entries",
             "of 4 items. The game offers entry (cycle start + tier): cycle start is",
             "0 / 2 / 4 for Cycles 1 / 2 / 3, tier is 0-3 by the party's score, and the",
             "player picks one of the entry's 4 items. A tier is reached when the bonus",
             "points times the player-count factor (x1.35 solo, x1.25, x1.1, x1.0 for",
             "2-4 players) are at least its threshold.",
             "",
             "BONUS_TABLE[dungeon] = (thresholds, entries)",
             "BONUS_CANDIDATES = the items a randomized slot can get.",
             '"""',
             "",
             "BONUS_TABLE = {"]
    for script, entries in pools.items():
        lines.append(f"    {names[script]!r}: ({thresholds[script]!r}, (")
        for ei in range(NEWBATTLE_ENTRY_COUNT):
            values = entries[ei]
            used.update(values)
            ids = ", ".join(f"0x{v:03x}" for v in values)
            label = ", ".join(items.NAMES.get(v, hex(v)) for v in values)
            lines.append(f"        ({ids}),   # {ei}: {label}")
        lines.append("    )),")
    lines.append("}")
    cand = ["", "BONUS_CANDIDATES = ("]
    for k in range(0, len(candidates), 10):
        cand.append("    " + ", ".join(f"0x{v:03x}" for v in candidates[k:k + 10]) + ",")
    cand.append(")")
    item_names = ["", "ITEM_NAMES = {"]
    for v in sorted(used):
        if v in items.NAMES:
            item_names.append(f"    0x{v:03x}: {items.NAMES[v]!r},")
    item_names.append("}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines + cand + item_names) + "\n")


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
    realistic and valid, and the 0xFFFF "not for sale" sentinel and unsold items are
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
    zero instead of 2/frame). Site in the retail NTSC-US `main.dol`: file
    offset 0x109bd4 = RAM 0x80119e34. Returns True once the patch is present
    (freshly applied or already there). Raises if the ISO's bytes there don't match either the
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


# Starting-location patch: a new game's opening camera focus (farewell_0.cft) and the caravan's actual
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
    previously patched copy still works). Raises on anything else."""
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


# Magicite needs its ring (Start.dol, NTSC-US). A magicite can only go into the
# command list once the player owns the matching ring in the permanent artifact
# list: Fire 0x100 -> Ring of Fire, Blizzard 0x101 -> Ring of Blizzard,
# Thunder 0x102 -> Ring of Thunder, Cure 0x105 -> Ring of Cure, Life 0x107 ->
# Ring of Life (artifact places 0x40-0x44, i.e. caravan +0x136 + 2 * place).
# Other items are not affected. Two code paths add magicite, so there are two
# hooks, each a branch into new code written in unused space of the debugger's
# interrupt table (gTRKInterruptVectorTable, as the trap-visuals patch does):
#   pickup:  the item-pickup dispatcher in gobjwork.o, hook 0x8012212c, code
#            at 0x800034dc. Without the ring it takes the game's own
#            "can't add" exit.
#   menu:    CCaravanWork::ChgCmdLst, hook 0x800a1a08, code at 0x800035b0.
#            Without the ring the menu change does nothing.
# (file offset, original bytes, new bytes), offsets inside Start.dol.
MAGICITE_RING_PATCHES = [
    (0x111ecc, bytes.fromhex("2c04009f"), bytes.fromhex("4bee13b0")),   # b 0x800034dc
    (0x4dc, bytes(116), bytes.fromhex(
        "2c040100" "41820028" "2c040101" "41820028" "2c040102" "41820028"
        "2c040105" "41820028" "2c040107" "41820028" "48000044"
        "38c00040" "48000020" "38c00041" "48000018" "38c00042" "48000010"
        "38c00043" "48000008" "38c00044"
        "807f0058" "54c6083c" "7cc33214" "a8060136" "2c00ffff" "40820008"
        "4811ec94"                      # b 0x801221d8, the game's "can't add" exit
        "2c04009f"                      # the instruction the hook replaced
        "4811ebe4")),                   # b 0x80122130, back after the hook
    (0x917a8, bytes.fromhex("7cdf0214"), bytes.fromhex("4bf61ba8")),    # b 0x800035b0
    (0x5b0, bytes(136), bytes.fromhex(
        "2c050000" "41800078" "54a7083c" "7cff3a14" "a8e700b6"
        "2c070100" "41820028" "2c070101" "41820028" "2c070102" "41820028"
        "2c070105" "41820028" "2c070107" "41820028" "48000040"
        "38e00040" "48000020" "38e00041" "48000018" "38e00042" "48000010"
        "38e00043" "48000008" "38e00044"
        "54e7083c" "7cff3a14" "a8e70136" "2c07ffff" "40820008"
        "4809e414"                      # b 0x800a1a3c, skip the change
        "5480083c" "7cdf0214"           # the instructions the hook replaced
        "4809e3d8")),                   # b 0x800a1a0c, back after the hook
]

# Always the best bonus tier (Start.dol, NTSC-US). CGame::GetBossArtifact picks
# the end-of-dungeon reward tier as rand() % (rank + 1), where rank 0-3 is the
# best tier the score reaches. Replacing that rand() call (0x8001439c) with
# "li r3, 11" always gives the best tier reached (11 % 1, 2, 3 or 4 = rank).
BEST_BONUS_TIER_PATCHES = [
    (0x413c, bytes.fromhex("481a3655"), bytes.fromhex("3860000b")),
]


# Picked-up artifacts are kept: picking an artifact (ids 0x9F-0xFF) up off the
# ground normally puts it in one of the caravan's 4 temporary slots
# (CCaravanWork::AddTmpArtifact, 0x800A14E0), and at the end of the dungeon
# each player keeps one of them. This replaces the function's start so it
# fills the artifact's permanent place instead, the place the artifact list
# and the save use (m_inventoryItems[64 + id - 0x9F], see SetArtifact).
# Its out-index becomes that place, so a Spell Ring's command points at it.
KEEP_ARTIFACTS_PATCHES = [
    (0x91280,
     bytes.fromhex("9421fff07c0802a67c671b789001001438000004"
                   "93e1000c3be0000093c100087cbe2b78"),
     bytes.fromhex(
         "38c4ffa1"    # addi  r6, r4, 64 - 0x9F  the artifact's permanent place
         "54c7083c"    # slwi  r7, r6, 1
         "7ce33a14"    # add   r7, r3, r7
         "b08700b6"    # sth   r4, 0xB6(r7)       m_inventoryItems[place] = id
         "2c050000"    # cmpwi r5, 0
         "41820008"    # beq   +8
         "90c50000"    # stw   r6, 0(r5)          *outIndex = place
         "38600001"    # li    r3, 1
         "4e800020")), # blr
]


def patch_keep_artifacts(iso, apply=True):
    """Artifacts picked up in a dungeon go straight into the artifact list
    (see KEEP_ARTIFACTS_PATCHES)."""
    return _dol_patch(iso, KEEP_ARTIFACTS_PATCHES, "keep-artifacts", apply)


def _dol_patch(iso, patches, name, apply=True):
    """Apply [(offset in Start.dol, original, new), ...] as one patch. Returns
    True once it is in place. Raises if the bytes are neither (wrong game
    version, or partly patched)."""
    with open(iso, "r+b" if apply else "rb") as f:
        off, _ = gciso.dol_span(f)
        current = []
        for at, orig, new in patches:
            f.seek(off + at)
            current.append(f.read(len(orig)))
        if all(cur == new for cur, (_, _, new) in zip(current, patches)):
            return True
        if not all(cur == orig for cur, (_, orig, _) in zip(current, patches)):
            raise ValueError(f"unexpected bytes at the {name} patch sites - wrong game version "
                             f"or partly patched?")
        if apply:
            for at, _, new in patches:
                f.seek(off + at)
                f.write(new)
    return True


def patch_magicite_needs_ring(iso, apply=True):
    """Magicite only goes into the command list once its ring is owned (see
    MAGICITE_RING_PATCHES)."""
    return _dol_patch(iso, MAGICITE_RING_PATCHES, "magicite-needs-ring", apply)


def patch_best_bonus_tier(iso, apply=True):
    """The end-of-dungeon bonus always gives the best tier reached (see
    BEST_BONUS_TIER_PATCHES)."""
    return _dol_patch(iso, BEST_BONUS_TIER_PATCHES, "best-bonus-tier", apply)


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
# questions) to "last_3" (the Raem fight itself).
# Experimental: skipping the Mio questions this way may leave some state unset
# that a later check expects.
METEO2_SKIP_DISC = "dvd/cft/meteo_2.cft"
METEO2_SKIP_OFFSET = 0x55DC3
METEO2_SKIP_ORIG = bytes.fromhex("35")      # ASCII '5' (of "last_5")
METEO2_SKIP_PATCHED = bytes.fromhex("33")   # ASCII '3' (of "last_3")


def patch_skip_mio_questions(iso, apply=True):
    """Retarget the post-Meteor-Parasite script from `last_5` to `last_3`,
    skipping straight to the Raem fight instead of the Mio question/diary-
    check sequence. Single-byte STR-pool patch. Returns True once present
    (freshly applied or already there). Raises if the byte doesn't match
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
# jumping straight past the cutscene. The STR pool has a duplicate
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
    already there). Raises if the bytes don't match either the vanilla
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


# mainBasha (world.cft) checks `currentYear >= 2` at three sites before revealing
# Goblin Wall's road/icon on the world map (dispBgModel calls that show the
# extra terrain + map marker). Each site is a PUSHI 2 feeding that comparison,
# immediately after a read of the year global - changing the literal 2 -> 1
# makes the check always pass (year is never < 1), permanently revealing
# Goblin Wall from a Year 1 save without touching the year value itself or
# anything else.
WORLD_GOBLIN_WALL_VISIBLE_DISC = "dvd/cft/world.cft"
# Three identical `year >= 2` gates. The first one (0x38CC3) is the one used on a
# fresh Year 1 world map, so without it Goblin Wall stays hidden on new saves.
WORLD_GOBLIN_WALL_VISIBLE_OFFSETS = (0x38CC3, 0x3DE9D, 0x4193C)
WORLD_GOBLIN_WALL_VISIBLE_ORIG = bytes.fromhex("00000002")
WORLD_GOBLIN_WALL_VISIBLE_PATCHED = bytes.fromhex("00000001")


def patch_goblin_wall_always_visible(iso, apply=True):
    """Change all three `currentYear >= 2` checks gating Goblin Wall's world-map
    road/icon reveal to `>= 1`, so it's visible from a Year 1 save. Three 4-byte
    site patches. Returns True once present (freshly applied or already
    there). Raises if either site's bytes don't match the vanilla original or
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
            if c not in (WORLD_GOBLIN_WALL_VISIBLE_ORIG, WORLD_GOBLIN_WALL_VISIBLE_PATCHED):
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
# slot 0/1/2/3 order). Changing a single slot's value
# in isolation does change which element that stream/road requires, and
# doesn't affect anything else. Randomizing this is only safe paired with
# `patch_goblin_wall_always_visible` - see that function's docstring. Without
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
        set_miasma_elements(iso, groups)
    return groups


def set_miasma_elements(iso, groups):
    """Write a Miasma Stream table: 4 rows (year % 4 == 1, 2, 3, 0) of the
    element each of the 4 gates needs (Fire=1/Water=2/Wind=4/Earth=8)."""
    if len(groups) != 4 or any(sorted(row) != sorted(MIASMA_ELEMENTS) for row in groups):
        raise ValueError(f"Miasma table must be 4 rows that each use all 4 elements: {groups}")
    with open(iso, "r+b") as f:
        _, files = gciso.parse_fst(f)
        _, off, _ = gciso.find_file(files, WORLD_MIASMA_ELEMENTS_DISC)[0]
        for group, row in zip(WORLD_MIASMA_ELEMENTS_GROUPS, groups):
            for site, value in zip(group, row):
                f.seek(off + site + 1)  # +1: skip the PUSHI opcode byte
                f.write(struct.pack(">i", value))


# Hotspot elements (AP option Hotspot Elements). A hotspot's element is the
# first argument of its SPAWN_HOT_SPOT call in a dungeon's SPAWN_MONSTER, and
# SPAWN_HOT_SPOT hands it to the HotSpot object. To make it change with the
# year, each call gets its own number (HOTSPOT_FIRST_ID + its place in the
# dungeon) and SPAWN_HOT_SPOT starts by turning that number into the element
# for the current year:
#     if ((year & 3) == y && arg0 == id) arg0 = element    (one test per year and hotspot)
HOTSPOT_TYPES = {"Fire": 1, "Water": 2, "Wind": 3, "Earth": 4, "Unknown": 5}
HOTSPOT_FIRST_ID = 100
_YEAR_SYSVAL = -0x40


def _hotspot_calls(script):
    """Code offsets of the element push of every SPAWN_HOT_SPOT call in
    SPAWN_MONSTER, in order."""
    import cft
    import spawn_map
    if "SPAWN_HOT_SPOT" not in script.names or "SPAWN_MONSTER" not in script.names:
        return []
    target = script.names.index("SPAWN_HOT_SPOT")
    reclen = spawn_map.RECORD_LEN["SPAWN_HOT_SPOT"]
    pushes, out = [], []
    for off, op, arg in cft.disasm(script.code("SPAWN_MONSTER")):
        if op in (0, 1, 2, 3, 4, 5):
            pushes.append((off, op))
        elif op == 0x0a:
            if (arg & 0xFFFF) == target and len(pushes) >= reclen:
                off0, op0 = pushes[-reclen]
                if op0 != 3:
                    raise ValueError("a SPAWN_HOT_SPOT element isn't a plain number")
                out.append(off0)
            pushes = []
    return out


# CFlat operands: (index << 8) | kind. Kind 0x01 = argument/local,
# 0x09 = global or system value, 0x19 = member of the running object.
def _arg(i):
    return (i << 8) | 0x01


def _global(i):
    return (i << 8) | 0x09


def _member(i):
    return (i << 8) | 0x19


def _year_chain(start, cases):
    """Bytecode for a chain of year tests: for each (y, key, key_value,
    sets) in `cases`, `if ((year & 3) == y && key == key_value) { each
    target = value in sets; }`, stopping at the first match. `key` and the
    targets are operands (_arg/_global/_member). `start` is where the code
    goes in its function, since jumps are absolute."""
    pushi = lambda v: b"\x03" + struct.pack(">i", v)
    year = b"\x00" + struct.pack(">i", _global(_YEAR_SYSVAL))
    lens = [22 + 16 + 12 * len(sets) + 5 for _, _, _, sets in cases]
    end = start + sum(lens)
    out = bytearray()
    pos = start
    for (y, key, key_value, sets), n in zip(cases, lens):
        nxt = pos + n
        out += year + pushi(3) + b"\x1f" + pushi(y) + b"\x2c" + b"\x08" + struct.pack(">i", nxt)
        out += b"\x00" + struct.pack(">i", key) + pushi(key_value) + b"\x2c" + b"\x08" + struct.pack(">i", nxt)
        for target, value in sets:
            out += b"\x01" + struct.pack(">i", target) + pushi(value) + b"\x0d\x0c"
        out += b"\x07" + struct.pack(">i", end)
        pos = nxt
    assert len(out) == end - start
    return bytes(out)


def _hotspot_remap(start, cases, arg_in=0, arg_out=0):
    """`if ((year & 3) == y && args[arg_in] == key) args[arg_out] = value`
    for each of `cases` = [(y, key, value)] (see _year_chain)."""
    return _year_chain(start, [(y, _arg(arg_in), key, [(_arg(arg_out), value)])
                               for y, key, value in cases])


def set_hotspot_elements(iso, table, log=None, menus=None):
    """Write hotspot elements that change every year. `table` is
    {dungeon name: 4 rows (years 1-4, repeating) of one element name per
    hotspot}, hotspots in the game's order (area file, then call order) - the
    AP world's rules.HOTSPOTS. The world map's name bubbles show the same
    elements. `menus` ({stop: 4 rows of element names}, the AP world's
    rules.make_menus) also sets the stops' "Change element" menus. Returns
    the number of hotspots changed."""
    import cft
    import cftpatch
    log = log if log is not None else []
    script_of = {name: script for script, name in lootcft.DUNGEONS}
    changed = 0
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    for dungeon, rows in table.items():
        script = script_of[dungeon]
        n = 0
        for k in range(8):
            disc = f"dvd/cft/{script}_{k}.cft"
            if not gciso.find_file(files, disc):
                continue
            tmp = os.path.join(tempfile.gettempdir(), f"hotspots_{script}_{k}.cft")
            _extract(iso, disc, tmp)
            s = cftpatch.Script(tmp)
            calls = _hotspot_calls(s)
            if not calls:
                continue
            first = struct.unpack(">i", s.code("SPAWN_MONSTER")[calls[0] + 1:calls[0] + 5])[0]
            if first >= HOTSPOT_FIRST_ID:
                raise ValueError(f"{disc}: hotspot elements are already set")
            code = bytearray(s.code("SPAWN_MONSTER"))
            cases = []
            for off in calls:
                if n >= len(rows[0]):
                    raise ValueError(f"{dungeon}: more hotspots than the table has")
                hid = HOTSPOT_FIRST_ID + n
                code[off + 1:off + 5] = struct.pack(">i", hid)
                for row, elements in enumerate(rows):
                    cases.append(((row + 1) & 3, hid, HOTSPOT_TYPES[elements[n]]))
                n += 1
                changed += 1
            s.set_code("SPAWN_MONSTER", bytes(code))
            ins = list(cft.disasm(s.code("SPAWN_HOT_SPOT")))
            # it opens with `if (!flag) return 0`: the remap goes after that
            at = ins[1][2] & 0xFFFFFF if [i[1] for i in ins[:4]] == [0x00, 0x08, 0x3f, 0x3c] else 0
            cftpatch.insert_code(s, "SPAWN_HOT_SPOT", at, _hotspot_remap(at, cases), log)
            gciso.put_file(iso, disc, s.to_bytes())
        if n != len(rows[0]):
            raise ValueError(f"{dungeon}: found {n} hotspots, the table has {len(rows[0])}")
    _set_bubble_elements(iso, table, log)
    if menus:
        _set_menu_elements(iso, menus, log)
    return changed


# The world map's name bubble shows a dungeon's elements as icons:
# WM_mapInfoDispOn(place, element bits, ...) in world.cft, place = the
# dungeon's number (c_system.cfd place names: River Belle Path 0 ... Rebena Te
# Ra 12). The loading-zone shuffle moves both arguments with the dungeon.
BUBBLE_BITS = {"Fire": 1, "Water": 2, "Wind": 4, "Earth": 8}
BUBBLE_PLACES = ["River Belle Path", "Goblin Wall", "The Mine of Cathuriges", "The Mushroom Forest",
                 "Tida", "Moschet Manor", "Mount Kilanda", "Daemon's Court", "Selepation Cave",
                 "Veo Lu Sluice", "Lynari Desert", "Conall Curach", "Rebena Te Ra"]


def _set_bubble_elements(iso, table, log):
    """Make the bubble's element icons follow the year's hotspot elements:
    WM_mapInfoDispOn starts with `if ((year & 3) == y && arg0 == place)
    arg1 = bits` for every dungeon in `table` and year row."""
    import cftpatch
    disc = "dvd/cft/world.cft"
    tmp = os.path.join(tempfile.gettempdir(), "hotspots_world.cft")
    _extract(iso, disc, tmp)
    s = cftpatch.Script(tmp)
    cases = []
    for dungeon, rows in table.items():
        place = BUBBLE_PLACES.index(dungeon)
        for row, elements in enumerate(rows):
            bits = 0
            for element in elements:
                bits |= BUBBLE_BITS.get(element, 0)
            cases.append(((row + 1) & 3, place, bits))
    code = _hotspot_remap(0, cases, arg_in=0, arg_out=1)
    cftpatch.insert_code(s, "WM_mapInfoDispOn", 0, code, log)
    gciso.put_file(iso, disc, s.to_bytes())


# The "Change element" menu at a stop: MJ_SWING_ATTRIB_2 (two choices) and
# MJ_SWING_ATTRIB_1 (one) set, per stop (G61), the choices in this.m41/m42
# and the menu text in this.m43 (a world.cfd message), then show it.
# stop (spot named by its vanilla dungeon): (G61, vanilla message, function)
MENU_STOPS = {
    "River Belle Path":       (2,  315, "MJ_SWING_ATTRIB_2"),
    "Goblin Wall":            (7,  316, "MJ_SWING_ATTRIB_2"),
    "Tida":                   (23, 317, "MJ_SWING_ATTRIB_2"),
    "Moschet Manor":          (26, 318, "MJ_SWING_ATTRIB_2"),
    "The Mushroom Forest":    (17, 319, "MJ_SWING_ATTRIB_1"),
    "The Mine of Cathuriges": (16, 320, "MJ_SWING_ATTRIB_1"),
    "Selepation Cave":        (43, 321, "MJ_SWING_ATTRIB_1"),
    "Lynari Desert":          (81, 322, "MJ_SWING_ATTRIB_1"),
}
# an element's word in a message, with its colour code before and the
# reset code after
MENU_WORDS = {"Fire": b"\xff\xaefire", "Water": b"\xff\xb1water",
              "Wind": b"\xff\xb0wind", "Earth": b"\xff\xb2earth"}
_MENU_WORD = re.compile(rb"\xff[\xae\xb0\xb1\xb2](?:fire|water|wind|earth)(?=\xff\xb3)")


def _cfd_messages(data):
    """(chunks, messages): a .cfd file's CFLD children as [tag, arg0,
    version, payload] and its MES strings."""
    tag, size, _, _ = struct.unpack(">4sIII", data[:16])
    if tag != b"CFLD":
        raise ValueError("not a CFLD file")
    chunks, p, end = [], 16, 16 + (size & 0xFFFFFF)
    while p + 16 <= end:
        t, sz, a0, ver = struct.unpack(">4sIII", data[p:p + 16])
        sz &= 0xFFFFFF
        chunks.append([t, a0, ver, data[p + 16:p + 16 + sz]])
        p += 16 + (sz + 15) // 16 * 16
    mes = next(c for c in chunks if c[0] == b"MES ")
    return chunks, mes[3].split(b"\0")[:mes[1]]


def _cfd_build(chunks, messages):
    """A .cfd file from its chunks, with MES set to `messages`."""
    body = bytearray()
    for t, a0, ver, payload in chunks:
        if t == b"MES ":
            payload, a0 = b"".join(m + b"\0" for m in messages), len(messages)
        body += struct.pack(">4sIII", t, len(payload), a0, ver) + payload
        body += bytes(-len(payload) % 16)
    return struct.pack(">4sIII", b"CFLD", len(body), 0, 0) + bytes(body)


def _set_menu_elements(iso, menus, log):
    """Give every stop's "Change element" menu its year's choices: one new
    world.cfd message per stop and year row (the stop's own text, so a
    shuffled dungeon name stays, with that year's element words), and a
    year chain in MJ_SWING_ATTRIB_1/_2, before the menu is shown, that sets
    the choices and the message. `menus` = {stop: 4 rows of element names}."""
    import cft
    import cftpatch
    tmp = os.path.join(tempfile.gettempdir(), "hotspots_world.cfd")
    _extract(iso, "dvd/cft/world.cfd", tmp)
    chunks, messages = _cfd_messages(open(tmp, "rb").read())
    if len(messages) + 4 * len(menus) > 1122:
        raise ValueError("world.cfd would have too many messages")
    cases = {"MJ_SWING_ATTRIB_1": [], "MJ_SWING_ATTRIB_2": []}
    for stop, rows in menus.items():
        g61, base, fn = MENU_STOPS[stop]
        for row, elements in enumerate(rows):
            words = iter(MENU_WORDS[e] for e in elements)
            text, n = _MENU_WORD.subn(lambda m: next(words), messages[base])
            if n != len(elements):
                raise ValueError(f"message {base} has {n} element words, {stop} offers {len(elements)}")
            sets = [(_member(41 + i), BUBBLE_BITS[e]) for i, e in enumerate(elements)]
            sets.append((_member(43), len(messages)))
            messages.append(text)
            cases[fn].append(((row + 1) & 3, _global(61), g61, sets))
    tmp_cft = os.path.join(tempfile.gettempdir(), "hotspots_world.cft")
    _extract(iso, "dvd/cft/world.cft", tmp_cft)
    s = cftpatch.Script(tmp_cft)
    for fn, fn_cases in cases.items():
        if not fn_cases:
            continue
        # right after the switch that sets the vanilla choices: the first
        # read of this.m40 (the "stage cleared" flag test)
        at = next(o for o, op, a in cft.disasm(s.code(fn)) if op == 0x00 and a == _member(40))
        cftpatch.insert_code(s, fn, at, _year_chain(at, fn_cases), log)
    gciso.put_file(iso, "dvd/cft/world.cft", s.to_bytes())
    gciso.put_file(iso, "dvd/cft/world.cfd", _cfd_build(chunks, messages))


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
    if all(c in (WORLD_GOBLIN_WALL_VISIBLE_ORIG, WORLD_GOBLIN_WALL_VISIBLE_PATCHED) for c in cur):
        return False    # vanilla, or patched by an older version that missed a gate
    raise ValueError(f"unexpected bytes at Goblin-Wall-visible sites: "
                      f"{[c.hex() for c in cur]} (expected all "
                      f"{WORLD_GOBLIN_WALL_VISIBLE_ORIG.hex()} or all "
                      f"{WORLD_GOBLIN_WALL_VISIBLE_PATCHED.hex()} - wrong game version?)")


# Trap visuals: writing a status timer directly from the AP client (e.g.
# slow = CCaravanWork+0x3E+2*8) gives the effect but no particle/sound - CGCharaObj::setSta only starts those when it
# sees a timer go 0 -> nonzero, and the per-frame loop in onFramePostCalc only
# ever counts timers down. This hook gives the client a "pending" table
# instead: each frame, for player 1's character only, a nonzero pending[i]
# replaces the value the loop passes to setSta(i, ...) and is then cleared, so
# the game applies the status itself (0 -> pending = full visual + sound).
#
# The hook replaces `lhzx r3,r3,r0` (load timer[i]) at 0x80111A48 with a `bl`
# into TRKDoReadMemory's space (0x801A9CA8, 0x244 bytes): MetroTRK debugger
# code, only reached when a hardware debugger sends a read-memory request.
# The client writes a 2-byte duration (frames) to TRAP_PENDING_TABLE + 2*i:
# i = 0 freeze, 1 burn, 2 poison, 4 paralysis, 8 slow. Paralysis also gets
# changeStat(10) (the stunned state), which setSta alone doesn't do.
TRAP_HOOK_DOL_OFFSET = 0x1017E8                   # RAM 0x80111A48
TRAP_HOOK_ORIG = bytes.fromhex("7c63022e")        # lhzx r3, r3, r0
TRAP_HOOK_PATCHED = bytes.fromhex("48098261")     # bl 0x801A9CA8
TRAP_CAVE_DOL_OFFSET = 0x199A48                   # RAM 0x801A9CA8
TRAP_PENDING_TABLE = 0x801A9D28                   # RAM, u16[39]
TRAP_CAVE_ORIG = bytes.fromhex(
    "542b06fe7c2c0b78216bf6c07c21596e7c0802a6900c0004bf4cffe87c7f1b783c60801e"
    "3ba35718389d01b038600001835f0020a37f001c8bdf00187f46d37888bf00147f67db78"
    "7fc8f3784cc63182480047e557c007bd41820040386100643880000038a000404be5b6fd"
    "3860008038a000403800001298610068386100643880004090a100649801006c480033f5"
    "386000004800019857dc067393610020418200207f44d3783861010038a1002038c00001"
    "480010817c7e1b784800002457c0effe7f44d3783861010038a1")
TRAP_CAVE_PATCHED = bytes.fromhex(
    "7c63022e"   # lhzx  r3, r3, r0       original: r3 = timer[i]
    "81990058"   # lwz   r12, 0x58(r25)   this->m_scriptHandle
    "3d608022"   # lis   r11, 0x8022
    "396bf270"   # addi  r11, r11, -0xd90 (0x8021F270 = player 1's CCaravanWork)
    "7c0c5800"   # cmpw  r12, r11
    "4c820020"   # bnelr                  not player 1 -> unchanged
    "3d60801b"   # lis   r11, 0x801B
    "396b9d28"   # addi  r11, r11, -0x62d8 (TRAP_PENDING_TABLE)
    "7d8bea2e"   # lhzx  r12, r11, r29    pending[i] (r29 = 2*i)
    "2c0c0000"   # cmpwi r12, 0
    "4d820020"   # beqlr                  nothing pending
    "386c0001"   # addi  r3, r12, 1       loop subtracts 1 -> setSta(i, pending)
    "39800000"   # li    r12, 0
    "7d8beb2e"   # sthx  r12, r11, r29    clear pending[i]
    "2c1d0008"   # cmpwi r29, 8           paralysis (i == 4)?
    "4c820020"   # bnelr
    "9421fff0"   # stwu  r1, -0x10(r1)    paralysis also needs the stunned state,
    "7c0802a6"   # mflr  r0               as CGCharaObj::effective() does:
    "90010014"   # stw   r0, 0x14(r1)
    "90610008"   # stw   r3, 0x8(r1)
    "7f23cb78"   # mr    r3, r25
    "3880000a"   # li    r4, 10
    "38a00000"   # li    r5, 0
    "38c00000"   # li    r6, 0
    "4bf7ce61"   # bl    CGPrgObj::changeStat(10, 0, 0)  (0x80126B68)
    "80610008"   # lwz   r3, 0x8(r1)
    "80010014"   # lwz   r0, 0x14(r1)
    "7c0803a6"   # mtlr  r0
    "38210010"   # addi  r1, r1, 0x10
    "4e800020"   # blr
) + bytes(TRAP_PENDING_TABLE - 0x801A9CA8 - 120 + 39 * 2)
assert len(TRAP_CAVE_ORIG) == len(TRAP_CAVE_PATCHED)


def _trap_visuals_state(f):
    off, _ = gciso.dol_span(f)
    f.seek(off + TRAP_HOOK_DOL_OFFSET)
    hook = f.read(4)
    f.seek(off + TRAP_CAVE_DOL_OFFSET)
    cave = f.read(len(TRAP_CAVE_PATCHED))
    if hook in (TRAP_HOOK_PATCHED, ITEM_DROP_HOOK_PATCHED) and cave == TRAP_CAVE_PATCHED:
        return True
    if hook == TRAP_HOOK_ORIG and cave == TRAP_CAVE_ORIG:
        return False
    raise ValueError(f"unexpected bytes at trap-visuals patch sites (hook {hook.hex()}) "
                      f"- wrong game version or partially patched?")


def patch_trap_visuals(iso, apply=True):
    """Install the trap-visuals hook (see TRAP_HOOK_* above) so AP status
    traps show the game's own particle effects. Returns True once present."""
    with open(iso, "r+b" if apply else "rb") as f:
        if _trap_visuals_state(f):
            return True
        if apply:
            off, _ = gciso.dol_span(f)
            f.seek(off + TRAP_CAVE_DOL_OFFSET)
            f.write(TRAP_CAVE_PATCHED)
            f.seek(off + TRAP_HOOK_DOL_OFFSET)
            f.write(TRAP_HOOK_PATCHED)
    return True


# Item drops: the AP client can put an item on the ground in front of the
# player instead of in the bag. It writes the item id to ITEM_DROP_PENDING.
# Once a frame, for player 1 only, this code asks the game whether the player
# can put something down (CGPartyObj::canPlayerPutItem: alive, free to act,
# not carrying anything) and, if so, creates the item the way the game's own
# "put an item down" does (CGItemObj::CreateFromScript(0, 9, id, player, 0.0,
# 0), without the put-down animation) and clears ITEM_DROP_PENDING. If the
# player can't, it waits for a later frame.
#
# It shares the trap-visuals hook site: the hook calls this code instead,
# which then jumps on into the trap code, so installing it installs trap
# visuals too. The code sits in the rest of TRKDoReadMemory's space, after
# the trap pending table.
ITEM_DROP_HOOK_PATCHED = bytes.fromhex("48098339")  # bl 0x801A9D80
ITEM_DROP_DOL_OFFSET = 0x199B18                     # RAM 0x801A9D78
ITEM_DROP_PENDING = 0x801A9D78                      # RAM, u16 item id
ITEM_DROP_ORIG = bytes.fromhex(
    "6806000138e000014800241d7c7e1b787fe3fb78388000004bffec852c1e000040820078"
    "386100a43880000038a000404be5b66580810020380000809bc100ac7fe3fb7838840040"
    "38a00040908100a4388100a4980100a84bffeb712c1c000041820024574006fe38810100"
    "80a100207fe3fb787c8402144bffeb517c7e1b784800001880a100207fe3fb7838810100"
    "4bffeb397c7e1b782c1e00004182008c381ef900")
ITEM_DROP_PATCHED = bytes.fromhex(
    "0000"       # ITEM_DROP_PENDING (0x801A9D78)
    "0000"
    "00000000"   # 0.0f (0x801A9D7C)
    "9421ffe0"   # stwu  r1, -0x20(r1)    0x801A9D80, called from the hook
    "9001000c"   # stw   r0, 0xc(r1)      keep the loop's r0 and r3 for the
    "90610008"   # stw   r3, 0x8(r1)      instruction the hook replaced
    "7c0802a6"   # mflr  r0
    "90010024"   # stw   r0, 0x24(r1)
    "81990058"   # lwz   r12, 0x58(r25)   this->m_scriptHandle
    "3d608022"   # lis   r11, 0x8022
    "396bf270"   # addi  r11, r11, -0xd90 (0x8021F270 = player 1's CCaravanWork)
    "7c0c5800"   # cmpw  r12, r11
    "40820060"   # bne   done             not player 1
    "2c1d0000"   # cmpwi r29, 0
    "40820058"   # bne   done             only on the loop's first status (once a frame)
    "3d60801b"   # lis   r11, 0x801B
    "a18b9d78"   # lhz   r12, -0x6288(r11) ITEM_DROP_PENDING
    "2c0c0000"   # cmpwi r12, 0
    "41820048"   # beq   done             nothing to drop
    "7f23cb78"   # mr    r3, r25
    "4bf723d9"   # bl    CGPartyObj::canPlayerPutItem (0x8011C19C)
    "2c030000"   # cmpwi r3, 0
    "41820038"   # beq   done             can't put anything down right now
    "3d60801b"   # lis   r11, 0x801B
    "a0ab9d78"   # lhz   r5, -0x6288(r11) item id
    "38600000"   # li    r3, 0            an item
    "38800009"   # li    r4, 9            in front of the player, on safe ground
    "7f26cb78"   # mr    r6, r25          dropped by the player
    "c02b9d7c"   # lfs   f1, -0x6284(r11) 0.0f
    "38e00000"   # li    r7, 0
    "4bf7af29"   # bl    CGItemObj::CreateFromScript (0x80124D14)
    "2c030000"   # cmpwi r3, 0
    "41820010"   # beq   done             not created, try again next frame
    "39800000"   # li    r12, 0
    "3d60801b"   # lis   r11, 0x801B
    "b18b9d78"   # sth   r12, -0x6288(r11) clear ITEM_DROP_PENDING
    "80010024"   # lwz   r0, 0x24(r1)     done:
    "7c0803a6"   # mtlr  r0
    "80610008"   # lwz   r3, 0x8(r1)
    "8001000c"   # lwz   r0, 0xc(r1)
    "38210020"   # addi  r1, r1, 0x20
    "4bfffe90"   # b     0x801A9CA8       on into the trap code, which returns to the loop
)
assert len(ITEM_DROP_ORIG) == len(ITEM_DROP_PATCHED)


def _item_drops_state(f):
    off, _ = gciso.dol_span(f)
    f.seek(off + ITEM_DROP_DOL_OFFSET)
    code = f.read(len(ITEM_DROP_PATCHED))
    if code == ITEM_DROP_PATCHED:
        return True
    if code == ITEM_DROP_ORIG:
        return False
    raise ValueError("unexpected bytes at the item-drop patch site - wrong game version?")


def patch_item_drops(iso, apply=True):
    """Install the item-drop code (see ITEM_DROP_* above) and the trap-visuals
    hook it goes through. Returns True once present."""
    with open(iso, "r+b" if apply else "rb") as f:
        if _item_drops_state(f) and _trap_visuals_state(f):
            return True
    if apply:
        patch_trap_visuals(iso, apply=True)
        with open(iso, "r+b") as f:
            off, _ = gciso.dol_span(f)
            f.seek(off + ITEM_DROP_DOL_OFFSET)
            f.write(ITEM_DROP_PATCHED)
            f.seek(off + TRAP_HOOK_DOL_OFFSET)
            f.write(ITEM_DROP_HOOK_PATCHED)
    return True


def trap_visuals_status(iso):
    """True if `iso`'s Start.dol has the trap-visuals hook, False if vanilla."""
    with open(iso, "rb") as f:
        return _trap_visuals_state(f)


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
# codes, translated to direct Start.dol patches): normally hidden
# behind a retail build-check, this re-enables a real developer debug menu
# (MUTEKI/invincible, COLCHECK, PARTICLE, CHARA INFO, and more) plus a second-
# controller input path for it. All 9 sites are in the retail
# NTSC-US Start.dol (offsets are DOL-relative, i.e. added to gciso.dol_span()'s
# own offset, not raw ISO offsets - matches this file's other DOL patches).
# Once applied: plug in a second GameCube controller (Port 2). On Port 2,
# A opens the debug menu, B closes it, D-pad Up/Down moves the selection and
# A/B toggles the highlighted entry. This is a QA test-flag menu (invincibility,
# collision, particle/shadow toggles, etc.) and is not known to include a
# working free-roam camera. Treat it as an experimental bonus, not a core
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
    above) via 9 Start.dol patches. Returns True once all sites are in
    the patched state (freshly applied or already there). Raises if any site's
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

    All-magicite sets are element/magicite spawns, sets of only food / Phoenix
    Down / raw '*Seed' materials are gathering nodes, and everything else (artifacts, recipes/scrolls, or crafting materials like
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
            # Game8's matcher can map several sets to one generic chest, so keep only
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
# the chest editor: each Game8 chest is numbered once per dungeon ("Chest N"). Every
# other set is classified as
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
        data["_trap_visuals"] = trap_visuals_status(iso)
    except Exception:
        pass
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
    # true = pick the random parts (unlisted world zones, the stage-key chain)
    # with progression logic, false = apply as written (e.g. Archipelago)
    data["_progression_logic"] = False
    # keep the magicite needed for Holy (Lich/Zombie Dragon) and Tida's Fire
    # vanilla, false = no protection (the JSON's chest data is never changed either way)
    data["_protect_required_stones"] = True
    # EXPERIMENTAL boss shuffle. `_randomize_bosses: true` shuffles bosses on
    # patch (Goblin King and Lich stay home). `_bosses` places them explicitly
    # (dungeon -> boss, any boss in any dungeon) and wins over the shuffle for
    # every dungeon it lists. Needs a copy whose bosses haven't been moved yet.
    # EXPERIMENTAL world-map loading-zone shuffle. `_world_zones` maps each
    # world-map node (named by its vanilla dungeon) to the dungeon it leads to.
    # An entry naming the node's own dungeon means "no preference".
    data["_randomize_world_zones"] = False
    try:
        import worldzones
        zs = worldzones.status(iso)
        data["_world_zones"] = {worldzones._name(n): worldzones._name(d) for n, d in zs.items() if d}
        data["_world_zone_choices"] = [v[0] for v in worldzones.DUNGEONS.values()]
        # true = each stop's world-map building shows the dungeon it leads to
        data["_world_zone_icons"] = worldzones.icon_status(iso) == zs
    except Exception:
        pass  # older/unrecognized world.cft - leave the keys out rather than fail
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
            # alone. See "Boss Reward Sets (GameCube guide).md" for which entry indices
            # (0-7) a given cycle/score-tier can actually reach.
            data["_bonus_pools"] = {
                script: {str(ei): [items.label(v) for v in vals]
                        for ei, vals in entries.items()}
                for script, entries in pools.items()
            }
    except Exception:
        pass  # older/unrecognized newbattle.cfd - leave the key out rather than fail
    for script, friendly, discs in dungeons_in_iso(iso):
        dd = {"_name": friendly}
        # dungeon-wide numbering (each Game8 chest once). Every other set is
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
# of this feature. This section is the key-creation/placement half and works
# independently of the gate checks.
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
# (vanilla behavior) - so
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
# Stage ids, forward func indices and call-site bytes are for the
# retail world.cft. The stage id is the stage script's STR index, pushed as the call's first
# argument. Mount Kilanda is NOT here: it's entered through 4-argument
# MJ_SWING calls, locked separately below (_KILANDA_*).
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
    ("desert", 0x4E4B5, 173, 595),
]

# World-map stops with an element menu (picking the chalice element there,
# or entering). In the game the menu only appears once the stage has been
# cleared. With stage keys it is always offered and needs no key, so the
# element a stream asks for can always be picked up on the near side of it,
# whatever keys the player has. Entering still needs the key: the menu's
# "enter" calls go to the dispatcher instead of straight to
# MJ_SWING_PADCHECK. Both menus pick the stop's elements from the stop
# itself (G61), so they belong to the world-map stop, not the dungeon.
_ENTER_FUNC = 593                         # MJ_SWING_PADCHECK
_ELEMENT_MENU_FUNCS = (594, 595)          # MJ_SWING_ATTRIB_2 (two elements), MJ_SWING_ATTRIB_1 (one)
_STAGE_LOCK_DISPATCHER = 598              # encountKaido
_RIVER_STAGE_ID = 0x89                    # River Belle Path, never locked
_ELEMENT_MENU_EDITS = {
    # function: (code offset of the "stage cleared?" jz, its vanilla target, "enter" calls)
    "MJ_SWING_ATTRIB_1": (0x107, 0x1d9, (0x1c3, 0x201)),
    "MJ_SWING_ATTRIB_2": (0x137, 0x23d, (0x227, 0x265)),
}

# Earlier versions listed ("lava", 0x4E33A, 172, 593) above, but STR 172 is
# thief_0: that call is a LEUDA stop, so Leuda ended up locked behind the
# Kilanda Key and Kilanda stayed open. patch_stage_key_locks() puts this call
# back to vanilla if an ISO still has it redirected.
_STAGE_LOCK_LEUDA_SITE = 0x4E33A
_STAGE_LOCK_LEUDA_FORWARD = 593                               # MJ_SWING_PADCHECK

# Mount Kilanda (lava_0, STR 174/181/184/187) is entered through four
# 4-argument MJ_SWING calls, which the 8-argument encountKaido dispatcher
# can't take. They get their own dispatcher: world.cft's copy of the library
# function dropItem_fromNpc (never called on the world map, no class method,
# not looked up by the engine) is rewritten to take MJ_SWING's 4 arguments,
# check the Kilanda Key, and forward them. Same-size edit.
_KILANDA_SITES = (0x4E931, 0x4F1E7, 0x4F675, 0x4FA83)          # CALL MJ_SWING
_KILANDA_FORWARD = 592                                         # MJ_SWING (4 args)
_KILANDA_DISPATCHER_FUNC = 426                                 # dropItem_fromNpc
_KILANDA_DISPATCHER_NAME = "dropItem_fromNpc"
_KILANDA_DISPATCHER_CODE_LEN = 388

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
    forward_func_idx if owned, else silently deny. An item_id of None
    forwards without a check (River Belle Path, which is never locked). Falls
    through to a silent deny if local[0] doesn't match any case (should never
    happen - every call that reaches here pushes a stage id covered by
    exactly one case)."""
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

        jz_deny = None
        if item_id is not None:
            prog += op5(0x03, 0)                               # PUSHI 0   caravanIndex
            prog += op5(0x03, 2)                               # PUSHI 2   flags
            prog += op5(0x03, item_id)                         # PUSHI itemId
            prog += op5(0x0a, (0xFFFF << 16) | check_func_idx)  # CALL checkCaravanItem
            prog += op5(0x03, 2)
            prog += op1(0x2c)
            jz_deny = len(prog)
            prog += op5(0x08, 0)                               # JZ <deny> (patched below)
        for i in range(8):
            prog += op5(0x00, (i << 8) | 1)                    # GET local[i]
        prog += op5(0x0a, (0xFFFF << 16) | forward_func_idx)    # CALL <this dungeon's MJ_SWING variant>
        prog += op1(0x3c)                                      # RET
        if jz_deny is not None:
            deny_off = len(prog)
            prog += op1(0x3f)                                  # PUSH0
            prog += op1(0x3c)                                  # RET
            prog[jz_deny:jz_deny + 5] = op5(0x08, deny_off)

        next_case_off = len(prog)
        prog[jz_next:jz_next + 5] = op5(0x08, next_case_off)
    prog += op1(0x3f)   # default (should never be reached): silent deny
    prog += op1(0x3c)
    return bytes(prog)


def _kilanda_dispatcher_body(item_id, check_func_idx=234, forward_func_idx=_KILANDA_FORWARD):
    """4-argument dispatcher: forward MJ_SWING's 4 arguments if the caravan
    owns `item_id`, otherwise do nothing (same check as the main dispatcher)."""
    def op5(b, arg):
        return bytes([b]) + struct.pack(">I", arg & 0xffffffff)
    prog = bytearray()
    prog += op5(0x03, 0) + op5(0x03, 2) + op5(0x03, item_id)     # caravanIndex, flags, itemId
    prog += op5(0x0a, (0xFFFF << 16) | check_func_idx)            # CALL checkCaravanItem
    prog += op5(0x03, 2) + bytes([0x2c])                         # == 2 (owned)
    jz = len(prog)
    prog += op5(0x08, 0)                                         # JZ deny
    for i in range(4):
        prog += op5(0x00, (i << 8) | 1)                          # GET local[i]
    prog += op5(0x0a, (0xFFFF << 16) | forward_func_idx)          # CALL MJ_SWING
    prog += bytes([0x3c])                                        # RET
    deny = len(prog)
    prog += bytes([0x3f, 0x3c])                                  # PUSH0, RET
    prog[jz:jz + 5] = op5(0x08, deny)
    return bytes(prog)


def _patch_kilanda_and_leuda(iso, apply=True):
    """Lock Mount Kilanda's four entrances behind its key, and make sure the
    Leuda stop is not locked. Idempotent. Returns a short status string."""
    import cftpatch
    tmp = os.path.join(tempfile.gettempdir(), "stagelock_kilanda_world.cft")
    size = _extract(iso, WORLD_CFT_DISC, tmp)
    s = cftpatch.Script(tmp)
    if s.names[_KILANDA_DISPATCHER_FUNC] != _KILANDA_DISPATCHER_NAME:
        raise ValueError("world.cft function table isn't the expected one - wrong game version?")
    key = dict((sc, kid) for sc, kid, _ in STAGE_KEYS)["lava"]
    body = _kilanda_dispatcher_body(key)
    blk = s.funcs[_KILANDA_DISPATCHER_FUNC]
    code = blk.find(b"CODE")[0]
    already = code.payload[:len(body)] == body
    if not already and len(code.payload) != _KILANDA_DISPATCHER_CODE_LEN:
        raise ValueError(f"{_KILANDA_DISPATCHER_NAME}: unexpected code size {len(code.payload)}")
    if not already:
        code.payload = body + b"\x3c" * (len(code.payload) - len(body))   # rest unreachable
        info = blk.find(b"INFO")[0]
        info.payload = struct.pack(">I", 4) + info.payload[4:]          # argCount = 4
        val = blk.find(b"VAL ")[0]
        val.a0 = max(val.a0, 4)
    data = bytearray(s.to_bytes())
    if len(data) != size:
        raise ValueError("world.cft size changed - refusing to write")

    notes = []
    orig = bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | _KILANDA_FORWARD)
    patched = bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | _KILANDA_DISPATCHER_FUNC)
    for off in _KILANDA_SITES:
        cur = bytes(data[off:off + 5])
        if cur == orig:
            data[off:off + 5] = patched
        elif cur != patched:
            raise ValueError(f"Kilanda entrance 0x{off:x}: unexpected bytes {cur.hex()}")
    leuda_orig = bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | _STAGE_LOCK_LEUDA_FORWARD)
    leuda_wrong = bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | 598)
    cur = bytes(data[_STAGE_LOCK_LEUDA_SITE:_STAGE_LOCK_LEUDA_SITE + 5])
    if cur == leuda_wrong:
        data[_STAGE_LOCK_LEUDA_SITE:_STAGE_LOCK_LEUDA_SITE + 5] = leuda_orig
        notes.append("Leuda stop unlocked again")
    elif cur != leuda_orig:
        raise ValueError(f"Leuda stop 0x{_STAGE_LOCK_LEUDA_SITE:x}: unexpected bytes {cur.hex()}")
    if apply:
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, WORLD_CFT_DISC)[0]
            f.seek(off)
            f.write(data)
    notes.insert(0, "Mount Kilanda locked (4 entrances)")
    return "; ".join(notes)


# Mount Kilanda by boat. Port Tipa (port_1), the Jegon River ferry (port_0)
# and Leuda (thief_0) sail straight to Mount Kilanda. Without the key the
# world-map lock above turns the caravan away at the dock and the boat sails
# back and forth, so the boatman refuses the trip instead. In each boatman
# talk (mainEventClient), right after the destination and fare are set, the
# script checks whether the player said no (`this.m23 != -1`, at Leuda
# `this.m26 == -1`). That check now reads its value through a gate that says
# "no" (-1) for a Kilanda trip without the key, so the boatman just stops
# talking: no fare, no trip. The gate is the town's unused library helper
# dropItem_fromNpc4. Kilanda is destination 8 (this.m27) at both ports. At
# Leuda it is choice 2, or choice 0 once the river is low (this.m14, with
# eventWork[1] == 5).
_KILANDA_BOAT_FUNC = 427
_KILANDA_BOAT_FUNC_NAME = "dropItem_fromNpc4"
_KILANDA_BOAT_FUNC_LEN = 162
_KILANDA_BOATS = {
    # town script: (offset of the check's "load this.mN" in mainEventClient, N)
    "dvd/cft/port_1.cft": (0x23A3, 23),
    "dvd/cft/port_0.cft": (0x19D3, 23),
    "dvd/cft/thief_0.cft": (0x0FCE, 26),
}


def _kilanda_boat_gate(leuda, item_id, member, check_func_idx=234):
    """Gate body (no arguments): this.m<member>, or -1 when the trip being
    bought goes to Mount Kilanda and the caravan doesn't own `item_id`."""
    def op5(b, arg):
        return bytes([b]) + struct.pack(">I", arg & 0xffffffff)

    def load_member(n):
        return op5(0x00, (n << 8) | 0x19)                        # GET this.mN

    prog = bytearray()
    jumps_pass, jumps_check = [], []
    if leuda:
        prog += load_member(14) + op5(0x03, 2) + bytes([0x2c])   # choice == 2
        jumps_check.append(len(prog)); prog += op5(0x09, 0)      # JNZ check
        prog += load_member(14) + op5(0x03, 0) + bytes([0x2c])   # choice == 0
        jumps_pass.append(len(prog)); prog += op5(0x08, 0)       # JZ pass
        prog += op5(0x03, 1) + op5(0x00, 0xFFFE390A)             # eventWork[1]
        prog += op5(0x03, 5) + bytes([0x2c])                     # == 5 (river low)
        jumps_pass.append(len(prog)); prog += op5(0x08, 0)       # JZ pass
    else:
        prog += load_member(27) + op5(0x03, 8) + bytes([0x2c])   # destination == 8
        jumps_pass.append(len(prog)); prog += op5(0x08, 0)       # JZ pass
    check = len(prog)
    prog += op5(0x03, 0) + op5(0x03, 2) + op5(0x03, item_id)     # caravanIndex, flags, itemId
    prog += op5(0x0a, (0xFFFF << 16) | check_func_idx)            # CALL checkCaravanItem
    prog += op5(0x03, 2) + bytes([0x2c])                         # == 2 (owned)
    jz_deny = len(prog); prog += op5(0x08, 0)                    # JZ deny
    jumps_pass.append(len(prog)); prog += op5(0x07, 0)           # JMP pass
    deny = len(prog)
    prog += op5(0x03, -1) + bytes([0x3c])                        # return -1 ("no")
    passed = len(prog)
    prog += load_member(member) + bytes([0x3c])                  # return the player's answer
    for at in jumps_check:
        prog[at:at + 5] = op5(0x09, check)
    for at in jumps_pass:
        prog[at:at + 5] = op5(prog[at], passed)
    prog[jz_deny:jz_deny + 5] = op5(0x08, deny)
    return bytes(prog)


def _patch_kilanda_boats(iso, apply=True):
    """Make the boatmen of Port Tipa, the Jegon River ferry and Leuda refuse
    a trip to Mount Kilanda until its key is owned. Idempotent."""
    import cftpatch
    key = dict((sc, kid) for sc, kid, _ in STAGE_KEYS)["lava"]
    call = bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | _KILANDA_BOAT_FUNC)
    for disc, (site, member) in _KILANDA_BOATS.items():
        tmp = os.path.join(tempfile.gettempdir(), "kilanda_boat_" + os.path.basename(disc))
        size = _extract(iso, disc, tmp)
        s = cftpatch.Script(tmp)
        if s.names[_KILANDA_BOAT_FUNC] != _KILANDA_BOAT_FUNC_NAME:
            raise ValueError(f"{disc}: function table isn't the expected one - wrong game version?")
        body = _kilanda_boat_gate(disc.endswith("thief_0.cft"), key, member)
        gate = s.code(_KILANDA_BOAT_FUNC_NAME)
        if gate[:len(body)] != body:
            if len(gate) != _KILANDA_BOAT_FUNC_LEN:
                raise ValueError(f"{disc}: {_KILANDA_BOAT_FUNC_NAME} has unexpected size {len(gate)}")
            s.set_code(_KILANDA_BOAT_FUNC_NAME, body + b"\x3c" * (len(gate) - len(body)))
            blk = s.funcs[_KILANDA_BOAT_FUNC]
            info = blk.find(b"INFO")[0]
            info.payload = struct.pack(">I", 0) + info.payload[4:]          # argCount = 0
        code = bytearray(s.code("mainEventClient"))
        orig = bytes([0x00]) + struct.pack(">I", (member << 8) | 0x19)    # GET this.mN
        cur = bytes(code[site:site + 5])
        if cur == orig:
            code[site:site + 5] = call
            s.set_code("mainEventClient", code)
        elif cur != call:
            raise ValueError(f"{disc}: unexpected bytes at boatman check 0x{site:x}: {cur.hex()}")
        data = s.to_bytes()
        if len(data) != size:
            raise ValueError(f"{disc}: size changed - refusing to write")
        if apply:
            with open(iso, "r+b") as f:
                _, files = gciso.parse_fst(f)
                _, off, _ = gciso.find_file(files, disc)[0]
                f.seek(off)
                f.write(data)
    return "boats to Mount Kilanda need its key"


def patch_stage_key_locks(iso, apply=True, sites=None):
    """Apply the in-game locks for every dungeon in `sites` (default: all 13
    in _STAGE_LOCK_SITES). Redirects each dungeon's own mainBasha entrance
    call to the shared encountKaido dispatcher, rewrites encountKaido's body
    to the switch built by _stage_lock_dispatcher_body(), and applies the one
    Start.dol fix needed for the check to see permanent artifacts at all.
    Same-size edits throughout - no ISO resizing needed. Returns True once
    present (freshly applied or already there). Raises if any site's bytes
    are neither vanilla nor already-patched (wrong game version, a
    conflicting prior edit, or an already-modified `mainBasha`)."""
    import cftpatch
    sites = sites if sites is not None else _STAGE_LOCK_SITES
    key_by_dungeon = {s: kid for s, kid, _ in STAGE_KEYS}

    def call(func_idx):
        return bytes([0x0a]) + struct.pack(">I", (0xFFFF << 16) | func_idx)

    # A node whose call opens the element menu (MJ_SWING_ATTRIB_1/2) keeps
    # that call, so the element can be picked without the key. Its key is
    # checked when the menu's "enter" goes through the dispatcher, which then
    # forwards to MJ_SWING_PADCHECK. Other nodes have their call redirected
    # to the dispatcher, which forwards to the node's own MJ_SWING variant.
    cases, site_calls = [], []
    for script, call_off, stage_id, forward_idx in sites:
        if forward_idx in _ELEMENT_MENU_FUNCS:
            cases.append((stage_id, key_by_dungeon[script], _ENTER_FUNC))
            site_calls.append((script, call_off, call(forward_idx), call(_STAGE_LOCK_DISPATCHER)))
        else:
            cases.append((stage_id, key_by_dungeon[script], forward_idx))
            site_calls.append((script, call_off, call(_STAGE_LOCK_DISPATCHER), call(forward_idx)))
    cases.append((_RIVER_STAGE_ID, None, _ENTER_FUNC))
    body = _stage_lock_dispatcher_body(cases)
    if len(body) > 18000:
        raise ValueError(f"dispatcher body ({len(body)}B) exceeds encountKaido's "
                          f"18000B budget - split across more than one repurposed function")

    tmp = os.path.join(tempfile.gettempdir(), "stagelock_world.cft")
    size = _extract(iso, WORLD_CFT_DISC, tmp)
    data = bytearray(open(tmp, "rb").read())

    # each edit: (file offset, bytes it must end up as, bytes it may hold now)
    edits = [(_STAGE_LOCK_ENCOUNTER_CALL_OFF, _STAGE_LOCK_ENCOUNTER_CALL_PATCHED,
              {_STAGE_LOCK_ENCOUNTER_CALL_ORIG}, "WM_MoveEnd's call to encountKaido")]
    for script, call_off, want, other in site_calls:
        edits.append((call_off, want, {other}, f"{script} call site"))
    for off, want, allowed, what in edits:
        cur = bytes(data[off:off + len(want)])
        if cur != want and cur not in allowed:
            raise ValueError(f"{what}: unexpected bytes at 0x{off:x}: {cur.hex()} (expected "
                              f"{want.hex()} - wrong game version, or a conflicting prior edit?)")
        data[off:off + len(want)] = want
    data[_STAGE_LOCK_ENCOUNTKAIDO_INFO_OFF:_STAGE_LOCK_ENCOUNTKAIDO_INFO_OFF + 4] = struct.pack(">I", 8)
    data[_STAGE_LOCK_ENCOUNTKAIDO_VAL_ARG0_OFF:_STAGE_LOCK_ENCOUNTKAIDO_VAL_ARG0_OFF + 4] = struct.pack(">I", 8)
    data[_STAGE_LOCK_ENCOUNTKAIDO_CODE_OFF:_STAGE_LOCK_ENCOUNTKAIDO_CODE_OFF + len(body)] = body
    open(tmp, "wb").write(data)

    # The element menus: always offered (not only once the stage is cleared),
    # and "enter" goes through the dispatcher's key check.
    s = cftpatch.Script(tmp)
    for name, (cleared_jz, vanilla_target, enter_calls) in _ELEMENT_MENU_EDITS.items():
        if s.names.index(name) not in _ELEMENT_MENU_FUNCS:
            raise ValueError(f"world.cft function table isn't the expected one ({name})")
        code = bytearray(s.code(name))
        cur = bytes(code[cleared_jz:cleared_jz + 5])
        jz_vanilla = bytes([0x08]) + struct.pack(">I", vanilla_target)
        jz_always = bytes([0x08]) + struct.pack(">I", cleared_jz + 5)    # jumps to the next line either way
        if cur not in (jz_vanilla, jz_always):
            raise ValueError(f"{name}: unexpected bytes at 0x{cleared_jz:x}: {cur.hex()}")
        code[cleared_jz:cleared_jz + 5] = jz_always
        for at in enter_calls:
            cur = bytes(code[at:at + 5])
            if cur not in (call(_ENTER_FUNC), call(_STAGE_LOCK_DISPATCHER)):
                raise ValueError(f"{name}: unexpected bytes at 0x{at:x}: {cur.hex()}")
            code[at:at + 5] = call(_STAGE_LOCK_DISPATCHER)
        s.set_code(name, code)
    data = s.to_bytes()
    if len(data) != size:
        raise ValueError("world.cft size changed - refusing to write")
    if apply:
        with open(iso, "r+b") as f:
            _, files = gciso.parse_fst(f)
            _, off, _ = gciso.find_file(files, WORLD_CFT_DISC)[0]
            f.seek(off)
            if f.read(size) != data:
                f.seek(off)
                f.write(data)

    # Mount Kilanda's 4-argument entrances (and the Leuda stop repair), and
    # the boatmen who would sail there
    _patch_kilanda_and_leuda(iso, apply=apply)
    _patch_kilanda_boats(iso, apply=apply)

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
# spare room for set_item_description()'s default nearby auto-search, so they
# use an explicit farther donor slot, per the description recipe in
# Documentation/Adding Custom Items and Artifacts.md.
STAGE_KEY_DESC_DONOR = {
    "lava": 0xFB,
    "cave": 0xFC,   # distinct from lava's 0xFB - one shared donor lacks room for both
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
                     holy_dungeons=STONE_DUNGEONS, avoid_offsets=None):
    """Place each dungeon's required key into `chests_per_dungeon` chests
    (chosen at random, all 7 cycle-slots of each so the key doesn't depend on
    which year the player finds it in) of the PREVIOUS dungeon in `chain` -
    only ever the dungeon the player must already be ABLE to enter, never the
    gated dungeon itself. Chests only, never monster/spawn drop tables. In a
    `holy_dungeons` dungeon (see STONE_DUNGEONS) the magicite sets are never
    used, so a key can't overwrite the stones that dungeon needs.
    `avoid_offsets` ({disc: set of file offsets}) marks chests a patch JSON
    set explicitly, and sets touching those offsets are never used either.
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
        avoid = (avoid_offsets or {}).get(disc, set())
        candidates = [si for si, s in enumerate(sets)
                      if not (source_script in holy_dungeons and _is_magicite_set(s))
                      and not any(off in avoid for off, _ in s)]
        if not candidates:
            print(f"WARNING: every chest in {disc!r} is set by the JSON - "
                  f"{chain[i]!r}'s key could not be placed")
            continue
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
    # baked in automatically, and already-patched ISOs are left untouched.
    try:
        import customitem
        if customitem.ensure_ap_item(iso):
            print("Installed AP Item into ISO (definition, name, icon and logo model).")
    except Exception as e:
        print(f"note: could not auto-install AP Item ({e}); JSON placing it may fail")
    try:
        import titlelogo
        if titlelogo.install(iso):
            print("Installed the Archipelago title logo, disc name and banner.")
    except Exception as e:
        print(f"Note: could not install the title logo ({e}).")
    with open(json_path, encoding="utf-8") as f:
        spec = json.load(f)
    # Moved dungeons and shuffled Miasma Streams both rely on Goblin Wall's spot
    # being open in Year 1, so either one turns that patch on.
    import worldzones
    zones_moved = spec.get("_randomize_world_zones") or worldzones.normalize(spec.get("_world_zones") or {})
    if (zones_moved or spec.get("_randomize_miasma_elements")) and not spec.get("_goblin_wall_always_visible"):
        spec["_goblin_wall_always_visible"] = True
        print("Goblin Wall in Year 1 turned on (needed by the loading-zone / Miasma Stream shuffle).")
    boss_plan = _boss_plan_from_spec(spec)
    # `_progression_logic` (default false): an imported JSON is applied as
    # written - Archipelago's own logic decides what's reachable. Only when a
    # JSON opts in does the randomizer pick its random parts (unlisted zones,
    # the stage-key chain) with progression logic, after the Miasma Stream
    # step so it sees the final gate elements. Listed zones are never changed.
    logic = bool(spec.get("_progression_logic", False))
    logic_chain = None
    zone_plan = None if logic else _zone_plan_from_spec(spec)
    if zone_plan is not None:
        apply_world_zones(iso, zone_plan, icons=spec.get("_world_zone_icons", True))
        # report only - the JSON's layout is kept exactly as written
        try:
            import progression
            ok, report = progression.check(zone_plan, None, progression_gates(iso),
                                           bool(spec.get("_goblin_wall_always_visible")))
            if not ok:
                print("WARNING: by the randomizer's own progression logic this layout may "
                      "not be completable (kept as written): " + report[-1])
        except Exception:
            pass
    # `_protect_required_stones: false` turns off the Holy/Fire magicite
    # protection (stage keys may then use magicite sets, and no warning).
    # It never changes the JSON's own chest data, which is written as given.
    protect = spec.get("_protect_required_stones", True)
    holy = stone_dungeons_for(boss_plan) if protect else {}
    if spec.get("_mog_never_tired"):
        try:
            patch_mog_never_tired(iso, apply=True)
            print("Applied Mog-never-tired Start.dol patch.")
        except Exception as e:
            print(f"note: could not apply Mog-never-tired patch ({e})")
    if spec.get("_trap_visuals"):
        try:
            patch_trap_visuals(iso, apply=True)
            print("Applied trap-visuals Start.dol patch.")
        except Exception as e:
            print(f"note: could not apply trap-visuals patch ({e})")
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
    if logic:
        zone_plan, logic_chain = _logic_plan_from_spec(iso, spec)
        if zone_plan is not None:
            apply_world_zones(iso, zone_plan, icons=spec.get("_world_zone_icons", True))
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
    customised = {}        # disc -> file offsets the JSON actually changed
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
                        if ids[k % len(ids)] != s[ci][1]:
                            customised.setdefault(disc, set()).add(s[ci][0])
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
    # Stage keys go in AFTER the JSON's chest data, and only into chests the
    # JSON left unchanged, so neither overwrites the other.
    if spec.get("_stage_key_locks"):
        try:
            create_stage_key_items(iso)
            chain = logic_chain or randomize_stage_key_chain(random.Random())
            reqs = stage_key_requirements(chain)
            placements = place_stage_keys(iso, chain, random.Random(), holy_dungeons=holy,
                                          avoid_offsets=customised)
            patch_stage_key_locks(iso, apply=True, sites=stage_lock_sites_for(zone_plan))
            print("Stage-key artifacts: created all 14, placed via a randomized "
                  f"solvable chain starting at {STAGE_KEY_ALWAYS_OPEN!r}: {chain}")
            print("  All 13 gated dungeons now check for their key on entry.")
        except Exception as e:
            print(f"note: could not apply stage-key locks ({e})")
    if boss_plan is not None:
        apply_bosses(iso, boss_plan)
    for problem in check_stone_access(iso, holy):
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


def _zone_plan_from_spec(spec):
    """World-zone plan from a patch JSON, or None to leave the map alone.
    `_world_zones` entries that name a node's own dungeon mean "no
    preference". With `_randomize_world_zones: true` the rest are shuffled."""
    import worldzones
    fixed = worldzones.normalize(spec.get("_world_zones") or {})
    if spec.get("_randomize_world_zones"):
        return worldzones.random_plan(random.Random(), fixed=fixed)
    return worldzones.complete_plan(fixed) if fixed else None


def progression_gates(iso):
    """The ISO's Miasma Stream table (rows for year % 4 == 1, 2, 3, 0), or
    vanilla's if it can't be read."""
    import progression
    try:
        return miasma_elements_status(iso)
    except Exception:
        return progression.vanilla_gates()


def logic_plan(iso, rng, shuffle_zones, keys, goblin_year1, fixed_zones=None):
    """(zone plan, key chain, report) chosen with progression logic for this
    ISO's gate elements. Raises if nothing passes."""
    import progression
    plan, chain = progression.generate(rng, progression_gates(iso), goblin_year1,
                                       shuffle_zones=shuffle_zones, keys=keys,
                                       fixed_zones=fixed_zones)
    report = progression.check(plan, chain, progression_gates(iso), goblin_year1)[1]
    return plan, chain, report


def _logic_plan_from_spec(iso, spec):
    """(zone plan or None, key chain or None) for a JSON with
    `_progression_logic: true`. Falls back to plain random if nothing passes."""
    import worldzones
    fixed = worldzones.normalize(spec.get("_world_zones") or {})
    shuffle = bool(spec.get("_randomize_world_zones"))
    keys = bool(spec.get("_stage_key_locks"))
    if not (shuffle or keys):
        return _zone_plan_from_spec(spec), None
    try:
        plan, chain, report = logic_plan(iso, random.Random(), shuffle, keys,
                                         bool(spec.get("_goblin_wall_always_visible")), fixed)
    except Exception as e:
        print(f"WARNING: progression logic found no valid layout ({e}); using plain random")
        return _zone_plan_from_spec(spec), None
    print("Progression logic: " + "; ".join(report))
    return (plan if (shuffle or fixed) else None), chain


def apply_world_zones(iso, plan, spoiler=None, icons=False):
    """Apply a world-zone plan (EXPERIMENTAL) and print what moved. With
    `icons`, each world-map stop's building also shows its new dungeon."""
    import worldzones
    try:
        log = worldzones.apply_plan(iso, plan)
    except Exception as e:
        print(f"note: could not shuffle world-map loading zones ({e})")
        return False
    if icons:
        try:
            worldzones.apply_icons(iso, plan, log)
        except Exception as e:
            print(f"note: could not update world-map icons ({e})")
    print("World-map loading zones (EXPERIMENTAL): " + "; ".join(log))
    if spoiler:
        with open(spoiler, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(worldzones.plan_text(worldzones.complete_plan(plan))) + "\n")
    return True


def append_zone_spoiler(spoiler, plan):
    """Add the world-zone layout to a spoiler file."""
    import worldzones
    with open(spoiler, "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(worldzones.plan_text(worldzones.complete_plan(plan))) + "\n")


def stage_lock_sites_for(zone_plan):
    """Stage-key lock sites that follow a world-zone plan (None = default)."""
    if zone_plan is None:
        return None
    import worldzones
    return worldzones.stage_lock_sites(zone_plan, _STAGE_LOCK_SITES)


def stone_dungeons_for(boss_plan):
    """{script: (need, reason)} for every dungeon whose magicite must stay
    vanilla: wherever Lich and Zombie Dragon are (their home dungeons when
    bosses aren't moved), plus the fixed FIRE_DUNGEONS."""
    if boss_plan is None:
        return STONE_DUNGEONS
    import bossshuffle
    out = {k: ("fire", v) for k, v in FIRE_DUNGEONS.items()}
    for script, boss in bossshuffle.holy_dungeons(boss_plan).items():
        out[script] = ("holy", boss)     # a Holy boss's needs cover Fire too
    return out


holy_dungeons_for = stone_dungeons_for      # older name


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


# Version of the Archipelago world (worlds/ffcc VERSION) this randomizer is made
# for. Seeds record the version that generated them. The AP patch warns when
# they differ, since options and item placement rules change between versions.
AP_WORLD_VERSION = (0, 2, 0)


def load_ffcc(path):
    """Read a seed's .ffcc placement data, from the .ffcc file itself or from
    the .zip it comes in. Raises ValueError if it can't be read."""
    import json, zipfile as _zipfile
    try:
        with _zipfile.ZipFile(path) as zf:
            name = next((n for n in zf.namelist() if n.endswith(".ffcc")), None)
            if name is None:
                raise ValueError(f"No .ffcc entry found inside {path}")
            return json.loads(zf.read(name))
    except _zipfile.BadZipFile:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as e:
            raise ValueError(f"Could not read {path} as ZIP or JSON: {e}")
    except OSError as e:
        raise ValueError(f"Could not open {path}: {e}")


def _version_text(v):
    return ".".join(str(x) for x in v)


def ap_world_version_problem(placement_json):
    """None if the seed was made with the AP world version this randomizer is
    for, else a message saying what to update."""
    seed = tuple(placement_json.get("version") or ())
    want = AP_WORLD_VERSION
    if seed == want:
        return None
    if not seed or seed < want:
        return (f"This seed was made with an older FFCC apworld ({_version_text(seed) or 'unknown'}); "
                f"this randomizer is for apworld {_version_text(want)}. Install the newest "
                f"apworld and generate the seed again, or some fixes won't apply.")
    return (f"This seed was made with a newer FFCC apworld ({_version_text(seed)}) than this "
            f"randomizer supports ({_version_text(want)}). Download the newest randomizer.")


def cmd_hybrid_patch(iso, ref_iso, ffcc_file):
    """Hybrid AP patch: own-player chests get the real item, others get AP Item.

    Reads the .ffcc placement file produced by Archipelago generation to decide
    which item belongs in each chest.  For this player's own items the game
    engine gives the item naturally on chest open, so the AP client skips the
    memory-write for those locations (preventing a double-give).

    Usage:
        py randomizer.py ap-hybrid "Hacked Rom.iso" --ref "Vanilla.iso" --ffcc "seed.ffcc"
    """
    AP_ITEM_ID = 0x162

    # ── 1. Read placement from .ffcc file ──────────────────────────────────────
    # Accepts either a raw .ffcc JSON file (the one sitting in the output folder)
    # or the .zip container that wraps it — both contain the same placement data.
    try:
        placement_json = load_ffcc(ffcc_file)
    except ValueError as e:
        sys.exit(str(e))
    problem = ap_world_version_problem(placement_json)
    if problem:
        print("WARNING: " + problem)

    self_player = placement_json.get("player", "")
    raw_locs    = placement_json.get("locations", {})
    print(f"Loaded placement for player '{self_player}' — {len(raw_locs)} location(s).")

    # Stage keys are artifacts the patcher creates below, so they count as real items.
    stage_key_ids = {kid for _, kid, _ in STAGE_KEYS}

    # Build lookup: (dungeon, cycle, chest_no) -> item_id to write in binary.
    # Chest numbers are the game's own order (chestflags.py), the same numbering
    # the AP locations and the client use. Old .ffcc files used "game8_chest".
    chest_items = {}  # (dungeon:str, cycle:int, chest:int) -> int
    real_count  = 0
    import chestcolors
    gold = set()      # (dungeon, cycle, chest) whose item gets a gold chest
    for loc_name, loc_data in raw_locs.items():
        dungeon  = loc_data.get("dungeon", "")
        cycle    = int(loc_data.get("cycle", 1))
        chest_no = int(loc_data.get("chest", loc_data.get("game8_chest", 0)))
        is_self  = loc_data.get("player") == self_player
        if loc_data.get("class") in chestcolors.GOLD_CLASSES:
            gold.add((dungeon, cycle, chest_no))

        if is_self:
            # Use the item_id written directly into the .ffcc file — no name
            # resolution needed and guaranteed to match the in-game ID exactly.
            raw_id = loc_data.get("item_id")
            item_id = int(raw_id) if raw_id is not None else None
            # "in_chest" (newer AP worlds) says whether the item goes in the chest
            # itself. Artifacts don't, since the game only keeps the one artifact
            # picked as the dungeon reward. Older files: every own item with an ID.
            in_chest = loc_data.get("in_chest",
                                    item_id is not None and (is_item(item_id) or item_id in stage_key_ids))
            if in_chest and item_id is not None:
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
            print("Installed AP Item into ISO (definition, name, icon and logo model).")
    except Exception as e:
        print(f"Note: could not auto-install AP Item ({e}); 0x162 must already be present.")
    try:
        import titlelogo
        # the disc name and banner say whose seed this ISO is for
        if titlelogo.install(iso, player=self_player, seed=placement_json.get("seed")):
            print(f"Installed the Archipelago title logo; disc named for {self_player}, "
                  f"seed {placement_json.get('seed')}.")
    except Exception as e:
        print(f"Note: could not install the title logo ({e}).")

    # ── Options from the AP world ───────────────────────────────────────────────
    settings = placement_json.get("settings", {})
    tweaks = [
        ("mog_never_tired",      patch_mog_never_tired,            "Mog never tired"),
        ("skip_intro_cutscene",  patch_skip_intro_cutscene,        "Skip intro cutscene"),
        ("skip_mio_questions",   patch_skip_mio_questions,         "Skip Mio's questions"),
        ("goblin_wall_year_one", patch_goblin_wall_always_visible, "Goblin Wall in Year 1"),
        ("trap_visuals",         patch_trap_visuals,               "Trap visuals"),
        ("items_dropped_at_your_feet", patch_item_drops,           "Items dropped at your feet"),
        ("magicite_needs_ring",  patch_magicite_needs_ring,        "Magicite needs its ring"),
        ("best_bonus_tier",      patch_best_bonus_tier,            "Always best bonus tier"),
        ("keep_picked_up_artifacts", patch_keep_artifacts,         "Picked-up artifacts are kept"),
    ]
    if settings.get("randomize_miasma_streams") or settings.get("shuffle_loading_zones"):
        settings = dict(settings, goblin_wall_year_one=True)   # the logic assumes it
    for key, patch, label in tweaks:
        if settings.get(key):
            patch(iso, apply=True)
            print(f"{label}: patched")
    if placement_json.get("miasma_elements"):
        set_miasma_elements(iso, placement_json["miasma_elements"])
        print(f"Miasma Stream elements set by the multiworld: {placement_json['miasma_elements']}")
    rng = random.Random(str(placement_json.get("seed")) + str(placement_json.get("slot")))
    if placement_json.get("shop_stock"):
        # Shop Checks: the AP world decides every slot, and each shop keeps
        # the same list all game
        import shopchecks
        stock = {key: [int(i) for i in items] for key, items in placement_json["shop_stock"].items()}
        shopchecks.patch(iso, stock)
        own = sum(i != AP_ITEM_ID for items in stock.values() for i in items)
        print(f"Shop Checks: {sum(map(len, stock.values()))} slot(s) in {len(stock)} shop(s), "
              f"{own} selling this player's own item")
    elif settings.get("randomize_shops"):
        res = randomize_shops(iso, rng, apply=True)
        print(f"Shops: {sum(res.values())} slot(s) across {len(res)} shop(s) randomized")
    if settings.get("randomize_shop_prices"):
        n = randomize_prices(iso, rng, apply=True, pool=shop_pool(ref_iso))
        print(f"Shop prices: {n} item price(s) shuffled")
    # The AP world decides the bonus pools (so the trackers can show them).
    # Seeds made before that only say whether to randomize them here.
    if placement_json.get("bonus_pools"):
        import lootcft
        script_of = {name: script for script, name in lootcft.DUNGEONS}
        spec = {script_of[dungeon]: dict(enumerate(entries))
                for dungeon, entries in placement_json["bonus_pools"].items()}
        changed = set_bonus_pools(iso, spec, apply=True)
        print(f"Bonus pools: set by the multiworld ({sum(map(len, changed.values()))} slot(s) changed)")
    elif settings.get("randomize_bonus_pools"):
        changes = randomize_bonus_pools(iso, rng, mode="cross", pool=build_pool("all"), apply=True)
        print(f"Bonus pools: {len(changes)} slot(s) randomized")

    # ── World layout and stage keys from the AP options ─────────────────────────
    zone_plan = None
    if settings.get("shuffle_loading_zones"):
        import worldzones
        layout = {spot: dungeon for spot, dungeon in (placement_json.get("world_zones") or {}).items()
                  if spot in worldzones.BY_NAME and dungeon in worldzones.BY_NAME}
        zone_plan = worldzones.normalize(layout)
        apply_world_zones(iso, zone_plan, icons=True)
    if settings.get("stage_keys"):
        create_stage_key_items(iso)
        patch_stage_key_locks(iso, apply=True, sites=stage_lock_sites_for(zone_plan))
        print("Stage keys: 13 dungeons now need their key (keys come from the multiworld).")

    # AP option Monster Hunt Checks: enemies are the checks, so every chest is
    # emptied and hidden (step 4) and none is gold.
    hunt_checks = bool(settings.get("monster_hunt_checks"))
    # AP option Chest Color Matches Contents (off for seeds made before it existed)
    gold_chests = bool(settings.get("chest_color_matches_contents")) and not hunt_checks
    if gold_chests and chestcolors.install(iso):
        print("Added the gold chest texture (important items get gold chests).")

    # ── 3. Apply per-cycle item assignments ────────────────────────────────────
    # A chest rolls its get_treasure slot from the dungeon's cycle. Vanilla
    # windows overlap (cycle 1 = slots 0-3, 2 = 2-5, 3 = 4-7), so getIdxSet is
    # patched to always use slot 0 / 2 / 4, and each location's item goes in
    # exactly that slot. Gil-only chests work the same way: their gil is
    # cleared when the item goes in. Monsters that share a chest's loot case,
    # or whose own case rolls an artifact, are first moved to plain monster
    # loot (chestflags.separate_monster_drops), so a dungeon's artifacts and
    # AP items only come from its chests. See treasure.py and chestflags.py.
    import chestflags, treasure
    found = dungeons_in_iso(iso)
    total_slots = 0

    for script, friendly, discs in found:
        chests = chestflags.canonical(ref_iso, script, discs)
        for disc in discs:
            area = _area_no(disc)
            tmp  = os.path.join(tempfile.gettempdir(), "hybrid_" + os.path.basename(disc))
            size = _extract(iso, disc, tmp)
            buf  = bytearray(open(tmp, "rb").read())
            treasure.patch_getidxset(buf, tmp)
            # Chests that shared a loot case with another chest get a case of
            # their own (chestflags._area_split), so each is its own location.
            split = 0
            for c in chests:
                if c["area"] != area:
                    continue
                for off, new_a in c["retarget"]:
                    if buf[off] != 3:
                        raise ValueError(f"{disc}: unexpected bytes at chest case 0x{off:x}")
                    buf[off + 1:off + 5] = struct.pack(">i", new_a)
                split += bool(c["retarget"])
            if split:
                print(f"  {script:8s} a{area}: {split} chest(s) given their own loot case")
            moved = chestflags.separate_monster_drops(tmp, buf, chestflags.split_chest_cases(tmp))
            if moved:
                print(f"  {script:8s} a{area}: {len(moved)} monster drop(s) moved off chest/artifact loot")
            ranges = chestflags._case_ranges(tmp)
            written = 0
            for c in chests:
                if c["area"] != area or not c["items"]:
                    continue
                lo, hi = ranges[c["case"]]
                slots = treasure.case_slots(buf, lo, hi)
                for cycle, slot in treasure.CYCLE_SLOT.items():
                    if cycle not in c["cycles"]:
                        if c["split"]:
                            treasure.write_slot(buf, slots[slot], 0)   # not a location: empty
                        continue
                    item_id = 0 if hunt_checks else chest_items.get((friendly, cycle, c["chest"]), AP_ITEM_ID)
                    treasure.write_slot(buf, slots[slot], item_id)
                    written += 1
            if len(buf) != size:
                raise ValueError(f"{disc}: size changed, refusing to inject")

            # Gold chests: set each chest's gold bits for the cycles where its
            # item is important, then let initTreasureBox pick the gold
            # texture from them (chestcolors.py). That edit makes the script
            # a little longer, so it is written back with put_file.
            golden = 0
            for off, _, _, flag in (chestflags._chest_case_pushes(tmp) if gold_chests else []):
                c = next((c for c in chests if c["area"] == area and flag in c["flags"]), None)
                if c is None:
                    continue
                cycles = [cy for cy in c["cycles"] if (friendly, cy, c["chest"]) in gold]
                a = struct.unpack(">i", buf[off + 1:off + 5])[0] & ~chestcolors.ALL_GOLD_BITS
                buf[off + 1:off + 5] = struct.pack(">i", a | chestcolors.gold_bits(cycles))
                golden += bool(cycles)
            open(tmp, "wb").write(buf)
            content = (chestcolors.patch_script(tmp) if gold_chests else None) or bytes(buf)
            gciso.put_file(iso, disc, content)
            if golden:
                print(f"  {script:8s} a{area}: {golden} gold chest(s)")
            total_slots += written
            if written:
                print(f"  {script:8s} a{area}: {written} chest slot(s) patched (hybrid)")

    # ── 4. Hide Collected Chests: the client fills in each dungeon's mask.
    # With Monster Hunt checks every chest is hidden instead.
    if hunt_checks:
        import hidechests
        hidechests.apply(iso, hide_all=True)
        print("Monster Hunt checks: chests emptied and hidden (enemies are the checks)")
    elif settings.get("hide_collected_chests"):
        import hidechests
        hidechests.apply(iso)
        print("Hide collected chests: dungeon scripts patched")

    # ── 5. Dungeon shortcuts (AP options with the same names as shortcuts.SHORTCUTS)
    import shortcuts
    wanted = [name for name in shortcuts.SHORTCUTS if settings.get(name)]
    if wanted:
        shortcuts.apply(iso, wanted)
        print("Dungeon shortcuts: " + ", ".join(wanted))

    # ── 6. Hotspot elements by year (AP option Hotspot Elements). Last, since
    # it grows the dungeon scripts the steps above edit by offset.
    if placement_json.get("hotspot_elements"):
        n = set_hotspot_elements(iso, placement_json["hotspot_elements"],
                                 menus=placement_json.get("menu_elements"))
        print(f"Hotspot elements: {n} hotspot(s) now change element by year")

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
            print("Installed AP Item into ISO (definition, name, icon and logo model).")
    except Exception as e:
        print(f"Note: could not auto-install AP Item ({e}); 0x162 must already be present.")
    try:
        import titlelogo
        if titlelogo.install(iso):
            print("Installed the Archipelago title logo, disc name and banner.")
    except Exception as e:
        print(f"Note: could not install the title logo ({e}).")

    found = dungeons_in_iso(iso)
    total_slots = 0

    for script, friendly, discs in found:
        import chestflags
        chest_map = chestflags.patch_map(ref_iso, script, discs)
        if not chest_map:
            print(f"  {friendly}: no chests found — skipped")
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
    zone_plan = None
    if getattr(args, "randomize_world_zones", False):
        import worldzones
        zone_rng = random.Random(f"{args.seed}-zones")
        zone_plan = None
        if not getattr(args, "no_progression_logic", False):
            try:
                zone_plan, _, report = logic_plan(iso, zone_rng, True, False,
                                                  getattr(args, "goblin_wall_always_visible", False))
                print("Progression logic: " + "; ".join(report))
            except Exception as e:
                print(f"WARNING: progression logic found no valid layout ({e}); using plain random")
        if zone_plan is None:
            zone_plan = worldzones.random_plan(zone_rng)
    holy = stone_dungeons_for(boss_plan) if not getattr(args, "no_stone_protection", False) else {}
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
        if zone_plan is not None:
            apply_world_zones(iso, zone_plan, spoiler,
                              icons=not getattr(args, "no_world_zone_icons", False))
        for problem in check_stone_access(iso, holy):
            print(f"WARNING: {problem}")
    else:
        print("Run the same command with `run` (and the same --seed) to apply.")


def main():
    p = argparse.ArgumentParser(description="Randomize FFCC chest contents in an ISO.")
    p.add_argument("command", choices=["list", "preview", "run", "spoiler", "export",
                                        "patch", "ap-patch", "ap-hybrid", "shops", "preview-shops",
                                        "list-shops", "prices", "export-bonus"])
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
    p.add_argument("--no-stone-protection", action="store_true",
                   help="don't keep the magicite needed for Holy (Lich/Zombie Dragon) and "
                        "Tida's Fire vanilla (with `run`)")
    p.add_argument("--randomize-world-zones", action="store_true",
                   help="EXPERIMENTAL: shuffle which dungeon each world-map node leads to "
                        "(with `run`; 12 dungeons, Mount Kilanda and Mount Vellenge stay)")
    p.add_argument("--no-progression-logic", action="store_true",
                   help="with --randomize-world-zones, shuffle with no reachability check")
    p.add_argument("--no-world-zone-icons", action="store_true",
                   help="with --randomize-world-zones, keep each world-map stop's "
                        "original building instead of showing its new dungeon")
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
    elif args.command == "export-bonus":
        if not args.json:
            sys.exit("export-bonus needs an output path: randomizer.py export-bonus <iso> <bonus_table.py>")
        export_bonus_table(args.iso, args.json)
        print("wrote", args.json)
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
