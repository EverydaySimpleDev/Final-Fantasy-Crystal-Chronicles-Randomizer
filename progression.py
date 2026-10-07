"""
progression.py - progression logic for the loading-zone shuffle and the
stage-key chain: "can a player actually get through this seed?"

Model (NTSC-US; see Documentation/Randomizing World Loading Zones.md):

  * Every world-map spot belongs to a region. A region is entered from a
    neighbouring region, either through a Miasma Stream gate (one of the 4
    rotating slots in m_eventHeader, whose element per year comes from the
    ISO's own flashStreamAttrib table) or by a route that opens in a given
    year (the Jegon River crossing, the boats).
  * A dungeon gives the elements of its hotspots. Hotspots live in the
    dungeon's own files, so they move with the dungeon in the shuffle.
  * Entering a dungeon needs its stage key (River Belle Path never does).
    In the key chain, clearing chain[i] gives the key for chain[i+1].
  * The chalice keeps its element across the year change (confirmed in
    game), so a year can start with any element set the year before.
  * Each year the chalice needs DROPS_PER_YEAR (3) drops, each from a
    different reachable dungeon whose tree isn't regrowing. In the game a
    tree is back after 4 drops from other trees; this model uses the stricter
    "back in year y+2", which can only reject a valid seed, never pass a bad one.
  * The Unknown element (Lynari Desert) crosses every Miasma Stream. The
    Abyss (Mount Vellenge) needs it and Veo Lu Sluice cleared, and is the
    "Year 6+" step of the 5-year route.

A seed passes if years 1-5 can each be finished and, in year 6, every
dungeon (including Mount Vellenge) can be entered.

Sources: in-game mapping of gate slots 0-2, the world-map guide and the
5-year route guide (gamewith.net ffcc-remastered articles 21634 / 21108).

Slot -> gate was mapped live in game (slots 0-2); slot 3 is the remaining
rotating gate (assumed to be the Rebena Plains one by Daemon's Court). Region
links and opening years follow the world-map guide; the ones not yet checked
in game are marked "unconfirmed".

This logic is only applied to choices the randomizer makes itself. An
imported JSON (e.g. from Archipelago) is applied as written; it can opt in
with "_progression_logic": true for the parts it leaves random.
"""

import itertools

FIRE, WATER, WIND, EARTH, UNKNOWN = 1, 2, 4, 8, 16
ELEMENT_NAMES = {FIRE: "Fire", WATER: "Water", WIND: "Wind", EARTH: "Earth", UNKNOWN: "Unknown"}

DROPS_PER_YEAR = 3
LAST_YEAR = 6          # Mount Vellenge is the year-6+ step

# Elements each dungeon's hotspots give (from the SPAWN_HOT_SPOT calls in its files).
DUNGEON_ELEMENTS = {
    "river": WATER | WIND, "gob": FIRE | EARTH, "mine": FIRE, "kinoko": WATER,
    "ruin": WIND | EARTH, "gigas": WATER | FIRE, "cave": WIND, "desert": EARTH | UNKNOWN,
    "water": 0, "fort": 0, "swamp": 0, "city": 0, "lava": 0, "meteo": 0,
}

# Which region each world-map spot is in (spots are named by their vanilla dungeon).
SPOT_REGION = {
    "river": "tipa", "gob": "tipa",
    "mine": "iron", "kinoko": "iron",
    "ruin": "alfitaria", "gigas": "alfitaria",
    "water": "veolu",
    "cave": "fum", "fort": "fum",
    "swamp": "rebena", "city": "rebena",
    "desert": "lynari",
    "lava": "kilanda",
    "meteo": "abyss",
}

# region: (entered from, gate slot or None, opening year, element needed, dungeon cleared first)
REGION_ENTRY = {
    "tipa":      (None, None, 1, 0, None),
    "iron":      ("tipa", 0, 1, 0, None),             # gate slot 0 (confirmed)
    "alfitaria": ("iron", 1, 1, 0, None),             # gate slot 1 (confirmed)
    "veolu":     ("alfitaria", 2, 1, 0, None),        # gate slot 2 (confirmed); neighbour unconfirmed
    "fum":       ("iron", None, 3, 0, None),          # Jegon River ferry, from year 3 (route guide)
    "rebena":    ("fum", 3, 1, 0, None),              # gate slot 3 (unconfirmed)
    "kilanda":   ("tipa", None, 4, 0, None),          # boat, from year 4 (route guide)
    "lynari":    ("tipa", None, 5, 0, None),          # Port Tipa boat to Leuda, year 5 (route guide)
    "abyss":     ("rebena", None, 6, UNKNOWN, "water"),  # Unknown element + Veo Lu Sluice cleared
}

ALWAYS_OPEN = "river"


def vanilla_gates():
    """[year % 4 row][slot] in the order miasma_elements_status() returns
    (rows for year % 4 == 1, 2, 3, 0)."""
    return [[2, 8, 4, 1], [1, 2, 8, 4], [4, 1, 2, 8], [8, 4, 1, 2]]


def _gate_element(gates, year, slot):
    return gates[(year - 1) % 4][slot]


