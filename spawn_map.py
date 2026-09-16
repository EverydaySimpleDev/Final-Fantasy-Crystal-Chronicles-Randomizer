"""Build coordinate-indexed tables of every monster and treasure-chest placement
in each FFCC dungeon script, for cross-referencing real-time in-game position to
game data (e.g. tracking which physical monster/chest a player is near).

Monsters come from SPAWN_MONSTER's own `SPAWN` records (ordinal 0x192); chests
from `SPAWN_TBOX` (0x196). Each dungeon spans multiple area files
(dvd/cft/<prefix>_0.cft, _1, ...) - this walks all of them for a given prefix.

Record layouts (fields after monster_id/const, see cft.py's disasm()):
  SPAWN:      [monster_id, field1(0/1), C, D, x, y, z, rotation, 0, 0x40000004, E, 0, 0]
  SPAWN_TBOX: [127, A, 0, B, x, y, z, rotation]
`A` (chests) and `E` (monsters) are both CONFIRMED get_treasure indices -
swapping either between two records swaps what they drop (each index has 4
item slots, matching PutDropItem's m_dropItemCodes[4]). `C`/`D`/`B` are not
yet fully understood - see the project's own memory notes / research docs for
the latest findings; this module reports them as raw fields rather than
guessing at a meaning.

Workflow:
    python gciso.py extractall "Hacked Rom.iso" ../dungeon_cfts   # once
    python spawn_map.py table river_0.cft
    python spawn_map.py export ../dungeon_cfts/dvd/cft spawn_coordinates.json
"""
import glob
import json
import os
import struct
import sys

import cft
import lootcft

DEFAULT_CFT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dungeon_cfts", "dvd", "cft")

RECORD_LEN = {"SPAWN": 13, "SPAWN_TBOX": 8}

