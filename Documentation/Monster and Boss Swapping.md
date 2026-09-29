# Monster and Boss Swapping

How to make any monster, including a boss, work properly in a stage it wasn't
designed for. This covers how the game loads a monster's animations, sounds and
hitboxes; the `cftpatch.py` tool that moves them between stages; and the extra
arena-specific pieces some bosses need. It builds on
[Hotspot and Monster Editing.md](Hotspot%20and%20Monster%20Editing.md), which
covers the basic spawn-record edit.

Everything here was checked against the NTSC-US disc, all 132
`dvd/cft/*.cft` stage scripts, and the FFCC decompilation
(`CFlatRuntime2::onClassSystemFunc`, `CCharaPcs::CHandle::LoadAnim`,
`CGMonObj`, `CRomWork`).

## Summary

| What | Status |
|---|---|
| A field monster moved to another stage (Cactuar into River Belle Path) | Verified in-game: animations, attacks, hitboxes and its own sounds all work |
| A boss moved to another arena (Orc King into River Belle Path's boss room) | Verified in-game: fights normally and can be beaten |
| A boss with summons (Lich and its skeletons into River Belle Path's boss room) | Verified in-game: Lich, skeletons, summons and magic all work |
| Lich's orb shield and teleport, ported to another arena | Built; see [Bosses with special mechanics](#bosses-with-special-mechanics-lich) |
| Lich's orbs protecting a different boss | Verified in-game: the boss is protected until the orbs break, with no shield visual |
| Randomizer boss shuffle (GUI checkbox / JSON) | EXPERIMENTAL: all 156 boss-into-arena combinations build and pass structural checks; not every combination has been played |

If you only change a monster's ID in a `SPAWN` record, a monster the stage
doesn't normally contain becomes a **"zombie"**: its model appears and its AI
runs (it follows you), but it plays no animations, never attacks, and may have
no working hitbox. The rest of this document explains why, and how to fix it.

---

## 1. How a monster's assets are loaded

When a `SPAWN` record creates a monster, the monster's `initMonster_Logic`
script function runs roughly this:

```
setCharaAlloc(...)
loadModel(1, rom[+0x14], rom[+0x16], -1)   ; kind 1 = monster, model number, texture variant
setCharaAlloc(0)
ParamSet(monsterId)                        ; the stage's per-monster animation/sound table
setRadius / setAttackCollision / setDamageCollision / ...
```

### Monster ID → model folder

The model comes from the monster's record in `param.cfd`, DATA block #1 (file
offset `0xEE0`). Records start at `0xEE0 + 0x10`, are `0x1D0` bytes each, and
are indexed by monster ID:

- halfword 0 = **model number**: the `NNN` in `dvd/char/mon/mNNN/`
- halfword 1 = **texture variant**: 0 = `mNNN_root.tex`, 1 = `_b`, 2 = `_c`
- halfword 7 repeats the monster ID

| ID | Monster | Model | Variant |
|---|---|---|---|
| 10 | Griffin | m004 | 0 |
| 14 | Cactuar | m011 | 0 |
| 19 / 20 / 21 | same model, three colours | m014 | 0 / 1 / 2 |
| 43 / 44 / 45 / 46 | Goblin Sword / Mace / Spear / Mage | m026 | 0 / 0 / 0 / 1 |
| 71 | Bat | m042 | 0 |
| 91 | Giant Crab | m056 | 0 |
| 99 | Orc King | m057 | 0 |
| 113 | Golem | m039 | 0 |
| 127 | Lich | m062 | 0 |

The model number is **not** the monster ID: folder `m045` has nothing to do
with Goblin (Spear), ID 45. A monster-name table for the IDs is in
`Monster Addresses.md` (in the parent modding folder).

### `ParamSet`: the per-stage monster table

Every stage script has its own `ParamSet` function. It's a switch on monster
ID with one case per monster the stage supports. Every per-ID switch in these
scripts compiles to the same shape:

```
3A            DUP
03 <id>       PUSHI monster id
2C            ==
08 <next>     JZ  <code offset of the next case>
  0C          POP
  ...case body...
07 <exit>     JMP <shared exit>
```

A `ParamSet` case body contains, in order:

- `loadAnim(clip, slot, flags, -1, -1)` for each animation. `clip` is a
  string-table index (opcode `05`); the engine loads
  `dvd/char/mon/mNNN/<clip>.cha` from the model loaded above.
- `setAnimSlot(slot, slot)` for each slot, plus a few aliases.
- `send_int(…, 10+k, …, <attack id>, …, 100, k)`: registers the monster's
  attack definitions. For example, Cactuar uses attack IDs 635–638.
- `loadWave(bank)` and a run of `loadSe(id)` calls: the monster's sound bank
  and sound effects.

`loadAnim` arguments, from the decomp:

- `slot`: animation slot index (see the table below).
- `flags`: bit 0 = blend in, bit 1 = clamp (hold the last frame). In practice,
  idle/move/attack/faint use `1`, `damage` uses `0`, and `die` uses `2`, so
  the monster holds its death pose.
- `-1, -1`: model kind and number. `-1` means "this object's own model", which
  is why a clip name on its own is enough.

Standard slot layout:

| Slot | Role | Usual clip | Variants seen |
|---|---|---|---|
| 0 | idle | `idle` | `idle_sky` (flyers) |
| 1 | move | `run` | `walk`, `dash`, `fly` |
| 4 | take damage | `damage` | `dodge`, `damage_fly` |
| 5 | attack | `attack` | `spear` (45), `taiatari` (19–21), `upper` (Golem), `summon` (Lich) |
| 6 | die | `die` | `die_sky`, `die_a` |
| 26–28 | faint 1/2/3 | `faint_1..3` | — |
| 40–46 | ground set for flyers | `idle_grand`, `fly`, `damage_grand`, `die_grand`, `ririku` (take off), `chakuchi` (land), `damage_fly` | Bat, Lich |
| 50+ | boss entrance/death sequences | `appear_a..h`, `die_a..d`, `die_idle` | most bosses |

To print any stage's table:

```
py cft.py paramset river_0.cft
```

### The collision switches

Two more functions use the same per-ID switch:

| Function | What a case does |
|---|---|
| `setAttackCollision` | `setAttackCol(…, '<bone>', …)`: which bone the monster's **attack hitbox** follows |
| `setDamageCollision` | `setDamageCol(…, '<bone>', …)`: which bone its **hurtbox** follows |

For example, Cactuar's hitboxes follow bone `chest8`, while many other
monsters use `body`. A monster with no case takes the switch's default path,
which is correct for many bosses (Orc King, Lich and its skeletons all use the
default).

**Not every `case <n>` is a monster ID.** `get_treasure`, `MJ_MOGSU`,
`send_intCarryItem`, `initCarryItem` and others also contain cases numbered
like monster IDs, but those are item, drop or event numbers. Only the three
functions above switch on monster ID.

### Why a naive swap breaks

River Belle Path's field script (`river_0`) has `ParamSet` cases for exactly
the monsters it spawns: 10, 16, 19, 20, 21, 43, 44, 45, 46 and 159. Swap a
Goblin to a Griffin (10) and it works, because case 10 exists. Swap it to a
Cactuar (14) and there's no case, so no clips are loaded and there are no
Cactuar hitbox settings. The monster still has its model and AI, but no
animations. Attacks are driven by animation, so it never attacks either.

---

## 2. Donor stages

To add a monster to a stage, copy its cases from a stage that already
supports it.

- **`miya_0.cft`** has a `ParamSet` case for **163 monster IDs**, nearly the
  whole bestiary. It's the best donor for ordinary monsters. The only IDs it
  lacks are 178–181, 184–186, 189 and 197, which each appear in exactly one
  stage (`lava_1`, `city_0`/`city_1`, `swamp_1`, `fort_0`, `tutorial_0`).
- **A boss's own arena** is the best donor for that boss, because it also
  contains the boss's summons and any arena objects (see section 4).

Boss arenas at a glance ("summoned" means the monster is in the arena's
`ParamSet` but no `SPAWN` record places it, so the boss creates it during the
fight):

| Arena file | Dungeon | Boss | Also spawned | Summoned |
|---|---|---|---|---|
| `river_1` | River Belle Path | 91 Giant Crab | 94 ×2 | – |
| `mine_3` | Mine of Cathuriges | 99 Orc King | 100 ×2, 101, 102 | – |
| `city_2` | Rebena Te Ra | 127 Lich | 128 ×3 (skeletons) | 129, 130 (skeletons) |
| `swamp_3` | Conall Curach | 131 Zombie Dragon | 132 ×3 (Stone Sahagins) | – |
| `ruin_2` | Tida | 107 | 108 ×5, 109 ×2 | 110 |
| `gigas_8` | Moschet Manor | 111 + 112 (two bosses) | – | – |
| `cave_2` | Selepation Cave | 119 | 120 ×2 | – |
| `lava_2` | Mount Kilanda | 121 | 122 ×2, 165 ×4 | – |
| `fort_1` | Daemon's Court | 115 | 118 ×2, 158, 116, 117 | – |

A dungeon's boss fight is always in a separate file from its field (for
example `river_0` = field, `river_1` = boss room).

