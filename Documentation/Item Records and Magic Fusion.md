# Item Records and Magic Fusion

Reference for two data tables: the per-item records in `param.cfd` (stats,
spells, crafting recipes) and the single-player magic-fusion table in
`Start.dol`. `items.py` reads and edits the item records; the fusion table
has no tool yet.

## Item records (`dvd/cft/param.cfd`)

The item table starts at `param.cfd` file offset `0x175F0` (item ID 0, the
Null entry). Each record is 72 bytes (`0x48`), indexed by item ID, with 1205
entries (IDs `0x000`–`0x4B4`). All values are big-endian.

```
py items.py show param.cfd 0x0001            # Copper Sword
py items.py set  param.cfd 0x0001 damage 99
py items.py set  param.cfd <scroll id> mat1 0x0126
```

`items.py` named fields: `type model equiptype equipability value/damage/defense
status/bonus focus/spell gfxsize gil`, plus `craftgil mat1-3 qty1-3 clavat lilty
yuke selkie` for scrolls and `chargetime range` for spells and focus attacks. Any
other byte can be addressed as `0xOFF[:size]`.

### Item type codes (offset `0x00`)

| Code | Kind | Records |
|---|---|---|
| `0001` | Weapon (Strength) | 54 |
| `0045` | Armor / shield / gauntlets / helmet / belt (Defense) | 58 |
| `007F` | Accessory | 32 |
| `009F` / `00B6` / `00CC` | Artifact: Strength / Magic / Defense | 23 / 22 / 15 |
| `00DB` / `00DF` / `00E4` | Artifact: Pocket / Spell (Ring) / Health | 4 / 5 / 4 |
| `0100` | Magicite | 7 |
| `0125` | Phoenix Down | 1 |
| `0126` | Ore | 4 |
| `012A` | Material | 73 |
| `0191` | Scroll (crafting recipe) | 93 |
| `01F5` | Spell | 57 |
| `01F8` | Focus attack | 20 |

The record counts are from the NTSC-US disc.

### Shared fields

**Equipability** (offset `0x05`, weapons and armor) is a bit mask:
`01` Clavat, `02` Lilty, `04` Yuke, `08` Selkie (`0F` = anyone). Accessories
add `10` Male and `20` Female.

**Equip type** (offset `0x04`): `01` weapon, `02` shield, `04` armor, `08`
secondary armor (gauntlets, helmet, belt), `10` accessory.

**Bonus** (offset `0x08`, armor, shields, gauntlets, helmets, belts,
accessories):

| Code | Bonus | Code | Bonus |
|---|---|---|---|
| `01` | Resist Fire +1 | `0B` | Spell duration + |
| `02` | Resist Cold +1 | `0C` | Spell duration − |
| `03` | Resist Lightning +1 | `0D` | Resist Miasma |
| `04` | Resist Slow +1 | `0E` | Long spell range |
| `05` | Resist Stasis +1 | `0F` | Long focus-attack range |
| `06` | Resist Poison +1 | `10` | Regen |
| `07` | Resist Curse +1 | `11` | Focus attacks |
| `08` | Resist Paralysis +1 | `12` | Spell damage |
| `09` | Casting time | `13` | Stunproof |
| `0A` | Charge time | | |

### Weapons (type `0001`, based on Copper Sword)

| Offset | Field |
|---|---|
| `0x00` | Item type (`0001`) |
| `0x02` | Model |
| `0x04` | Equip type (`01`) |
| `0x05` | Equipability |
| `0x06` | Damage |
| `0x08` | Status effect |
| `0x0A` | Focus attack |
| `0x10` | Weapon trail length |
| `0x12` | Weapon trail / spark effect (unconfirmed) |
| `0x16` | Weapon trail colour / effect |
| `0x18` | Additional trail colour / effect |
| `0x1A` | Multiple trail colour / effect |
| `0x1C` | Hit spark |
| `0x38` | Swing sound |
| `0x3A` | Swing sound delay |
| `0x3C` | Additional swing sound |
| `0x3E` | Additional swing sound delay |
| `0x40` | Hit sound on swing |
| `0x42` | Hit sound |

The remaining bytes are fixed filler (`0000`, `0001` or `FFFF`) in the
records examined.

### Armor, shields, gauntlets, helmets, belts (type `0045`)

