"""
tribestats.py - each tribe's starting stats (AP options Starting Stats and
Starting Hearts).

The game starts every character's stats from the character table at the start
of dvd/cft/param.cfd (Game.m_charaRomTable in the decomp), then adds artifacts
and equipment (CCaravanWork::CalcStatus). The table has one 0x1D0-byte record
per tribe and gender, 8 in all. A character uses record id / 100 - 1. Each
record starts with these u16 values:

    +0x00 id (100, 200, ... 800)
    +0x02 tribe and gender (0x10 male, 0x20 female, plus 1 Clavat, 2 Lilty,
          4 Yuke or 8 Selkie)
    +0x06 max HP, in half hearts (8 = 4 hearts, the game caps it at 16)
    +0x08 Strength
    +0x0A Magic
    +0x0C Defense

The stats are worked out again every time, so a change also applies to
characters in an existing save.

    py tribestats.py show <iso>
"""

import struct
import sys

import customitem

FIRST_RECORD = 0x50
RECORD_SIZE = 0x1D0
RECORDS = 8
TRIBE_BITS = {1: "Clavat", 2: "Lilty", 4: "Yuke", 8: "Selkie"}


def _records(data):
    """[(file offset, tribe name)] for the 8 tribe records, checked against their ids."""
    out = []
    for i in range(RECORDS):
        off = FIRST_RECORD + i * RECORD_SIZE
        record_id, kind = struct.unpack_from(">2H", data, off)
        tribe = TRIBE_BITS.get(kind & 0xF)
        if record_id != (i + 1) * 100 or tribe is None:
            raise ValueError(f"param.cfd: record {i} doesn't look like a tribe record (id {record_id})")
        out.append((off, tribe))
    return out


def status(iso):
    """{tribe: (hearts, Strength, Magic, Defense)} as the ISO has them (from the male record)."""
    disc = customitem._disc(iso, "param.cfd")
    _, _, data = customitem._read(iso, disc)
    out = {}
    for off, tribe in _records(data):
        if tribe not in out:
            hp, strength, magic, defense = struct.unpack_from(">4H", data, off + 6)
            out[tribe] = (hp // 2, strength, magic, defense)
    return out


def apply(iso, stats=None, hearts=None):
    """Write the tribes' stats, {tribe: [Strength, Magic, Defense]}, and the
    starting hearts into both records of each tribe. None leaves that part as it
    is. Returns True if anything changed."""
    if not stats and not hearts:
        return False
    disc = customitem._disc(iso, "param.cfd")
    _, _, data = customitem._read(iso, disc)
    data = bytearray(data)
    for off, tribe in _records(data):
        if stats:
            strength, magic, defense = (max(1, min(99, int(v))) for v in stats[tribe])
            struct.pack_into(">3H", data, off + 8, strength, magic, defense)
        if hearts:
            struct.pack_into(">H", data, off + 6, 2 * max(1, min(8, int(hearts))))
    customitem._write(iso, disc, bytes(data))
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "show":
        sys.exit(__doc__)
    for tribe, (hearts, strength, magic, defense) in status(sys.argv[2]).items():
        print(f"{tribe:7} hearts {hearts}  Strength {strength:2}  Magic {magic:2}  Defense {defense:2}")
