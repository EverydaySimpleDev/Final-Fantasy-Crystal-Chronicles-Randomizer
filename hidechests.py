"""
hidechests.py - Chests whose AP check is already done don't appear.

A dungeon script spawns a chest from its SPAWN_TBOX record [mask, A, 0, B, ...]
unless that chest's "opened" bit is set: bit B-1 of G368 (flags 0-31) or G369
(flags 32-63). The game sets those bits when a chest is opened and clears them
when the caravan leaves the dungeon, so an opened chest stays gone only for
that visit.

With this patch every dungeon area's director starts by adding a mask from the
save's event data to those bits, before any chest is created:

    G368 = G368 | (eventWork[B] & 0xFFFF) | ((eventWork[B + 1] & 0xFFFF) << 16)
    G369 = G369 | (eventWork[B + 2] & 0xFFFF)

B = MASK_BASE + 3 * dungeon (the game's stage order, as lootcft.DUNGEONS).
The AP client keeps each dungeon's mask up to date for its current cycle (the
flags of the chests whose check for that cycle is done). eventWork 180-221 is
used by no game script (eventWork 150-179 is used by the ending, 230 by the
client). The highest chest flag in any dungeon is 36, so 48 bits each is
enough. OR-ing keeps chests opened during this visit opened when the caravan
moves between areas.

With `hide_all` (the AP world's Monster Hunt checks, where chests aren't
checks) the director instead marks every chest opened, so none appears:

    G368 = -1
    G369 = -1

Usage:
    py hidechests.py apply <game.iso>
    py hidechests.py hide-all <game.iso>
"""

import os
import struct
import sys
import tempfile

import cft
import cftpatch
import gciso
import lootcft

MASK_BASE = 180
MASK_WORDS = 3

_LOAD_G368 = struct.pack(">BI", 0x00, 0x00017009)
_ADDR_G368 = struct.pack(">BI", 0x01, 0x00017009)
_LOAD_G369 = struct.pack(">BI", 0x00, 0x00017109)
_ADDR_G369 = struct.pack(">BI", 0x01, 0x00017109)
_LOAD_EVENT_WORK = struct.pack(">BI", 0x00, 0xFFFE390A)    # index on the stack
_AND, _OR, _SHIFT_LEFT, _STORE, _POP = 0x1F, 0x1E, 0x22, 0x0D, 0x0C


def _push(value):
    return struct.pack(">Bi", 0x03, value)


def _event_word(index):
    """Bytecode that pushes eventWork[index] & 0xFFFF."""
    return _push(index) + _LOAD_EVENT_WORK + _push(0xFFFF) + bytes([_AND])


def mask_code(dungeon_index):
    """The two statements added at the start of a dungeon area's director."""
    base = MASK_BASE + MASK_WORDS * dungeon_index
    low = (_ADDR_G368 + _LOAD_G368 + _event_word(base) + bytes([_OR])
           + _event_word(base + 1) + _push(16) + bytes([_SHIFT_LEFT, _OR, _STORE, _POP]))
    high = _ADDR_G369 + _LOAD_G369 + _event_word(base + 2) + bytes([_OR, _STORE, _POP])
    return low + high


def hide_all_code():
    """The two statements that mark every chest of an area opened."""
    return (_ADDR_G368 + _push(-1) + bytes([_STORE, _POP])
            + _ADDR_G369 + _push(-1) + bytes([_STORE, _POP]))


def patch_script(path, dungeon_index, hide_all=False):
    """The .cft at `path` with the mask statements (or, with `hide_all`, the
    every-chest statements) at the start of director, or None if they are
    already there."""
    s = cftpatch.Script(path)
    code = s.code("director")
    added = hide_all_code() if hide_all else mask_code(dungeon_index)
    if code.startswith(added):
        return None
    spawn = {(op, arg & 0xFFFFFFFF) for _, op, arg in cft.disasm(s.code("SPAWN_TBOX")) if arg is not None}
    if (0x00, 0x00017009) not in spawn or (0x00, 0x00017109) not in spawn:
        raise ValueError(f"{os.path.basename(path)}: SPAWN_TBOX doesn't use G368/G369 as expected")
    cftpatch.insert_code(s, "director", 0, added, [])
    return s.to_bytes()


def apply(iso, hide_all=False):
    """Patch every dungeon area. Returns the scripts changed."""
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    done = []
    for index, (script, _) in enumerate(lootcft.DUNGEONS):
        discs = sorted(p for p, _, _ in files if p.startswith(f"dvd/cft/{script}_") and p.endswith(".cft"))
        for disc in discs:
            tmp = os.path.join(tempfile.gettempdir(), "hidechests_" + os.path.basename(disc))
            with open(iso, "rb") as f:
                _, off, size = gciso.find_file(files, disc)[0]
                f.seek(off)
                open(tmp, "wb").write(f.read(size))
            content = patch_script(tmp, index, hide_all)
            if content is not None:
                gciso.put_file(iso, disc, content)
                done.append(disc)
    return done


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] in ("apply", "hide-all"):
        print(f"patched {len(apply(sys.argv[2], sys.argv[1] == 'hide-all'))} dungeon script(s)")
    else:
        print(__doc__)
