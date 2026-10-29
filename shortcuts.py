"""
shortcuts.py - Open a dungeon's gates, bridges and blockages from the start.

Gates, drawbridges and blockages a player opens in a dungeon are kept in the
area script's stage variables (global G51[0..7]), which start at 0 every time
the area is loaded. The objects that draw them check those values when they
are created: if the "opened" bit is set, they appear opened, without their
collision, and without the switch, sphere or cutscene. So setting the bits at
the very start of the area's `director` (the function that creates the area's
objects) makes them open on every visit, in every cycle.

Each option below sets only its own values in its own area scripts:

  river_belle_path_bridges  River Belle Path, river_0: the two drawbridges.
      myMapGimmik lowers bridge 1 / 2 when G51[3] / G51[4] is 4 (the floor
      switch pairs set them to 3, then the bridge to 4).
  goblin_wall_gates         Goblin Wall, gob_0 and gob_1: every gate.
      SwitchSphere gate n is open when bit n of G51[4] (gob_0, 9 gates) or
      G51[5] (gob_1, 13 gates) is set (resInit / resFunc).
  mine_boxes                The Mine of Cathuriges, mine_0: the box piles the
      mine cart breaks. Woodbox 7, 8 and 9 are gone when bit 7, 8 or 9 of
      G51[2] is set (initWoodbox / onPushWoodbox).
  tida_webs                 Tida, ruin_1: the spider webs. They are
      SwitchSpheres 25100-25120 that only burn with Fire. Web n is gone when
      bit n of G51[4] is set (resInit / resFunc, 21 webs).
  moschet_manor_doors       Moschet Manor, gigas_0 to gigas_7: every door
      with a tribe switch. A raceSw switch presses down while a player of
      the tribe its icon shows stands on it (mainraceSw checks this.m14,
      set by onPushraceSw), then opens its doors. The doors keep no state,
      so instead the switches press themselves: their "if (this.m14)"
      always passes, and the game opens each door the usual way.
  selepation_cave_elevators Selepation Cave, cave_0: the three elevators
      start at the bottom. Elevator n is up when G51[n] is 0 and down when
      it is 1 (initelevater draws it and sets its floors from that value,
      and riding it flips the value).
  conall_curach_log_bridges Conall Curach, swamp_1: the log bridges that
      normally appear only after bombing the log bridges in Daemon's Court.
      Each one bombed there adds 1 to the saved eventWork[3] (up to 6), and
      swamp_1's initmyMapGimmik shows more log bridges for 1, 2 and 3 or more.
      Here it reads that value as 6. Daemon's Court's own count is unchanged.
  rebena_te_ra_gates        Rebena Te Ra, city_0 and city_1: the gates and
      barriers opened by its switches (not the item pedestals, the Lock
      objects, which would have to be given items). city_0: the gate opens
      when G51[3] is set, the barriers when G51[4] has bits 0x3C and 0xC0
      and G51[0] has bit 0x100. city_1: the gates open when G51[5] has bits
      0x18 and 0x20 (with the high bits the game sets alongside), the
      barriers when G51[6] has 0x18 and 0x20. The low bits only clear map
      markers.
  lynari_desert_unknown     Lynari Desert: the Unknown element puzzle solved.
      desert_0: the saved eventWork[40] counts the puzzle (four spheres hit
      in order, then the hotspot). At 5 the hotspot gives Unknown, and the
      spheres in both areas remove themselves (above 3). Only Lynari
      Desert's scripts read it. desert_1: the twelve element obstacles
      (SwitchSpheres 14100-14111) are cleared too. Obstacle n is gone when
      bit n of G51[5] is set (resInit / resFunc).

Usage:
    py shortcuts.py apply <game.iso> <option> [<option> ...]
"""

import os
import struct
import sys
import tempfile

import cft
import cftpatch
import gciso

# option: {area script on the disc: [edit, ...]}
#   ("set", i, v)       add `G51[i] = v` at the start of director
#   ("pressed", func)   in `func`, the first `if (this.m14)` always passes
#   ("reads", func, i, v)  in `func`, eventWork[i] reads as v (the saved
#                       value itself is left alone)
#   ("save", i, v)      add `eventWork[i] = v` (a saved value) at the start
#                       of director
_MOSCHET_SWITCHES = [("pressed", "mainraceSw")]
SHORTCUTS = {
    "river_belle_path_bridges": {"dvd/cft/river_0.cft": [("set", 3, 4), ("set", 4, 4)]},
    "goblin_wall_gates": {"dvd/cft/gob_0.cft": [("set", 4, 0x1FF)],
                          "dvd/cft/gob_1.cft": [("set", 5, 0x1FFF)]},
    "mine_boxes": {"dvd/cft/mine_0.cft": [("set", 2, 0x380)]},
    "tida_webs": {"dvd/cft/ruin_1.cft": [("set", 4, 0x1FFFFF)]},
    "moschet_manor_doors": {f"dvd/cft/gigas_{n}.cft": _MOSCHET_SWITCHES for n in range(8)},
    "selepation_cave_elevators": {"dvd/cft/cave_0.cft": [("set", 1, 1), ("set", 2, 1), ("set", 3, 1)]},
    "conall_curach_log_bridges": {"dvd/cft/swamp_1.cft": [("reads", "initmyMapGimmik", 3, 6)]},
    "rebena_te_ra_gates": {"dvd/cft/city_0.cft": [("set", 3, 3), ("set", 4, 0xFC), ("set", 0, 0x300)],
                           "dvd/cft/city_1.cft": [("set", 5, 0x1FFE003F), ("set", 6, 0x3F)]},
    "lynari_desert_unknown": {"dvd/cft/desert_0.cft": [("save", 40, 5)],
                              "dvd/cft/desert_1.cft": [("set", 5, 0xFFF)]},
}