| Offset | Field |
|---|---|
| `0x00` | Item type (`0045`) |
| `0x02` | Model (shields only; `0000` otherwise) |
| `0x04` | Equip type (`02` shield, `04` armor, `08` gauntlets/helmet/belt) |
| `0x05` | Equipability |
| `0x06` | Defense |
| `0x08` | Bonus |

### Accessories (type `007F`, based on Lion's Heart)

| Offset | Field |
|---|---|
| `0x04` | Equip type (`10`) |
| `0x05` | Equipability (plus `10` Male / `20` Female) |
| `0x06` | Bonus value |
| `0x08` | Bonus |

### Artifacts (based on Shuriken)

| Offset | Field |
|---|---|
| `0x00` | Item type (`009F` Strength, `00B6` Magic, `00CC` Defense, `00DB` Pocket, `00DF` Spell, `00E4` Health) |
| `0x02` | Model |
| `0x06` | Stat value |
| `0x0A` | Spell |
| `0x0C` | Unknown |
| `0x10` | GFX size |
| `0x14` | GFX |
| `0x16` | Additional GFX |
| `0x18`–`0x1F` | Additional GFX |

How artifact bonuses are actually applied is covered in
[Adding Custom Items and Artifacts.md](Adding%20Custom%20Items%20and%20Artifacts.md).

### Magicite (type `0100`)

| Offset | Field |
|---|---|
| `0x0A` | Spell |

### Phoenix Down, ore, materials

| Offset | Phoenix Down (`0125`) | Ore (`0126`, e.g. Bronze) | Material (`012A`, e.g. Diamond Ore) |
|---|---|---|---|
| `0x02` | Model | Texture (1 byte), then model (1 byte) | Model |
| `0x10` | GFX size | `0064` | GFX size |
| `0x14` | — | `0002` | `0002` |
| `0x16` | Item GFX | — | GFX 1 |
| `0x18`–`0x1F` | — | — | GFX 2 |
| `0x20` | Gil price | Gil price | Gil price |

### Scrolls (type `0191`): crafting recipes

Verified against the disc (all 93 scrolls decode to real recipes).

| Offset | Field | `items.py` name |
|---|---|---|
| `0x02` | Model | `model` |
| `0x10` | GFX size | `gfxsize` |
| `0x16`, `0x18`–`0x1F` | GFX 1, GFX 2 | |
| `0x20` | Gil price (buy/sell) | `gil` |
| `0x24` | Crafting price | `craftgil` |
| `0x26` / `0x28` / `0x2A` | Required material 1 / 2 / 3 (item ID, `0000` = none) | `mat1`–`mat3` |
| `0x2C` / `0x2E` / `0x30` | Quantity of material 1 / 2 / 3 | `qty1`–`qty3` |
| `0x38` / `0x3A` / `0x3C` / `0x3E` | Item crafted for a Clavat / Lilty / Yuke / Selkie | `clavat` `lilty` `yuke` `selkie` |

Example: **Novice's Weapon**, 100 gil to craft, 1 Iron, makes Iron Sword
(Clavat), Partisan (Lilty), Wave Hammer (Yuke) or Solid Racket (Selkie).

### Spells (type `01F5`, based on Fire) and focus attacks (type `01F8`, based on Power Slash)

| Offset | Spell | Focus attack |
|---|---|---|
| `0x02` | Disables hurtbox? | Disables hurtbox? |
| `0x04` | `0064` | `0064` |
| `0x06` | Damage | Damage |
| `0x08` | Status effect | Status effect |
| `0x0A` | — | Character animation (1 byte), focus-attack type (1 byte) |
| `0x0C` | Projectile / hit behaviour? | Projectile / hit behaviour |
| `0x10` | GFX size | GFX size |
| `0x12` | GFX category (usually `0002` or `0003`) | GFX category (usually `0005`) |
| `0x14` / `0x16` | Charge GFX 1 / 2 | — |
| `0x16`–`0x1B` | GFX behaviour + GFX pairs (from `0x18`) | GFX 1–3 behaviour + GFX pairs |
| `0x1C` | — | Affects hit spark? |
| `0x24` | Number of GFX 2 (e.g. orbiting spell orbs) | Affects number of GFX 3 |
| `0x26` | GFX play speed (`01F4`) | GFX play speed (`01F4`) |
| `0x2E` | Charge time | Charge time |
| `0x30` | Range | Range |
| `0x38` | Charge SFX (4 bytes) | `021E 8001` |
| `0x40` | SFX 1 (attack) | SFX 1 (attack) |
| `0x42` | SFX 2 (hit) | SFX 2 (hit) |

