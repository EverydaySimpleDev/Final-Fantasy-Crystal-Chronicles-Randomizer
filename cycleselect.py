"""
cycleselect.py - Choose which cycle of a dungeon to play when entering it.

A dungeon's cycle is the system value -0x56 + dungeon (m_bossArtifactStageTable,
dungeon = the game's stage order, as lootcft.DUNGEONS). The dungeon scripts
read it when they load (getIdxSet picks the chest set, SPAWN_MONSTER the
spawns), and the engine reads it for monster strength and the bonus screen.

Every dungeon entry from the world map goes through MJ_SWING(file, ...) in
world.cft, with `file` the string index of the dungeon's first area
("river_0"). This patch adds, at the start of MJ_SWING:

    if file is a dungeon's "<script>_0" and that dungeon's cycle >= 1:
        eventWork[232] = dungeon + 1
        eventWork[233] = cycle                     (the real one)
        ask "Which cycle?" - Cycle 1, Cycle 2 (, Cycle 3), Never mind
        Never mind: eventWork[232] = 0, return without entering
        otherwise:  cycle = the line picked

Only cycles the dungeon has already reached are offered. With Cycle Locks
(the AP option) the cycles offered are the ones unlocked instead: the AP
client keeps eventWork[128 + dungeon] at the number of unlock items received
for it (0-2), and with none the dungeon is always played on Cycle 1. The
menu gives -1 for "Never mind" and for B. The world map's director puts the
real cycle back when the caravan returns:

    if eventWork[232]:
        cycle[eventWork[232] - 1] = eventWork[233]
        eventWork[232] = 0

This is safe because the only thing that raises a cycle is incMana (a myrrh
harvest), and it never raises the cycle of the dungeon being harvested. Both
event words are part of the save, so the restore also happens after a reload.
eventWork 128-140 and 232-234 are used by no game script.

Usage:
    py cycleselect.py apply <game.iso>
    py cycleselect.py apply-locked <game.iso>
"""

import os
import struct
import sys
import tempfile

import cft
import cftpatch
import gciso
import lootcft
import randomizer

STASH_DUNGEON = 232     # dungeon + 1 whose cycle is overridden, 0 = none
STASH_CYCLE = 233       # its real cycle
CHOICE = 234            # line picked in the menu
UNLOCK_BASE = 128       # with Cycle Locks: eventWork[128 + dungeon] = cycles unlocked past
                        # the first (0-2), kept up to date by the AP client

# dungeons with more than one cycle (Mount Vellenge has one)
DUNGEONS = [script for script, _ in lootcft.DUNGEONS if script != "meteo"]

# The menus, appended to world.cfd. FF A0 is a line break and FF A1 ends the
# message. The choice list (FF A7 and the two bytes after it) is laid out the
# same way as the world map's own element menus (world.cfd messages 315-322).
MESSAGES = [
    b"Which cycle?\xff\xa0\xff\xa7 \" \"Cycle 1\xff\xa0Cycle 2\xff\xa0Never mind.\xff\xa1",
    b"Which cycle?\xff\xa0\xff\xa7 # #Cycle 1\xff\xa0Cycle 2\xff\xa0Cycle 3\xff\xa0Never mind.\xff\xa1",
]

_GET, _SELV, _PUSHI, _JMP, _JZ, _JNZ, _CALL = 0x00, 0x02, 0x03, 0x07, 0x08, 0x09, 0x0A
_POP, _SETSYS, _SHL, _EQ, _LT, _GT, _GE = 0x0C, 0x13, 0x22, 0x2C, 0x2E, 0x30, 0x31
_RET, _PUSH0 = 0x3C, 0x3F


def _event(index):
    """Operand of eventWork[index] (system value index - 455)."""
    return ((index - 455) << 8) | 0x09


