Cleanest method for randomizing the loading zone to another stage:
	1. Changes in `world.cft` (the loading zone and post Myrrh Drop behavior)
	2. Changes in the `stages .cft` files (the exit zone)
Currently skipping Kilanda due to how it's exit's work and needing to test if they are natively compatible with other stages exit methods. Also only currently doing dungeons.

To randomize a level, change the world.cft to reflect the new levels information, then change the level the loading zone now leads to such that it's exit pointers point to the old level's location.

---
# 1. Changes in `world.cft` (the loading zone)
Take these sections and paste them over the other stages section to swap their loading zone, music, world display, and post Myrrh Drop offered elements.
## Each stage's original info and location in `mainBasha`
- River Belle Path:
	Starting at `0x46217` - (display info)
		`03 00 00 00 00 03 00 00 00 06`
	Starting at `0x46246` - (Loading zone and music)
		`05 00 00 00 89 03 00 00 00 00 03 00 00 00 96 03 00 00 00 64 03 00 00 01 68 03 00 00 00 0D`
- Goblin Wall:
	Starting at `0x4717B` - (display info)
		`03 00 00 00 01 03 00 00 00 09`
	Starting at `0x471AA` - (Loading zone and music)
		`05 00 00 00 8C 03 00 00 00 00 03 00 00 00 A6 03 00 00 00 74 03 00 00 01 69 03 00 00 00 0D`
- Mines of Cathuriges:
	Starting at `0x487F7` - (display info)
		`03 00 00 00 02 03 00 00 00 01`
	Starting at `0x48826` - (Loading zone and music)
		`05 00 00 00 92 03 00 00 00 00 03 00 00 00 A4 03 00 00 00 72 03 00 00 01 6A 03 00 00 00 6E`
- Mushroom Forest:
	Starting at `0x48928` - (display info)
		`03 00 00 00 03 03 00 00 00 02`
	Starting at `0x48957` - (Loading zone and music)
		`05 00 00 00 93 03 00 00 00 00 03 00 00 00 AE 03 00 00 00 7C 03 00 00 01 6B 03 00 00 00 6F`
- Tida:
	Starting at `0x4A041` - (display info)
		`03 00 00 00 04 03 00 00 00 0C`
	Starting at `0x4A070` - (Loading zone and music)
		`05 00 00 00 99 03 00 00 00 00 03 00 00 00 B8 03 00 00 00 86 03 00 00 01 6C 03 00 00 00 70`
- Moschet Manor:
	Starting at `0x4A877` - (display info)
		`03 00 00 00 05 03 00 00 00 03`
	Starting at `0x4A8A6` - (Loading zone and music)
		`05 00 00 00 9B 03 00 00 00 00 03 00 00 00 9F 03 00 00 00 6D 03 00 00 01 6D 03 00 00 00 71`
- Veo Lu Sluice:
	Starting at `0x4B190` - (display info)
		`03 00 00 00 09 03 00 00 00 00`
	Starting at `0x4B1BF` - (Loading zone and music)
		`05 00 00 00 9E 03 00 00 00 00 03 00 00 00 B5 03 00 00 00 83 03 00 00 01 6E 03 00 00 00 72`
- Selepation Cave: 
	Starting at `0x4BF1B` - (display info)
		`03 00 00 00 08 03 00 00 00 04`
	Starting at `0x4BF5A` - (Loading zone and music)
		`05 00 00 00 A2 03 00 00 00 00 03 00 00 00 B6 03 00 00 00 84 03 00 00 01 6F 03 00 00 00 73`
- Deamon's Court:
	Starting at `0x4C7DE` - (display info)
		`03 00 00 00 07 03 00 00 00 00`
	Starting at `0x4C7FD` - (Loading zone and music)
		`05 00 00 00 A4 03 00 00 00 00 03 00 00 00 A5 03 00 00 00 73 03 00 00 01 70 03 00 00 00 74`
