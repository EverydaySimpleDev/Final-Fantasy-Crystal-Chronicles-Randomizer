"""Game8 treasure-chest reference for FFCC dungeons (per cycle), plus a name->ID
resolver and a matcher that maps a dungeon script's loot SETS to chest numbers.

Source: game8.co FFCC Remastered dungeon walkthroughs. Item names are resolved to
IDs via ffcc_items; gil/empty entries are ignored.
"""
import re
import ffcc_items as I

# Distinctive item names per chest (union across cycles). Keyed by dungeon name.
# Only items that resolve to an ID matter for matching; gil/"empty" are skipped.
CHESTS = {
    "River Belle Path": {
        1: ["Cure"], 2: ["Bronze Belt", "Iron Shield", "Iron Belt", "Mythril Belt"],
        3: ["Buckler", "Silver Spectacles", "Black Hood", "Wonder Bangle"],
        4: ["Bronze Gloves", "Bronze Sallet", "Iron Gloves", "Iron Sallet"],
        5: ["Novice's Weapon", "Frost Craft", "Valiant Weapon"],
        6: ["Raise"], 7: ["Bronze Armor", "Lightning Craft", "Mythril Armor"],
    },
    "Goblin Wall": {
        1: ["Earth Pendant", "Moogle Pocket"], 2: ["Tome of Wisdom"],
        3: ["Iron Gloves", "Mythril Shield", "Flame Gloves", "Flame Shield"],
        4: ["Master's Weapon", "Warrior's Weapon", "Victorious Weapon", "Valiant Weapon"],
        5: ["Double Axe", "Green Beret", "Maneater", "Shuriken", "Flametongue", "Ice Brand", "Loaded Dice", "Sasuke's Blade"],
        6: ["Master's Weapon", "Victorious Weapon", "Valiant Weapon"],
        7: ["Buckler", "Silver Spectacles", "Black Hood", "Wonder Bangle"],
        8: ["Iron Armor", "Mythril Armor", "Time Armor", "Holy Armor", "Pure Armor"],
        9: ["Iron Belt", "Iron Sallet", "Mythril Belt", "Mythril Sallet", "Lightning Belt", "Pure Belt", "Time Sallet"],
        10: ["Cat's Bell", "Dragon's Whisker", "Mage Masher", "Silver Bracer", "Kris", "Rune Bell"],
        11: ["Lightning Gloves", "Lightning Shield", "Mythril Gloves", "Mythril Shield", "Gold Gloves", "Holy Shield"],
    },
    "The Mine of Cathuriges": {
        2: ["Clear"], 3: ["Alloy", "Mythril", "Diamond Ore", "Tiny Crystal"],
        4: ["Tome of Speed", "Secret of Speed"], 6: ["Cure"], 7: ["Raise"],
        10: ["Buckler", "Silver Spectacles", "Black Hood"], 11: ["Earth Pendant", "Moogle Pocket", "Wonder Bangle"],
    },
    "The Mushroom Forest": {
        2: ["Buckler", "Dragon's Whisker", "Silver Spectacles", "Black Hood", "Wonder Bangle"],
        3: ["Cat's Bell", "Mage Masher", "Silver Bracer", "Kris", "Sage's Staff", "Rune Bell"],
        4: ["Green Beret", "Maneater", "Shuriken", "Flametongue", "Ice Brand", "Loaded Dice", "Sasuke's Blade"],
        5: ["Earth Pendant"], 6: ["Iron Belt", "Iron Sallet", "Mythril Belt", "Mythril Sallet", "Pure Belt", "Time Sallet"],
        7: ["Fiend Kit", "Daemon Kit"], 8: ["Iron Shield", "Mythril Gloves", "Gold Gloves", "Magic Shield"],
    },
    "Moschet Manor": {
        1: ["Raise"], 2: ["Cure"], 3: ["Fashion Kit", "Lady's Accessories"],
        4: ["Ashura", "Flametongue", "Kaiser Knuckles", "Shuriken", "Fang Charm", "Ogrekiller", "Engetsurin", "Mjollnir"],
        5: ["Faerie Ring", "Rune Staff", "Winged Cap", "Wonder Wand", "Candy Ring", "Dark Matter", "Noah's Lute"],
        7: ["Helm of Arai", "Elven Mantle", "Wonder Bangle"],
    },
    "Veo Lu Sluice": {
        1: ["Phoenix Down"], 2: ["Ashura", "Kaiser Knuckles", "Power Wristband", "Twisted Headband", "Engetsurin", "Ogrekiller", "Masquerade", "Onion Sword"],
        3: ["Drill", "Main Gauche", "Rat's Tail", "Chicken Knife"], 4: ["Fire", "Thunder", "Blizzard", "Cure"],
        5: ["Book of Light", "Dragon's Whisker", "Kris", "Silver Bracer", "Red Slippers", "Sage's Staff", "Dark Matter", "Tome of Ultima"],
        8: ["Frost Shield"], 9: ["Frost Gloves"], 10: ["Frost Sallet"], 11: ["Frost Armor"], 13: ["Frost Belt"],
    },
    "Daemon's Court": {
        1: ["Fire", "Thunder", "Blizzard", "Cure"], 2: ["Raise"], 3: ["Phoenix Down"],
        4: ["Eyewear Techniques", "Designer Glasses"], 5: ["Main Gauche", "Rat's Tail", "Chicken Knife"],
        6: ["Book of Light", "Cat's Bell", "Faerie Ring", "Rune Staff", "Gold Hairpin", "Mage's Staff", "Noah's Lute", "Tome of Ultima"],
        7: ["Engetsurin", "Fang Charm", "Power Wristband", "Twisted Headband", "Heavy Armband", "Masquerade", "Giant's Glove", "Onion Sword"],
        8: ["Cure"], 9: ["Chocobo Pocket", "Moon Pendant"],
        10: ["Master's Weapon", "Warrior's Weapon", "Victorious Weapon", "Mighty Weapon", "Valiant Weapon"],
    },
    "Selepation Cave": {
        1: ["Iron Gloves", "Mythril Gloves", "Mythril Shield", "Lightning Gloves", "Gold Gloves", "Holy Shield"],
        2: ["Iron Belt", "Iron Sallet", "Mythril Belt", "Mythril Sallet", "Lightning Belt", "Lightning Sallet", "Pure Belt", "Time Sallet"],
        3: ["Iron Armor", "Mythril Armor", "Time Armor", "Holy Armor", "Pure Armor"],
        4: ["Ring of Light"], 5: ["Green Beret", "Power Wristband", "Twisted Headband", "Heavy Armband", "Mjollnir", "Masquerade", "Onion Sword"],
        6: ["Moon Pendant", "Ring of Thunder"], 7: ["Ring of Light"],
        8: ["Drill", "Main Gauche", "Chicken Knife"],
        9: ["Book of Light", "Cat's Bell", "Mage Masher", "Wonder Wand", "Faerie Ring", "Rune Bell", "Gold Hairpin", "Tome of Ultima"],
        10: ["Master's Weapon", "Warrior's Weapon", "Valiant Weapon", "Mighty Weapon", "Victorious Weapon"],
    },
    "Conall Curach": {
        1: ["Phoenix Down"], 2: ["Master's Weapon", "Mighty Weapon", "Valiant Weapon", "Victorious Weapon"],
        3: ["Lightning Shield", "Mythril Shield", "Holy Shield", "Magic Shield"],
        4: ["Lightning Sallet", "Mythril Sallet", "Eternal Sallet", "Time Sallet", "Diamond Sallet"],
        7: ["Main Gauche", "Teddy Bear", "Chicken Knife"],
        8: ["Candy Ring", "Faerie Ring", "Mage Masher", "Red Slippers", "Noah's Lute", "Sage's Staff", "Dark Matter", "Tome of Ultima"],
        9: ["Eternal Armor", "Mythril Armor", "Holy Armor", "Pure Armor", "Diamond Armor"],
        10: ["Lightning Gloves", "Mythril Gloves", "Gold Gloves"], 12: ["Lightning Belt", "Mythril Belt", "Pure Belt", "Diamond Belt"],
        13: ["Ring of Cure", "Star Pendant"], 14: ["Green Beret", "Kaiser Knuckles", "Loaded Dice", "Flametongue", "Mjollnir", "Giant's Glove", "Heavy Armband"],
        16: ["Soul of the Lion", "Soul of the Dragon"],
    },
    "Rebena Te Ra": {
        1: ["Fang Charm", "Ice Brand", "Power Wristband", "Shuriken", "Engetsurin", "Heavy Armband", "Onion Sword"],
        2: ["Blue Yarn", "White Yarn", "Ancient Potion"], 3: ["Tome of Magic", "Tome of Sorcery"],
        4: ["Raise", "Blizzard"], 10: ["Eternal Sallet", "Gold Gloves", "Holy Armor", "Pure Armor", "Diamond Armor"],
        12: ["Gobbie Pocket", "Star Pendant"], 13: ["Elven Mantle", "Teddy Bear"],
        14: ["Rune Bell", "Rune Staff", "Silver Bracer", "Winged Cap", "Cat's Bell", "Mage Masher", "Gold Hairpin", "Mage's Staff"],
        15: ["Holy Shield", "Pure Belt", "Holy Armor", "Pure Armor", "Diamond Armor"],
    },
    "Mount Vellenge": {
        1: ["Aegis", "Masamune", "Ribbon"], 2: ["Flametongue", "Ice Brand", "Mjollnir", "Sasuke's Blade"],
        3: ["Dark Matter", "Kris", "Mage's Staff", "Sage's Staff"], 5: ["Elven Mantle", "Wonder Bangle"],
    },
}