# cycle[index on the stack - 1]: system value -0x57 + (dungeon + 1)
_CYCLE_OF_STASH = (-0x57 << 8) | 0x0A
# eventWork[UNLOCK_BASE - 1 + index on the stack]
_UNLOCK_OF_STASH = ((UNLOCK_BASE - 1 - 455) << 8) | 0x0A
_ARG0 = (0 << 8) | 0x01
_THIS0 = (0 << 8) | 0x19


class _Asm:
    """Bytecode with forward labels. Jumps are absolute (function offsets)."""

    def __init__(self, base=0):
        self.base, self.items = base, []

    def op(self, code, arg=None):
        self.items.append((code, arg))
        return self

    def label(self, name):
        self.items.append(("label", name))
        return self

    def build(self):
        labels, pos = {}, self.base
        for code, arg in self.items:
            if code == "label":
                labels[arg] = pos
            else:
                pos += 5 if code < 0x0C else 1
        out = bytearray()
        for code, arg in self.items:
            if code == "label":
                continue
            if code < 0x0C:
                if isinstance(arg, str):
                    arg = labels[arg]
                out += struct.pack(">BI", code, arg & 0xFFFFFFFF)
            else:
                out.append(code)
        return bytes(out)


def _call(a, s, fn, *args):
    for v in args:
        if isinstance(v, tuple):
            a.op(_GET, v[0])
        else:
            a.op(_PUSHI, v)
    a.op(_CALL, (0xFFFF << 16) | s.names.index(fn)).op(_POP)


def _set_event(a, index, value):
    a.op(_SELV, _event(index)).op(_PUSHI, value).op(_SETSYS).op(_POP)


def _menu(a, s, message, last):
    """Show `message`, store the line picked in eventWork[CHOICE], go to
    "back" if it is past `last` or negative (the menu gives -1 for its last
    line, "Never mind", and for B)."""
    # message box slot, position and size: the same as the world map's
    # element menu (MJ_SWING_ATTRIB_1/_2)
    for v in (4, 320, 224, 40, 1):
        a.op(_PUSHI, v)
    a.op(_GET, _THIS0).op(_SHL)
    for v in (0, 0, message):
        a.op(_PUSHI, v)
    a.op(_CALL, (0xFFFF << 16) | s.names.index("dispCubeMes")).op(_POP)
    _call(a, s, "waitCubeMes", 4)
    a.op(_SELV, _event(CHOICE)).op(_PUSHI, 4).op(_PUSHI, 0)
    a.op(_CALL, (0xFFFF << 16) | s.names.index("getCubeMesValue"))
    a.op(_SETSYS).op(_POP)
    a.op(_GET, _event(CHOICE)).op(_PUSHI, last).op(_GT).op(_JNZ, "back")
    a.op(_GET, _event(CHOICE)).op(_PUSHI, 0).op(_LT).op(_JNZ, "back")


def _push_limit(a, locked):
    """Push the highest cycle the menu offers, minus one: the dungeon's real
    cycle, or with `locked` its unlock count eventWork[UNLOCK_BASE + dungeon]."""
    a.op(_GET, _event(STASH_DUNGEON)).op(_GET, _UNLOCK_OF_STASH if locked else _CYCLE_OF_STASH)