# Monster ID -> name, from the team's own in-game ID-sweep research
# (Monster Addresses.md). Some entries are unconfirmed/commentary as noted.
MONSTER_NAMES = {
    0x00: "None?",
    0x01: "Flan",
    0x02: "Water Flan",
    0x03: "Dark Flan",
    0x04: "Bomb",
    0x05: "Ice Bomb",
    0x06: "Thunder Bomb",
    0x07: "Ahriman",
    0x08: "Ice Ahriman",
    0x09: "Lava Ahriman",
    0x0a: "Griffin",
    0x0b: "Cerberus",
    0x0c: "Ochu",
    0x0d: "Behemoth",
    0x0e: "Cactuar",
    0x0f: "Blazer Beetle",
    0x10: "Mu",
    0x11: "Snow Mu",
    0x12: "Lava Mu",
    0x13: "Hedgehog Pie",
    0x14: "Dark Hedgehog",
    0x15: "Stone Hedgehog",
    0x16: "Skeleton (Sword)",
    0x17: "Skeleton (Mace)",
    0x18: "Skeleton (Spear)",
    0x19: "Skeleton (Mage)",
    0x1a: "Mushroom Forest Carrion Worm",
    0x1b: "Tiny Worm",
    0x1c: "Lizardman (Axe)",
    0x1d: "Lizardman (Mace)",
    0x1e: "Lizardman (Javelin)",
    0x1f: "Lizardman (Mage)",
    0x20: "Lizard Soldier",
    0x21: "Lizard Warrior",
    0x22: "Lizard Skirmisher",
    0x23: "Lizard Wizard",
    0x24: "Gigan Toad",
    0x25: "Abaddon",
    0x26: "Ghost",
    0x27: "Tonberry",
    0x28: "Tonberry Chef",
    0x29: "Electric Jellyfish",
    0x2a: "Wraith",
    0x2b: "Goblin (Sword)",
    0x2c: "Goblin (Mace)",
    0x2d: "Goblin (Spear)",
    0x2e: "Goblin (Mage)",
    0x2f: "Goblin (???)",
    0x30: "Orc (Axe)",
    0x31: "Orc (Mace)",
    0x32: "Orc (Spear)",
    0x33: "Orc (Mage)",
    0x34: "Ogre",
    0x35: "Chimera",
    0x36: "Gigas",
    0x37: "Coeurl",
    0x38: "Zu",
    0x39: "Gargoyle",
    0x3a: "Cockatrice",
    0x3b: "Lamia",
    0x3c: "Sahagin",
    0x3d: "Sand Sahagin",
    0x3e: "Stone Sahagin",
    0x3f: "Sahagin Lord",
    0x40: "Scorpion",
    0x41: "Electric Scorpion",
    0x42: "Rock Scorpion",
    0x43: "Killer Bee",
    0x44: "Killer Bee again",
    0x45: "Killer Bee again again",
    0x46: "Ghost version of Bee (unused in game)",
    0x47: "Bat",
    0x48: "Sonic Bat",
    0x49: "Vampire Bat",
    0x4a: "Nightmare",
    0x4b: "Shade (Sword)",
    0x4c: "Shade (Mace)",
    0x4d: "Shade (Spear)",
    0x4e: "Hell Plant",
    0x4f: "Magic Plant",
    0x50: "Stone Plant",
    0x51: "Gremlin",
    0x52: "Death Knight",
    0x53: "Death Knight again (different weapon?)",
    0x54: "Death Knight again again (different weapon?)",
    0x55: "Mimic",
    0x56: "Sphere",
    0x57: "Tentacle (Fire)",
    0x58: "Tentacle (Ice)",
    0x59: "Tentacle (Lightning)",
    0x5a: "Tentacle (Dark)",
    0x5b: "Giant Crab",
    0x5c: "Clavat (with a bunch of white grid texture surrounding)",
    0x5d: "Clavat (with a bunch of white grid texture surrounding)",
    0x5e: "No enemy was visible (maybe Mu for boss fight underground?)",
    0x5f: "Malboro",
    0x60: "Hell Plant in Malboro boss fight Cycle 1",
    0x61: "Magic Plant in Malboro boss fight Cycle 2",
    0x62: "Stone Plant in Malboro boss fight Cycle 3",
    0x63: "Orc King",
    0x64: "Orc (Axe) in Orc King boss fight",
    0x65: "Orc (Mace) in Orc King boss fight",
    0x66: "Orc (Spear) in Orc King boss fight",
    0x67: "Goblin King",
    0x68: "Goblin (Sword/Spear?) in Goblin King boss fight",
    0x69: "Goblin (Mace) in Goblin King boss fight",
    0x6a: "No enemy was visible",
    0x6b: "Armstrong",
    0x6c: "Skeleton (mage) in Armstrong boss fight",
    0x6d: "Skeleton (mace) in Armstrong boss fight",
    0x6e: "Skeleton (Sword?/Spear?) in Armstrong boss fight",
    0x6f: "Jack Moschet",
    0x70: "Maggie Moschet",
    0x71: "Golem",
    0x72: "Water Flan in Golem boss fight",
    0x73: "Lizardman King",
    0x74: "Lizardman (Javelin?) in Lizardman King boss fight",
    0x75: "Lizardman (Wizard) in Lizardman King boss fight",
    0x76: "Coeurl in Lizardman King boss fight",
    0x77: "Cave Worm",
    0x78: "Electric Jellyfish in Cave Worm boss fight",
    0x79: "Iron Giant",
    0x7a: "Goblin (Mage) in Iron Giant boss fight",
    0x7b: "Antlion",
    0x7c: "Scorpion in Antlion boss fight",
    0x7d: "Scorpion (Lightning) in Antlion boss fight",
    0x7e: "Scorpion (Stone) in Antlion boss fight",
    0x7f: "Lich",
    0x80: "Skeleton (Sword?) in Lich boss fight",
    0x81: "Skeleton (Mace) in Lich boss fight",
    0x82: "Skeleton (Spear?) in Lich boss fight",
    0x83: "Zombie Dragon",
    0x84: "Stone Sahagin in Zombie Dragon boss fight",
    0x85: "Game crashed",
    0x86: "No enemy was visible",
    0x87: "Meteor Parasite",
    0x88: "Meteor Parasite antenna (the vulnerable part)",
    0x9a: "Memoira",
    0x9b: "Raem",
    0x9c: "Minion (Red) in Raem boss fight",
    0x9d: "Minion (Blue) in Raem boss fight",
    0x9e: "No enemy was visible",
    0x9f: "Goblin Chieftain",
    0xa0: "Tida Carrion Worm",
    0xa1: "Lizardman Captain",
    0xa2: "Jack Mochet (seemed to have a different AI)",
    0xa3: "Orc King (w/ axe instead of hammer) (moved towards me)",
    0xa4: "Orc King (w/ axe instead of hammer) again",
    0xa5: "No enemy was visible",
    0xa6: "No enemy was visible",
    0xa7: "Minion (Blue)",
    0xa8: "Little Minion (Blue)",
    0xa9: "Big Minion (Green)",
    0xaa: "Cave Worm",
    0xab: "Iron Giant",
    0xac: "Antlion",
    0xad: "Antlion",
    0xae: "Lich",
    0xaf: "Zombie Dragon",
    0xb0: "Meteor Parasite antenna (the vulnerable part)",
    0xb1: "Meteor Parasite antenna (the vulnerable part)",
    0xb2: "Kilanda Ogre",
    0xb3: "Rebena Te Ra Skeleton Mage",
    0xb4: "Conall Curach Gigan Toad",
    0xb5: "Conall Curach Flan",
    0xb6: "Memoria",
    0xb7: "Raem",
    0xb8: "Skeleton Fire Mage",
    0xb9: "Skeleton Ice Mage",
    0xba: "Skeleton Lightning Mage",
    0xbb: "Goblin King",
    0xbc: "Goblin King",
    0xbd: "Gold Lizard Skirmisher",
    0xbe: "Chimera",
    0xbf: "Giant Crab",
    0xc0: "Giant Crab",
    0xc1: "Malboro",
    0xc2: "Armstrong",
    0xc3: "Golem",
    0xc4: "Golem",
    0xc5: "Practice Goblin",
    0xc6: "Game crashed, unable to push through (most likely no data starting from here)",
}