---

## 3. The tool: `cftpatch.py`

`cftpatch.py` loads a `.cft` file as a chunk tree, edits it structurally, and
writes it back. Files may grow or shrink, so put the result in the ISO with
`gciso.py rebuild`, not `inject` (which only accepts same-size files).

### Swap one monster

```
py cftpatch.py transplant <stage.cft> <donor.cft> <old_id> <new_id> <out.cft>
```

This replaces monster `old_id` with `new_id` everywhere in the stage:

- In each monster-ID switch (`ParamSet`, `setAttackCollision`,
  `setDamageCollision`):
  - If the donor has a case for `new_id`, it **replaces** `old_id`'s case.
  - If the donor has none (it uses the default path), `old_id`'s case is
    **disabled** so `new_id` takes the same default path here.
- Every `SPAWN` record for `old_id` becomes `new_id`.

It checks everything first and writes nothing if any step can't be done
safely.

Example (Cactuar replaces monster 16 in River Belle Path, using `miya_0` as
the donor):

```
py cftpatch.py transplant river_0.cft miya_0.cft 16 14 river_0_new.cft
py gciso.py rebuild "Your.iso" dvd/cft/river_0.cft river_0_new.cft "Your_new.iso"
```

The monster being replaced must be one the stage already has, and **all** of
its spawns change. Otherwise its remaining spawns become zombies.