def prompt_code(s, msg2, msg3, locked=False):
    """The code added at the start of MJ_SWING. With `locked` the cycles
    offered are the ones unlocked (eventWork[UNLOCK_BASE + dungeon], written
    by the AP client), and with none unlocked the dungeon is played on
    Cycle 1 without asking."""
    a = _Asm()
    for n, script in enumerate(DUNGEONS):
        name = f"{script}_0".encode()
        for idx in (i for i, x in enumerate(s.strs) if x == name):
            a.op(_GET, _ARG0).op(_PUSHI, idx).op(_EQ).op(_JNZ, f"d{n}")
    a.op(_JMP, "end")
    for n in range(len(DUNGEONS)):
        a.label(f"d{n}")
        _set_event(a, STASH_DUNGEON, n + 1)
        a.op(_JMP, "found")
    a.label("found")
    a.op(_SELV, _event(STASH_CYCLE)).op(_GET, _event(STASH_DUNGEON)).op(_GET, _CYCLE_OF_STASH)
    a.op(_SETSYS).op(_POP)
    _push_limit(a, locked)
    a.op(_PUSHI, 1).op(_GE).op(_JNZ, "ask")
    if locked:
        _set_event(a, CHOICE, 0)
        a.op(_JMP, "chosen")
    else:
        a.op(_JMP, "clear")
    a.label("ask")
    _call(a, s, "closeCubeMes", 5)
    _push_limit(a, locked)
    a.op(_PUSHI, 2).op(_GE).op(_JZ, "two")
    _menu(a, s, msg3, 2)
    a.op(_JMP, "chosen")
    a.label("two")
    _menu(a, s, msg2, 1)
    a.label("chosen")
    a.op(_GET, _event(STASH_DUNGEON)).op(_SELV, _CYCLE_OF_STASH).op(_GET, _event(CHOICE))
    a.op(_SETSYS).op(_POP)
    a.op(_JMP, "end")
    a.label("back")
    _set_event(a, STASH_DUNGEON, 0)
    a.op(_PUSH0).op(_RET)
    a.label("clear")
    _set_event(a, STASH_DUNGEON, 0)
    a.label("end")
    return a.build()


def restore_code():
    """The code added at the start of world.cft's director."""
    a = _Asm()
    a.op(_GET, _event(STASH_DUNGEON)).op(_JZ, "skip")
    a.op(_GET, _event(STASH_DUNGEON)).op(_SELV, _CYCLE_OF_STASH).op(_GET, _event(STASH_CYCLE))
    a.op(_SETSYS).op(_POP)
    _set_event(a, STASH_DUNGEON, 0)
    a.label("skip")
    return a.build()


def apply(iso, locked=False):
    """Add the cycle menu to `iso` (with `locked`, the Cycle Locks version).
    Returns False if it is already there. Run it after every patch that
    edits world.cft by offset (loading zones, Miasma Streams, stage keys)."""
    tmp_cfd = os.path.join(tempfile.gettempdir(), "cycleselect_world.cfd")
    randomizer._extract(iso, "dvd/cft/world.cfd", tmp_cfd)
    chunks, messages = randomizer._cfd_messages(open(tmp_cfd, "rb").read())
    if MESSAGES[0] in messages:
        return False
    if len(messages) + len(MESSAGES) > 1122:
        raise ValueError("world.cfd would have too many messages")
    msg2, msg3 = len(messages), len(messages) + 1
    messages += MESSAGES

    tmp_cft = os.path.join(tempfile.gettempdir(), "cycleselect_world.cft")
    randomizer._extract(iso, "dvd/cft/world.cft", tmp_cft)
    s = cftpatch.Script(tmp_cft)
    call = (0xFFFF << 16) | s.names.index("func_MJ_SWING")
    if not any(op == _CALL and arg & 0xFFFFFFFF == call for _, op, arg in cft.disasm(s.code("MJ_SWING"))):
        raise ValueError("MJ_SWING doesn't call func_MJ_SWING as expected")
    log = []
    cftpatch.insert_code(s, "MJ_SWING", 0, prompt_code(s, msg2, msg3, locked), log)
    cftpatch.insert_code(s, "director", 0, restore_code(), log)
    gciso.put_file(iso, "dvd/cft/world.cft", s.to_bytes())
    gciso.put_file(iso, "dvd/cft/world.cfd", randomizer._cfd_build(chunks, messages))
    return True


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] in ("apply", "apply-locked"):
        added = apply(sys.argv[2], locked=sys.argv[1] == "apply-locked")
        print("cycle menu added" if added else "cycle menu already there")
    else:
        print(__doc__)
