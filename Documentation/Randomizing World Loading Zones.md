# Randomizing World Loading Zones

How to make a world-map spot lead to a different dungeon, and the
randomizer option that does it. All offsets are for the NTSC-US disc and
were verified against it.

A **node** is a dungeon's spot on the world map, named here by the dungeon
that sits there in vanilla. Putting dungeon **D** on node **N** takes three
sets of edits:

1. `world.cft`: node N's display and loading-zone blocks get D's values,
   and for 1- and 2-element nodes the Myrrh-drop check uses D's completion
   flag.
2. `world.cfd`: for 1- and 2-element nodes, the post-clear menu shows D's
   name.
3. D's own `.cft` files: every exit sends the caravan back to node N.

What stays with the node: its `MJ_SWING_*` variant, the elements offered
after a Myrrh drop, and whatever gates reaching it (Miasma Streams, Goblin
Wall's Year-2 visibility). So element progression works like vanilla, and
only the dungeon you enter changes.

**Not included:** Mount Kilanda, which is entered through four 4-argument
`MJ_SWING` calls and whose exits work differently, and Mount Vellenge.

## Using it in the randomizer (EXPERIMENTAL)

- **GUI:** tick "Randomize world-map loading zones".
- **Command line:** `py randomizer.py run <iso> --seed N --randomize-world-zones`
- **JSON:** Export writes the current layout:

  ```json
  "_randomize_world_zones": false,
  "_world_zones": { "River Belle Path": "River Belle Path", "Goblin Wall": "Goblin Wall", ... },
  "_world_zone_choices": [ "River Belle Path", "Goblin Wall", ... ]
  ```

  Each key is a node, and each value is the dungeon it leads to. Change a
  value to any name in `_world_zone_choices` to place that dungeon there.
  An entry naming the node's own dungeon means "no preference".
  - Without `_randomize_world_zones`, the rest of the map is completed so
    each dungeon appears exactly once. If one node is changed and nothing
    else is, the result is a swap.
  - With `_randomize_world_zones: true`, the dungeons you didn't place are
    shuffled among the remaining nodes.

The layout is written to the spoiler file. The source ISO's zones must still
be vanilla; re-applying the same layout does nothing.

**Stage-key locks follow the dungeons.** Each dungeon's key check moves to
the call of the node it now sits on, using that node's own `MJ_SWING`
variant. The node that hosts River Belle Path (never locked) is left open.

**Not for Archipelago seeds.** The apworld's logic assumes each dungeon is
at its vanilla node.

**Code:** `worldzones.py` (`apply_plan`, `status`, `random_plan`,
`complete_plan`, `stage_lock_sites`).

---

## 1. `world.cft`

### Display and loading-zone blocks (in `mainBasha`)

Each node has a **display block** (arguments to `WM_mapInfoDispOn`: the name
and Myrrh bubble) and a **zone block** (arguments to its `MJ_SWING_*` call:
which stage loads, and its music). Copy D's blocks over node N's.

```
display  03 000000 DD  03 000000 EE                      DD = display index, EE = elements shown
zone     05 000000 XX  03 000000 00  03 000000 MM  03 000000 NN  03 000001 YY  03 000000 ZZ
         XX = stage script (STR index), MM/NN = music, YY/ZZ = unknown (both rise by 1 per stage)
```

The node's `MJ_SWING_*` call is 40 bytes after the start of its zone block
(after two more `03 00000000` pushes).

| Dungeon | Display @ | DD | EE | Zone @ | XX | MM | NN | YY | ZZ | Call | Variant |
|---|---|---|---|---|---|---|---|---|---|---|---|
| River Belle Path | `0x46217` | 00 | 06 | `0x46246` | 89 | 96 | 64 | 68 | 0D | `0x4626E` | ATTRIB_2 |
| Goblin Wall | `0x4717B` | 01 | 09 | `0x471AA` | 8C | A6 | 74 | 69 | 0D | `0x471D2` | ATTRIB_2 |
| Mine of Cathuriges | `0x487F7` | 02 | 01 | `0x48826` | 92 | A4 | 72 | 6A | 6E | `0x4884E` | ATTRIB_1 |
| Mushroom Forest | `0x48928` | 03 | 02 | `0x48957` | 93 | AE | 7C | 6B | 6F | `0x4897F` | ATTRIB_1 |
| Tida | `0x4A041` | 04 | 0C | `0x4A070` | 99 | B8 | 86 | 6C | 70 | `0x4A098` | ATTRIB_2 |
| Moschet Manor | `0x4A877` | 05 | 03 | `0x4A8A6` | 9B | 9F | 6D | 6D | 71 | `0x4A8CE` | ATTRIB_2 |
| Veo Lu Sluice | `0x4B190` | 09 | 00 | `0x4B1BF` | 9E | B5 | 83 | 6E | 72 | `0x4B1E7` | PADCHECK |
| Selepation Cave | `0x4BF2B` | 08 | 04 | `0x4BF5A` | A2 | B6 | 84 | 6F | 73 | `0x4BF82` | ATTRIB_1 |
| Daemon's Court | `0x4C7CE` | 07 | 00 | `0x4C7FD` | A4 | A5 | 73 | 70 | 74 | `0x4C825` | PADCHECK |
| Conall Curach | `0x4D000` | 0B | 00 | `0x4D02F` | A6 | 9A | 68 | 73 | 77 | `0x4D057` | PADCHECK |
| Rebena Te Ra | `0x4D66E` | 0C | 00 | `0x4D69D` | A7 | B7 | 85 | 74 | 78 | `0x4D6C5` | PADCHECK |
| Lynari Desert | `0x4E45E` | 0A | 08 | `0x4E48D` | AD | AA | 78 | 72 | 76 | `0x4E4B5` | ATTRIB_1 |

Variants: `MJ_SWING_ATTRIB_2` (function 594) is for 2-element nodes,
`MJ_SWING_ATTRIB_1` (595) for 1-element nodes, and `MJ_SWING_PADCHECK` (593)
for the rest. For reference, Mount Kilanda's display index is 06 and Mount
Vellenge's is 0D.

### Myrrh-drop completion check (1- and 2-element nodes)

`MJ_SWING_ATTRIB_1` and `_2` each have a switch on the node's world param.
Each case stores the dungeon's **completion flag** into `this[40]` and later
reads event flag `sysval[-2547 + this[40]]`, i.e. **event flag number
`this[40]`**, which the engine sets when the dungeon is cleared.

**Completion flag = 200 + the dungeon's display index (DD).** All 8 values
used in vanilla fit this rule, and so does Mount Vellenge (D5):

| Flag | Dungeon | Flag | Dungeon |
|---|---|---|---|
| C8 | River Belle Path | CF | Daemon's Court |
| C9 | Goblin Wall | D0 | Selepation Cave |
| CA | Mine of Cathuriges | D1 | Veo Lu Sluice |
| CB | Mushroom Forest | D2 | Lynari Desert |
| CC | Tida | D3 | Conall Curach |
| CD | Moschet Manor | D4 | Rebena Te Ra |
| CE | Mount Kilanda | D5 | Mount Vellenge |

When D goes on an ATTRIB node, write D's flag at the node's case:

| Node | Byte @ | Vanilla |
|---|---|---|
| River Belle Path (ATTRIB_2) | `0x33146` | C8 |
| Goblin Wall (ATTRIB_2) | `0x3318D` | C9 |
| Tida (ATTRIB_2) | `0x331D4` | CC |
| Moschet Manor (ATTRIB_2) | `0x3321B` | CD |
| Mushroom Forest (ATTRIB_1) | `0x33486` | CB |
| Mine of Cathuriges (ATTRIB_1) | `0x334C1` | CA |
| Selepation Cave (ATTRIB_1) | `0x334FC` | D0 |
| Lynari Desert (ATTRIB_1) | `0x33537` | D2 |

Each case's structure, for reference (River Belle Path node):

```
3A  03 000000 02  2C  08 <next>  0C             switch case: world node 0x02
01 00002819  03 000000 C8  0D 0C                this[40] = completion flag
01 00002919  03 000000 02  0D 0C                this[41] = offered element 1
01 00002A19  03 000000 04  0D 0C                this[42] = offered element 2 (ATTRIB_2 only)
01 00002B19  03 0000013B   0D 0C                this[43] = world.cfd display template
07 <exit>
```

## 2. `world.cfd`: post-clear menu name (1- and 2-element nodes)

**Name value = 0x20 + the dungeon's display index**:

| Value | Dungeon | Value | Dungeon |
|---|---|---|---|
| 20 | River Belle Path | 27 | Daemon's Court |
| 21 | Goblin Wall | 28 | Selepation Cave |
| 22 | Mine of Cathuriges | 29 | Veo Lu Sluice |
| 23 | Mushroom Forest | 2A | Lynari Desert |
| 24 | Tida | 2B | Conall Curach |
| 25 | Moschet Manor | 2C | Rebena Te Ra |
| 26 | Mount Kilanda | 2D | Mount Vellenge |

| Node | Byte @ | Vanilla |
|---|---|---|
| River Belle Path | `0x13A6B` | 20 |
| Goblin Wall | `0x13AD9` | 21 |
| Tida | `0x13B47` | 24 |
| Moschet Manor | `0x13BB5` | 25 |
| Mushroom Forest | `0x13C06` | 23 |
| Mine of Cathuriges | `0x13C56` | 22 |
| Selepation Cave | `0x13CA6` | 28 |
| Lynari Desert | `0x13CF7` | 2A |

## 3. The dungeon's exits

Every exit in D's own `.cft` files names the world param of the node the
caravan returns to. Change D's param to node N's everywhere, or the world
map desyncs from where the caravan is and it can't move.

World params: River Belle Path `02`, Goblin Wall `07`, Mine of Cathuriges
`10`, Mushroom Forest `11`, Tida `17`, Moschet Manor `1A`, Veo Lu Sluice
`21`, Selepation Cave `2B`, Daemon's Court `2E`, Conall Curach `34`, Rebena
Te Ra `36`, Lynari Desert `51`.

Two patterns (`ID` = the world param):

```
stage exit      01 00 00 3D 09 03 00 00 00 ID 0D 0C 04 00 00 00 00 0A FF FF 00 28 0C
post-boss exit  03 00 00 00 ID 0D 0C 03 00 00 00 1E 0A FF FF 00 01 0C
```

Every area file has stage exits, **including boss rooms**, and the boss room
also has the post-boss exit. `worldzones.py` finds them all by pattern scan.
The offsets of the ID byte:

| Dungeon | Stage exits | Boss room |
|---|---|---|
| River Belle Path | river_0 `0x2C57F`, `0x344D6` | river_1 `0x262C1`, `0x33600`; post-boss `0x54A9F` |
| Goblin Wall | gob_0 `0x29F2F`, `0x32096`; gob_1 `0x312A6` | gob_2 `0x347E1`; post-boss `0x57C09` |
| Mine of Cathuriges | mine_0 `0x297D7`, `0x31786`; mine_1 `0x2F916`; mine_2 `0x2FA86` | mine_3 `0x35522`; post-boss `0x58F1F` |
| Mushroom Forest | kinoko_0 `0x2CB53`, `0x34B16` | kinoko_1 `0x34EAD`; post-boss `0x58042` |
| Tida | ruin_0 `0x2BA42`, `0x33A20`; ruin_1 `0x32880` | ruin_2 `0x34AE2`; post-boss `0x59202` |
| Moschet Manor | gigas_0 `0x279D9`, `0x2FCE6`; gigas_1 `0x28D16`; gigas_2 `0x2AEF6`; gigas_3 `0x2AF86`; gigas_4 `0x2B6F6`; gigas_5 `0x2A2B6`; gigas_6 `0x2BB86`; gigas_7 `0x29FA6` | gigas_8 `0x34E89`; post-boss `0x5B9ED` |
| Veo Lu Sluice | water_0 `0x2D6B3`, `0x355C6` | water_1 `0x341A3`; post-boss `0x5900E` |
| Selepation Cave | cave_0 `0x2A63F`, `0x32776`; cave_1 `0x2EED6` | cave_2 `0x336C7`; post-boss `0x594DB` |
| Daemon's Court | fort_0 `0x2B057`, `0x32F36` | fort_1 `0x35CA5`; post-boss `0x5A25E` |
| Conall Curach | swamp_0 `0x28AB3`, `0x30AB6`; swamp_1 `0x30EF6`; swamp_2 `0x2F146` | swamp_3 `0x341DB`; post-boss `0x592C1` |
| Rebena Te Ra | city_0 `0x2B68B`, `0x338B6`; city_1 `0x338F6` | city_2 `0x35721`; post-boss `0x59D9B` |
| Lynari Desert | desert_0 `0x29ADB`, `0x31D56`; desert_1 `0x2EAB6` | desert_2 `0x349D6`; post-boss `0x5A848` |

River Belle Path's boss room is the only one with two stage exits.

## Worked example: swap River Belle Path and Conall Curach

This is exactly what `worldzones.py` writes for this swap (checked against
the disc):

- `world.cft`:
  - River Belle Path node: display → `03 000000 0B 03 000000 00`, zone →
    Conall Curach's (`05 000000 A6 … 03 000000 77`), completion byte
    `0x33146` C8 → **D3**.
  - Conall Curach node: display and zone → River Belle Path's. It's a
    PADCHECK node, so there's no completion byte.
- `world.cfd`: `0x13A6B` 20 → **2B** (Conall Curach).
- Conall Curach's exits `34` → `02`: swamp_0 `0x28AB3`, `0x30AB6`; swamp_1
  `0x30EF6`; swamp_2 `0x2F146`; swamp_3 `0x341DB`, `0x592C1`.
- River Belle Path's exits `02` → `34`: river_0 `0x2C57F`, `0x344D6`;
  river_1 `0x262C1`, `0x33600`, `0x54A9F`.

## Corrections to earlier notes

- **Completion flags:** Veo Lu Sluice is **D1** and Mount Kilanda **CE**. Earlier notes had them swapped. The worked example's ATTRIB edit is **C8 → D3**, not "20 → 2B".
- **Menu names:** Conall Curach is **2B** and Rebena Te Ra **2C**. Value `28` is Selepation Cave, not the Mine.
- **Display offsets:**
  - Selepation Cave is `0x4BF2B` (not `0x4BF1B`).
  - Daemon's Court is `0x4C7CE` (not `0x4C7DE`).
  - Lynari Desert is `0x4E45E` (not `0x4E46E`).
- **Daemon's Court exit:** its second exit is `0x32F36` (not `0x322F36`).
- **Post-boss exit pattern:** it has a `0D` store before the `0C`.
- **Boss-room stage exits:** boss rooms also contain ordinary stage exits, which need patching too.

## Stage keys and Mount Kilanda (fixed)

Earlier versions of the stage-key feature listed Mount Kilanda's lock site
as `0x4E33A` (stage id 172). That call is actually a **Leuda** stop
(`thief_0`), so Leuda asked for the Kilanda Key and Mount Kilanda wasn't
locked.

Mount Kilanda is entered through four 4-argument `MJ_SWING` calls (STR 174,
181, 184, 187 at `0x4E931`, `0x4F1E7`, `0x4F675`, `0x4FA83`), which the main
8-argument dispatcher (`encountKaido`) can't take. They now have their own
dispatcher: `world.cft`'s copy of the library function `dropItem_fromNpc`
(function 426), which the world map never calls, is rewritten to take 4
arguments, check the Kilanda Key (`0xEE`), and forward them to `MJ_SWING`
(592). All four entrances call it instead. The Leuda stop is left vanilla,
and an ISO made with the old version gets it put back. See
`_patch_kilanda_and_leuda()` in `randomizer.py`.

## World-map buildings (icons)

Each world-map stop's building is a flat card (picture plus ground shadow):
one mesh part in `dvd/map/stg033/map000_0.mpl`. Its picture is one 128x128
cell of a 4x4 plate texture in `map000_0.mtx`: material 4 = `w7_plate`
(plate 1), material 5 = `w13_plate2` (plate 2). The part's UVs pick the cell.
They are signed 16-bit with 1024 = one texture width (256 = one cell), and v
is negative and wraps:

    col = (u % 1024) // 256
    row = 3 - ((-v_max // 256) % 4)

`Start.dol`'s crest table (DOL offset `0x1D8214`, RAM `0x801DB214`, also used
by the save screen) lists each place's cell as `[plate, col, row, 0]`, indexed
by the dungeon's display index DD. Mesh part per stop:

| Stop | Part | Stop | Part |
|---|---|---|---|
| River Belle Path | 3 | Veo Lu Sluice | 12 |
| Goblin Wall | 25 | Selepation Cave | 16 |
| Mine of Cathuriges | 7 | Daemon's Court | 17 |
| Mushroom Forest | 5 | Conall Curach | 18 |
| Tida | 10 | Rebena Te Ra | 19 |
| Moschet Manor | 11 | Lynari Desert | 22 |

To show another dungeon's building, shift all of the part's UVs by the cell
difference (`u += dcol*256`, `v += drow*256`) and, if the cell is on the
other plate, set the display list's material (first 2 bytes of its `DLST`)
to 4 or 5. The file size doesn't change. `worldzones.apply_icons()` does this
for a zone plan, and `icon_status()` reads back which building each stop shows.
Confirmed in game (Tipa's stop showing River Belle Path's building).
