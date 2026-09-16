# Adding Custom Items and Artifacts

Items and artifacts are the **same underlying mechanism** - an "artifact"
is just a regular item whose ID falls in the `0x9F`-`0xFE` range, which is
the only thing that makes the game track it in the permanent
`m_artifacts[96]` list and run its bonus through `CCaravanWork::CalcStatus()`
(the effect system itself is broken down further below). Adding either one
is the exact same 3-file edit; the only difference is which ID range you
pick and which fields you set.

## The three edits, every time

1. **`dvd/cft/param.cfd`** - the item's definition record (72 bytes,
   `id * 0x48` into the table). Stats, model, and (for artifacts/equipment)
   the actual gameplay effect all live here.
2. **`dvd/cft/c_system.cfd`** - the display name (5 null-terminated forms:
   singular / (empty) / plural / Title / article), a fixed-width slot per
   item ID.
3. **`Start.dol`** - one byte in a per-item icon-cell table that decides
   which menu/shop icon grid cell the item uses.

All three are **fixed-size files** - every edit above writes back in
place, byte-for-byte, so nothing ever needs an ISO rebuild.

## Already automated: `customitem.py`

This repo's `customitem.py` does all three edits for you by cloning an
existing "donor" item's record:

```
py gciso.py extract "Hacked Rom.iso" dvd/cft/param.cfd param.cfd   # (customitem.py works on a full ISO copy directly)
py customitem.py list-free "copy.iso"                 # see what's actually empty right now
py customitem.py show      "copy.iso" 0xE8             # inspect one slot before touching it
py customitem.py add       "copy.iso" 0xE8 "HP Charm" --like "Earth Pendant"
```

`--like` clones the donor's full record (stats, model, effect) under a
new name and (optionally) a new icon (`set_icon_cell`) or description
(`set_item_description`, which borrows spare bytes from a nearby unused
"Help Message" slot so the file size never changes). This already worked
end-to-end this session for the randomizer's own custom "AP Item" (slot
`0x162`).

## Finding empty slots

`customitem.py list-free` only catches slots literally named `"Extra N"`.
There's a SECOND, larger batch of empty slots it doesn't list: IDs whose
name is still the auto-generated `"equipment NNN"` placeholder, `type=0`,
`model=0`, `gil=0xFFFF` - confirmed via `customitem.py show <id>`. In the
Artifact ID range specifically, **`0xE8`-`0xFE` (23 IDs) are empty this
way** - the top of the `m_artifacts[96]` array's own valid range
(`0x9F`-`0xFE`) that the base game never populated. Always `show` a
candidate slot first to confirm it's really empty before reusing it.

## What actually makes something "an artifact" vs. a plain item

Nothing about the file format changes - only two things matter:

- **The ID.** `0x9F`-`0xFE` is the range `CGPartyObj::command()`'s pickup
  dispatch (`itemIdx >= 0x9F && itemIdx <= 0xFF`) routes to
  `AddTmpArtifact` instead of `AddItem` - i.e. "goes in the permanent
  artifact list" vs. "goes in the regular inventory."
- **Record offset 0** ("type"/family code). For a real bonus effect, this
  must be one of exactly 6 recognized values, each feeding a different
  stat bucket in `CCaravanWork::CalcStatus()`:

  | offset-0 value | bonus bucket |
  |---|---|
  | `0x9F` | Strength |
  | `0xB6` | Magic |
  | `0xCC` | Defense |
  | `0xDB` | extra command-list slot |
  | `0xDF` | Magic (same bucket as `0xB6` - all 5 elemental Rings use this) |
  | `0xE4` | Max HP |

  **Record offset 6** ("value"/magnitude) is added straight into that
  bucket - this is a real numeric field, not a lookup, so any value works.
  A brand-new artifact can pick ANY of these 6 buckets with ANY magnitude,
  entirely as data - no code/DOL changes needed. (A gear-slot item instead
  of a passive artifact uses a richer, still fully data-driven 18-code
  system at offset 8 - elemental resistances, status timers, or 7
  free-form numeric params. Elemental Rings specifically use offset 10 as
  a pointer to a SECOND item record that defines the actual spell/particle
  effect, rather than a raw element ID.)

The one real ceiling: a genuinely NEW effect category beyond those 6 + 18
existing codes would need native code changes to the switch statements
that read them - not reachable through data edits alone.

## What the `model` field actually shows (and doesn't)

