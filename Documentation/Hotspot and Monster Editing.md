# Editing Hotspot Elements and Monster Spawns

How to change a Myrrh-chalice hotspot's element, and how to swap which monster
spawns at a given point, straight from a dungeon's `.cft` file. Both are single
literal-byte edits once you know where to look — no VM/opcode changes needed.
This uses `cft.py`'s `disasm()` / `code_abs_offset()` (this repo) plus
`gciso.py` to get the result into a testable ISO.

## Requirements & ground rules

- Python 3 (`py` on Windows).
- **Never edit your main ISO directly.** `gciso.py inject` writes in place.
  Always `cp` your working ISO to a throwaway test copy first, and inject into
  that.
- Verify every write: read the bytes before you change them and confirm they're
  what you expect, read them back after, and diff the whole file afterward to
  confirm you changed *only* the byte(s) you meant to. One wrong offset can
  corrupt unrelated bytecode in a way that's hard to notice until much later.

## The shared concept: `SPAWN_MONSTER` is a multi-type dispatcher

Every dungeon script (`river_0.cft`, `gob_0.cft`, ...) has one `SPAWN_MONSTER`
function per room that spawns everything placed in that room — not just
monsters. Each spawn is a function call whose **ordinal** (its position in the
file's own function table) tells you what kind of thing it spawns:

| Ordinal | Function name | Spawns |
|---|---|---|
| `0x192` | `SPAWN` | a monster |
| `0x193` | `SPAWN_POT` | a breakable pot |
| `0x194` | `SPAWN_HOT_SPOT` | a Myrrh-chalice element pool |
| `0x195` | `SPAWN_LAVA_HOLE` | a lava pool |
| `0x196` | `SPAWN_TBOX` | a treasure chest |
| `0x197` | `SPAWN_SWITCH_SPHERE` | a sphere switch (Rebena Te Ra) |

Ordinals are **per-file** (the Nth function in that file's own table is ordinal
N), so always resolve the name from the same file you're editing — don't
assume the same ordinal number means the same function in a different dungeon.

Each of these calls pushes its arguments as plain literal `PUSHI`/`PUSHF`
instructions right before the call — that's what makes them editable: find the
literal, overwrite it, done.

## Setup: extract the file you're going to edit

```
py gciso.py extract "Your.iso" dvd/cft/river_0.cft river_0.cft
```

Everything below assumes you have a local copy of the dungeon's `.cft` file
(here, River Belle Path = `river_0.cft`) sitting next to `cft.py`.

## Method 1 — changing a hotspot's element

**What the argument means:** `SPAWN_HOT_SPOT`'s first argument is a small
integer 1–5 that becomes the pool's element:

| Value | Element |
|---|---|
| 1 | Fire |
| 2 | Water |
| 3 | Wind |
| 4 | Earth |
| 5 | Holy |

(Internally this gets copied into the new object's own state, translated into
the real in-game bitmask — `1,2,4,8,16` respectively — and written to the
player's chalice on touch. You don't need any of that to make the edit; the
literal 1–5 argument is all that matters.)

**1. Find the call sites and their arguments:**

```python
import cft, struct

root, _ = cft.parse("river_0.cft")
func = next(s for s in root.subtags if s.type == b"FUNC")
names = [k.name() for k in func.subtags]
fi = names.index("SPAWN_MONSTER")
code = cft._code_of(func.subtags[fi])
target = names.index("SPAWN_HOT_SPOT")

ops = list(cft.disasm(code))
pushes = []
for off, op, arg in ops:
    if op in (3, 5):
        pushes.append((off, arg))
    elif op == 4:
        pushes.append((off, round(struct.unpack(">f", struct.pack(">i", arg))[0], 3)))
    elif op in (0, 1, 2):
        pushes.append((off, '?'))
    elif op == 0x0a and (arg & 0xFFFF) == target:
        print(f"call @0x{off:04x}: {pushes[-11:]}")
        pushes = []
```

This prints every `SPAWN_HOT_SPOT` call with its arguments and each argument's
**code-relative offset** (the number next to each value). The first value in
each call is the element (1–5); note its offset.

**2. Turn that code-relative offset into a real file offset and patch it:**

```python
block = func.subtags[fi]
code_abs_start = cft.code_abs_offset("river_0.cft", block)
target_off = code_abs_start + <the offset you noted>

with open("river_0.cft", "r+b") as f:
    f.seek(target_off)
    before = f.read(5)                       # opcode byte + 4-byte big-endian int
    assert before[0] == 0x03                 # PUSHI
    print("current value:", before.hex())
    f.seek(target_off)
    f.write(bytes.fromhex("0300000001"))     # new value = 1 (Fire), keep opcode 03
```

`code_abs_offset()` exists because a function's raw bytecode does **not** start
right after its own 16-byte block header — the `NAME`/`INFO`/`VAL` sub-blocks
are parsed out first and aren't included in the naive offset math. Always use
this helper (or verify your own math against it) rather than assuming
`block.off + 16 + code_relative_offset`.

**3. Verify, then inject into a test ISO:**

```
py -c "a=open('river_0.cft','rb').read(); b=open('ORIGINAL_river_0.cft','rb').read(); print([i for i in range(len(a)) if a[i]!=b[i]])"
```
should print exactly one changed offset. Then:
```
py gciso.py inject "Your_test.iso" dvd/cft/river_0.cft river_0.cft
```

## Method 2 — replacing a monster

**What the argument means:** `SPAWN` (the generic monster spawner) pushes a
13-value record per monster; the first value is the **monster ID** (see
`Monster Addresses.md` for the full ID table). The record layout:

```
MonsterID, field2, field3, field4, X, Y, Z, rotation, 0, 0x40000004, spawnParam, 0, 0
```

`field2` is 0 for a small minority of records and 1 for most — treat it as a
conditional/cycle-ish gate you don't fully control yet: **prefer editing
records where `field2 == 1`**, since that's the group proven to actually spawn
during normal play.

**The one real gotcha:** a stage only has *animations* loaded for the monster
IDs it already uses natively. Swap to some ID with a valid model that's never
used in that stage and the monster **will spawn and behave (AI/targeting/
movement works) but will play no animations and won't attack** — confirmed by
testing (River Belle Path: swapping a Goblin to a Griffin, an ID already used
elsewhere in that same file, worked perfectly; swapping to a Cactuar, an ID
used nowhere in that file, produced a monster with no attack animation).

**So: before picking a replacement ID, check which IDs are already used
elsewhere in the same dungeon's `SPAWN_MONSTER`, and pick from that set** if
you want a monster that actually fights. Free-form swapping to *any* valid ID
is possible today only if you don't mind the "zombie" animation state, or want
to separately track down and patch wherever each stage's animation table gets
populated (not yet investigated — bigger job, a real research project of its
own).

### Boss fights work the same way, with the same limitation

A dungeon's boss fight lives in a **separate file** — `river_0.cft` is the
field, `river_1.cft` is the boss room (look for `Map_Floor_ID_Boss`/
`PC_BOSS_DIE` in its function names to confirm you've got the right file). It
has its own `SPAWN_MONSTER` with its own handful of `SPAWN` records — one is
the actual boss, others may be helper/add spawns. Same edit, same tooling,
just point it at the boss's own record instead.

Confirmed by testing (River Belle Path's real boss is Giant Crab, not a
goblin, despite the field being goblin-heavy — always check the boss file
rather than assuming): swapping the boss to a different monster ID works at
the combat level (hit detection, damage, death all function normally,
including a fully winnable fight against a monster with no special elemental
requirement), but hits the **exact same animation-roster limitation** as field
monsters — the replacement boss loads and can be fought, but with broken/
missing animations, since the boss file's animation table only covers the
monster IDs it originally shipped with. **Boss-swapping is paused for now**
until that animation-loading mechanism is understood well enough to fix;
further ID swaps alone won't get around it.

**1. List the records and find candidates:**

```python
import cft, struct

root, _ = cft.parse("river_0.cft")
func = next(s for s in root.subtags if s.type == b"FUNC")
names = [k.name() for k in func.subtags]
fi = names.index("SPAWN_MONSTER")
code = cft._code_of(func.subtags[fi])
target = names.index("SPAWN")

ops = list(cft.disasm(code))
pushes = []
for off, op, arg in ops:
    if op in (3, 5):
        pushes.append((off, arg))
    elif op == 4:
        pushes.append((off, round(struct.unpack(">f", struct.pack(">i", arg))[0], 3)))
    elif op in (0, 1, 2):
        pushes.append((off, '?'))
    elif op == 0x0a and (arg & 0xFFFF) == target:
        rec = pushes[-13:]
        monster_id_off, monster_id = rec[0]
        field2 = rec[1][1]
        print(f"@0x{off:04x}  id={monster_id}  field2={field2}  id_code_offset=0x{monster_id_off:04x}  full={[v for _,v in rec]}")
        pushes = []
```

Also worth printing the full set of monster IDs seen across all records first
(`{v for _,v in rec_id_pairs}` style) so you know which IDs are "safe" (already
native to this dungeon) before picking a replacement.

**2. Patch the same way as Method 1** — same `code_abs_offset()` +
before/after-verified single-byte write (the monster ID is a 4-byte big-endian
int right after a `03` opcode byte, exactly like the hotspot's element arg),
same whole-file diff, same `gciso.py inject` into a test copy.

## Worked example from this project

River Belle Path (`river_0.cft`), `SPAWN_MONSTER`:
- Hotspot at code-offset `5757`, changed element `2` (Water) → `1` (Fire) —
  confirmed in-game via the "Your crystal's element remains fire" message.
- 11 Goblin(Sword) records (code-offsets `1037, 1109, 1182, 1470, 1616, 1762,
  2339, 2554, 3702, 5018, 5092`, all `field2==1`) changed to Griffin (ID `10`,
  already native to this file) — confirmed working with full AI and attacks.
- The same 11 offsets changed to Cactuar (ID `14`, not native to this file)
  instead — confirmed spawning with AI but no animations/attacks, demonstrating
  the per-stage animation-roster limit above.