### Swap a boss and its helpers

```
py cftpatch.py group <arena.cft> <donor_arena.cft> <old:new,old:new,...> <out.cft>
```

This does several swaps in one pass, then **adds** `ParamSet` cases for every
monster the donor arena supports but never spawns directly, meaning the boss's
summons. For example, to put Lich and its skeletons in River Belle Path's
boss room:

```
py cftpatch.py group river_1.cft city_2.cft 91:127,94:128 river_1_new.cft
```

This replaces Giant Crab with Lich, turns the crab's two helpers into
skeletons, and adds the two summoned skeleton types (129, 130). New cases go
in front of the switch's first case.

### Safety

- **Lossless:** loading and saving reproduces all 132 disc `.cft` files byte
  for byte (`py cftpatch.py roundtrip <file.cft>`).
- **Exact copies:** every copied case, function and class matches the donor
  instruction for instruction once names are resolved. Nothing outside the
  targeted cases changes, and every jump in every function lands on an
  instruction boundary.

### What the tool remaps when copying code between files

Each stage script numbers its strings, functions, classes and global
variables differently, so copied code is re-encoded for the destination:

- **Strings** (opcode `05`): matched by content. Missing clip names are
  appended to the destination's string table.
- **Calls** (opcode `0A`): the low 16 bits are the function-table index,
  matched by function name. The high 16 bits are kept as-is (see the bytecode
  notes).
- **Class creation** (opcode `0B`): the class index, matched by class name.
- **Global variables:** both files' variable tables start with the same
  entries (from the shared headers), and indices in that shared part map to
  themselves. Other pairs are learned by lining up code both files contain.
- **Jumps** (opcodes `07`/`08`/`09`): absolute code offsets, shifted when code
  grows or shrinks.

### Rebuilding the ISO

`gciso.py rebuild` appends the new file at the end of the disc image and
points the file table at it. The game rounds read lengths up to 32 bytes and
Dolphin reads in 32 KB blocks, so the image is padded to a 32 KB boundary.
Without that padding, the last file is read past the end of the image and the
game shows "The Game Disc could not be read".

---

## 4. Bosses: what's generic and what's per-arena

Diffing boss arenas against each other shows:

- **Generic (moves with the monster):** the boss's fighting AI lives in the
  game engine and is keyed by monster ID. The monster-logic script functions
  (`beginMonster_Logic`, `initMonster_Logic`, `onAnimPointMonster_Logic`,
  `onDamageMonster_Logic`, …) are identical in every stage.
- **Per monster ID (handled by `transplant` / `group`):** `ParamSet` and the
  two collision switches.
- **Per arena (not moved):**
  - `mainMonster_Logic` holds the arena's **boss entrance**: starting position,
    which appear animations play, entrance sound effects and particles. A
    swapped boss runs the old boss's entrance. This is cosmetic.
  - Arena objects and helper classes, such as River Belle Path's `BossQuad`
    boundary walls, or Lich's orbs.
  - `mainEventDirector` (cutscenes). It isn't keyed by monster ID; some
    numbers in it happen to equal boss IDs but are diary and story-flag
    values.