Setting a custom artifact's `model` field only changes two things: its
dropped/ground-pickup mesh, and its post-stage reward-tally 3D preview.
**It never makes the artifact appear on your character.** Confirmed
directly in the decomp: `CGObject` has exactly three model-handle members
(character body, weapon, shield) and no others - armor/tribal/accessory/
artifact equips are stat-only and never call any model-load/attach
function. This matches vanilla behavior (a real Ribbon or Wonder Bangle
isn't visible on the Clavat either), so it's not a modding limitation -
only weapon and shield ever render on the character.

## Worked example (byte-exact, verified 2026-09-14)

New artifact "HP Charm" (+50 HP instead of Earth Pendant's own +2),
cloned into empty slot `0xE8`, in the retail NTSC-US ISO used all session
(`main.dol` at file offset `0x1ec00`):

**1. `param.cfd` record for `0xE8`** - absolute ISO offset `0x29d0e0f0` (72 bytes)
- Original (empty slot): `00000000000000000000ffff000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffff0000ffffffff0000ffffffff00000000000000000000000000000000`
- New (cloned from Earth Pendant, `0xE4`): `00e40078000000020000ffff000200000064ffff00630062ffffffffffffffffffffffffffffffffffffffff0000ffffffff0000ffffffff00000000000000000000000000000000`

Then, separately, the magnitude field at record+6 = absolute offset `0x29d0e0f6` (2 bytes):
- Original: `00 02` (Earth Pendant's own +2 HP)
- New: `00 32` (+50 HP)

**2. `c_system.cfd` name slot for `0xE8`** - absolute offset `0x29c89260`-`0x29c89289` (41 bytes, this slot's fixed span)
- Original: `65717569706d656e7420313837000065717569706d656e74203138370045717569702e203138370000` (`"equipment 187"` placeholder ×2 + `"Equip. 187"`)
- New: `687020636861726d0000687020636861726d73202020202020202000485020436861726d0074686500` (`"hp charm"` / `""` / `"hp charms"` padded / `"HP Charm"` / `"the"`)

**3. `Start.dol` icon-cell byte for `0xE8`** - DOL start (`0x1ec00`) + `0x1da684` = absolute offset `0x1f936c` (1 byte)
- Original: `0x26` (38 - the shared "Gold" icon every never-populated slot defaults to)
- New: `0x0e` (14 - Earth Pendant's own icon)

That's the complete, from-scratch recipe. In practice, just run:
```
py customitem.py add "copy.iso" 0xE8 "HP Charm" --like "Earth Pendant"
```
then hand-edit the single magnitude byte above if you want a different
number than the donor's own.

## Giving a new item/artifact a unique look (unused models)

All 73 real artifacts (`0x9F`-`0xE7`) only use 9 distinct meshes between
them (model ids 113-121), grouped by stat-family rather than flavor - e.g.
Ribbon and Dark Matter share one mesh despite being unrelated items. `--like`
inherits the donor's mesh, so a straight clone repeats one of those same 9.

Checked directly against the ISO (verified 2026-09-14, not just theory):
`dvd/char/fa/` holds 129 numbered meshes (`f001`-`f138`, this is the
kind=3 "ground pickup / reward-screen" namespace - confirmed via Copper
Sword -> `f001`, and crafting-material Gold -> `f055` matching the already
-known "64 materials share model 0x37"). Scanning every item in the entire
1205-row `param.cfd` table for which of those 129 mesh ids are ever
referenced: **only 40 are used anywhere in the game.** The other 89 sit on
the disc completely unused by any item, weapon, armor, or artifact - real,
non-degenerate files (2-131KB, spot-checked), not placeholders, except
`f063` (64 bytes - almost certainly a broken/stub file, skip it).

Pass `--model <id>` to `customitem.py add` to point a new item at one of
these instead of the donor's own mesh, e.g.:
```
py customitem.py add "copy.iso" 0xE8 "HP Charm" --like "Earth Pendant" --model 15
```
Unused mesh ids (decimal, i.e. `f015` = model `15`; excludes the `f063`
stub):
```
15, 26, 28, 30, 31, 33-37, 39, 41-48, 50-54, 56-62, 64, 66, 67, 69-77, 79-90,
92-104, 108-110, 112, 127, 128, 130-138
```
None of these have been visually confirmed in-game (no 3D viewer in this
toolchain) - try a candidate in-game before committing to it, since a few
may be unfinished/cut assets.

Full per-model breakdown (which item, if any, already uses each of the 138
mesh ids) is in `Item Model Reference.md`.
