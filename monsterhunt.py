"""
monsterhunt.py - The enemy list for the AP world's Monster Hunt.

Every monster a dungeon spawns comes from a SPAWN record in that dungeon's
scripts (see spawn_map.py): its monster id and a C field whose low byte says
when it appears - bits 4-6 the cycles (1, 2, 3), bits 0-3 the player counts
(1, 2, 3, 4 players). The id is the same number the game keeps on a live
monster (CMonWork.m_baseDataIndex), which is what the AP client reads when a
monster dies.

Several ids are the same enemy: a boss fight spawns its own copies of
normal enemies (the Goblins in the Goblin King fight), and some fights are
made of several pieces (the Meteor Parasite). SPECIES groups those ids under
one name. Ids missing from it (invisible helpers) are not part of the hunt.

The export writes monster_table.py for the AP world:
    MONSTERS = {name: (code, boss, ids, main dungeon, {dungeon: cycles})}
    ENEMIES  = {name: (code, dungeon, enemy type, id, area, entry, (x, y, z), cycles)}
MONSTERS has one row per enemy type, ENEMIES one per enemy (its spawn spot).
`cycles` are the cycles the enemy appears in for one player. Enemies that
only appear with more players are left out. The main dungeon is the one with
the most such spawns. Codes already in an existing table are kept, so a
location keeps its AP id when the table is made again.

Usage:
    py monsterhunt.py export <game.iso | cft folder> <monster_table.py>
    py monsterhunt.py list <game.iso | cft folder>
"""

import ast
import collections
import os
import sys
import tempfile

import gciso
import lootcft
import spawn_map

FIRST_CODE = 1000           # enemy types
FIRST_ENEMY_CODE = 2000     # single enemies

BOSSES = {
    0x5B: "Giant Crab",
    0x5F: "Malboro",
    0x63: "Orc King",
    0x67: "Goblin King",
    0x6B: "Armstrong",
    0x6F: "Gigas Lord",
    0x70: "Lamia Queen",
    0x71: "Golem",
    0x73: "Lizardman King",
    0x77: "Cave Worm",
    0x79: "Iron Giant",
    0x7B: "Antlion",
    0x7F: "Lich",
    0x83: "Zombie Dragon",
    # the Meteor Parasite's cores
    0x85: "Meteor Parasite", 0x86: "Meteor Parasite", 0x87: "Meteor Parasite", 0x88: "Meteor Parasite",
}

ENEMIES = {
    0x01: "Flan", 0x02: "Water Flan", 0x03: "Dark Flan",
    0x04: "Bomb", 0x05: "Ice Bomb", 0x06: "Thunder Bomb",
    0x07: "Ahriman", 0x08: "Ice Ahriman", 0x09: "Lava Ahriman",
    0x0A: "Griffin", 0x0B: "Cerberus", 0x0C: "Ochu", 0x0D: "Behemoth", 0x0E: "Cactuar",
    0x0F: "Blazer Beetle", 0x10: "Mu", 0x11: "Snow Mu", 0x12: "Lava Mu",
    0x13: "Hedgehog Pie", 0x14: "Dark Hedgehog", 0x15: "Stone Hedgehog",
    0x16: "Skeleton (Sword)", 0x17: "Skeleton (Mace)", 0x18: "Skeleton (Spear)", 0x19: "Skeleton (Mage)",
    0x1A: "Mushroom Forest Carrion Worm", 0x1B: "Tiny Worm",
    0x1C: "Lizardman (Axe)", 0x1D: "Lizardman (Mace)", 0x1E: "Lizardman (Javelin)", 0x1F: "Lizardman (Mage)",
    0x20: "Lizard Soldier", 0x21: "Lizard Warrior", 0x22: "Lizard Skirmisher", 0x23: "Lizard Wizard",
    0x24: "Gigan Toad", 0x25: "Abaddon", 0x26: "Ghost", 0x27: "Tonberry", 0x28: "Tonberry Chef",
    0x29: "Electric Jellyfish", 0x2A: "Wraith",
    0x2B: "Goblin (Sword)", 0x2C: "Goblin (Mace)", 0x2D: "Goblin (Spear)", 0x2E: "Goblin (Mage)",
    0x30: "Orc (Axe)", 0x31: "Orc (Mace)", 0x32: "Orc (Spear)", 0x33: "Orc (Mage)", 0x34: "Ogre",
    0x35: "Chimera", 0x36: "Gigas", 0x37: "Coeurl", 0x38: "Zu", 0x39: "Gargoyle", 0x3A: "Cockatrice",
    0x3B: "Lamia", 0x3C: "Sahagin", 0x3D: "Sand Sahagin", 0x3E: "Stone Sahagin", 0x3F: "Sahagin Lord",
    0x40: "Scorpion", 0x41: "Electric Scorpion", 0x42: "Rock Scorpion", 0x43: "Killer Bee",
    0x47: "Bat", 0x48: "Sonic Bat", 0x49: "Vampire Bat", 0x4A: "Nightmare",
    0x4B: "Shade (Sword)", 0x4C: "Shade (Mace)", 0x4D: "Shade (Spear)",
    0x4E: "Hell Plant", 0x4F: "Magic Plant", 0x50: "Stone Plant", 0x51: "Gremlin",
    0x52: "Death Knight", 0x55: "Mimic", 0x56: "Sphere",
    0x57: "Tentacle (Fire)", 0x58: "Tentacle (Ice)", 0x59: "Tentacle (Lightning)", 0x5A: "Tentacle (Dark)",
    0x9F: "Goblin Chieftain", 0xA0: "Tida Carrion Worm", 0xA1: "Lizardman Captain",
    0xB2: "Kilanda Ogre", 0xB3: "Rebena Te Ra Skeleton Mage",
    0xB4: "Conall Curach Gigan Toad", 0xB5: "Conall Curach Flan",
    0xB8: "Skeleton Fire Mage", 0xB9: "Skeleton Ice Mage", 0xBA: "Skeleton Lightning Mage",
    0xBD: "Gold Lizard Skirmisher",
    # the boss fights' own copies of normal enemies
    0x60: "Hell Plant", 0x61: "Magic Plant", 0x62: "Stone Plant",
    0x64: "Orc (Axe)", 0x65: "Orc (Mace)", 0x66: "Orc (Spear)",
    0x68: "Goblin (Sword)", 0x69: "Goblin (Mace)",
    0x6C: "Skeleton (Mage)", 0x6D: "Skeleton (Mace)",
    0x72: "Water Flan",
    0x74: "Lizardman (Javelin)", 0x75: "Lizardman (Mage)", 0x76: "Coeurl",
    0x78: "Electric Jellyfish", 0x7A: "Goblin (Mage)",
    0x7C: "Scorpion", 0x7D: "Electric Scorpion", 0x7E: "Rock Scorpion",
    0x80: "Skeleton (Sword)", 0x81: "Skeleton (Mace)", 0x82: "Skeleton (Spear)",
    0x84: "Stone Sahagin",
}

