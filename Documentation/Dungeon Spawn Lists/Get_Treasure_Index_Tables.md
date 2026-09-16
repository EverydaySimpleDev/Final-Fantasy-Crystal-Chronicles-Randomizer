# FFCC `get_treasure` Index Tables

Maps every `get_treasure` index referenced by `SPAWN_MONSTER`'s treasure-chest
form (`A`, opcode `0A FF FF 01 96`) and monster-drop form (`E`, opcode
`0A FF FF 01 92`) to the actual item(s) it resolves to, traced directly from
each stage's `get_treasure` bytecode.

## Methodology

`get_treasure(index)` is a **two-level switch**, confirmed by direct
bytecode tracing (not inferred from community guides):

- **Outer switch** on `index` (the `A`/`E` value). Each matching case falls
  straight through into...
- **Inner switch on a second value, 0-7** (8 slots). This is the real
  structure — **not** the 7-slot / "cycle 1/2/3" model external player
  guides use (built without code access). The 8 slots most likely track
  something finer-grained than the 3 broad cycles, plausibly a per-year
  or per-threshold counter — worth keeping in mind rather than assuming
  a clean 3-way split.
- Each inner case pushes one item ID (`03 00 00 <id16>`) immediately
  followed by a fixed 10-byte signature (`0d0c0300000000010000`) — the
  same signature `lootcft.py`'s `find_item_slots()` already keys off.
  Entries marked **(!)** below did *not* match this signature; the item
  shown is a lower-confidence fallback guess (see Caveats). Entries marked
  **(empty)** matched a distinct, confirmed "zero out locals" reset
  pattern instead of an item push - these slots genuinely carry no
  treasure, verified by direct bytecode inspection (not a heuristic
  guess). The two are diagnostically different and were confirmed not to
  overlap: `(!)` cases (e.g. `river_0` index 1/2) land on real unrelated
  code elsewhere in the file; `(empty)` cases (first seen in Mount
  Vellenge) contain no item-granting code at all for that slot.

Extraction tool: `get_treasure_dispatch.py` (reusable per-stage; see
`items_for_index()`).

## Caveats

- **Not every monster in `spawn_coordinates.json` necessarily spawns
  in-game.** Some entries may be unused/junk data left in the stage file,
  or serve a purpose other than a literal spawn (placeholder, cut content,
  a template the game copies at runtime, etc). Treat entries whose `E`
  doesn't resolve cleanly — or resolves to a suspicious sequential run
  like `Copper Sword, Iron Sword, Steel Blade...` (IDs 1-7 in file order)
  — as a signal the entry may not be real, not just a parsing failure.
  `river_0`'s `E = 1, 2, 26, 28, 52` all showed this pattern.
- A handful of monster entries in the raw JSON have huge, clearly-bogus
  `E` values (e.g. `268435474`). These are almost certainly an artifact of
  whatever script built `spawn_coordinates.json` misaligning on those
  specific records, not real indices — listed as garbage below rather than
  silently dropped, so it's visible which spawns need re-checking at the
  source.
- Low-confidence `(!)` entries used a loose fallback (first in-range
  `push_i32` after the case body, no signature match) and should not be
  trusted for actual randomization edits without manual verification.
- **Cross-stage pattern, `index = 1` — corrected:** in every stage checked
  through Tida, index 1 showed an all-`(!)` broken run, which looked like a
  reserved/empty sentinel. `gigas_1` disproves that: its `A=1` chest
  resolves to a real, coherent, on-theme set (`Fashion Kit`/`Lady's
  Accessories`, matching the reference doc's Moschet Manor chest almost
  exactly) — so index 1 is not universally reserved, it's simply *unused*
  in most of the stage files seen so far. Note also that even in this
  genuinely real case, 2 of the 8 slots (0 and 4) still show `(!)` — so
  `(!)` should be read per-slot, not as a verdict on the whole index.
- **Cross-stage pattern, `index = 2`:** also reproduces in every stage
  checked - but with a more specific signature: slots 0-6 fail `(!)`
  every time, while **slot 7 consistently succeeds** (REC_SIG match) and
  always resolves to a plain seed item (`Vegetable Seed`/`Fruit Seed`).
  This looks like index 2's inner switch genuinely only has a real case
  for slot 7, with slots 0-6 falling through into a shared default that
  happens to sit near an unrelated sequential sword-ID table (IDs 1-7 in
  file order) common to every stage's compiled code.

---

