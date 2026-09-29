"""
bossshuffle.py - EXPERIMENTAL: move dungeon bosses between arenas.

Each boss arena (`<dungeon>_<n>.cft`) gets another dungeon's boss, with that
boss's helpers and summons, using cftpatch.transplant_group (see
Documentation/Monster and Boss Swapping.md). All arenas are built from the
disc's vanilla arena files, then the ISO is rebuilt once (arena files change
size, so this uses gciso.rebuild_iso).

    plan = random_plan(random.Random(seed))       # {script: boss name}
    apply_boss_plan(iso, plan, log)                # writes the ISO

Special cases:
  - Goblin King and Lich teleport to fixed coordinates in Start.dol and rely
    on their arena's script (Goblin Wall's gimmick / Rebena Te Ra's orbs) to
    drive their boss state. Random shuffles keep them home (PINNED); an
    explicit plan may still move them. A moved Lich brings its orb shield
    (cftpatch.import_lich_orbs), and a moved Lich or Goblin King gets its
    teleport table rewritten around the new arena's spawn points. Those
    positions are estimated, not hand-checked.
  - Lich and Zombie Dragon need Holy; holy_dungeons(plan) says where they end
    up so randomizer.py can keep that dungeon's magicite sets vanilla.
  - Mount Vellenge's multi-part final boss is not included.
"""

import os
import random
import struct
import tempfile

import cftpatch
import gciso

# (dungeon script, boss arena file, boss name, boss monster ID)
BOSSES = [
    ("river",  "river_1",  "Giant Crab",     91),
    ("gob",    "gob_2",    "Goblin King",    103),
    ("mine",   "mine_3",   "Orc King",       99),
    ("kinoko", "kinoko_1", "Malboro",        95),
    ("ruin",   "ruin_2",   "Armstrong",      107),
    ("gigas",  "gigas_8",  "Gigas Lord",     111),   # with Maggie (112)
    ("water",  "water_1",  "Golem",          113),
    ("cave",   "cave_2",   "Cave Worm",      119),
    ("fort",   "fort_1",   "Lizardman King", 115),
    ("lava",   "lava_2",   "Iron Giant",     121),
    ("desert", "desert_2", "Antlion",        123),
    ("swamp",  "swamp_3",  "Zombie Dragon",  131),
    ("city",   "city_2",   "Lich",           127),
]
BY_SCRIPT = {s: (a, n, i) for s, a, n, i in BOSSES}
BY_NAME = {n: (s, a, i) for s, a, n, i in BOSSES}
BY_ID = {i: n for _, _, n, i in BOSSES}
PINNED = {"Goblin King", "Lich"}
HOLY_BOSSES = {"Lich", "Zombie Dragon"}

# Start.dol teleport tables (4 x Vec3 big-endian floats each)
TELEPORT_TABLES = {
    "Lich":        (0x20E678, (0, 25.36, -137, 0, 0, -38, -132, 0, -38, 132, 0, -38)),
    "Goblin King": (0x20E648, (-1.5, -5.99, -44.28, -85.16, -5.95, 41.4,
                               83.88, -5.74, 43.21, -1.64, 13.74, -141.45)),
}


def _disc(arena):
    return f"dvd/cft/{arena}.cft"


def vanilla_plan():
    return {s: n for s, _, n, _ in BOSSES}


def random_plan(rng, fixed=None):
    """Shuffle every non-pinned boss among the non-pinned arenas. `fixed`
    ({script: boss}) is kept as given; those arenas and bosses are left out
    of the shuffle. If fixed placements leave more arenas than bosses, the
    spare arenas keep their own boss."""
    fixed = dict(fixed or {})
    arenas = [s for s, _, n, _ in BOSSES if n not in PINNED and s not in fixed]
    names = [n for _, _, n, _ in BOSSES if n not in PINNED and n not in fixed.values()]
    rng.shuffle(names)
    plan = vanilla_plan()
    plan.update(dict(zip(arenas, names)))
    plan.update(fixed)
    return plan


def holy_dungeons(plan):
    """{script: boss} for the dungeons hosting a Holy-only boss."""
    return {s: n for s, n in plan.items() if n in HOLY_BOSSES}


def normalize_plan(spec):
    """Accept {script or dungeon name: boss name}; return {script: boss}.
    Unknown keys or bosses raise ValueError. Missing arenas keep their boss."""
    import lootcft
    friendly = {f.lower(): s for s, f in lootcft.DUNGEONS}
    plan = vanilla_plan()
    for k, v in spec.items():
        key = k.strip().lower()
        script = key if key in BY_SCRIPT else friendly.get(key)
        if script not in BY_SCRIPT:
            raise ValueError(f"_bosses: {k!r} is not a dungeon with a boss arena")
        name = next((n for n in BY_NAME if n.lower() == str(v).strip().lower()), None)
        if name is None:
            raise ValueError(f"_bosses: {v!r} is not a known boss "
                             f"(choices: {', '.join(BY_NAME)})")
        plan[script] = name
    return plan


def plan_text(plan):
    """Spoiler lines: which boss each dungeon ends in."""
    import lootcft
    friendly = dict(lootcft.DUNGEONS)
    lines = ["Boss placement (EXPERIMENTAL boss shuffle):"]
    for script, _, home_boss, _ in BOSSES:
        boss = plan.get(script, home_boss)
        mark = "" if boss == home_boss else f"   (was {home_boss})"
        lines.append(f"  {friendly.get(script, script):28s} {boss}{mark}")
    return lines


def _read(iso, disc, tag):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, disc)[0]
        f.seek(off)
        data = f.read(size)
    path = os.path.join(tempfile.gettempdir(), f"boss_{tag}_{os.path.basename(disc)}")
    open(path, "wb").write(data)
    return path