SPECIES = {**ENEMIES, **BOSSES}
BOSS_NAMES = set(BOSSES.values())

SOLO = 0x01


def cycles_of(c):
    """The cycles (1-3) a SPAWN record's C field lets the monster appear in."""
    return [cycle for cycle in (1, 2, 3) if c >> (3 + cycle) & 1]


def _cft_dir(source):
    """A folder holding the dungeon scripts: `source` itself, or the scripts
    copied out of an ISO."""
    if os.path.isdir(source):
        return source
    out = tempfile.mkdtemp(prefix="monsterhunt_")
    prefixes = tuple(f"dvd/cft/{prefix}_" for prefix, _ in lootcft.DUNGEONS)
    with open(source, "rb") as f:
        _, files = gciso.parse_fst(f)
        for path, off, size in files:
            if path.startswith(prefixes) and path.endswith(".cft"):
                f.seek(off)
                open(os.path.join(out, os.path.basename(path)), "wb").write(f.read(size))
    return out


def collect(data):
    """{name: {"boss", "ids", "spawns": {dungeon: count}, "cycles": {dungeon: set}}}
    counting only spawns that appear for one player. `data` is
    spawn_map.build_all's."""
    species = {}
    for dungeon, areas in data.items():
        for area in areas.values():
            for record in area["monsters"]:
                name = SPECIES.get(record["monster_id"])
                if name is None:
                    continue
                entry = species.setdefault(name, {"boss": name in BOSS_NAMES, "ids": set(),
                                                  "spawns": collections.Counter(), "cycles": {}})
                entry["ids"].add(record["monster_id"])
                c = record["C"] & 0xFF
                if c & SOLO:
                    entry["spawns"][dungeon] += 1
                    entry["cycles"].setdefault(dungeon, set()).update(cycles_of(c))
    # every id of a species counts when it dies, even ones not spawned by a SPAWN record
    for monster_id, name in SPECIES.items():
        if name in species:
            species[name]["ids"].add(monster_id)
    return {name: info for name, info in species.items() if info["spawns"]}


def collect_spawns(data):
    """Every enemy a player can meet alone, once each: [{"dungeon", "enemy",
    "id", "area", "entry", "pos", "cycles", "boss"}] in the game's order.
    A script can list the same enemy at the same spot twice (two code paths,
    only one of which runs), so records of one id at one spot are one enemy
    (cycles combined). A boss fight is one enemy, whichever piece dies."""
    out, seen = [], {}
    for dungeon, areas in data.items():
        for area in sorted(areas, key=lambda a: int(a.rsplit("_", 1)[1])):
            for record in areas[area]["monsters"]:
                enemy = SPECIES.get(record["monster_id"])
                c = record["C"] & 0xFF
                if enemy is None or not c & SOLO:
                    continue
                w = record["world"]
                pos = (round(w["x"], 2), round(w["y"], 2), round(w["z"], 2))
                boss = enemy in BOSS_NAMES
                key = (dungeon, enemy) if boss else (dungeon, record["monster_id"], pos)
                if key in seen:
                    seen[key]["cycles"].update(cycles_of(c))
                    continue
                seen[key] = {"dungeon": dungeon, "enemy": enemy, "id": record["monster_id"], "area": area,
                             "entry": record["entry"], "pos": pos, "cycles": set(cycles_of(c)), "boss": boss}
                out.append(seen[key])
    return out


