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
yet fully understood - see the research docs in Documentation/ for the
latest findings; this module reports them as raw fields rather than
guessing at a meaning.

Each record also gets an `entry` number: its position in that area file's
SPAWN_MONSTER, counted separately for monsters and chests. Area file + entry
identifies one placed monster/chest (a natural ID for kill/chest checks).

Coordinates: `x`/`y`/`z` are the literal values as stored. Negative
coordinates are compiled as PUSHF |v| followed by opcode 0x2B (float
negate), so those fields read unsigned; `world` has the true signed world
position (what the engine and live RAM use).

Workflow:
    python gciso.py extractall "Hacked Rom.iso" ../dungeon_cfts   # once
    python spawn_map.py table river_0.cft
    python spawn_map.py export ../dungeon_cfts/dvd/cft spawn_coordinates.json
    python spawn_map.py blender river_0.cft river_0_labels.py     # or a cft dir + prefix
        -> run the .py in Blender (Scripting tab) to drop a text label on every
           monster and chest, grouped in one collection per area file.
           Add `--axes x,-z,y` (the default) with other signs/orders if the
           labels come out mirrored against your map mesh.
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
    """Return [(abs_addr, [field, ...], [signed field, ...]), ...] for every
    call to `ordinal` inside this file's SPAWN_MONSTER dispatcher block, in
    placement order. The second list applies float negates (opcode 0x2B)."""
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

    pushes, signed, recs = [], [], []
    for off, op, arg in cft.disasm(code):
        if op in (3, 5):
            pushes.append((off, arg)); signed.append(arg)
        elif op == 4:
            v = round(struct.unpack(">f", struct.pack(">i", arg))[0], 3)
            pushes.append((off, v)); signed.append(v)
        elif op == 0x2B and signed and isinstance(signed[-1], float):
            signed[-1] = -signed[-1]
        elif op in (0, 1, 2):
            pushes.append((off, "?")); signed.append("?")
        elif op == 0x0a:
            if (arg & 0xFFFF) == target and len(pushes) >= reclen:
                rec = pushes[-reclen:]
                addr = abs0 + rec[0][0]
                recs.append((addr, [v for _, v in rec], signed[-reclen:]))
            pushes, signed = [], []
    return recs


def monsters(path):
    """[{addr, monster_id, name, field1, C, D, x, y, z, rotation, E}, ...]
    E is the CONFIRMED get_treasure index for this monster's drop (swapping E
    between two records swaps their drops - user-verified in-game)."""
    out = []
    for entry, (addr, r, w) in enumerate(_records(path, "SPAWN")):
        out.append({
            "entry": entry,
            "addr": f"0x{addr:x}",
            "monster_id": r[0],
            "name": monster_name(r[0]),
            "field1": r[1],
            "C": r[2],
            "D": r[3],
            "x": r[4], "y": r[5], "z": r[6], "rotation": r[7],
            "world": {"x": w[4], "y": w[5], "z": w[6]},
            "E": r[10],
        })
    return out


