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
MonsterID, field2, cycles, field4, X, Y, Z, rotation, 0, 0x40000004, drop, 0, 0
```

- **`field2`** is 0 for a small minority of records and 1 for most. Its
  meaning isn't known, so **prefer editing records where `field2 == 1`**;
  that group is proven to spawn in normal play.
- **`cycles`** is a packed bitfield of which cycles (and player counts) the
  spawn appears in, so a record can be absent in some playthroughs.
- **`field4`** (seen as 0, 2, 7 or 8) is still unidentified.
- **`drop`** is the index of the monster's drop table.

Example records from River Belle Path (`river_0.cft`):

| Monster (ID) | field2 | cycles | field4 | X, Y, Z, rotation | drop |
|---|---|---|---|---|---|
| Hedgehog Pie (19) | 0 | `0x1F` | 2 | -237.06, 6.91, -406.64, 0.00 | 50 |
| Goblin, Sword (43) | 0 | `0x7F` | 7 | -237.19, 4.58, -479.42, 0.79 | 50 |
| Goblin, Mage (46) | 0 | `0x7F` | 7 | -185.76, 3.76, -431.75, 0.79 | 51 |
| Mu (16) | 0 | `0x7F` | 2 | -291.33, 8.19, -381.63, 0.79 | 52 |
| Mu (16) | 0 | `0x7C` | 2 | -243.26, 0.48, -304.49, 1.57 | 52 |
| Goblin, Sword (43) | 0 | `0x7C` | 8 | -220.52, 0.30, -526.14, 0.00 | 52 |

Negative coordinates are compiled as a positive float followed by opcode
`0x2B` (float negate), so read the instruction after each `PUSHF` before
trusting its sign.

**The one real gotcha:** changing only the monster ID works if the stage
already contains that monster. For a monster the stage doesn't normally have,
the new monster **spawns and its AI runs, but it plays no animations and
never attacks** (a "zombie"). Each stage loads animations, sounds and hitbox
settings only for its own monsters. For example, in River Belle Path a Goblin
changed to a Griffin (already in that stage) works fully, but a Goblin
changed to a Cactuar (not in that stage) is a zombie.

So either pick a replacement from the monsters the stage already spawns, or
use `cftpatch.py` to copy the new monster's data into the stage first. See
[Monster and Boss Swapping.md](Monster%20and%20Boss%20Swapping.md).
`py cft.py paramset <stage>.cft` lists the monsters a stage supports.

### Boss fights

A dungeon's boss fight lives in a **separate file**. For River Belle Path,
`river_0.cft` is the field and `river_1.cft` is the boss room; look for
`Map_Floor_ID_Boss` / `PC_BOSS_DIE` among the function names to confirm
you have the boss file. It has its own `SPAWN_MONSTER` with a few `SPAWN`
records: one is the boss, the others are its helpers. The boss is often not
the monster the field suggests (River Belle Path's is Giant Crab), so check
the boss file.

The same single-byte edit changes the boss, with the same zombie limitation.
A different boss changed in this way fights and can be killed, but its
animations are broken. For a proper boss swap, including summons and
arena-specific mechanics such as Lich's orbs, see
[Monster and Boss Swapping.md](Monster%20and%20Boss%20Swapping.md).

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

## Worked example (verified in-game)

River Belle Path (`river_0.cft`), `SPAWN_MONSTER`:
- Hotspot at code-offset `5757`, element changed from `2` (Water) to `1`
  (Fire). The game then shows "Your crystal's element remains fire".
- 11 Goblin (Sword) records (code-offsets `1037, 1109, 1182, 1470, 1616, 1762,
  2339, 2554, 3702, 5018, 5092`, all `field2 == 1`) changed to Griffin (ID
  `10`, already in this stage): full AI and attacks.
- The same 11 records changed to Cactuar (ID `14`, not in this stage): the
  monsters spawn with AI but no animations or attacks. The fix is in
  [Monster and Boss Swapping.md](Monster%20and%20Boss%20Swapping.md).