## River Belle Path (`river_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 13 | Buckler | Buckler | Silver Spectacles | Silver Spectacles | Black Hood | Buckler | Wonder Bangle | Wonder Bangle |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 29 | Bronze Belt | Bronze Belt | Iron Shield | Iron Shield | Iron Belt | Iron Belt | Mythril Belt | Mythril Shield |
| 30 | Bronze Gloves | Bronze Sallet | Bronze Gloves | Bronze Sallet | Iron Gloves | Iron Sallet | Mythril Gloves | Mythril Sallet |
| 31 | Novice's Weapon | Novice's Weapon | Novice's Weapon | Novice's Weapon | Frost Craft | Frost Craft | Valiant Weapon | Valiant Weapon |
| 32 | Bronze Armor | Bronze Armor | Bronze Armor | Bronze Armor | Lightning Craft | Lightning Craft | Mythril Armor | Mythril Armor |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Sonic Lance (!) | Halberd (!) | Dragoon Spear (!) | Treasured Spear (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Vegetable Seed |
| 5 | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 11 | Shuriken | Maneater | Double Axe | Green Beret | Flametongue | Ice Brand | Loaded Dice | Sasuke's Blade |
| 12 | Dragon's Whisker | Mage Masher | Silver Bracer | Cat's Bell | Sage's Staff | Kris | Rune Bell | Mage's Staff |
| 14 | Moogle Pocket | Moogle Pocket | Moogle Pocket | Moogle Pocket | Earth Pendant | Moogle Pocket | Earth Pendant | Moogle Pocket |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 26 | Copper Sword (!) | Iron Sword (!) | Iron | Iron | Iron | Iron | Mythril | Mythril |
| 27 | Bronze | Bronze | Bronze | Bronze | Iron | Iron | Mythril | Mythril |
| 28 | Copper Sword (!) | Flame Craft | Flame Craft | Mythril | Flame Craft | Griffin's Wing | Mythril | Griffin's Wing |
| 50 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 51 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 52 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Treasured Maul (!) |
| 268435474 | *(garbage - JSON extraction artifact, not a real index)* | | | | | | | |
| 536870931 | *(garbage - JSON extraction artifact, not a real index)* | | | | | | | |
| 805306369 | *(garbage - JSON extraction artifact, not a real index)* | | | | | | | |

## The Mushroom Forest (`kinoko_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Dragoon Spear (!) | Marr Spear (!) | Equipment 122 (Unused) (!) | Sonic Hammer (!) | Dreamcatcher (!) | Gold Mail (!) | Jade Bracer (Female) (!) | Dark Matter (!) |
| 11 | Shuriken | Maneater | Double Axe | Green Beret | Flametongue | Ice Brand | Loaded Dice | Sasuke's Blade |
| 12 | Dragon's Whisker | Mage Masher | Silver Bracer | Cat's Bell | Sage's Staff | Kris | Rune Bell | Mage's Staff |
| 13 | Buckler | Buckler | Silver Spectacles | Silver Spectacles | Black Hood | Black Hood | Wonder Bangle | Wonder Bangle |
| 14 | Moogle Pocket | Moogle Pocket | Earth Pendant | Earth Pendant | Earth Pendant | Earth Pendant | Moogle Pocket | Moogle Pocket |
| 37 | Copper Sword (!) | Iron Shield | Iron Shield | Iron Gloves | Mythril Shield | Mythril Gloves | Holy Shield | Gold Gloves |
| 38 | Copper Sword (!) | Iron Sallet | Iron Sallet | Iron Belt | Mythril Sallet | Mythril Belt | Time Sallet | Pure Belt |
| 39 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Fiend Kit | Fiend Kit | Fiend Kit | Daemon Kit | Daemon Kit |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Dragoon Spear (!) | Marr Spear (!) | Equipment 122 (Unused) (!) | Sonic Hammer (!) | Dreamcatcher (!) | Gold Mail (!) | Jade Bracer (Female) (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 5 | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes |
| 8 | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn |
| 9 | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 26 | Iron | Iron | Iron | Iron | Bastard Sword (!) | Mythril | Mythril | Mythril |
| 27 | Copper Sword (!) | Strange Seed | Strange Seed | Flower Seed | Bastard Sword (!) | Flower Seed | Flower Seed | Strange Seed |
| 28 | Gold | Silver | Crystal Ball | Gold | Gold | Silver | Crystal Ball | Father's Spear (!) |
| 29 | Copper Sword (!) | Chilly Gel | Chilly Gel | Faerie's Tear | Chilly Gel | Chilly Gel | Angel's Tear | Bronze |
| 30 | Bronze | Iron | Wheat Seed | Tiny Crystal | Mythril | Mythril | Tiny Crystal | Wheat Seed |
| 31 | Bronze | Bronze | Novice's Weapon | Novice's Weapon | Master's Weapon | Valiant Weapon | Mighty Weapon | Victorious Weapon |
| 32 | Bronze | Bronze | Bronze Armor | Bronze Armor | Mythril Armor | Mythril Armor | Pure Armor | Holy Armor |
| 33 | Bronze | Bronze Gloves | Bronze Gloves | Bronze | Mythril Shield | Mythril Gloves | Gold Gloves | Magic Shield |
| 34 | Bronze | Bronze | Bronze Sallet | Bronze Belt | Mythril Belt | Mythril Sallet | Time Sallet | Pure Belt |
| 35 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Tome of Speed | Tome of Speed | Ruby | Jade | Fiend Kit |
| 36 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Alloy | Alloy | Ruby | Jade | Diamond Ore |

> **Note:** `gob_2.cft` not yet provided — `spawn_coordinates.json` shows
> 11 monsters (0 chests) in `gob_2` that aren't traced below.

## Goblin Wall - Area 1 (`gob_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 11 | Shuriken | Maneater | Double Axe | Green Beret | Flametongue | Ice Brand | Loaded Dice | Sasuke's Blade |
| 14 | Earth Pendant | Earth Pendant | Earth Pendant | Moogle Pocket | Earth Pendant | Moogle Pocket | Earth Pendant | Moogle Pocket |
| 31 | Warrior's Weapon | Warrior's Weapon | Warrior's Weapon | Master's Weapon | Master's Weapon | Victorious Weapon | Valiant Weapon | Mighty Weapon |
| 32 | Iron Shield | Iron Gloves | Mythril Gloves | Mythril Shield | Mythril Gloves | Mythril Shield | Flame Gloves | Flame Shield |
| 33 | Bronze | Bronze | Iron | Tome of Wisdom | Tome of Wisdom | Tome of Wisdom | Secrets of Wisdom | Secrets of Wisdom |
| 34 | Copper Sword (!) | Master's Weapon | Master's Weapon | Master's Weapon | Master's Weapon | Victorious Weapon | Valiant Weapon | Mighty Weapon |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Iron Lance (!) | Marr Spear (!) | Sonic Hammer (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Vegetable Seed |
| 5 | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 29 | Copper Sword (!) | Iron Sword (!) | Iron | Iron | Mythril | Cerberus Fang | Mythril | Cerberus Fang |
| 30 | Bronze | Bronze | Iron | Iron | Alloy | Alloy | Mythril | Mythril |

## Goblin Wall - Area 2 (`gob_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 12 | Dragon's Whisker | Mage Masher | Silver Bracer | Cat's Bell | Sage's Staff | Kris | Rune Bell | Mage's Staff |
| 13 | Buckler | Buckler | Silver Spectacles | Silver Spectacles | Black Hood | Black Hood | Wonder Bangle | Wonder Bangle |
| 31 | Warrior's Weapon | Warrior's Weapon | Warrior's Weapon | Master's Weapon | Master's Weapon | Mighty Weapon | Valiant Weapon | Victorious Weapon |
| 32 | Iron Shield | Iron Gloves | Mythril Gloves | Mythril Shield | Lightning Gloves | Lightning Shield | Gold Gloves | Holy Shield |
| 33 | Iron Armor | Iron Armor | Iron Armor | Mythril Armor | Mythril Armor | Time Armor | Pure Armor | Holy Armor |
| 34 | Iron Sallet | Iron Belt | Mythril Sallet | Mythril Belt | Lightning Sallet | Lightning Belt | Time Sallet | Pure Belt |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Iron Lance (!) | Marr Spear (!) | Sonic Hammer (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 28 | Shiny Shard | Shiny Shard | Crystal Ball | Thunderball | Ruby | Jade | Thunderball | Thunderball |
| 29 | Copper Sword (!) | Iron Sword (!) | Blue Silk | Blue Silk | Diamond Ore | Diamond Ore | White Silk | White Silk |
| 30 | Bronze | Bronze | Iron | Iron | Alloy | Alloy | Mythril | Mythril |
| 268435486 | *(garbage - JSON extraction artifact)* | | | | | | | |

> **Note:** `mine_3.cft` not yet provided — `spawn_coordinates.json` shows
> 5 monsters (0 chests) in `mine_3` that aren't traced below.

## The Mine of Cathuriges - Area 1 (`mine_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Vegetable Seed |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 30 | Copper Sword (!) | Alloy | Alloy | Shiny Shard | Mythril | Mythril | Tiny Crystal | Diamond Ore |
| 31 | Copper Sword (!) | Iron Sword (!) | Tome of Speed | Tome of Speed | Tome of Speed | Secrets of Speed | Secrets of Speed | Secrets of Speed |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Vegetable Seed |
| 5 | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 8 | Star Carrot | Round Corn | Gourd Potato | Star Carrot | Round Corn | Gourd Potato | Star Carrot | Round Corn |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 11 | Shuriken | Maneater | Double Axe | Green Beret | Flametongue | Ice Brand | Loaded Dice | Sasuke's Blade |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 26 | Bronze | Novice's Weapon | Bronze Armor | Iron | Master's Weapon | Mythril Armor | Mythril | Mythril |
| 27 | Bronze | Bronze Shard | Iron Shard | Iron | Flame Craft | Magma Rock | Flame Armor | Magma Rock |
| 29 | Copper Sword (!) | Crystal Ball | Crystal Ball | Cockatrice Scale | Mythril | Mythril | Diamond Ore | Cockatrice Scale |

## The Mine of Cathuriges - Area 2 (`mine_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fish |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 30 | Copper Sword (!) | Alloy | Alloy | Shiny Shard | Mythril | Mythril | Tiny Crystal | Diamond Ore |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fish |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Rainbow Grapes | Cherry Cluster | Striped Apple | Rainbow Grapes | Cherry Cluster | Striped Apple | Rainbow Grapes |
| 8 | Star Carrot | Round Corn | Gourd Potato | Star Carrot | Round Corn | Gourd Potato | Star Carrot | Round Corn |
| 9 | Spring Water | Strange Liquid | Milk | Spring Water | Strange Liquid | Milk | Spring Water | Strange Liquid |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 27 | Bronze | Bronze Shard | Iron Shard | Iron | Flame Craft | Magma Rock | Flame Armor | Magma Rock |
| 29 | Copper Sword (!) | Crystal Ball | Crystal Ball | Cockatrice Scale | Mythril | Mythril | Diamond Ore | Cockatrice Scale |
| 268435468 | *(garbage - JSON extraction artifact)* | | | | | | | |

## The Mine of Cathuriges - Area 3 (`mine_2`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 13 | Buckler | Buckler | Silver Spectacles | Silver Spectacles | Black Hood | Black Hood | Wonder Bangle | Wonder Bangle |
| 14 | Earth Pendant | Earth Pendant | Earth Pendant | Earth Pendant | Moogle Pocket | Earth Pendant | Rune Blade (!) | Stone of Fire |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fish |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Rainbow Grapes | Cherry Cluster | Striped Apple | Rainbow Grapes | Cherry Cluster | Striped Apple | Rainbow Grapes |
| 8 | Star Carrot | Round Corn | Gourd Potato | Star Carrot | Round Corn | Gourd Potato | Star Carrot | Round Corn |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 28 | Copper Sword (!) | Iron | Iron | Alloy | Alloy | Ogre Fang | Mythril | Ogre Fang |
| 30 | Bronze | Bronze Shard | Iron Shard | Iron | Frost Craft | Chilly Gel | Frost Armor | Chilly Gel |
| 31 | Bronze | Bronze Shard | Iron Shard | Iron | Lightning Craft | Thunderball | Lightning Armor | Thunderball |

## Tida - Area 1 (`ruin_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fish |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 11 | Maneater | Ashura | Kaiser Knuckles | Ice Brand | Ogrekiller | Fang Charm | Engetsurin | Mjollnir |
| 13 | Sparkling Bracer | Sparkling Bracer | Helm of Arai | Helm of Arai | Elven Mantle | Elven Mantle | Rune Staff | Wonder Bangle |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 31 | Warrior's Weapon | Warrior's Weapon | Warrior's Weapon | Master's Weapon | Master's Weapon | Victorious Weapon | Valiant Weapon | Mighty Weapon |
| 32 | Iron Armor | Iron Armor | Iron Armor | Mythril Armor | Mythril Armor | Time Armor | Pure Armor | Holy Armor |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Iron Lance (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fish |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 26 | Bronze Shard | Crystal Ball | Iron Shard | Shiny Shard | Blue Silk | Ruby | Jade | Tiny Crystal |
| 27 | Copper Sword (!) | Iron | Iron | Worm Antenna | Bastard Sword (!) | Defender (!) | Worm Antenna | Worm Antenna |
| 28 | Copper Sword (!) | Iron Sword (!) | Gear | Gear | Bastard Sword (!) | Defender (!) | Gear | Gear |
| 29 | Copper Sword (!) | Flower Seed | Flower Seed | Strange Seed | Bastard Sword (!) | Flower Seed | Flower Seed | Strange Seed |
| 30 | Bronze | Bronze Shard | Iron Shard | Iron | Flame Craft | Magma Rock | Flame Armor | Magma Rock |
| 51 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 52 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | ? (!) |
| 268435456 | *(garbage - JSON extraction artifact)* | | | | | | | |
| 536870942 | *(garbage - JSON extraction artifact)* | | | | | | | |

## Tida - Area 2 (`ruin_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 12 | Dragon's Whisker | Mage Masher | Silver Bracer | Cat's Bell | Sage's Staff | Kris | Rune Bell | Mage's Staff |
| 14 | Chocobo Pocket | Chocobo Pocket | Chocobo Pocket | Moogle Pocket | Bastard Sword (!) | Chocobo Pocket | Chocobo Pocket | Moogle Pocket |
| 32 | Iron Shield | Iron Gloves | Mythril Gloves | Mythril Shield | Frost Gloves | Frost Shield | Gold Gloves | Magic Shield |
| 33 | Iron Sallet | Iron Belt | Mythril Sallet | Mythril Belt | Frost Sallet | Frost Belt | Eternal Sallet | Wind Belt |
| 34 | Copper Sword (!) | Iron Sword (!) | Faerie Kit | Faerie Kit | Faerie Kit | Angel Kit | Angel Kit | Angel Kit |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Iron Lance (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 5 | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 26 | Copper Sword (!) | Iron Sword (!) | Jagged Scythe | Jagged Scythe | Mythril | Diamond Ore | Diamond Ore | Jagged Scythe |
| 27 | Copper Sword (!) | Iron | Iron | Worm Antenna | Bastard Sword (!) | Defender (!) | Worm Antenna | Worm Antenna |
| 28 | Copper Sword (!) | Iron Sword (!) | Gear | Gear | Bastard Sword (!) | Defender (!) | Gear | Gear |
| 29 | Copper Sword (!) | Flower Seed | Flower Seed | Strange Seed | Bastard Sword (!) | Flower Seed | Flower Seed | Strange Seed |
| 30 | Bronze | Bronze Shard | Iron Shard | Iron | Flame Craft | Magma Rock | Flame Armor | Magma Rock |
| 31 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Mythril | Mythril | Alloy | Tiny Crystal | Diamond Ore |
| 34 | Copper Sword (!) | Iron Sword (!) | Faerie Kit | Faerie Kit | Faerie Kit | Angel Kit | Angel Kit | Angel Kit |
| 805306377 | *(garbage - JSON extraction artifact)* | | | | | | | |
| 1073741825 | *(garbage - JSON extraction artifact)* | | | | | | | |
| 1073741850 | *(garbage - JSON extraction artifact)* | | | | | | | |

> **Note:** `gigas_8.cft` not provided (2 monsters, 0 chests) — presumably
> the boss stage you're intentionally skipping.

## Moschet Manor - Area 1 (`gigas_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 14 | Chocobo Pocket | Chocobo Pocket | Earth Pendant | Earth Pendant | Earth Pendant | Earth Pendant | Moon Pendant | Moon Pendant |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 26 | Iron | Iron | Alloy | Alloy | Alloy | Alloy | Mythril | Mythril |
| 30 | Bronze | Iron | Tiny Crystal | Tiny Crystal | Mythril | Mythril | Tiny Crystal | ? (!) |

## Moschet Manor - Area 2 (`gigas_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Copper Sword (!) | Lady's Accessories | Lady's Accessories | Fashion Kit | Bastard Sword (!) | Fashion Kit | Fashion Kit | Lady's Accessories |

### Monsters

*(none)*

## Moschet Manor - Area 3 (`gigas_2`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 11 | Shuriken | Ashura | Kaiser Knuckles | Flametongue | Fang Charm | Ogrekiller | Engetsurin | Mjollnir |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 5 | Wheat Seed | Wheat Seed | Wheat Seed | Wheat Seed | Wheat Seed | Wheat Seed | Wheat Seed | Wheat Seed |

## Moschet Manor - Area 4 (`gigas_3`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 12 | Rune Staff | Faerie Ring | Winged Cap | Wonder Wand | Candy Ring | Red Slippers | Noah's Lute | Dark Matter |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 27 | Silver | Holy Water | Ruby | Coeurl Whisker | Ruby | Silver | Holy Water | Coeurl Whisker |
| 28 | Equipment 119 (Unused) (!) | Equipment 122 (Unused) (!) | Sonic Hammer (!) | Mythril Hammer (!) | Ultima Maul (!) | Gold Mail (!) | Yellow Feather | Yellow Feather |

## Moschet Manor - Area 5 (`gigas_4`)

### Chests

*(none)*

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 26 | Bronze | Iron | Alloy | Alloy | Alloy | Alloy | Mythril | Mythril |
| 27 | Silver | Holy Water | Ruby | Coeurl Whisker | Ruby | Silver | Holy Water | Coeurl Whisker |
| 28 | Equipment 119 (Unused) (!) | Equipment 122 (Unused) (!) | Sonic Hammer (!) | Mythril Hammer (!) | Ultima Maul (!) | Gold Mail (!) | Yellow Feather | Yellow Feather |

## Moschet Manor - Area 6 (`gigas_5`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 27 | Silver | Holy Water | Ruby | Coeurl Whisker | Ruby | Silver | Holy Water | Coeurl Whisker |
| 28 | Equipment 119 (Unused) (!) | Equipment 122 (Unused) (!) | Sonic Hammer (!) | Mythril Hammer (!) | Ultima Maul (!) | Gold Mail (!) | Yellow Feather | Yellow Feather |

## Moschet Manor - Area 7 (`gigas_6`)

### Chests

*(none)*

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |

## Moschet Manor - Area 8 (`gigas_7`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 13 | Sparkling Bracer | Sparkling Bracer | Helm of Arai | Helm of Arai | Elven Mantle | Elven Mantle | Wonder Bangle | Wonder Bangle |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |

> **Note:** `water_1.cft` not yet provided — `spawn_coordinates.json` shows
> 11 monsters (0 chests) in `water_1` that aren't traced below.

## Veo Lu Sluice - Area 1 (`water_0`)

### Chests

> Note: raw `A` values in the JSON for this stage all have an extra
> `0x10000` (65536) bit set (e.g. `65546` = `65536 + 10`). Corrected
> index shown below is `A - 65536`; the raw value is kept for reference.

| A (raw) | A (corrected) | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|---|
| 65537 | 1 | Mythril Shield (!) | Diamond Shield (!) | Iron Gauntlets (!) | Gold Armlets (!) | Jade Bracer (Female) (!) | Dark Matter (!) | Item Gil (Unused) (!) | design 100 (Unused) (!) |
| 65546 | 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 65547 | 11 | Ashura | Kaiser Knuckles | Power Wristband | Twisted Headband | Ogrekiller | Engetsurin | Masquerade | Onion Sword |
| 65548 | 12 | Dragon's Whisker | Book of Light | Silver Bracer | Kris | Sage's Staff | Red Slippers | Dark Matter | Tome of Ultima |
| 65549 | 13 | Drill | Drill | Main Gauche | Main Gauche | Rat's Tail | Rat's Tail | Chicken Knife | Chicken Knife |
| 65557 | 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 65566 | 30 | Copper Sword (!) | Iron Sword (!) | Frost Belt | Frost Belt | Frost Belt | Frost Belt | Rune Blade (!) | Ultima Lance (!) |
| 65567 | 31 | Copper Sword (!) | Iron Sword (!) | Frost Shield | Frost Shield | Frost Shield | Frost Shield | Rune Blade (!) | Equipment 119 (Unused) (!) |
| 65568 | 32 | Copper Sword (!) | Frost Gloves | Frost Gloves | Frost Gloves | Frost Gloves | Defender (!) | Rune Blade (!) | Equipment 120 (Unused) (!) |
| 65569 | 33 | Copper Sword (!) | Frost Armor | Frost Armor | Frost Armor | Frost Armor | Defender (!) | Rune Blade (!) | Equipment 121 (Unused) (!) |
| 65570 | 34 | Copper Sword (!) | Frost Sallet | Frost Sallet | Frost Sallet | Frost Sallet | Defender (!) | Rune Blade (!) | Equipment 126 (Unused) (!) |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 0 | NOT FOUND IN SWITCH | | | | | | | |
| 1 | Mythril Shield (!) | Diamond Shield (!) | Iron Gauntlets (!) | Gold Armlets (!) | Jade Bracer (Female) (!) | Dark Matter (!) | Item Gil (Unused) (!) | design 100 (Unused) (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 5 | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 14 | Moon Pendant | Moon Pendant | Moon Pendant | Ring of Blizzard | Ring of Blizzard | Ring of Blizzard | Ring of Blizzard | Ring of Blizzard |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 25 | Shella Mark | Shella Mark | Shella Mark | Shella Mark | Shella Mark | Shella Mark | Shella Mark | Shella Mark |
| 26 | Alloy | Alloy | Shella Mark | Griffin's Wing | Bastard Sword (!) | Shella Mark | Shella Mark | Griffin's Wing |
| 27 | Copper Sword (!) | Alloy | Alloy | Toad Oil | Bastard Sword (!) | Defender (!) | Toad Oil | Toad Oil |
| 28 | Copper Sword (!) | Iron Sword (!) | Chilly Gel | Chilly Gel | Bastard Sword (!) | Defender (!) | Chilly Gel | Chilly Gel |
| 29 | Copper Sword (!) | Iron Shard | Iron Shard | Chilly Gel | Bastard Sword (!) | Iron Shard | Iron Shard | Chilly Gel |
| 30 | (empty) | (empty) | Frost Belt | Frost Belt | Frost Belt | Frost Belt | (empty) | (empty) |
| 31 | (empty) | (empty) | Frost Shield | Frost Shield | Frost Shield | Frost Shield | (empty) | (empty) |
| 32 | (empty) | Frost Gloves | Frost Gloves | Frost Gloves | Frost Gloves | Defender (!) | (empty) | (empty) |
| 33 | (empty) | Frost Armor | Frost Armor | Frost Armor | Frost Armor | Defender (!) | (empty) | (empty) |
| 34 | (empty) | Frost Sallet | Frost Sallet | Frost Sallet | Frost Sallet | Defender (!) | (empty) | (empty) |
| 50 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Stone of Fire |
| 51 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 52 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | ? (!) |
| 1073741824 | *(garbage - JSON extraction artifact)* | | | | | | | |

## Selepation Cave - Area 1 (`cave_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 11 | Green Beret | Green Beret | Power Wristband | Twisted Headband | Heavy Armband | Mjollnir | Masquerade | Onion Sword |
| 14 | Moon Pendant | Moon Pendant | Moon Pendant | Ring of Thunder | Ring of Thunder | Ring of Thunder | Ring of Thunder | Ring of Thunder |
| 30 | Iron Shield | Iron Gloves | Mythril Gloves | Mythril Shield | Lightning Gloves | Lightning Shield | Gold Gloves | Holy Shield |
| 31 | Iron Sallet | Iron Belt | Mythril Sallet | Mythril Belt | Lightning Sallet | Lightning Belt | Time Sallet | Pure Belt |
| 32 | Iron Armor | Iron Armor | Iron Armor | Mythril Armor | Mythril Armor | Time Armor | Pure Armor | Holy Armor |
| 33 | Copper Sword (!) | Iron Sword (!) | Ring of Light | Ring of Light | Bastard Sword (!) | Defender (!) | Ring of Light | Ring of Light |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Sonic Lance (!) | Dragoon Spear (!) | Treasured Spear (!) | Marr Spear (!) | Equipment 126 (Unused) (!) | Gold Mail (!) | Mythril Belt (!) | Jade Bracer (Female) (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fish |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 26 | Copper Sword (!) | Iron Sword (!) | Hard Shell | Hard Shell | Bastard Sword (!) | Defender (!) | Hard Shell | Hard Shell |
| 27 | Copper Sword (!) | Iron Sword (!) | Thunderball | Thunderball | Bastard Sword (!) | Defender (!) | Thunderball | Thunderball |
| 28 | Copper Sword (!) | Iron Sword (!) | Gigas Claw | Gigas Claw | Bastard Sword (!) | Defender (!) | Gigas Claw | Gigas Claw |
| 29 | Alloy | Alloy | Mythril | Mythril | Alloy | Alloy | Mythril | Mythril |

## Selepation Cave - Area 2 (`cave_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 12 | Mage Masher | Book of Light | Cat's Bell | Wonder Wand | Faerie Ring | Rune Bell | Gold Hairpin | Tome of Ultima |
| 13 | Drill | Drill | Main Gauche | Main Gauche | Rat's Tail | Rat's Tail | Chicken Knife | Chicken Knife |
| 30 | Warrior's Weapon | Warrior's Weapon | Master's Weapon | Master's Weapon | Master's Weapon | Valiant Weapon | Mighty Weapon | Victorious Weapon |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Sonic Lance (!) | Dragoon Spear (!) | Treasured Spear (!) | Marr Spear (!) | Equipment 126 (Unused) (!) | Gold Mail (!) | Mythril Belt (!) | Jade Bracer (Female) (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fish |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 26 | Copper Sword (!) | Iron Sword (!) | Cockatrice Scale | Cockatrice Scale | Bastard Sword (!) | Defender (!) | Cockatrice Scale | Cockatrice Scale |
| 27 | Copper Sword (!) | Iron Sword (!) | Thunderball | Thunderball | Bastard Sword (!) | Defender (!) | Thunderball | Thunderball |
| 28 | Copper Sword (!) | Iron Sword (!) | Gigas Claw | Gigas Claw | Bastard Sword (!) | Defender (!) | Gigas Claw | Gigas Claw |

> **Note:** `fort_1.cft` not provided (6 monsters, 0 chests) — presumably
> the boss stage you're intentionally skipping.

## Daemon's Court (`fort_0`)

### Chests

> Note: raw `A` values here carry a `0x20000` high bit (a *different*
> flag value than `water_0`'s `0x10000` - consistent with a per-cycle
> flag bit rather than a fixed offset). Corrected index = `A & 0xFFFF`.

| A (raw) | A (corrected) | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|---|
| 11 | 11 | Power Wristband | Fang Charm | Engetsurin | Twisted Headband | Masquerade | Heavy Armband | Giant's Glove | Onion Sword |
| 21 | 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 32 | 32 | Copper Sword (!) | Eyewear Techniques | Eyewear Techniques | Eyewear Techniques | Bastard Sword (!) | Designer Glasses | Designer Glasses | Designer Glasses |
| 131082 | 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 131084 | 12 | Rune Staff | Book of Light | Faerie Ring | Cat's Bell | Mage's Staff | Book of Light | Noah's Lute | Tome of Ultima |
| 131085 | 13 | Drill | Drill | Main Gauche | Main Gauche | Rat's Tail | Rat's Tail | Chicken Knife | Chicken Knife |
| 131086 | 14 | Moon Pendant | Moon Pendant | Chocobo Pocket | Chocobo Pocket | Moon Pendant | Chocobo Pocket | Moon Pendant | Chocobo Pocket |
| 131090 | 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 131091 | 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 131103 | 31 | Warrior's Weapon | Warrior's Weapon | Master's Weapon | Master's Weapon | Master's Weapon | Victorious Weapon | Mighty Weapon | Valiant Weapon |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 0 | NOT FOUND IN SWITCH | | | | | | | |
| 1 | Rune Hammer (!) | Sonic Hammer (!) | Mythril Hammer (!) | Father's Hammer (!) | Gold Mail (!) | Iron Gauntlets (!) | Dark Matter (!) | Silver (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fish |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 26 | Copper Sword (!) | Iron Sword (!) | Coeurl Whisker | Coeurl Whisker | Bastard Sword (!) | Defender (!) | Coeurl Whisker | Coeurl Whisker |
| 27 | Iron | Iron | Mythril | Mythril | Bastard Sword (!) | Alloy | Alloy | Mythril |
| 28 | Copper Sword (!) | Heavenly Dust | Heavenly Dust | Holy Water | Bastard Sword (!) | Heavenly Dust | Heavenly Dust | Holy Water |
| 268435456 | *(garbage - JSON extraction artifact)* | | | | | | | |
| 536870912 | *(garbage - JSON extraction artifact)* | | | | | | | |

> **Note:** `swamp_3.cft` not provided (4 monsters, 0 chests) — presumably
> the boss stage you're intentionally skipping.

## Conall Curach - Area 1 (`swamp_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 31 | Valiant Weapon | Mighty Weapon | Victorious Weapon | Master's Weapon | Valiant Weapon | Mighty Weapon | Victorious Weapon | Master's Weapon |
| 32 | Mythril Shield | Mythril Shield | Lightning Shield | Lightning Shield | Magic Shield | Holy Shield | Diamond Shield | Diamond Shield |
| 34 | Mythril Sallet | Mythril Sallet | Lightning Sallet | Lightning Sallet | Time Sallet | Eternal Sallet | Diamond Sallet | Diamond Sallet |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 26 | Chilly Gel | Chilly Gel | Chilly Gel | Chilly Gel | Chilly Gel | Chilly Gel | Chilly Gel | Chilly Gel |
| 27 | Thunderball | Thunderball | Thunderball | Thunderball | Thunderball | Thunderball | Thunderball | Thunderball |
| 28 | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Vegetable Seed | Fruit Seed |
| 29 | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Fruit Seed | Marr Spear (!) |
| 30 | Copper Sword (!) | Iron Sword (!) | Wheat Seed | Wheat Seed | Bastard Sword (!) | Defender (!) | Wheat Seed | Wheat Seed |

## Conall Curach - Area 2 (`swamp_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 11 | Kaiser Knuckles | Maneater | Green Beret | Loaded Dice | Flametongue | Mjollnir | Heavy Armband | Giant's Glove |
| 12 | Faerie Ring | Mage Masher | Candy Ring | Red Slippers | Sage's Staff | Noah's Lute | Dark Matter | Tome of Ultima |
| 13 | Sparkling Bracer | Sparkling Bracer | Main Gauche | Main Gauche | Teddy Bear | Teddy Bear | Chicken Knife | Chicken Knife |
| 14 | Star Pendant | Star Pendant | Star Pendant | Ring of Cure | Star Pendant | Ring of Cure | Star Pendant | Ring of Cure |
| 31 | Soul of the Lion | Soul of the Lion | Soul of the Lion | Soul of the Lion | Soul of the Dragon | Soul of the Dragon | Soul of the Dragon | Soul of the Dragon |
| 32 | Mythril Gloves | Mythril Gloves | Lightning Gloves | Lightning Gloves | Gold Gloves | Gold Gloves | Diamond Gloves | Diamond Gloves |
| 33 | Mythril Armor | Mythril Armor | Mythril Armor | Eternal Armor | Pure Armor | Holy Armor | Diamond Armor | Diamond Armor |
| 34 | Mythril Belt | Mythril Belt | Lightning Belt | Lightning Belt | Wind Belt | Pure Belt | Diamond Belt | Diamond Belt |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 21 | Copper Sword (!) | Pressed Flower | Pressed Flower | Remedy | Bastard Sword (!) | Pressed Flower | Pressed Flower | Remedy |
| 26 | Copper Sword (!) | Iron Sword (!) | Toad Oil | Toad Oil | Bastard Sword (!) | Toad Oil | Toad Oil | Ancient Potion |
| 27 | Copper Sword (!) | Jagged Scythe | Jagged Scythe | Jagged Scythe | Jagged Scythe | Jagged Scythe | Jagged Scythe | Legendary Weapon |

## Conall Curach - Area 3 (`swamp_2`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 31 | Valiant Weapon | Mighty Weapon | Victorious Weapon | Master's Weapon | Valiant Weapon | Mighty Weapon | Victorious Weapon | Legendary Weapon |
| 32 | Mythril Shield | Mythril Gloves | Lightning Gloves | Lightning Gloves | Gold Gloves | Holy Shield | Diamond Gloves | Diamond Shield |
| 33 | Mythril Armor | Mythril Armor | Mythril Armor | Eternal Armor | Pure Armor | Gold Armor | Diamond Armor | Diamond Armor |
| 34 | Mythril Sallet | Mythril Belt | Lightning Sallet | Lightning Belt | Time Sallet | Pure Belt | Diamond Sallet | Diamond Belt |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 26 | Worn Bandanna | Worn Bandanna | Worn Bandanna | Worn Bandanna | Worn Bandanna | Worn Bandanna | Worn Bandanna | Worn Bandanna |
| 28 | Copper Sword (!) | Iron Sword (!) | Blue Silk | Blue Silk | Diamond Ore | Diamond Ore | White Silk | White Silk |
| 29 | Copper Sword (!) | Iron Sword (!) | Orichalcum | Orichalcum | Diamond Ore | Diamond Ore | Diamond Ore | Orichalcum |
| 30 | Bronze | Bronze | Iron | Iron | Alloy | Alloy | Mythril | Mythril |

> **Note:** `city_2.cft` not provided (4 monsters, 0 chests) — presumably
> the boss stage you're intentionally skipping.

## Rebena Te Ra - Area 1 (`city_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 11 | Shuriken | Power Wristband | Ice Brand | Fang Charm | Engetsurin | Heavy Armband | Giant's Glove | Onion Sword |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 31 | Copper Sword (!) | Iron Sword (!) | Tome of Magic | Tome of Magic | Tome of Magic | Tome of Sorcery | Tome of Sorcery | Tome of Sorcery |
| 32 | Copper Sword (!) | Blue Yarn | Blue Yarn | White Yarn | Blue Yarn | White Yarn | Ancient Potion | Ancient Potion |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 0 | NOT FOUND IN SWITCH | | | | | | | |
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 27 | Copper Sword (!) | Iron Sword (!) | Gear | Gear | Bastard Sword (!) | Defender (!) | Gear | Gear |
| 28 | Copper Sword (!) | Iron Sword (!) | Tiny Crystal | Tiny Crystal | Alloy | Alloy | Diamond Ore | Diamond Ore |
| 29 | Copper Sword (!) | Iron Sword (!) | Blue Silk | Blue Silk | Diamond Ore | Diamond Ore | White Silk | White Silk |
| 30 | Copper Sword (!) | Iron Sword (!) | Fiend's Claw | Fiend's Claw | Mythril | Mythril | Mythril | Devil's Claw |
| 268435465 | *(garbage - JSON extraction artifact)* | | | | | | | |

## Rebena Te Ra - Area 2 (`city_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 12 | Rune Staff | Silver Bracer | Winged Cap | Rune Bell | Mage Masher | Cat's Bell | Gold Hairpin | Mage's Staff |
| 13 | Silver Spectacles | Silver Spectacles | Elven Mantle | Elven Mantle | Teddy Bear | Teddy Bear | Chicken Knife | Chicken Knife |
| 14 | Star Pendant | Star Pendant | Gobbie Pocket | Gobbie Pocket | Star Pendant | Gobbie Pocket | Star Pendant | Gobbie Pocket |
| 31 | Copper Sword (!) | Iron Sword (!) | Tome of Magic | Tome of Magic | Tome of Magic | Tome of Sorcery | Tome of Sorcery | Tome of Sorcery |
| 32 | Copper Sword (!) | Blue Yarn | Blue Yarn | White Yarn | Blue Yarn | White Yarn | Ancient Potion | Ancient Potion |
| 33 | Copper Sword (!) | Holy Shield | Holy Shield | Pure Belt | Holy Armor | Pure Armor | Diamond Armor | Diamond Armor |
| 34 | Copper Sword (!) | Eternal Sallet | Eternal Sallet | Gold Gloves | Pure Armor | Holy Armor | Diamond Armor | Diamond Armor |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 0 | NOT FOUND IN SWITCH | | | | | | | |
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 27 | Copper Sword (!) | Iron Sword (!) | Gear | Gear | Bastard Sword (!) | Defender (!) | Gear | Gear |
| 29 | Copper Sword (!) | Holy Water | Holy Water | Heavenly Dust | Diamond Ore | Diamond Ore | Holy Water | Heavenly Dust |
| 30 | Copper Sword (!) | Iron Sword (!) | Cerberus Fang | Cerberus Fang | Mythril | Mythril | Mythril | Cerberus Fang |

> **Note:** `lava_2.cft` not provided (7 monsters, 0 chests) — presumably
> the boss stage you're intentionally skipping. Also worth flagging: the
> reference doc lists Mount Kilanda chest contents as "N/A" (not mapped by
> any existing community guide) - the table below is new data, not a
> cross-check against prior documentation like the other stages.

## Mount Kilanda - Area 1 (`lava_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |
| 31 | Copper Sword (!) | Flame Craft | Flame Craft | Flame Craft | Zeal Kit | Flame Armor | Flame Armor | Healing Kit |
| 32 | Flame Sallet | Flame Shield | Flame Gloves | Flame Belt | Flame Sallet | Flame Shield | Flame Gloves | Flame Belt |
| 33 | Warrior's Weapon | Warrior's Weapon | Master's Weapon | Master's Weapon | Master's Weapon | Mighty Weapon | Valiant Weapon | Victorious Weapon |
| 34 | Iron | Iron | Iron | Mythril | Mythril | Alloy | Mythril | Diamond Ore |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 26 | Copper Sword (!) | Magma Rock | Magma Rock | Faerie's Tear | Bastard Sword (!) | Magma Rock | Magma Rock | Faerie's Tear |
| 27 | Copper Sword (!) | Iron Sword (!) | Hard Shell | Hard Shell | Bastard Sword (!) | Defender (!) | Hard Shell | Hard Shell |

## Mount Kilanda - Area 2 (`lava_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 29 | Copper Sword (!) | Iron Sword (!) | Kilanda Sulfur | Kilanda Sulfur | Kilanda Sulfur | Kilanda Sulfur | Kilanda Sulfur | Kilanda Sulfur |
| 30 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Legendary Weapon | Legendary Weapon |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 11 | Power Wristband | Flametongue | Engetsurin | Giant's Glove | Twisted Headband | Heavy Armband | Masquerade | Onion Sword |
| 12 | Cat's Bell | Faerie Ring | Sage's Staff | Noah's Lute | Red Slippers | Kris | Wonder Wand | Gold Hairpin |
| 13 | Buckler | Buckler | Black Hood | Black Hood | Chicken Knife | Chicken Knife | Teddy Bear | Teddy Bear |
| 14 | Ring of Fire | Ring of Fire | Moon Pendant | Moon Pendant | Ring of Fire | Moon Pendant | Star Pendant | Ring of Fire |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 26 | Copper Sword (!) | Magma Rock | Magma Rock | Faerie's Tear | Bastard Sword (!) | Magma Rock | Magma Rock | Angel's Tear |
| 27 | Copper Sword (!) | Iron Sword (!) | Ogre Fang | Ogre Fang | Bastard Sword (!) | Ogre Fang | Ogre Fang | Diamond Armor |
| 28 | Copper Sword (!) | Iron Sword (!) | Coeurl Whisker | Coeurl Whisker | Bastard Sword (!) | Coeurl Whisker | Coeurl Whisker | Ancient Potion |

> **Note:** `desert_2.cft` not provided (14 monsters, 0 chests) - worth
> double-checking whether this is actually the boss file, since 14
> monsters is higher than the boss-stage counts seen elsewhere (typically
> 3-8). Also: the reference doc lists Lynari Desert chest contents as
> "N/A" - the table below is new data, not a cross-check.

## Lynari Desert - Area 1 (`desert_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 14 | Star Pendant | Gobbie Pocket | Star Pendant | Gobbie Pocket | Star Pendant | Gobbie Pocket | Star Pendant | Gobbie Pocket |
| 31 | Valiant Weapon | Mighty Weapon | Victorious Weapon | Master's Weapon | Valiant Weapon | Mighty Weapon | Victorious Weapon | Legendary Weapon |
| 32 | Flame Craft | Frost Craft | Lightning Craft | Flame Craft | Flame Craft | Frost Craft | Lightning Craft | Mythril Armor |
| 33 | Mythril Armor | Mythril Armor | Mythril Armor | Eternal Armor | Pure Armor | Gold Armor | Diamond Armor | Diamond Armor |
| 34 | Clockwork | New Clockwork | Gold Craft | Clockwork | Clockwork | New Clockwork | Gold Craft | (empty) |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 0 | NOT FOUND IN SWITCH | | | | | | | |
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 2 | Copper Sword (!) | Iron Sword (!) | Steel Blade (!) | Feather Saber (!) | Bastard Sword (!) | Defender (!) | Rune Blade (!) | Fruit Seed |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 26 | Copper Sword (!) | Iron Sword (!) | Zu's Beak | Zu's Beak | Bastard Sword (!) | Zu's Beak | Zu's Beak | Orichalcum |
| 27 | Copper Sword (!) | Iron Sword (!) | Needle | Needle | Bastard Sword (!) | Defender (!) | Needle | Needle |
| 28 | Copper Sword (!) | Iron Sword (!) | Thunderball | Thunderball | Bastard Sword (!) | Defender (!) | Thunderball | Thunderball |
| 29 | Copper Sword (!) | Alloy | Alloy | Alloy | Bastard Sword (!) | Alloy | Alloy | Diamond Ore |

## Lynari Desert - Area 2 (`desert_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 11 | Ashura | Fang Charm | Double Axe | Loaded Dice | Ogrekiller | Ice Brand | Giant's Glove | Masquerade |
| 31 | Copper Sword (!) | Iron Sword (!) | Goggle Techniques | Goggle Techniques | Goggle Techniques | Goggle Techniques | Designer Goggles | Designer Goggles |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 | Excalibur (!) | Treasured Sword (!) | Marr Sword (!) | Ultima Sword (!) | Sonic Hammer (!) | Equipment 126 (Unused) (!) | Iron Gauntlets (!) | Dark Matter (!) |
| 6 | Fish | Meat | Fish | Meat | Fish | Meat | Fish | Meat |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster | Rainbow Grapes | Striped Apple | Cherry Cluster |
| 8 | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato | Round Corn | Star Carrot | Gourd Potato |
| 9 | Spring Water | Milk | Strange Liquid | Spring Water | Milk | Strange Liquid | Spring Water | Milk |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 26 | Copper Sword (!) | Iron Sword (!) | Chimera's Horn | Chimera's Horn | Bastard Sword (!) | Chimera's Horn | Chimera's Horn | Legendary Weapon |
| 27 | Copper Sword (!) | Iron Sword (!) | Needle | Needle | Bastard Sword (!) | Defender (!) | Needle | Needle |

> **Note:** `meteo_2.cft` and `meteo_3.cft` not provided (24 monsters each,
> 0 chests) - worth checking whether these are real areas rather than boss
> files, since 24 monsters is well above the boss-stage pattern seen
> elsewhere.

## Mount Vellenge - Area 1 (`meteo_0`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 11 | Flametongue | Ice Brand | Sasuke's Blade | Mjollnir | (empty) | (empty) | (empty) | Kris |
| 12 | Kris | Sage's Staff | Mage's Staff | Dark Matter | (empty) | (empty) | (empty) | Elven Mantle |
| 13 | Elven Mantle | Elven Mantle | Wonder Bangle | Wonder Bangle | (empty) | (empty) | (empty) | Masamune |
| 14 | Masamune | Aegis | Ribbon | (empty) | (empty) | (empty) | (empty) | Stone of Fire |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 0 | NOT FOUND IN SWITCH | | | | | | | |
| 6 | Fish | Meat | Fish | Meat | (empty) | (empty) | (empty) | Striped Apple |
| 7 | Striped Apple | Cherry Cluster | Rainbow Grapes | (empty) | (empty) | (empty) | (empty) | Star Carrot |
| 8 | Star Carrot | Gourd Potato | Round Corn | (empty) | (empty) | (empty) | (empty) | Spring Water |
| 9 | Spring Water | Milk | Strange Liquid | (empty) | (empty) | (empty) | (empty) | Phoenix Down |
| 10 | Phoenix Down | Phoenix Down | Phoenix Down | Phoenix Down | (empty) | (empty) | (empty) | Flametongue |
| 15 | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire | Stone of Fire |
| 16 | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard | Stone of Blizzard |
| 17 | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder | Stone of Thunder |
| 18 | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure | Stone of Cure |
| 19 | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life | Stone of Life |
| 20 | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear | Stone of Clear |
| 21 | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure | Stone of Fire | Stone of Blizzard | Stone of Thunder | Stone of Cure |

## Mount Vellenge - Area 2 (`meteo_1`)

### Chests

| A | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 11 | Flametongue | Ice Brand | Sasuke's Blade | Mjollnir | (empty) | (empty) | (empty) | Kris |
| 12 | Kris | Sage's Staff | Mage's Staff | Dark Matter | (empty) | (empty) | (empty) | Elven Mantle |
| 13 | Elven Mantle | Elven Mantle | Wonder Bangle | Wonder Bangle | (empty) | (empty) | (empty) | Stone of Fire |

### Monsters

| E | Slot 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 0 | NOT FOUND IN SWITCH | | | | | | | |