_G51 = bytes.fromhex("010000330a")      # address of G51[index], index on the stack
_LOAD_M14 = 0x00000E19                  # operand of "load this.m14"
_PUSH_1 = struct.pack(">Bi", 0x03, 1)
_LOAD_EVENT_WORK = 0xFFFE390A           # operand of "load eventWork[index]", index on the stack
_POP = 0x0C
_SELECT_EVENT_WORK = bytes.fromhex("02fffe390a")   # select eventWork[index] for a set
_SET_SYSTEM_VALUE = 0x13


def _set_g51(index, value):
    """Bytecode for `G51[index] = value`."""
    return (struct.pack(">Bi", 0x03, index) + _G51 + struct.pack(">Bi", 0x03, value)
            + bytes([0x0D, 0x0C]))


def _press(s, func):
    """Make the switch check in `func` always pass. The switch loop starts
    with `while (1) { if (this.m14) ...`, compiled as push 1, jump-if-zero,
    load this.m14, jump-if-zero. The load becomes "push 1" (same size).
    False if it already was."""
    code = bytearray(s.code(func))
    ins = list(cft.disasm(bytes(code)))
    for k in range(len(ins) - 3):
        (o0, op0, a0), (_, op1, _), (o2, op2, a2), (_, op3, _) = ins[k:k + 4]
        if not (op0 == 0x03 and a0 == 1 and op1 == 0x08 and op3 == 0x08):
            continue
        if op2 == 0x00 and a2 == _LOAD_M14:
            code[o2:o2 + 5] = _PUSH_1
            s.set_code(func, code)
            return True
        if op2 == 0x03 and a2 == 1:
            return False                        # done on an earlier run
    raise ValueError(f"{func}: no 'if (this.m14)' found")


def _save(index, value):
    """Bytecode for `eventWork[index] = value`."""
    return (struct.pack(">Bi", 0x03, index) + _SELECT_EVENT_WORK + struct.pack(">Bi", 0x03, value)
            + bytes([_SET_SYSTEM_VALUE, _POP]))


def _reads(s, func, index, value):
    """Make `func` read eventWork[index] as `value`: right after each load of
    it, insert a POP and a push of `value`. False if that is already there."""
    changed = False
    while True:
        code = s.code(func)
        ins = list(cft.disasm(code))
        for k in range(1, len(ins)):
            (_, op0, a0), (o1, op1, a1) = ins[k - 1], ins[k]
            if not (op0 == 0x03 and a0 == index and op1 == 0x00 and a1 & 0xFFFFFFFF == _LOAD_EVENT_WORK):
                continue
            after = o1 + 5
            if code[after:after + 6] == bytes([_POP]) + struct.pack(">Bi", 0x03, value):
                continue                        # done already
            cftpatch.insert_code(s, func, after, bytes([_POP]) + struct.pack(">Bi", 0x03, value), [])
            changed = True
            break
        else:
            return changed


def patch_script(path, edits):
    """The .cft at `path` with `edits` made, or None if they already were."""
    s = cftpatch.Script(path)
    changed = False
    added = b"".join(_set_g51(*rest) if kind == "set" else _save(*rest)
                     for kind, *rest in edits if kind in ("set", "save"))
    if added:
        code = s.code("director")
        if not code.startswith(added):
            if any(op in (0x07, 0x08, 0x09) and (arg & 0xFFFFFF) == 0 for _, op, arg in cft.disasm(code)):
                raise ValueError(f"{os.path.basename(path)}: director jumps back to its start")
            cftpatch.insert_code(s, "director", 0, added, [])
            changed = True
    for kind, *rest in edits:
        if kind == "pressed":
            changed |= _press(s, rest[0])
        elif kind == "reads":
            changed |= _reads(s, *rest)
    return s.to_bytes() if changed else None


def apply(iso, options):
    """Apply the named shortcut options to `iso`. Several options can touch
    the same area script. Their edits are made together, in option order."""
    by_script = {}
    for name in options:
        for disc, edits in SHORTCUTS[name].items():
            by_script.setdefault(disc, []).extend(edits)
    done = []
    for disc, edits in by_script.items():
        tmp = os.path.join(tempfile.gettempdir(), "shortcut_" + os.path.basename(disc))
        with open(iso, "rb") as f:
            _, files = gciso.parse_fst(f)
            _, off, size = gciso.find_file(files, disc)[0]
            f.seek(off)
            open(tmp, "wb").write(f.read(size))
        content = patch_script(tmp, edits)
        if content is not None:
            gciso.put_file(iso, disc, content)
            done.append(disc)
    return done


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "apply":
        unknown = [o for o in sys.argv[3:] if o not in SHORTCUTS]
        if unknown:
            sys.exit(f"Unknown option(s): {', '.join(unknown)}. Choose from: {', '.join(SHORTCUTS)}")
        print("patched:", apply(sys.argv[2], sys.argv[3:]) or "nothing (already applied)")
    else:
        print(__doc__)
