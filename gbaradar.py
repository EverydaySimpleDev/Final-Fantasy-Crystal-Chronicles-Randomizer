"""
gbaradar.py - An all-in-one GBA radar: the map, its exits, enemies and
treasure chests on one screen.

The GBA radar has four kinds, and normally each player's GBA gets one
(GbaQueue::SetRadarType, and in single player it comes from how the Moogle's
fur was brushed):

    0 Map       the area map and its exits
    1 Monster   enemies
    2 Scouter   details of the enemies instead of a radar
    3 Treasure  chests and special enemies

Each kind is only a filter. The GameCube sends the positions of every enemy
and chest near the player, hiding the ones the player's kind doesn't show,
and the GBA draws the dots its kind uses. This patch gives every player the
Map radar and takes the filters away from it:

    Start.dol
      SetRadarType      every player gets kind 0 (the game already does this
                        outside dungeons)
      GetEnemyPos       enemies are no longer hidden from the Map radar
      GetTreasurePos    chests are no longer hidden from every kind but Treasure
    dvd/gba/ffcc_cli.bin
      RadarScreen_Main  enemy and chest dots are drawn for every kind

Usage:
    py gbaradar.py apply <game.iso>
"""

import struct
import sys

import gciso
import randomizer

GBA_FILE = "dvd/gba/ffcc_cli.bin"
GBA_LOAD = 0x02000000

# (address, original, new)
DOL_PATCHES = [
    # SetRadarType: `blt` past "everyone gets kind 0 outside dungeons" -> nop
    (0x800CF1E8, "41800018", "60000000"),
    # GetEnemyPos: `bne` past "hide for kind 0" -> b
    (0x800CE110, "40820010", "48000010"),
    # GetTreasurePos: `beq` past "hide unless kind 3" -> b
    (0x800CDED4, "4182000C", "4800000C"),
]
GBA_PATCHES = [
    # RadarScreen_Main: `beq` to the enemy dots when the kind is Monster -> b
    (0x020147B8, "01d0", "01e0"),
    # RadarScreen_Main: `bne` past the chest dots unless the kind is Treasure -> nop
    (0x020147C6, "01d1", "c046"),
]


def _dol_offset(iso, addr):
    with open(iso, "rb") as f:
        off, _ = gciso.dol_span(f)
        f.seek(off)
        header = f.read(0xE4)
    offsets = struct.unpack(">18I", header[0:72])
    starts = struct.unpack(">18I", header[72:144])
    sizes = struct.unpack(">18I", header[144:216])
    for o, start, size in zip(offsets, starts, sizes):
        if size and start <= addr < start + size:
            return o + addr - start
    raise ValueError(f"0x{addr:08x} isn't in Start.dol")


def _patch_gba(iso):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, GBA_FILE)[0]
        f.seek(off)
        image = bytearray(f.read(size))
    for addr, orig, new in GBA_PATCHES:
        at, orig, new = addr - GBA_LOAD, bytes.fromhex(orig), bytes.fromhex(new)
        current = image[at:at + len(orig)]
        if current not in (orig, new):
            raise ValueError("the GBA radar code isn't the game's own")
        image[at:at + len(new)] = new
    gciso.put_file(iso, GBA_FILE, bytes(image))


def apply(iso):
    """Install the all-in-one radar. Safe to run twice."""
    patches = [(_dol_offset(iso, addr), bytes.fromhex(orig), bytes.fromhex(new))
               for addr, orig, new in DOL_PATCHES]
    randomizer._dol_patch(iso, patches, "all-in-one radar")
    _patch_gba(iso)
    return True


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "apply":
        apply(sys.argv[2])
        print("all-in-one radar installed")
    else:
        print(__doc__)