Fields marked "?" are guesses from comparing records.

### Enemy resistances

Each monster has a resistance entry per element and status. The notes give
this order (2 bytes each): Physical, Fire, Blizzard, Thunder, Slow, Stop,
Gravity, Holy, Poison, Curse, Petrify. These live in the monster's record in
`param.cfd` DATA block #1 (see
[Monster and Boss Swapping.md](Monster%20and%20Boss%20Swapping.md)); the
decomp calls this block `ElementResistances` (halfword `0x6F` of a monster's
data).

---

## Magic fusion (single player): `Start.dol`

The table of which stone combinations make which spell is at **ISO offset
`0x1F94EA`**, which is `Start.dol` **file offset `0x1DA8EA`** (the DOL starts
at ISO offset `0x1EC00`). It has 28 records of 12 bytes and ends with `FFFF`
padding.

```
AAAA  spell created (an item ID, type 01F5)
BBBB  number of stones (2 or 3)
CCCC  stone 1  \
CCCC  stone 2   > item IDs, in order; unused slots are 0000;
CCCC  stone 3  /  03E7 = any stone
DDDD  unknown (0 or 1)
```

**Order matters.** The stones must be combined in the order listed.

| Stones, in order | Spell |
|---|---|
| Life + Cure + Cure | Haste |
| Fire + (any) | Fire |
| Blizzard + (any) | Blizzard |
| Thunder + (any) | Thunder |
| Fire + Fire + Fire | Firaga |
| Blizzard + Blizzard + Blizzard | Blizzaga |
| Thunder + Thunder + Thunder | Thundaga |
| Fire + Fire | Fira |
| Blizzard + Blizzard | Blizzara |
| Thunder + Thunder | Thundara |
| Two different elements (any order) | Gravity |
| **Fire / Blizzard / Thunder + Life** | **Holy** |
| Life + Fire / Blizzard / Thunder | Slow |
| Life + two different elements (any order) | Stop |

So **Holy is an element stone followed by Life**; reversing the order gives
Slow. Stone IDs: Fire `0100`, Blizzard `0101`, Thunder `0102`, Cure `0105`,
Clear `0106`, Life `0107`. Spell IDs: Fire `0207`, Fira `0208`, Blizzard
`020B`, Blizzara `020C`, Thunder `020F`, Thundara `0210`, Slow `0214`, Holy
`0221`, Gravity `0226`, Haste `022A`, Firaga `0230`, Blizzaga `0231`, Thundaga
`0232`, Stop `023E`. (Item `0108` is also named "Holy", but it's a stone that
never drops; the castable spell is `0221`.)

### Command list

The game's list of command-menu categories (Clavat weapon, Lilty weapon, …,
attack magicite, support magicite, Phoenix Down, scroll, …) is referenced from
ISO offset `0x1F9285` (`Start.dol` file offset `0x1DA685`). The Game Boy
Advance version of the list (used for multiplayer) is in
`dvd/gba/ffcc_cli.bin` at file offset `0x25D4E` (ISO offset `0x1387D5FA`).

| ID | Command | ID | Command |
|---|---|---|---|
| `00`–`03` | Clavat / Lilty / Yuke / Selkie weapon | `13` | Drink barrel |
| `04` | Armor | `14`–`19` | Striped Apple, Cherry Cluster, Rainbow Grapes, Star Carrot, Gourd Potato, Round Corn |
| `05` | Shield | `1A` / `1B` | Meat / Fish |
| `06` | Gauntlets | `1C` | Phoenix Down |
| `07` | Helmet | `1D`–`21` | Family status (very good → very bad) |
| `08` | Belt | `22` | Scroll |
| `09` | Seed | `23` / `24` / `25` | Wheat / Flour / Bannock |
| `0A` | Accessory | `26` | Generic item |
| `0B` / `0C` | Artifact 1 / 2 | `27` | Empty item |
| `0D` / `0E` / `0F` | Pocket / Health / Ring artifact | | |
| `10` / `11` | Attack / Support magicite | | |
| `12` | Ore | | |

In the GBA list, IDs up to `1C` are the same; scroll, wheat, flour, bannock
and generic item are `30`–`34` instead.

The command-list offsets and IDs come from notes and haven't been
re-verified byte by byte; the fusion table above has been.