def enterable(plan, chain, gates, year, goblin_year1=False, carried=0, with_elements=False):
    """Dungeons a player can enter in `year`, given every key obtainable that
    year (keys and elements are found by entering/clearing, not harvesting).
    `plan` = {spot: dungeon}; `chain` = stage-key chain or None (no locks);
    `carried` = elements the chalice could hold coming into the year."""
    spot_of = {d: s for s, d in plan.items()}
    spot_of.setdefault("lava", "lava")
    spot_of.setdefault("meteo", "meteo")
    key_from = {chain[i + 1]: chain[i] for i in range(len(chain) - 1)} if chain else {}
    cleared, elements = set(), carried
    while True:
        regions = set()
        changed = True
        while changed:
            changed = False
            for r, (src, slot, open_year, need, first) in REGION_ENTRY.items():
                if r in regions or year < open_year or (need and not elements & need):
                    continue
                if first is not None and first not in cleared:
                    continue
                if src is not None and src not in regions:
                    continue
                # the Unknown element crosses every Miasma Stream
                if slot is not None and not elements & (_gate_element(gates, year, slot) | UNKNOWN):
                    continue
                regions.add(r)
                changed = True
        can = set()
        for d, s in spot_of.items():
            if SPOT_REGION[s] not in regions:
                continue
            if s == "gob" and year < 2 and not goblin_year1:
                continue
            if chain and d != ALWAYS_OPEN and key_from.get(d) not in cleared:
                continue
            can.add(d)
        new_elements = elements
        for d in can:
            new_elements |= DUNGEON_ELEMENTS[d]
        if can <= cleared and new_elements == elements:
            return (can, elements) if with_elements else can
        cleared |= can
        elements = new_elements


def check(plan, chain, gates=None, goblin_year1=False, drops=DROPS_PER_YEAR):
    """(ok, report). `plan` = {spot: dungeon} for the 12 shuffled spots."""
    gates = gates or vanilla_gates()
    by_year, carried = {}, 0
    for y in range(1, LAST_YEAR + 1):
        by_year[y], carried = enterable(plan, chain, gates, y, goblin_year1, carried, True)
    report = [f"Year {y}: {len(by_year[y])} dungeon(s) open - {', '.join(sorted(by_year[y]))}"
              for y in by_year]
    everything = set(DUNGEON_ELEMENTS)
    if not everything <= by_year[LAST_YEAR]:
        missing = sorted(everything - by_year[LAST_YEAR])
        return False, report + [f"not enterable by year {LAST_YEAR}: {', '.join(missing)}"]

    # Is there a harvest schedule that fills the chalice in years 1-4?
    seen = {}

    def ok_from(year, regrowing):
        if year == LAST_YEAR:
            return True
        key = (year, regrowing)
        if key not in seen:
            avail = sorted(by_year[year] - regrowing)
            seen[key] = len(avail) >= drops and any(
                ok_from(year + 1, frozenset(pick))
                for pick in itertools.combinations(avail, drops))
        return seen[key]

    if not ok_from(1, frozenset()):
        return False, report + ["the chalice can't be filled every year"]
    return True, report


def build_chain(rng, plan, gates=None, goblin_year1=False):
    """A stage-key chain that follows reachability: each next dungeon is a
    random one the player can already reach (by region, year and the
    elements of the dungeons before it); the year only moves on when
    nothing new is reachable. `check` still has the final say."""
    gates = gates or vanilla_gates()
    chain, year, carried = [ALWAYS_OPEN], 1, 0
    remaining = set(DUNGEON_ELEMENTS) - {ALWAYS_OPEN}
    while remaining:
        # a candidate is reachable if it would open as the very next link
        cands = sorted(d for d in remaining
                       if d in enterable(plan, chain + [d], gates, year, goblin_year1, carried))
        if cands:
            nxt = rng.choice(cands)
            chain.append(nxt)
            remaining.discard(nxt)
        elif year < LAST_YEAR:
            carried = enterable(plan, chain, gates, year, goblin_year1, carried, True)[1]
            year += 1
        else:
            raise ValueError(f"unreachable even in year {LAST_YEAR}: {sorted(remaining)}")
    return chain


def generate(rng, gates=None, goblin_year1=False, shuffle_zones=True, keys=True,
             fixed_zones=None, fixed_chain=None, tries=5000):
    """Random (plan, chain) that passes `check`. Fixed choices are kept as
    given; only the rest is randomized. Raises if nothing passes."""
    import worldzones
    gates = gates or vanilla_gates()
    for _ in range(tries):
        if shuffle_zones:
            plan = worldzones.random_plan(rng, fixed=fixed_zones)
        else:
            plan = worldzones.complete_plan(fixed_zones or {})
        chain = None
        if keys:
            if fixed_chain:
                chain = list(fixed_chain)
            else:
                try:
                    chain = build_chain(rng, plan, gates, goblin_year1)
                except ValueError:
                    continue
        if check(plan, chain, gates, goblin_year1)[0]:
            return plan, chain
        if not shuffle_zones and (fixed_chain or not keys):
            break
    raise ValueError("no world layout / key chain passes the progression logic "
                     f"after {tries} tries")