# script basename -> Game8 dungeon name (filled where confirmed; matcher can also auto-detect)
SCRIPT_TO_DUNGEON = {
    "river": "River Belle Path", "gob": "Goblin Wall", "mine": "The Mine of Cathuriges",
    "kinoko": "The Mushroom Forest", "cave": "Selepation Cave", "water": "Veo Lu Sluice",
    "swamp": "Conall Curach", "ruin": "Rebena Te Ra", "meteo": "Mount Vellenge",
    "miya": "Moschet Manor",
}

# Spell/typo aliases -> canonical name used by ffcc_items
ALIASES = {
    "cure": "Stone of Cure", "raise": "Stone of Life", "clear": "Stone of Clear",
    "fire": "Stone of Fire", "blizzard": "Stone of Blizzard", "thunder": "Stone of Thunder",
    "engetsuri": "Engetsurin", "winded cap": "Winged Cap", "mage staff": "Mage's Staff",
    "sage staff": "Sage's Staff", "goblin pocket": "Gobbie Pocket", "moogle pendant": "Moon Pendant",
    "tome of wisdom": "Wisdom Tome", "secret of speed": "Speed Secrets", "tome of speed": "Speed Tome",
    "lady accessories": "Lady's Accessories", "mighty gloves": "Mythril Gloves", "mjolnir": "Mjollnir",
}

