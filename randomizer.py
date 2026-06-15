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


def _randomize_area(iso, disc, rng, mode, pool, nonart, fill_empty, apply, rolls,
                    max_artifacts, art_per_cycle, only_sets):
    """Randomize ONE area file in place. `art_per_cycle` is the dungeon-wide
    artifact tally (shared across the dungeon's areas). Returns
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
                      max_artifacts=4, only_by_disc=None):
    """Randomize all area files of one dungeon, enforcing at most `max_artifacts`
    artifacts per cycle ACROSS the whole dungeon (one shared tally). `only_by_disc`
    (dict disc -> set of chest set indices) restricts to chests; None = everything.
    Returns [(area_no, set_index, slot_index, old_id, new_id)]."""
    nonart = [v for v in pool if items.category(v) != "Artifact"]
    art_per_cycle = {1: 0, 2: 0, 3: 0}            # shared across the dungeon's areas
    changes = []
    for disc in discs:
        only = only_by_disc.get(disc) if only_by_disc is not None else None
        changes += _randomize_area(iso, disc, rng, mode, pool, nonart, fill_empty,
                                   apply, rolls, max_artifacts, art_per_cycle, only)
    return changes


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
                                    getattr(args, "max_artifacts", 4), only_by_disc)
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
    else:
        print("Run the same command with `run` (and the same --seed) to apply.")


def main():
    p = argparse.ArgumentParser(description="Randomize FFCC chest contents in an ISO.")
    p.add_argument("command", choices=["list", "preview", "run", "spoiler", "export",
                                        "patch", "shops", "preview-shops", "list-shops",
                                        "prices"])
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