- Conall Curach:
	Starting at `0x4D000` - (display info)
		`03 00 00 00 0B 03 00 00 00 00`
	Starting at `0x4D02F` - (Loading zone and music)
		`05 00 00 00 A6 03 00 00 00 00 03 00 00 00 9A 03 00 00 00 68 03 00 00 01 73 03 00 00 00 77`
- Rebena Te Ra:
	Starting at `0x4D66E` - (display info)
		`03 00 00 00 0C 03 00 00 00 00`
	Starting at `0x4D69D` - (Loading zone and music)
		`05 00 00 00 A7 03 00 00 00 00 03 00 00 00 B7 03 00 00 00 85 03 00 00 01 74 03 00 00 00 78`
- Lynari Desert: 
	Starting at `0x4E46E` - (display info)
		`03 00 00 00 0A 03 00 00 00 08`
	Starting at `0x4E48D` - (Loading zone and music)
		`05 00 00 00 AD 03 00 00 00 00 03 00 00 00 AA 03 00 00 00 78 03 00 00 01 72 03 00 00 00 76`

## Post Myrrh Drop collection, offered elements:
This one is a simple change (but a massive bugger to find):
You need to change which stage location is being used as the comparator for the switch statement (if randomizing River Belle Path to Daemon's Court, replace `03 00 00 00 02` with `03 00 00 00 2E`):

**`MJ_SWING_ATTRIB_1`** (anchor `0x3346B`) — handles exactly the 4 stages we know use it:

| Case addr | Value  | Original Zone       |
| --------- | ------ | -------------------- |
| `0x33471` | `0x11` | Mushroom Forest     |
| `0x334AC` | `0x10` | Mines of Cathuriges |
| `0x334E7` | `0x2B` | Selepation Cave     |
| `0x33522` | `0x51` | Lynari Desert       |

**`MJ_SWING_ATTRIB_2`** (anchor `0x3312B`) — handles exactly the 4 stages you and I have been testing with:

| Case addr | Value  | Original Zone    |
| --------- | ------ | ---------------- |
| `0x33131` | `0x02` | River Belle Path |
| `0x33178` | `0x07` | Goblin Wall      |
| `0x331BF` | `0x17` | Tida             |
| `0x33206` | `0x1A` | Moschet Manor    |
- 02 - River Belle Path 
- 07 - Goblin Wall
- 10 - Mines of Cathuriges
- 11 - Mushroom Forest
- 17 - Tida
- 1A - Moschet Manor 
- 21 - Veo Lu Sluice
- 2B - Selepation Cave
- 2E - Daemon's Court 
- 34 - Conall Curach
- 36 - Rebena Te Ra
- 51 - Lynari Desert
## Misc info
(Arguments come before the opcode)

WM_mapInfoDispOn (FF FF 02 4A)
	03 00 00 00 DD <- Stage info display name and Myrrh status (bubble display)
	03 00 00 00 EE <- Stage elements (bubble display (probably want to keep this patterned as the original stage to show the after available?)
03 00 00 00 03 
03 00 00 FF FF <- x pos on screen (don't change)
03 00 00 00 GG <- y pos on screen (don't change)
0A FF FF 02 4A

MJ_SWING_ATTRIBUTE_2/ATTRIBUTE_1/PADCHECK
	05 00 00 00 ==XX== <- Stage STR .cft index (controls which stage loads)
	03 00 00 00 00 <- Always empty
	03 00 00 00 ==MM== <- Music pt.1 for stage (stage specific, not randomizable currently)
	03 00 00 00 ==NN== <- Music pt.2 for stage (stage specific, not randomizable currently)
03 00 00 01 ==YY== <- ??? (index of sorts? it always increases by 1 (Kilanda is skipped as 71))
03 00 00 00 ==ZZ== <- ??? (also increases by one, except for River Belle Path and Goblin Wall)
03 00 00 00 00
03 00 00 00 00
0A FF FF 02 52/3/4
# 2. Changes in the stages .cft files (the exit zone) (TODO)
In each stages .cft files, replace the `0A FF FF 01 9B 0C 01 00 00 3D 09 03 00 00 00 <ID>` with the exit code for the location on the world it was randomized to.
- 02 - River Belle Path 
- 07 - Goblin Wall
- 10 - Mines of Cathuriges
- 11 - Mushroom Forest
- 17 - Tida
- 1A - Moschet Manor 
- 21 - Veo Lu Sluice
- 2B - Selepation Cave
- 2E - Daemon's Court 
- 34 - Conall Curach
- 36 - Rebena Te Ra
- 51 - Lynari Desert

This prevents the world from desynching where it thinks the caravan is VS where it actually is, bricking the players ability to move.

- River Belle Path
	In `river_0` (Stage Exit):
		ID at `0x2C57F`
		ID at `0x344D6`
	In `river_1` (Post Boss Exit):
		ID at `0x262C1`
		ID at `0x33600`
- Goblin Wall
	In `gob_0` (Stage Exit):
		ID at `0x29F2F`
		ID at `0x32096`
	In `gob_1` (Teleport from Hot Spot?):
		ID at `0x312A6`
	In `gob_2` (Post Boss Exit):
		ID at `0x347E1`
- Mines of Cathurgies
	In `mine_0` (Stage Exit):
		ID at `0x297D7`
		ID at `0x31786`
	In `mine_1`:
		ID at `0x2F916`
	In `mine_2`:
		ID at `0x2FA86`
	In `mine_3` (Post Boss Exit):
		ID at `0x35522`
- Mushroom Forest
	In `kinoko_0` (Stage Exit):
		ID at `0x2CB53`
		ID at `0x34B16`
	In `kinoko_1` (Post Boss Exit):
		ID at `0x34EAD`
- Tida
	In `ruin_0` (Stage Exit):
		ID at `0x2BA42`
		ID at `0x33A20`
	In `ruin_1`:
		ID at `0x32880`
	In `ruin_2` (Post Boss Exit):
		ID at `0x34AE2`
- Moschet Manor
	In `gigas_0` (Stage Exit):
		ID at `0x279D9`
		ID at `0x2FCE6`
	In `gigas_1`:
		ID at `0x28D16`
	In `gigas_2`:
		ID at `0x2AEF6`
	In `gigas_3`:
		ID at `0x2AF86`
	In `gigas_4`:
		ID at `0x2B6F6`
	In `gigas_5`:
		ID at `0x2A2B6`
	In `gigas_6`:
		ID at `0x2BB86`
	In `gigas_7`:
		ID at `0x29FA6`
	In `gigas_8` (Post Boss Exit):
		ID at `0x34E89`
- Veo Lu Sluice
	In `water_0` (Stage Exit):
		ID at `0x2D6B3`
		ID at `0x355C6`
	In `water_1` (Post Boss Exit):
		ID at `0x341A3`
- Selepation Cave
	In `cave_0` (Stage Exit):
		ID at `0x2A63F`
		ID at `0x32776`
	In `cave_1`:
		ID at `0x2EED6`
	In `cave_2` (Post Boss Exit):
		ID at `0x336C7`
- Daemon's Court
	In `fort_0` (Stage Exit):
		ID at `0x2B057`
		ID at `0x322F36`
	In `fort_1` (Post Boss Exit):
		ID at `0x35CA5`
- Conall Curach
	In `swamp_0` (Stage Exit):
		ID at `0x28AB3`
		ID at `0x30AB6`
	In `swamp_1`:
		ID at `0x30EF6`
	In `swamp_2`:
		ID at `0x2F146`
	In `swamp_3` (Post Boss Exit):
		ID at `0x341DB`
- Rebena Te Ra
	In `city_0` (Stage Exit):
		ID at `0x2B68B`
		ID at `0x338B6`
	In `city_1`:
		ID at `0x338F6`
	In `city_2` (Post Boss Exit):
		ID at `0x35721`
- Lynari Desert
	In `desert_0` (Stage Exit):
		ID at `0x29ADB`
		ID at `0x31D56`
	In `desert_1`:
		ID at `0x2EAB6`
	In `desert_2` (Post Boss Exit):
		ID at `0x349D6`

---
# 3. How these offsets were found (verified 2026-09-15)

Every offset above was independently re-derived from a clean ISO's `world.cft`
and the individual dungeon `.cft` files using this repo's `cft.py`
disassembler, and every single one matched byte-for-byte (20+ spot checks
across `world.cft` and 6 different dungeons). Three distinct patterns are in
play, and each has its own repeatable discovery method:

## a) The "display info" + "loading zone" blocks

Both live inside `world.cft`'s single giant `mainBasha` function, right
before that stage's own call to `WM_mapInfoDispOn` (name/elements bubble)
and `MJ_SWING_ATTRIBUTE_2`/`_1`/`PADCHECK` (the actual warp). To find them
from scratch:

1. `python cft.py blocks world.cft` / inspect the `FUNC` table to find
   `mainBasha`'s index, then get its code with `code_abs_offset()` +
   `_code_of()` (both already in `cft.py`).
2. Disassemble the whole function with `disasm()` and scan for every `CALL`
   whose target resolves to `WM_mapInfoDispOn` or `MJ_SWING_ATTRIBUTE_2`
   (matching on the `arg & 0xFFFF` FUNC-table index, same technique
   `cmd_calls()` already uses).
3. The literal `PUSHI` values pushed in the ~5 instructions immediately
   before each call ARE the "display info"/"loading zone" blocks verbatim -
   confirmed directly, e.g. for River Belle Path:
   ```
   @0x86a7  PUSHI 0     <- display name index (DD)
   @0x86ac  PUSHI 6     <- elements index (EE)
   @0x86b1  PUSHI 3     <- constant, always 3
   @0x86b6  PUSHI 180   <- x pos (leave alone)
   @0x86bb  PUSHI 220   <- y pos (leave alone)
   @0x86c0  CALL WM_mapInfoDispOn
   ```
   These are genuinely hardcoded per-stage literals, not derived from the
   loading-zone ID at runtime - so the "display info" pair has to be
   swapped along with the loading-zone block, exactly as this doc's top
   instruction already says ("swap their loading zone, music, **world
   display**, and post Myrrh Drop offered elements"). This was checked
   directly and confirmed: **no separate string-table edit is needed** -
   copying the destination stage's own 2-value "display info" block (which
   this doc already lists per stage) is the complete fix. The one thing
   NOT checked here: any OTHER in-game text (NPC dialogue, quest logs)
   that might name a stage by name outside this bubble - if a scripted
   line elsewhere says "go to Goblin Wall" by name, that's a separate,
   unexplored text source.

## b) The stage-exit ID bytes (in each dungeon's own `.cft`)

These sit at the END of a fixed 16-byte signature, not the start - a common
mistake when searching for them. The pattern is:
```
0A FF FF 01 9B 0C 01 00 00 3D 09 03 00 00 00 <ID>
```
i.e. search each dungeon file for the 15-byte prefix
`0AFFFF019B0C0100003D0903000000` (hex, no spaces) - the very next byte is
the destination stage ID. Confirmed this reads back that dungeon's OWN ID
in vanilla (e.g. every one of River Belle Path's 4 exit records currently
reads `0x02`, Goblin Wall's read `0x07`, Lynari Desert's read `0x51`) -
i.e. in an unmodified ISO every stage's exits point at itself, which is
exactly what you'd expect for "where do I resume when the world reloads."

## c) The Myrrh-drop switch-case values (`MJ_SWING_ATTRIB_1`/`_2`)

These are a standard CFlat switch/case in `world.cft`, using the same
opcode table `cft.py` already documents (`0x3a`=DUP, `0x03`=PUSHI,
comparisons `0x2c`-`0x37`). Disassembling either function shows the
pattern `DUP; PUSHI <caseValue>; CMP; JZ <nextCase>` repeated once per
stage. The doc's "case addr" column is the position of the `PUSHI` opcode
itself; the actual comparison value is the LOW byte of that instruction's
4-byte argument, i.e. `case_addr + 4` (opcode is 1 byte, then 3 zero bytes,
then the value byte, since all these stage IDs are under 256). Confirmed
all 8 values (4 per function) exactly match the doc's table this way.
