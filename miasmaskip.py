"""
miasmaskip.py - Skip the Miasma Stream gates: entering one takes the caravan
straight to the world-map stop on the other side, whatever element the
chalice holds.

How a gate works in the game
----------------------------
A Miasma Stream gate is a small stage (stream_0) between two world-map stops,
one on each side:

    gate (m_eventHeader slot)   stops
    0                           5 and 10
    1                           15 and 20
    2                           25 and 30
    3                           45 and 50

The scripts keep the world-map position in three CFlat globals (written G59,
G61 and G62 below):

    G61   the stop the caravan stands at
    G62   when a stage is entered, func_MJ_SWING copies G61 here and clears
          G61. The gate stage reads it to know which gate it is
    G59   when going back to the world map, the stop to put the caravan at

Walking out of the gate stage on one side or the other (stream_0's
mainMapJump, after onPushMapJump) does this:

    fade the stage music out, stop the map sounds, load the world map's music
    clear the stage's state: sysControl(9, 1), resetSpawnBit(-1), G368 and
        G369 = 0, eventWork[5] and [6] = 0, clearStageVar(0)
    G61 = stop, setCamRot(0), G59 = stop, G60 = 1
    loadCFlat("world")

What this patch does
--------------------
It adds code to stream_0's director, right after initAllFinished:

    if G62 is one of a gate's two stops:
        do the exit steps above, to the gate's other stop

The stage has loaded at that point but hasn't faded in, so the player only
sees a loading screen. The code can't go anywhere earlier: the game doesn't
change stage before the current one calls initAllFinished, and world.cft
can't load itself again, so the world map can't do the crossing on its own.

The gate stage keeps nothing once it's left, so skipping it changes nothing
else. The Mystery Miasma Stream (stream_1, stops 56 and 60, which needs the
Unknown element) is left as it is.

Usage:
    py miasmaskip.py apply <game.iso>
"""

import os
import struct
import sys
import tempfile

import cft
import cftpatch
import gciso
import randomizer
from cycleselect import _Asm, _GET, _PUSHI, _JMP, _JNZ, _CALL, _POP, _EQ

STREAM_CFT = "dvd/cft/stream_0.cft"

# the two stops of each gate
GATE_STOPS = [(5, 10), (15, 20), (25, 30), (45, 50)]
GATES = sorted(stop for pair in GATE_STOPS for stop in pair)

WORLD_MUSIC = 105       # the world map's music, loaded by every gate exit

# CFlat opcodes used here besides the ones from cycleselect: address of a
# value, select a system value, push a float, push a string, store, set the
# selected system value
_GETA, _SELV, _PUSHF, _PUSHS, _STORE, _SETSYS = 0x01, 0x02, 0x04, 0x05, 0x0D, 0x13


def _global(index):
    """Operand of the CFlat global G<index>."""
    return (index << 8) | 0x09


def _event(index):
    """Operand of eventWork[index] (stored as the global index - 455)."""
    return _global(index - 455)


_CURRENT_STOP = _global(61)
_ENTERED_FROM = _global(62)
_ARRIVE_AT = _global(59)
_FROM_A_STAGE = _global(60)


def _store(a, operand, push):
    """`operand = <value>`, where push(a) emits the code for the value."""
    a.op(_GETA, operand)
    push(a)
    a.op(_STORE).op(_POP)


def _call(a, s, name, *args):
    """Call `name` (a function of script `s`) with int or float arguments."""
    for v in args:
        if isinstance(v, float):
            a.op(_PUSHF, struct.unpack(">i", struct.pack(">f", v))[0])
        else:
            a.op(_PUSHI, v)
    a.op(_CALL, (0xFFFF << 16) | s.names.index(name)).op(_POP)


def skip_code(s, at):
    """The code added to stream_0's director at offset `at`: a gate exit to
    the other stop of the gate the caravan came from."""
    a = _Asm(at)
    for first, second in GATE_STOPS:
        a.op(_GET, _ENTERED_FROM).op(_PUSHI, first).op(_EQ).op(_JNZ, f"to{second}")
        a.op(_GET, _ENTERED_FROM).op(_PUSHI, second).op(_EQ).op(_JNZ, f"to{first}")
    a.op(_JMP, "end")
    for stop in GATES:
        a.label(f"to{stop}")
        _store(a, _CURRENT_STOP, lambda a, v=stop: a.op(_PUSHI, v))
        a.op(_JMP, "exit")
    a.label("exit")
    # music
    _call(a, s, "fadeOutBgm", 100)
    _call(a, s, "stopMapSeAll", 100)
    _call(a, s, "LOAD_WAVE_ASYNC", WORLD_MUSIC)
    # the stage's state
    _call(a, s, "sysControl", 9, 1)
    _call(a, s, "resetSpawnBit", -1)
    for index in (368, 369):
        _store(a, _global(index), lambda a: a.op(_PUSHI, 0))
    for index in (5, 6):
        a.op(_SELV, _event(index)).op(_PUSHI, 0).op(_SETSYS).op(_POP)
    _call(a, s, "clearStageVar", 0)
    # back to the world map, at the other stop
    _call(a, s, "setCamRot", 0.0)
    _store(a, _ARRIVE_AT, lambda a: a.op(_GET, _CURRENT_STOP))
    _store(a, _FROM_A_STAGE, lambda a: a.op(_PUSHI, 1))
    a.op(_PUSHS, s.strs.index(b"world"))
    a.op(_CALL, (0xFFFF << 16) | s.names.index("loadCFlat")).op(_POP)
    a.label("wait")
    _call(a, s, "wait", 1)
    a.op(_JMP, "wait")
    a.label("end")
    return a.build()


def _insert_at(s):
    """Offset in stream_0's director just after the call to initAllFinished
    and the pop of its result."""
    call = (0xFFFF << 16) | s.names.index("initAllFinished")
    ins = list(cft.disasm(s.code("director")))
    for k, (off, op, arg) in enumerate(ins):
        if op == _CALL and arg & 0xFFFFFFFF == call and ins[k + 1][1] == _POP:
            return ins[k + 1][0] + 1
    raise ValueError("stream_0's director doesn't call initAllFinished as expected")


def is_applied(s):
    """Whether script `s` (stream_0) already has the skip."""
    at = _insert_at(s)
    code = skip_code(s, at)
    return s.code("director")[at:at + len(code)] == code


def apply(iso):
    """Add the Miasma Stream skip to `iso`. Returns False if it is already
    there."""
    tmp = os.path.join(tempfile.gettempdir(), "miasmaskip_stream_0.cft")
    randomizer._extract(iso, STREAM_CFT, tmp)
    s = cftpatch.Script(tmp)
    if is_applied(s):
        return False
    at = _insert_at(s)
    cftpatch.insert_code(s, "director", at, skip_code(s, at), [])
    gciso.put_file(iso, STREAM_CFT, s.to_bytes())
    return True


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "apply":
        print("Miasma Stream skip added" if apply(sys.argv[2]) else "Miasma Stream skip already there")
    else:
        print(__doc__)
