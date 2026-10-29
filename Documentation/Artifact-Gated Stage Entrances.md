# Artifact-Gated Stage Entrances

Worked example: entering Goblin Wall from the world map
requires owning a specific artifact ("Gob Key", item `0xE9`). No key, no
entry - the world map just doesn't let the transition happen. This document
is the full recipe: every file touched, every byte changed, and why each
step was necessary. It covers **one** stage (Goblin Wall); the randomizer's
`_stage_key_locks` option applies the same technique to the other dungeons
(see "Generalizing to all stages" at the end).

Five changes were needed: one new item, one chest edit, and three separate
edits to the world map's own script file (`world.cft`) plus one single
instruction changed in the game's own executable (`Start.dol`). All of it
can be done with this repo's existing tools (`cft.py`, `lootcft.py`,
`customitem.py`, `gciso.py`) plus some hand-written script bytecode.

## 1. Make the key artifact a real, valid item

`customitem.py` can turn any of the game's ~20 unused artifact-ID slots
(`0xE8`-`0xFE`) into a real item. This example uses `0xE9`, cloned from an
existing real artifact ("Earth Pendant") rather than leaving it as an empty
placeholder:

```
py customitem.py add "game.iso" 0xE9 "Gob Key" --like "Earth Pendant"
```

This edits two files inside the ISO: `param.cfd` (the item's stats/type
record - cloning gives it a real `type`/`model`/`gil` instead of the
all-zero placeholder every unused slot starts with) and `c_system.cfd` (the
display name strings). **Cloning matters**: if the slot is left as an
empty placeholder record, chests silently refuse to drop the item at all,
in every dungeon - the game's reward logic appears to skip items whose
record looks unpopulated. Real artifact data fixes this.

## 2. Put it somewhere the player can actually find it

For testing, every treasure record in River Belle Path's own script file
(`river_0.cft`) was pointed at item `0xE9`:

```python
import lootcft
slots = lootcft.find_item_slots('river_0.cft', valid=lootcft._valid_item)
lootcft.apply_edits('river_0.cft', {off: 0xE9 for off, _ in slots})
```

For a real feature you'd only touch the specific chest(s)/monster drop(s)
meant to hold this particular key, in whichever OTHER dungeon(s) it should
come from - not every chest in one dungeon like this test did.

**Note on how FFCC's artifact system actually works**: artifacts aren't
picked up instantly like a normal item. Finding one in a dungeon adds it to
a temporary "Treasures" list; only when you clear the dungeon and beat its
boss do you choose ONE candidate from that list to keep permanently. This
is normal, vanilla behavior for all 73 real artifacts, and the new key
behaves the same way.

## 3. Free up some dead code to build the gate check in

The world map's own script file, `world.cft`, has a function called
`WM_MoveEnd` that runs every time the player finishes moving on the world
map. Among other things, it used to call another function, `encountKaido`,
to roll a random overworld monster encounter.

Disable that specific call by replacing the 5-byte `CALL` instruction
with a harmless "push zero" instruction (`WM_MoveEnd` immediately discards
whatever `encountKaido` returns, so this is a safe, no-op-equivalent swap):

- File offset `0x387C0` in `world.cft`
- Before: `0A FF FF 02 56` (call function #598, `encountKaido`)
- After: `03 00 00 00 00` (push the literal 0)

This has an observable side effect worth knowing about: it turns off *that
one* random-encounter trigger on the world map. In testing this didn't
seem to break anything else, but it's a real behavior change, not just an
implementation detail.

With that call gone, `encountKaido` itself is never invoked from its
original spot - freeing its ~18,000 bytes of now-unused code to become our
gate-check function.

## 4. Rewrite that dead code into the actual gate check

`encountKaido`'s body was overwritten with new logic (still well within its
original 18,000-byte budget, so no file resizing was needed):

> if the player has item `0xE9`: do what the original "confirm travel to
> Goblin Wall" call would have done, using the same inputs
> otherwise: do nothing (silently refuse the travel)

