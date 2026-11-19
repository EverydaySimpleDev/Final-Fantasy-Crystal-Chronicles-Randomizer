"""
gbaloot.py - Loot pages on the GBA: press A on the radar to see the
dungeon's end-of-stage bonus pool and the artifacts this area's enemies carry.

The GBA (a GBA in controller port 2 in single player) shows its radar.
Pressing A there opens pages in the window the Scouter radar uses:

    Bonus pool    one page per bonus tier: the 4 items of that tier's row for
                  the dungeon's current cycle, and the points it needs
    Enemy drops   the artifacts the area's living enemies carry, each with
                  the kind of enemy carrying it (an enemy's drops are picked
                  when it spawns, so they are known before it dies)

A turns the page, B goes back to the radar. Each kind of page can be turned
on by itself.

How it works
------------
The GameCube already sends the GBA a "scouter" message with every enemy's
details when an area loads, for the Scouter radar. Start.dol is patched so
that message goes to every radar kind and carries 0x80 more bytes: the bonus
pool (newbattle.cfd's rows for this dungeon and cycle, as CGame::GetBossArtifact
reads them) and the artifacts carried (gbacode/gc_loot.c, in MetroTRK debugger
code the game never runs). The GBA program (dvd/gba/ffcc_cli.bin) gets new code
after its end that keeps those bytes and draws the pages (gbacode/gba_loot.c).
The game ignores the GBA's buttons in single player, so the pages read them
from the GBA's key register.

    Start.dol
      SendScouInfo          calls Loot_ScouterInfo instead of GetScouterInfo
      ThreadMain            sends the scouter message for every radar kind
    ffcc_cli.bin
      Scouter_OnInfo        keeps 0x280 bytes instead of 0x200, and only
                            redraws the scouter window on the Scouter radar
      RadarScreen_Main      checks for A every frame (Loot_RadarFrame)
      FieldMode_Update      the Scouter screen goes through Loot_Main

The machine code is in gbaloot_code.py, and gbacode/build.py rebuilds it.

Usage:
    py gbaloot.py apply <game.iso> [bonus_pool] [enemy_drops]
"""

import struct
import sys

import gbaloot_code as code
import gbaradar
import gciso
import randomizer

GBA_FILE = "dvd/gba/ffcc_cli.bin"
GBA_LOAD = 0x02000000
GBA_MAX = 0x30000                # the GameCube's buffer for the GBA program
SHOW_BONUS_POOL = 1
SHOW_ENEMY_DROPS = 2

# GBA program: (address, function the bl calls now, function it calls after)
GBA_CALLS = [
    (0x02004FAC, 0x02015C88, code.GBA_ON_SCOUTER_INFO),   # Scouter_OnInfo: Scouter_SetDirty
    (0x020052AE, 0x02015828, code.GBA_MAIN),              # FieldMode_Update: ScouterScreen_Main
    (0x02014766, 0x020094DC, code.GBA_RADAR_FRAME),       # RadarScreen_Main: StatusWin_DrawIcon
]
# Scouter_OnInfo's copy size: movs r2, #0x80 (<< 2 = 0x200) -> #0xA0 (0x280)
GBA_COPY_SIZE = (0x02004F90, "8022", "a022")

GET_SCOUTER_INFO = 0x800C9124
SEND_SCOUTER_CALL = 0x800A7A84          # SendScouInfo: bl GetScouterInfo
SCOUTER_RADAR_ONLY = (0x800AE9C8, "408200A0", "60000000")   # bne past it unless Scouter -> nop
CAVE_START = bytes.fromhex("9421ffc07c0802a6")              # TRKRequestSend's first two instructions


def _thumb_bl(frm, to):
    off = to - (frm + 4)
    return struct.pack("<HH", 0xF000 | ((off >> 12) & 0x7FF), 0xF800 | ((off >> 1) & 0x7FF))


def _ppc_bl(frm, to):
    return struct.pack(">I", 0x48000001 | ((to - frm) & 0x3FFFFFC))


def _read_gba(iso):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, GBA_FILE)[0]
        f.seek(off)
        return bytearray(f.read(size))


def _patch_gba(iso, pages):
    image = _read_gba(iso)
    at = code.GBA_AT - GBA_LOAD
    end = at + len(code.GBA_CODE)
    if len(image) >= end and image[at + 4:end] == code.GBA_CODE[4:]:
        image[at] = pages                         # already installed: only the pages change
    else:
        if len(image) > at and any(image[at:]):
            raise ValueError("the GBA program already has other code where the loot pages go")
        image[at:] = b""
        image += b"\0" * (at - len(image))
        image += bytes([pages]) + code.GBA_CODE[1:]
        for addr, old, new in GBA_CALLS:
            i = addr - GBA_LOAD
            if image[i:i + 4] != _thumb_bl(addr, old):
                raise ValueError("the GBA radar code isn't the game's own")
            image[i:i + 4] = _thumb_bl(addr, new)
        addr, old, new = GBA_COPY_SIZE
        i = addr - GBA_LOAD
        if image[i:i + 2] != bytes.fromhex(old):
            raise ValueError("the GBA scouter code isn't the game's own")
        image[i:i + 2] = bytes.fromhex(new)
    if len(image) > GBA_MAX:
        raise ValueError("the GBA program would be too big")
    gciso.put_file(iso, GBA_FILE, bytes(image))


def _patch_dol(iso):
    cave = gbaradar._dol_offset(iso, code.GC_AT)
    with open(iso, "rb") as f:
        dol, _ = gciso.dol_span(f)
        f.seek(dol + cave)
        current = f.read(len(code.GC_CODE))
    if current != code.GC_CODE and not current.startswith(CAVE_START):
        raise ValueError("the MetroTRK functions the loot pages use are already patched")
    addr, old, new = SCOUTER_RADAR_ONLY
    patches = [
        (cave, current if current != code.GC_CODE else code.GC_CODE, code.GC_CODE),
        (gbaradar._dol_offset(iso, SEND_SCOUTER_CALL), _ppc_bl(SEND_SCOUTER_CALL, GET_SCOUTER_INFO),
         _ppc_bl(SEND_SCOUTER_CALL, code.GC_SCOUTER_INFO)),
        (gbaradar._dol_offset(iso, addr), bytes.fromhex(old), bytes.fromhex(new)),
    ]
    randomizer._dol_patch(iso, patches, "GBA loot pages")


def apply(iso, bonus_pool=True, enemy_drops=True):
    """Install the loot pages with the chosen kinds of page. Run it after
    gbanames (the pages go after the GBA's item names). Safe to run again,
    e.g. to change which pages show."""
    pages = (SHOW_BONUS_POOL if bonus_pool else 0) | (SHOW_ENEMY_DROPS if enemy_drops else 0)
    if not pages:
        return False
    _patch_dol(iso)
    _patch_gba(iso, pages)
    return True


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "apply":
        kinds = set(sys.argv[3:]) or {"bonus_pool", "enemy_drops"}
        if kinds - {"bonus_pool", "enemy_drops"}:
            sys.exit("pages are bonus_pool and enemy_drops")
        apply(sys.argv[2], "bonus_pool" in kinds, "enemy_drops" in kinds)
        print("GBA loot pages installed: " + ", ".join(sorted(kinds)))
    else:
        print(__doc__)