def chests(path):
    """[{addr, A, B, x, y, z, rotation}, ...] - A is the CONFIRMED
    get_treasure index (user-verified: swapping A between two chests swaps
    their contents). B's meaning is still unresolved (see module docstring)."""
    out = []
    for entry, (addr, r, w) in enumerate(_records(path, "SPAWN_TBOX")):
        out.append({
            "entry": entry,
            "addr": f"0x{addr:x}",
            "A": r[1],
            "B": r[3],
            "x": r[4], "y": r[5], "z": r[6], "rotation": r[7],
            "world": {"x": w[4], "y": w[5], "z": w[6]},
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
        w = r["world"]
        print(f"  #{r['entry']:<3d} {r['addr']}  id=0x{r['monster_id']:02x} ({r['name']})  "
              f"field1={r['field1']} C={r['C']} D={r['D']} E={_e_text(r['E'])}  "
              f"world=({w['x']}, {w['y']}, {w['z']}) rot={r['rotation']}")
    c = chests(path)
    print(f"-- {len(c)} chest(s) --")
    for r in c:
        w = r["world"]
        print(f"  #{r['entry']:<3d} {r['addr']}  A={r['A']} B={r['B']}  "
              f"world=({w['x']}, {w['y']}, {w['z']}) rot={r['rotation']}")


def _e_text(e):
    """Drop index E, with its high flag bits split off when present (e.g.
    0x10000012 = drop table 18 + flag 0x1000; thought to mark a key drop)."""
    if isinstance(e, int) and e >> 16:
        return f"{e & 0xFFFF}+flag0x{e >> 16:x}"
    return str(e)


# Blender script template. Positions use the same convention as the team's
# existing label script: Blender (X, Y, Z) = (world x, -world z, world y) / 10.
_BLENDER_HEAD = """# Generated by spawn_map.py - run in Blender's Scripting tab.
# One collection per area file; a text label per monster (orange) and chest
# (cyan). Label: entry number, name/ID, drop (get_treasure) index, cycles.
import bpy

def _mat(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m

MON = _mat("spawn_monster", (1.0, 0.35, 0.0, 1.0))
BOX = _mat("spawn_chest", (0.0, 0.8, 1.0, 1.0))

def label(coll, name, text, loc, mat):
    cu = bpy.data.curves.new(type="FONT", name=name)
    cu.body = text
    cu.size = 0.6
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    ob.data.materials.append(mat)
    coll.objects.link(ob)

def area(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll

"""


BLENDER_AXES = "x,-z,y"     # Blender X, Y, Z from world axes (default: team label script)


def _bl_loc(w, axes=BLENDER_AXES):
    """World position -> Blender location, per `axes` ("x,-z,y" = Blender X is
    world x, Blender Y is -world z, Blender Z is world y), scaled by 1/10."""
    out = []
    for a in axes.split(","):
        a = a.strip()
        neg = a.startswith("-")
        v = w[a.lstrip("-")]
        out.append(round((-v if neg else v) / 10, 3))
    return tuple(out)


def blender_script(paths, axes=BLENDER_AXES):
    """Text of a Blender script labelling every monster and chest in `paths`."""
    out = [_BLENDER_HEAD]
    for path in paths:
        base = os.path.splitext(os.path.basename(path))[0]
        m, c = monsters(path), chests(path)
        if not (m or c):
            continue
        out.append(f"coll = area({base!r})")
        for r in m:
            text = (f"Entry {r['entry']}: {r['name']} (0x{r['monster_id']:02x})\n"
                    f"drop {_e_text(r['E'])}  cycles 0x{r['C']:x}" if isinstance(r["C"], int)
                    else f"Entry {r['entry']}: {r['name']}\ndrop {_e_text(r['E'])}")
            out.append(f"label(coll, {base + '_mon' + str(r['entry'])!r}, {text!r}, "
                       f"{_bl_loc(r['world'], axes)}, MON)")
        for r in c:
            text = f"Chest entry {r['entry']}\ndrop {r['A']}"
            out.append(f"label(coll, {base + '_box' + str(r['entry'])!r}, {text!r}, "
                       f"{_bl_loc(r['world'], axes)}, BOX)")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__.strip())
        sys.exit(1)
    cmd = args[0].lower()
    if cmd == "table" and len(args) >= 2:
        _print_table(args[1])
    elif cmd == "blender" and len(args) >= 3:
        # blender <file.cft> <out.py>   |   blender <cft_dir> <prefix> <out.py>
        # optional trailing --axes x,-z,y  (to match a map mesh's orientation)
        axes = BLENDER_AXES
        if "--axes" in args:
            i = args.index("--axes"); axes = args[i + 1]; args = args[:i] + args[i + 2:]
        if os.path.isdir(args[1]):
            if len(args) < 4:
                sys.exit("usage: spawn_map.py blender <cft_dir> <dungeon prefix> <out.py>")
            paths = sorted(glob.glob(os.path.join(args[1], f"{args[2]}_*.cft")))
            outpath = args[3]
        else:
            paths, outpath = [args[1]], args[2]
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(blender_script(paths, axes))
        nm = sum(len(monsters(p)) for p in paths); nc = sum(len(chests(p)) for p in paths)
        print(f"wrote {outpath}: {nm} monster and {nc} chest label(s) from {len(paths)} area file(s)")
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