### Bosses with special mechanics: Lich

Lich (Rebena Te Ra) has three mechanics that live outside the monster itself.

**Teleport destinations are fixed in the executable.** `gLichTeleportPoints`
is four absolute world positions in `Start.dol` at **file offset `0x20E678`**
(12 big-endian floats):

```
(0, 25.36, -137)   (0, 0, -38)   (-132, 0, -38)   (132, 0, -38)
```

`CGMonObj::teleport()` picks one at random (never the same twice) and moves
Lich there. Lich's own spawn point, `(0, 25.37, -137.12)`, is the first of
them. In any other arena these points are off-stage, so a moved Lich
teleports out of the arena. Rewrite the table for Lich's new arena; only one
Lich exists per game, so one table is enough. Goblin King has the same kind
of table (`gGoblinKingTeleportPoints`) just before it, at `0x20E648`.

**The shield is driven by the arena script.** The engine keeps Lich's shield
up while bit 0 of the "boss state" is set, and uses bit 1 to choose attack
patterns. The arena script sets this value with `sysControl(3, value)`. In
Lich's arena this is done by the `JochuSE` class: it starts the state at 3
(both orbs intact), then each frame clears bit 0 or bit 1 when an orb's
"destroyed" flag (`64` or `128` in a global flag word) is set. In other
arenas, `JochuSE` is just an ambient-sound class and never sets the state.

**The orbs are an arena class.** Lich's arena defines a `SwitchSphere` class
(model `f060`; methods `begin/init/main/onHitParticle/onDamage`; helpers
`resInit/resLoop/resFunc`). Two orbs are placed by `SPAWN_SWITCH_SPHERE` calls
at the end of the arena's `SPAWN_MONSTER`, at `(-172.77, 0.34, -38.62)` and
`(172.23, 0.34, -38.62)`. Other arenas only have an empty `SPAWN_SWITCH_SPHERE`
placeholder.

Lich's arena also has a `Portal` class and a pathfinding graph (`setMobLine`),
which aren't needed for the fight.

**Porting it:** `cftpatch.import_lich_orbs(dst, donor, var_map, orb_positions, log)`
copies all of this from Lich's arena (`city_2.cft`) into another arena:

1. appends the eight `SwitchSphere` functions and the `SwitchSphere` class;
2. replaces `SPAWN_SWITCH_SPHERE`, `initJochuSE` and `mainJochuSE` with
   Lich's versions, and gives `JochuSE` the extra member variable they use;
3. adds two `SPAWN_SWITCH_SPHERE` calls at the given positions to the end of
   the arena's `SPAWN_MONSTER`.

Combined with the teleport-table rewrite, this gives a moved Lich its full
fight.

### Orbs protecting a different boss

In the engine, Lich's shield bit only drives the shield *visual* (a particle
effect and a sound). No other boss reads the boss state, so for a different
boss the protection is added in script. `cftpatch.add_orb_shield(dst, boss_id, log)`
adds one member variable to the `Monster_Logic` class and inserts this at the
top of the `mainMonster_Logic` loop:

```
if (this[18] == boss_id) {              // this[18] holds the monster ID
    s = getSysControl(3) & 1;           // orbs still up?
    if (s != this[last]) {              // act only when it changes
        this[last] = s;
        setDamageColMask(0, !s);
        setDamageColMask(1, !s);
    }
}
```

This does the same as the engine's own `CGMonObj::enableDamageCol()`: it
switches the monster's hurtboxes 0 and 1 off (mask 0) and back on (mask 1).
Because it only acts when the orb state changes, it never overrides the
engine's own hurtbox switching in between. The boss is untouchable until the
orbs are destroyed, but no shield is drawn around it.

### Bosses that need Holy

Lich and Zombie Dragon take only 1 damage until they're hit with Holy. Holy
is cast by fusing a Stone of Life with a Fire, Blizzard or Thunder stone, and
stones don't carry between dungeons. The randomizer therefore keeps the
magicite sets vanilla in whichever dungeons host those two bosses (their home
dungeons unless the boss shuffle moves them). See "Notes & known scope" in
[RANDOMIZER.md](RANDOMIZER.md).

### Boss shuffle in the randomizer (EXPERIMENTAL)

`bossshuffle.py` uses all of the above to move the 13 dungeon bosses between
their arenas (Mount Vellenge's multi-part final boss isn't included). It's
available as:

- the **"Randomize bosses"** checkbox in the GUI;
- `py randomizer.py run <iso> --seed N --randomize-bosses` on the command line;
- the JSON keys `_randomize_bosses` and `_bosses` (see below).