def _previous_codes(path, table):
    if not os.path.exists(path):
        return {}
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == table:
            return {name: row[0] for name, row in ast.literal_eval(node.value).items()}
    return {}


def _enemy_lines(spawns, codes, first_code):
    """ENEMIES rows: each named "<dungeon> - <enemy> <n>" (n counting that
    enemy in that dungeon) or "<dungeon> - <boss>"."""
    next_code = max(list(codes.values()) + [first_code - 1]) + 1
    counts = collections.Counter()
    lines = []
    for s in spawns:
        counts[(s["dungeon"], s["enemy"])] += 1
        name = f"{s['dungeon']} - {s['enemy']}"
        if not s["boss"]:
            name += f" {counts[(s['dungeon'], s['enemy'])]}"
        if name not in codes:
            codes[name] = next_code
            next_code += 1
        lines.append(f"    {name!r}: ({codes[name]}, {s['dungeon']!r}, {s['enemy']!r}, {s['id']}, "
                     f"{s['area']!r}, {s['entry']}, {s['pos']!r}, {tuple(sorted(s['cycles']))!r}),")
    return lines


def export(source, out_path):
    data = spawn_map.build_all(_cft_dir(source))
    species = collect(data)
    codes = _previous_codes(out_path, "MONSTERS")
    next_code = max(list(codes.values()) + [FIRST_CODE - 1]) + 1
    dungeon_order = [name for _, name in lootcft.DUNGEONS]

    def main_dungeon(name):
        spawns = species[name]["spawns"]
        return max(spawns, key=lambda d: (spawns[d], -dungeon_order.index(d)))

    def sort_key(name):
        return (species[name]["boss"], dungeon_order.index(main_dungeon(name)), min(species[name]["ids"]))

    lines = []
    for name in sorted(species, key=sort_key):
        info = species[name]
        if name not in codes:
            codes[name] = next_code
            next_code += 1
        main = main_dungeon(name)
        cycles = {d: tuple(sorted(info["cycles"][d])) for d in dungeon_order if d in info["cycles"]}
        ids = tuple(sorted(info["ids"]))
        lines.append(f"    {name!r}: ({codes[name]}, {info['boss']}, {ids!r}, {main!r}, {cycles!r}),")

    header = '''"""
Written by monsterhunt.py (Final-Fantasy-Crystal-Chronicles-Randomizer) from
the dungeon scripts - make it again instead of editing it.

Every enemy type of the Monster Hunt:
    name: (code, boss, monster ids, main dungeon, {dungeon: cycles})

code          the location's AP code (AP id = 2326528 + code)
boss          True for a dungeon's boss
monster ids   the ids a dying monster can have to count as this enemy
              (CMonWork.m_baseDataIndex, boss fights spawn their own copies)
main dungeon  the dungeon where it appears most
cycles        the cycles it appears in, per dungeon, for one player

ENEMIES lists every enemy a player can meet alone, once each (the "Every
Enemy" mode), named "<dungeon> - <enemy> <n>", or "<dungeon> - <boss>":
    name: (code, dungeon, enemy type, monster id, area, entry, (x, y, z), cycles)

monster id    its id in the dungeon script (a boss: any of its type's ids counts)
area, entry   the area file and its place among that file's SPAWN records
(x, y, z)     where it spawns: a live monster keeps this as its home position
cycles        the cycles it appears in, for one player
"""

MONSTERS = {
'''
    enemy_lines = _enemy_lines(collect_spawns(data), _previous_codes(out_path, "ENEMIES"), FIRST_ENEMY_CODE)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n}\n\nENEMIES = {\n" + "\n".join(enemy_lines) + "\n}\n")
    return len(lines), len(enemy_lines)


def print_list(source):
    species = collect(source)
    for name, info in sorted(species.items(), key=lambda kv: (kv[1]["boss"], kv[0])):
        where = ", ".join(f"{d} {sorted(info['cycles'][d])}" for d in info["cycles"])
        print(f"{'boss  ' if info['boss'] else '      '}{name:30s} {where}")
    left_out = sorted({n for n in SPECIES.values()} - set(species))
    print(f"{len(species)} enemies; only with more players: {', '.join(left_out) or 'none'}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "export":
        types, enemies = export(sys.argv[2], sys.argv[3])
        print(f"wrote {types} enemy types and {enemies} enemies to {sys.argv[3]}")
    elif len(sys.argv) == 3 and sys.argv[1] == "list":
        print_list(sys.argv[2])
    else:
        print(__doc__)