def boss_status(iso):
    """{script: boss name currently in that arena} (None if unrecognised)."""
    out = {}
    for script, arena, _, _ in BOSSES:
        s = cftpatch.Script(_read(iso, _disc(arena), "status"))
        ids = cftpatch.spawned_ids(s)
        out[script] = next((BY_ID[i] for i in ids if i in BY_ID), None)
    return out


def _groups(script_obj, boss_id):
    """(boss id, [other spawned IDs in order])."""
    others = []
    for i in cftpatch.spawned_ids(script_obj):
        if i != boss_id and i not in others:
            others.append(i)
    return boss_id, others


def _spawn_positions(script_obj):
    """(x, y, z) of every SPAWN record in SPAWN_MONSTER."""
    import cft
    target = script_obj.names.index("SPAWN")
    pushes, out = [], []
    for o, op, a in cft.disasm(script_obj.code("SPAWN_MONSTER")):
        if op in (0x03, 0x05):
            pushes.append(a)
        elif op == 0x04:
            pushes.append(struct.unpack(">f", struct.pack(">i", a))[0])
        elif op == 0x2B and pushes and isinstance(pushes[-1], float):
            pushes[-1] = -pushes[-1]
        elif op in (0x00, 0x01, 0x02):
            pushes.append(None)
        elif op == 0x0A and (a & 0xFFFF) == target and len(pushes) >= 13:
            x, y, z = pushes[-9:-6]
            if all(isinstance(v, (int, float)) for v in (x, y, z)):
                out.append((float(x), float(y), float(z)))
            pushes = []
    return out


def _arena_centre(script_obj):
    pts = _spawn_positions(script_obj)
    if not pts:
        return (0.0, 0.0, 0.0)
    n = len(pts)
    return tuple(sum(p[k] for p in pts) / n for k in range(3))


def build_arena(dst_path, donor_path, dst_boss_id, donor_boss_id, out_path, log,
                lich_donor_path=None):
    """Put donor's boss group into dst's arena. Returns the arena centre used
    for teleport/orb placement."""
    dst = cftpatch.Script(dst_path)
    donor = cftpatch.Script(donor_path)
    a_boss, a_others = _groups(dst, dst_boss_id)
    h_boss, h_others = _groups(donor, donor_boss_id)
    pairs = [(a_boss, h_boss)]
    for k, old in enumerate(a_others):
        if h_others:
            pairs.append((old, h_others[k % len(h_others)]))
    centre = _arena_centre(dst)
    log += cftpatch.transplant_group(dst_path, donor_path, pairs, out_path)
    if lich_donor_path is not None:
        s = cftpatch.Script(out_path)
        d = cftpatch.Script(lich_donor_path)
        vm = cftpatch.learn_var_map(s, d)
        cx, cy, cz = centre
        cftpatch.import_lich_orbs(s, d, vm, [(cx - 60.0, cy + 0.3, cz), (cx + 60.0, cy + 0.3, cz)], log)
        s.save(out_path)
    return centre


def _teleport_points(centre):
    cx, cy, cz = centre
    return (cx, cy, cz,  cx + 40, cy, cz,  cx - 40, cy, cz,  cx, cy, cz + 40)


def apply_boss_plan(iso, plan, log=None):
    """Rebuild `iso` in place with bosses placed per `plan` ({script: boss}).
    Arenas whose boss doesn't change are left alone. The ISO must still have
    vanilla bosses. Returns the log (list of strings)."""
    log = [] if log is None else log
    status = boss_status(iso)
    moved = {s: n for s, n in plan.items() if n != BY_SCRIPT[s][1]}
    if status == plan or not moved:
        log.append("Bosses: already placed as requested - no changes")
        return log
    if status != vanilla_plan():
        raise ValueError("boss placement needs an ISO whose bosses are still in their "
                         "original arenas; start from a fresh copy of the source ISO")
    vanilla = {s: _read(iso, _disc(a), "v") for s, a, _, _ in BOSSES}
    edits, teleports = {}, {}
    for script, name in moved.items():
        arena, _, dst_id = BY_SCRIPT[script]
        home, home_arena, boss_id = BY_NAME[name]
        out_path = os.path.join(tempfile.gettempdir(), f"boss_out_{arena}.cft")
        sub = []
        centre = build_arena(vanilla[script], vanilla[home], dst_id, boss_id, out_path, sub,
                             lich_donor_path=vanilla["city"] if name == "Lich" else None)
        log.append(f"{arena}: {BY_SCRIPT[script][1]} -> {name}")
        log += ["    " + line for line in sub]
        edits[_disc(arena)] = open(out_path, "rb").read()
        if name in TELEPORT_TABLES:
            teleports[name] = centre
    tmp_iso = iso + ".bossrebuild.tmp"
    gciso.rebuild_iso(iso, edits, tmp_iso)
    os.replace(tmp_iso, iso)
    for name, centre in teleports.items():
        off, orig = TELEPORT_TABLES[name]
        with open(iso, "r+b") as f:
            dol_off, _ = gciso.dol_span(f)
            f.seek(dol_off + off)
            cur = f.read(48)
            if cur != struct.pack(">12f", *orig):
                raise ValueError(f"{name} teleport table at DOL 0x{off:x} isn't vanilla")
            f.seek(dol_off + off)
            f.write(struct.pack(">12f", *_teleport_points(centre)))
        log.append(f"Start.dol: {name} teleport points moved around "
                   f"({centre[0]:.1f}, {centre[1]:.1f}, {centre[2]:.1f}) (estimated)")
    return log