For each arena that gets a new boss:

1. The arena's boss becomes the new boss, and each of the arena's helper
   monster types becomes one of the new boss's helper types (cycling if the
   counts differ). The new boss's summons are added.
2. If the new boss is Lich, its orb shield is imported and its teleport table
   is rewritten.
3. Arena files are built from the disc's original arena files, then the ISO
   is rebuilt once, after every other patch.

The ISO must still have its original bosses in place. Running a boss
placement on an already-shuffled copy is refused.

Every boss has been built into every other arena (156 combinations) and
checked structurally. They have not all been played.

**Random shuffles keep Goblin King and Lich at home.** Both rely on their
arena's script (Goblin Wall's gimmick and Rebena Te Ra's orbs set their boss
state) and teleport to fixed coordinates. They can still be placed by JSON.
Their new teleport points (and Lich's orb positions) are then **estimated**
from the centre of the new arena's spawn points, so check them in-game.

**Holy follows the bosses.** Wherever Lich and Zombie Dragon end up, that
dungeon's magicite sets stay vanilla (every dungeon has a Stone of Life set
and element sets), and the dungeons they left are randomized normally.

**JSON:** Export writes the current layout:

```json
"_randomize_bosses": false,
"_bosses": { "River Belle Path": "Giant Crab", "Rebena Te Ra": "Lich", ... },
"_boss_choices": [ "Giant Crab", "Goblin King", "Orc King", ... ]
```

- Change a dungeon's entry in `_bosses` to any name from `_boss_choices` to
  place that boss there. Dungeon keys may be the name or the script name
  (`river`, `city`, …).
- An entry naming the dungeon's own original boss means "no preference".
- With `_randomize_bosses: true`, every dungeon without a preference is
  shuffled, and bosses placed explicitly are taken out of the shuffle.
- Without it, dungeons that aren't changed keep their own boss, so the same
  boss can appear in two dungeons.

The final placement is appended to the spoiler file.

---

## 5. Bytecode notes

Details confirmed against the VM in the decomp (`cflat_runtime.cpp`) that
matter when writing or copying code:

- **Instruction width:** opcodes below `0x0C` are 5 bytes (opcode plus a
  4-byte big-endian argument). Everything else is 1 byte.
- **Jumps** (`07` JMP, `08` JZ, `09` JNZ): the target is the low 24 bits, an
  absolute offset within the function. The top byte is a flag used by `&&` /
  `||` short-circuiting and must be preserved.
- **Fall-through jumps:** after its `JMP <exit>`, each switch case has a
  second, unreachable jump to the next case. It targets 13 bytes past the case
  end when a case header follows, or 5 bytes when the default block follows.
  Moving a case between those positions means recomputing it.
- **Calls** (`0A`): low 16 bits = function-table index. High 16 bits = `0xFFFF`
  for ordinary script functions, but for engine functions that act on the
  calling object, the engine command number, e.g. `setDamageColMask` = `0xFFD0`
  (−0x30).
- **Operators:** `2B` = float negate (a negative literal is written as `PUSHF
  |x|` then `2B`), `2C` = equal, `2D` = not equal, `1F` = bitwise AND.
- **Variables** (`00` GET / `01` address-of): argument = `index << 8 | flags`.
  Flags `0x19` = the object's own member (`this[index]`); `0x09` = file global;
  `0x01` = local. Bit `0x02` makes it an indexed (array) access. Negative
  indices are engine "system values"; −200 to −499 map to
  `CGameWork::m_eventWork[value + 0x1C7]`.
- **Chunk counts:** the `FUNC` and `CLAS` chunks store their entry counts in
  the first header field, and a class's member table (`VAL`) stores its
  member count the same way. Update these when adding entries.
- **Class method table:** each class's `VTBL` is 128 function indices (−1 =
  unused); slot 0 = `begin`, 2 = `init`, 3 = `main`, 11 = `onHitParticle`,
  71 = `onDamage`.

---

## 6. Open questions

- Swapping many *different* monster types into one stage has crashed the game
  in the past. That may be a memory budget (`setCharaAlloc`) rather than
  anything in these tables; it hasn't been investigated.
- A swapped boss uses the old boss's entrance sequence from `mainMonster_Logic`.
  Porting the new boss's own entrance hasn't been done.
- Some bosses may have more arena-specific mechanics like Lich's, for example
  Goblin King's teleport table, Lizardman King's switch-triggered saws, or
  Goblin King's opening key fight. Check the boss's arena file for extra
  classes and `sysControl(3, …)` calls before moving it.