def monster_name(monster_id):
    return MONSTER_NAMES.get(monster_id, "?")


def _records(path, ordinal):
    """Return [(abs_addr, [field, ...]), ...] for every call to `ordinal`
    inside this file's SPAWN_MONSTER dispatcher block, in placement order."""
    root, _ = cft.parse(path)
    func = next((s for s in root.subtags if s.type == b"FUNC"), None)
    if func is None:
        return []
    names = [k.name() for k in func.subtags]
    if "SPAWN_MONSTER" not in names or ordinal not in names:
        return []
    block = func.subtags[names.index("SPAWN_MONSTER")]
    abs0 = cft.code_abs_offset(path, block)
    code = cft._code_of(block)
    target = names.index(ordinal)
    reclen = RECORD_LEN[ordinal]

    pushes, recs = [], []
    for off, op, arg in cft.disasm(code):
        if op in (3, 5):
            pushes.append((off, arg))
        elif op == 4:
            pushes.append((off, round(struct.unpack(">f", struct.pack(">i", arg))[0], 3)))
        elif op in (0, 1, 2):
            pushes.append((off, "?"))
        elif op == 0x0a:
            if (arg & 0xFFFF) == target and len(pushes) >= reclen:
                rec = pushes[-reclen:]
                addr = abs0 + rec[0][0]
                recs.append((addr, [v for _, v in rec]))
            pushes = []
    return recs


def monsters(path):
    """[{addr, monster_id, name, field1, C, D, x, y, z, rotation, E}, ...]
    E is the CONFIRMED get_treasure index for this monster's drop (swapping E
    between two records swaps their drops - user-verified in-game)."""
    out = []
    for addr, r in _records(path, "SPAWN"):
        out.append({
            "addr": f"0x{addr:x}",
            "monster_id": r[0],
            "name": monster_name(r[0]),
            "field1": r[1],
            "C": r[2],
            "D": r[3],
            "x": r[4], "y": r[5], "z": r[6], "rotation": r[7],
            "E": r[10],
        })
    return out


def chests(path):
    """[{addr, A, B, x, y, z, rotation}, ...] - A is the CONFIRMED
    get_treasure index (user-verified: swapping A between two chests swaps
    their contents). B's meaning is still unresolved (see module docstring)."""
    out = []
    for addr, r in _records(path, "SPAWN_TBOX"):
        out.append({
            "addr": f"0x{addr:x}",
            "A": r[1],
            "B": r[3],
            "x": r[4], "y": r[5], "z": r[6], "rotation": r[7],
        })
    return out


def build_dungeon(prefix, cft_dir):
    """{'<prefix>_0': {'monsters': [...], 'chests': [...]}, ...} for every
    area file belonging to this dungeon prefix."""
    out = {}
    for f in sorted(glob.glob(os.path.join(cft_dir, f"{prefix}_*.cft"))):
        base = os.path.splitext(os.path.basename(f))[0]
        m, c = monsters(f), chests(f)
        if m or c:
            out[base] = {"monsters": m, "chests": c}
    return out


def build_all(cft_dir):
    """{'River Belle Path': {...}, 'Goblin Wall': {...}, ...} for every
    dungeon in lootcft.DUNGEONS."""
    return {name: build_dungeon(prefix, cft_dir) for prefix, name in lootcft.DUNGEONS}


def _print_table(path):
    print(f"=== {path} ===")
    m = monsters(path)
    print(f"-- {len(m)} monster(s) --")
    for r in m:
        print(f"  {r['addr']}  id=0x{r['monster_id']:02x} ({r['name']})  "
              f"field1={r['field1']} C={r['C']} D={r['D']} E={r['E']}  "
              f"pos=({r['x']}, {r['y']}, {r['z']}) rot={r['rotation']}")
    c = chests(path)
    print(f"-- {len(c)} chest(s) --")
    for r in c:
        print(f"  {r['addr']}  A={r['A']} B={r['B']}  "
              f"pos=({r['x']}, {r['y']}, {r['z']}) rot={r['rotation']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__.strip())
        sys.exit(1)
    cmd = args[0].lower()
    if cmd == "table" and len(args) >= 2:
        _print_table(args[1])
    elif cmd == "export":
        cft_dir = args[1] if len(args) > 1 else DEFAULT_CFT_DIR
        outpath = args[2] if len(args) > 2 else "spawn_coordinates.json"
        data = build_all(cft_dir)
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        total_m = sum(len(v["monsters"]) for d in data.values() for v in d.values())
        total_c = sum(len(v["chests"]) for d in data.values() for v in d.values())
        print(f"wrote {outpath}: {len(data)} dungeons, {total_m} monster records, {total_c} chest records")
    else:
        print(__doc__.strip())
        sys.exit(1)