Concretely, this calls a built-in game function, `checkCaravanItem(0, 2,
0xE9)`, which asks "does slot-0 player have item `0xE9`?" and returns 2
(yes) or 0 (no). If yes, it re-forwards to the game's own original
`MJ_SWING_ATTRIB_2` function (the one that actually performs "confirm and
travel to Goblin Wall"), passing through the same 8 arguments Goblin Wall's
own entry always used. If no, it just returns a dummy value and stops -
same as it does today for every OTHER call site checkCaravanItem was never
meant to intercept.

Two bookkeeping fields on `encountKaido` itself also had to change, since
it now receives 8 arguments (forwarded straight through to the real travel
function) instead of the 0 it used to declare:

- Its declared argument count (`INFO` tag) : `0` -> `8`
- Its declared local-variable count (`VAL` tag's own header field) : `0` -> `8`

Getting the second one wrong would have been a real, silent, hard-to-debug
bug (it controls where the function's stack starts, not just how it's
labeled) - this isn't cosmetic metadata.

## 5. Point Goblin Wall's own entry at the new gate check

The world map's `mainBasha` function has one call, specific to Goblin Wall,
that used to go straight to "confirm and travel there." That one call was
redirected to the new gate-check function instead - a one-byte change
(only the target function's index number changes; everything about how the
call is made stays the same):

- File offset `0x471D2` in `world.cft`
- Before: `0A FF FF 02 52` (call function #594, `MJ_SWING_ATTRIB_2` directly)
- After: `0A FF FF 02 56` (call function #598, the new `encountKaido`)

Every other stage's own "confirm and travel" call is completely untouched
- only Goblin Wall's is rerouted.

## 6. The one change inside the game's executable itself

This step is required, not optional.
`checkCaravanItem` (the "does the player have item X" check from step 4)
turned out to only search the first 64 of the player's inventory slots.
Artifacts - including the new key - are stored further along in that same
list, past slot 64, so the check could never see them, no matter how
correctly the key was granted. This is a real limitation of the compiled
game code, not a bug in any of the script edits above.

The fix is one instruction in the game's own executable (`Start.dol`),
located by tracing the check with a live debugger:

- `Start.dol` file offset `0x913fc`
- Before: `38 00 00 08` (an internal loop-count value of 8, which covers 64
  items total - the check works in batches of 8)
- After: `38 00 00 14` (a loop-count of 20, covering 160 items - the
  original 64 regular-item slots plus every one of the game's 96 permanent
  artifact slots)

This is the only change in this whole recipe that lives in the game's
executable rather than in a data/script file. **It only needs to be applied
once** - it fixes the underlying check itself, so every stage that's ever
gated this way (not just Goblin Wall) benefits from the same single patch.

## Generalizing to all stages

The recipe above gates a single stage. Gating more stages means giving each
stage-entry point in `mainBasha` its own version of steps 4-5. The
randomizer's `_stage_key_locks` option (`patch_stage_key_locks()` in
`randomizer.py`) gates 13 dungeons with one shared function instead of 13
repurposed ones: every `mainBasha` entrance call already pushes a unique
per-site stage id as its first argument, so `encountKaido`'s new body
switches on that id, checks that dungeon's key, and forwards the 8 original
arguments to that site's original `MJ_SWING` variant. Mount Kilanda is the
exception - it is entered through four 4-argument `MJ_SWING` calls, so
world.cft's unused copy of `dropItem_fromNpc` is rewritten into a separate
4-argument dispatcher for it. River Belle Path is always left open. The
`Start.dol` fix from step 6 is shared by all of them. See `STAGE_KEYS`,
`_STAGE_LOCK_SITES` and `_KILANDA_SITES` in `randomizer.py` for the key IDs,
call-site offsets and stage ids.

Note: the `mainBasha` call at `0x4E33A` (stage id 172, `thief_0`) is a Leuda
stop, not Mount Kilanda - don't gate it as Kilanda.

### Element menus stay open

Stops with an element menu (`MJ_SWING_ATTRIB_1` for one element: the Mine,
Mushroom Forest, Selepation Cave, Lynari Desert; `MJ_SWING_ATTRIB_2` for two:
River Belle Path, Goblin Wall, Tida, Moschet Manor) let the player change the
chalice's element or enter. In the game the menu only shows once the stage
has been cleared (`if (evtFlag[this.m40])`, the stage's Myrrh flag 200+n),
otherwise A goes straight in. If the key check guarded the whole stop, an
element could only be had with that dungeon's key, and a player missing the
right key could be stuck in front of a Miasma Stream for the year.

So with stage keys the lock works differently at these stops:

- Their `mainBasha` call stays the original `MJ_SWING_ATTRIB_1/2` call.
- The "stage cleared?" `jz` in each menu jumps to the next instruction either
  way, so the menu always shows (`MJ_SWING_ATTRIB_1` code `0x107`,
  `MJ_SWING_ATTRIB_2` code `0x137`).
- The menu's "enter" calls (`MJ_SWING_ATTRIB_1` `0x1C3`/`0x201`,
  `MJ_SWING_ATTRIB_2` `0x227`/`0x265`) call the dispatcher instead of
  `MJ_SWING_PADCHECK`. The dispatcher's case for that stage checks the key
  and forwards to `MJ_SWING_PADCHECK`.
- River Belle Path (stage id `0x89`) is never locked, so its case forwards
  without a check. The stage id belongs to the dungeon, so this follows River
  Belle Path to whatever stop it is shuffled onto.

The menus pick their elements from the stop (`G61`), so with shuffled loading
zones the elements stay with the world-map stop, not the dungeon.

So at a stop whose dungeon isn't cleared and whose key you don't have, the
menu still shows and the element can be changed, but entering is refused;
with the key, entering works.

### Boats to Mount Kilanda

Mount Kilanda is reached by boat, and the boat trip is already decided when
the world map's Kilanda lock turns the caravan away, so on its own the boat
just sails back and forth. The boatmen therefore refuse the trip as well
(`_patch_kilanda_boats()`). Each boatman talk (`mainEventClient` in the town
script) checks whether the player declined, right after the destination and
fare are set. That check now reads its value through a gate (the town's
unused library helper `dropItem_fromNpc4`, function 427) that answers "no"
for a Kilanda trip without the key. The boatman then just ends the talk: no
fare, no trip.

| Town | Script | Check (offset in `mainEventClient`) | Kilanda trip |
|---|---|---|---|
| Jegon River pier | `port_0` | `this.m23 != -1` at `0x19D3` | destination `this.m27 == 8` |
| Port Tipa | `port_1` | `this.m23 != -1` at `0x23A3` | destination `this.m27 == 8` |
| Leuda | `thief_0` | `this.m26 == -1` at `0x0FCE` | choice `this.m14 == 2`, or `0` while `eventWork[1] == 5` |

When each boat offers Kilanda (the menu is picked from `eventWork[1]`, which
`changeYear` sets: Year 2 → 1, 3 → 2, 4 → 4, 5-7 → 5 (river dry), 8+ → 6, and
refilling the river at Veo Lu Sluice also sets 6):

- Jegon River pier: from Year 4 (`eventWork[1]` 4 or 6). While the river is
  dry the pier is `port_2`, which has no boat.
- Port Tipa: only while the river is dry (`eventWork[1] == 5`).
- Leuda: from Year 5.

Without the key, the boatman turns down the Mount Kilanda trip. With it, the
trip goes through and the caravan enters Mount Kilanda (the world-map lock
passes too). All three boats use the same gate.

Limitations:

- Real artifacts can only be obtained through the vanilla "find several
  candidates in a dungeon, choose one when you beat the boss" flow. Any
  other intended way to hand out these keys (a specific fixed chest, an
  NPC, granted automatically from the start, etc.) isn't built.