# build normalized name -> id
def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).replace(" s ", " ").strip()

_NAME2ID = {}
for _id, _nm in I.NAMES.items():
    _NAME2ID[_norm(_nm)] = _id


def resolve(name):
    n = _norm(name)
    if n in _NAME2ID:
        return _NAME2ID[n]
    if name.lower() in ALIASES:
        return _NAME2ID.get(_norm(ALIASES[name.lower()]))
    if n in ALIASES:
        return _NAME2ID.get(_norm(ALIASES[n]))
    return None


def chest_id_sets(dungeon):
    """{chest_num: set(item_ids)} for a dungeon (unresolved names dropped)."""
    out = {}
    for cn, names in CHESTS.get(dungeon, {}).items():
        ids = set(filter(None, (resolve(x) for x in names)))
        if ids:
            out[cn] = ids
    return out


def _is_generic(v):
    # magicite/spells and Phoenix Down appear in nearly every dungeon -> useless for ID
    return 0x100 <= v <= 0x125


def _specific(ids):
    return set(v for v in ids if not _is_generic(v))


def match_dungeon(parsed_sets):
    """Identify the dungeon by matching DISTINCTIVE (non-generic) multi-item chests.
    Returns (dungeon_name, score)."""
    set_specs = [_specific(set(it for it in s if 1 <= it <= 0x4b4)) for s in parsed_sets]
    best, best_score = None, 0
    for dn in CHESTS:
        cs = chest_id_sets(dn)
        score = 0
        for want in cs.values():
            want = _specific(want)
            if len(want) < 2:
                continue  # need a distinctive multi-item chest
            # matched if some set contains >=2 of this chest's specific items
            if any(len(want & ss) >= 2 for ss in set_specs):
                score += 1
        if score > best_score:
            best, best_score = dn, score
    return best, best_score


def reference_text(dungeon):
    """Human-readable 'Chest N can contain: ...' reference for a dungeon."""
    if dungeon not in CHESTS:
        return f"(no Game8 chest data for {dungeon})"
    lines = [f"{dungeon} - chest contents (varies by cycle; '/' = possible items):", ""]
    for cn in sorted(CHESTS[dungeon]):
        lines.append(f"  Chest {cn}: " + " / ".join(CHESTS[dungeon][cn]))
    return "\n".join(lines)


def label_sets(parsed_sets, dungeon):
    """Return {set_index: chest_number}. A set is labeled with the chest whose
    distinctive (non-generic) items it best contains; generic-only chests
    (single magicite/Phoenix) are matched only if no specific chest fits."""
    cs = chest_id_sets(dungeon)
    labels = {}
    used_specific = set()
    # pass 1: specific multi-item chests (strong matches)
    for i, s in enumerate(parsed_sets):
        ids = set(it for it in s if 1 <= it <= 0x4b4)
        spec = _specific(ids)
        bestcn, bestov = None, 1
        for cn, want in cs.items():
            w = _specific(want)
            if len(w) < 2:
                continue
            ov = len(w & spec)
            if ov >= 2 and ov > bestov:
                bestcn, bestov = cn, ov
        if bestcn is not None:
            labels[i] = bestcn
            used_specific.add(bestcn)
    # pass 2: generic single-item chests (e.g. Cure/Raise) for still-unlabeled sets
    for i, s in enumerate(parsed_sets):
        if i in labels:
            continue
        ids = set(it for it in s if 1 <= it <= 0x4b4)
        for cn, want in cs.items():
            if cn in used_specific:
                continue
            if want and want <= ids:   # contains all of this chest's items
                labels[i] = cn
                break
    return labels
