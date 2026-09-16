# Item Model Reference (dvd/char/fa/ mesh IDs)

Every item's `model` field (`param.cfd` record offset 2) is a packed value:
`meshId = value & 0xFFF`, `variant = value >> 12`. `meshId` indexes into
`dvd/char/fa/f0NN/f0NN_root.tex` (and its matching geometry in the packed
`.mrg` archives) - this is the kind=3 "ground pickup / bonus-screen 3D
preview" mesh namespace (see `Adding Custom Items and Artifacts.md` for how
`model` is consumed differently by weapon/shield/character code).

Built directly from a real ISO (`Updated_start_alfitaria_v2.iso`, verified
2026-09-14): scanned the entire 1205-row `param.cfd` table for every item's
masked mesh id, and cross-referenced against which `f0NN_root.tex` files
actually exist in the disc.

- **Status `used`**: at least one item (named or not) points at this mesh.
- **Status `UNUSED`**: the mesh file exists on the disc but NO item
  anywhere in the game references it - a free, distinct look for a new
  custom item/artifact (see the "Giving a new item/artifact a unique look"
  section in `Adding Custom Items and Artifacts.md`). 83 of 138 fall here.
- **`(no mesh file!)`**: an item's record points at a mesh id with no
  corresponding file on disc (ids 5, 6, 38, 49, 78, 111, 124, 125, 129) -
  these are usually reusing a hardcoded record layout rather than an actual
  missing asset (e.g. Ragnarok/Halberd/etc., all late-game weapons); not
  worth targeting for a new item since nothing will render.
- **"N unnamed recipe/scroll record(s)"**: additional `param.cfd` rows that
  point at this mesh id but aren't in this repo's curated item-name table
  (`ffcc_items.py`) - mostly recipes/scrolls (0x191-0x1ed) and internal
  spell/effect definition rows (the ~0x1f5+ range used by the Ring
  spell-indirection mechanism - see `project_ffcc_artifact_effects.md`).
  These aren't world-droppable collectibles, so their model field is
  likely inherited from a template and not meaningful - don't read anything
  into which mesh they point at.

| Model | Mesh | Status | Named item(s) using it |
|---|---|---|---|
| 1 | f001 | used | Copper Sword, Feather Saber, Test1, Test2, Treasured Sword (72 unnamed recipe/scroll record(s)) |
| 2 | f002 | used | Bastard Sword, Father's Sword, Iron Sword, Marr Sword, Ultima Sword |
| 3 | f003 | used | Defender, Steel Blade |
| 4 | f004 | used | Excalibur, Rune Blade (2 unnamed recipe/scroll record(s)) |
| 5 | (no mesh file!) | used | Ragnarok |
| 6 | (no mesh file!) | used | Father's Spear, Halberd, Marr Spear, Partisan, Ultima Lance |
| 7 | f007 | used | Iron Lance, Titan Lance, Treasured Spear |
| 8 | f008 | used | Dragon Lance, Dragoon Spear (603 unnamed recipe/scroll record(s)) |
| 9 | f009 | used | Gungnir (11 unnamed recipe/scroll record(s)) |
| 10 | f010 | used | Longinus |
| 11 | f011 | used | Goblin Hammer, Orc Hammer, Treasured Hammer |
| 12 | f012 | used | Father's Hammer, Marr Hammer, Sonic Hammer, Ultima Hammer, Wave Hammer |
| 13 | f013 | used | Mythril Hammer, Prism Hammer, Rune Hammer |
| 14 | f014 | used | Mystic Hammer |
| 15 | f015 | UNUSED | - |
| 16 | f016 | used | Aura Racket, Elemental Cudgel, Treasured Maul |
| 17 | f017 | used | Father's Maul, Marr Maul, Solid Racket, Steel Cudgel, Ultima Maul |
| 18 | f018 | used | Dual Shooter, Prism Bludgeon, Stone of ???, Stone of Blizzard, Stone of Clear, Stone of Cure, Stone of Fire, Stone of Gravity, Stone of Holy, Stone of Life, Stone of Slow, Stone of Stop, Stone of Thunder, Striped Apple (8 unnamed recipe/scroll record(s)) |
| 19 | f019 | used | Butterfly Head, Cherry Cluster, Queen's Heel |
| 20 | f020 | used | Dreamcatcher, Rainbow Grapes |
| 21 | f021 | used | Flame Shield, Makeshift Shield, Star Carrot |
| 22 | f022 | used | Gourd Potato, Iron Shield, Storm Shield |
| 23 | f023 | used | Frost Shield, Mythril Shield, Round Corn |
| 24 | f024 | used | Chocobo Shield, Meat |
| 25 | f025 | used | Highwind, Sonic Lance |
| 26 | f026 | UNUSED | - |
| 27 | f027 | used | Diamond Shield, Milk, Rune Shield, Saintly Shield, Spring Water |
| 28 | f028 | UNUSED | - |
| 29 | f029 | used | Strange Liquid |
| 30 | f030 | UNUSED | - |
| 31 | f031 | UNUSED | - |
| 32 | f032 | used | (1 unnamed recipe/scroll record(s)) |
| 33 | f033 | used | (4 unnamed recipe/scroll record(s)) |
| 34 | f034 | UNUSED | - |
| 35 | f035 | UNUSED | - |
| 36 | f036 | UNUSED | - |
| 37 | f037 | UNUSED | - |
| 38 | (no mesh file!) | UNUSED | - |
| 39 | f039 | UNUSED | - |
| 40 | f040 | used | Crop Seed, Flower Seed, Fruit Seed, Strange Seed, Vegetable Seed, Wheat Seed |
| 41 | f041 | UNUSED | - |
| 42 | f042 | UNUSED | - |
| 43 | f043 | UNUSED | - |
| 44 | f044 | UNUSED | - |
| 45 | f045 | UNUSED | - |
| 46 | f046 | UNUSED | - |
| 47 | f047 | UNUSED | - |
| 48 | f048 | UNUSED | - |
| 49 | (no mesh file!) | UNUSED | - |
| 50 | f050 | UNUSED | - |
| 51 | f051 | UNUSED | - |
| 52 | f052 | UNUSED | - |
| 53 | f053 | UNUSED | - |
| 54 | f054 | UNUSED | - |
| 55 | f055 | used | AP Item, Alloy, Ancient Potion, Ancient Sword, Angel's Tear, Blue Silk, Bronze Shard, Cerberus Fang, Chilly Gel, Chimera's Horn, Cockatrice Scale, Coeurl Whisker, Crystal Ball, Cursed Crook, Dark Sphere, Desert Fang, Devil's Claw, Devil's Mask, Diamond Ore, Dragon's Fang, Dweomer Spore, Ethereal Orb, Faerie's Tear, Fiend's Claw, Gear, Gigas Claw, Goddess Statuette, Gold, Green Sphere, Griffin's Wing, Hard Shell, Heavenly Dust, Holy Water, Iron Shard, Jade, Jagged Scythe, King's Scale, Lord's Robe, Magma Rock, Malboro Seed, Needle, Ogre Fang, Orc Belt, Pressed Flower, Red Eye, Remedy, Ruby, Shiny Shard, Silver, Thunderball, Tiny Crystal, Toad Oil, Ultimite, White Silk, Wind Crystal, Worm Antenna, Yellow Feather, Zu's Beak (10 unnamed recipe/scroll record(s)) |
| 56 | f056 | UNUSED | - |
| 57 | f057 | UNUSED | - |
| 58 | f058 | UNUSED | - |
| 59 | f059 | UNUSED | - |
| 60 | f060 | UNUSED | - |
| 61 | f061 | UNUSED | - |
| 62 | f062 | UNUSED | - |
| 63 | f063 | UNUSED (64-byte stub file - likely broken/degenerate, avoid) | - |
| 64 | f064 | UNUSED | - |
| 65 | f065 | used | Bronze, Iron, Mythril, Orichalcum |
| 66 | f066 | UNUSED | - |
| 67 | f067 | UNUSED | - |
| 68 | f068 | used | Angel Kit, Blue Yarn, Brigandology, Bronze Armor, Bronze Belt, Bronze Gloves, Bronze Sallet, Celestial Weapon, Clockwork, Daemon Kit, Dark Weapon, Designer Glasses, Designer Goggles, Diamond Armor, Diamond Belt, Diamond Gloves, Diamond Sallet, Diamond Shield, Earth Armor, Eternal Armor, Eternal Sallet, Eyewear Techniques, Faerie Kit, Fashion Kit, Fiend Kit, Flame Armor, Flame Belt, Flame Craft, Flame Gloves, Flame Sallet, Flame Shield, Forbidden Tome, Frost Armor, Frost Belt, Frost Craft, Frost Gloves, Frost Sallet, Frost Shield, Goggle Techniques, Gold Armor, Gold Craft, Gold Gloves, Greatest Weapon, Healing Kit, Hero's Weapon, Holy Armor, Holy Shield, Iron Armor, Iron Belt, Iron Gloves, Iron Sallet, Iron Shield, Lady's Accessories, Legendary Shield, Legendary Weapon, Lightning Armor, Lightning Belt, Lightning Craft, Lightning Gloves, Lightning Sallet, Lightning Shield, Lunar Weapon, Magic Shield, Magic Tome, Master's Weapon, Mighty Weapon, Mythril Armor, Mythril Belt, Mythril Gloves, Mythril Sallet, Mythril Shield, New Clockwork, Novice's Weapon, Pure Armor, Pure Belt, Radiant Armor, Ring of Invincibility, Ring of Light, Sorcery Tome, Soul of the Dragon, Soul of the Lion, Speed Secrets, Speed Tome, Time Armor, Time Sallet, Valiant Weapon, Victorious Weapon, Warrior's Weapon, White Yarn, Wind Belt, Wisdom Secrets, Wisdom Tome, Zeal Kit (7 unnamed recipe/scroll record(s)) |
| 69 | f069 | UNUSED | - |
| 70 | f070 | UNUSED | - |
| 71 | f071 | UNUSED | - |
| 72 | f072 | UNUSED | - |
| 73 | f073 | UNUSED | - |
| 74 | f074 | UNUSED | - |
| 75 | f075 | UNUSED | - |
| 76 | f076 | UNUSED | - |
| 77 | f077 | UNUSED | - |
| 78 | (no mesh file!) | UNUSED | - |
| 79 | f079 | UNUSED | - |
| 80 | f080 | UNUSED | - |
| 81 | f081 | UNUSED | - |
| 82 | f082 | UNUSED | - |
| 83 | f083 | UNUSED | - |
| 84 | f084 | UNUSED | - |
| 85 | f085 | UNUSED | - |
| 86 | f086 | UNUSED | - |
| 87 | f087 | UNUSED | - |
| 88 | f088 | UNUSED | - |
| 89 | f089 | UNUSED | - |
| 90 | f090 | UNUSED | - |
| 91 | f091 | used | Cactus Flower, Kilanda Sulfur, Shella Mark, Worn Bandanna |
| 92 | f092 | UNUSED | - |
| 93 | f093 | UNUSED | - |
| 94 | f094 | UNUSED | - |
| 95 | f095 | UNUSED | - |
| 96 | f096 | UNUSED | - |
| 97 | f097 | UNUSED | - |
| 98 | f098 | UNUSED | - |
| 99 | f099 | UNUSED | - |
| 100 | f100 | UNUSED | - |
| 101 | f101 | UNUSED | - |
| 102 | f102 | UNUSED | - |
| 103 | f103 | UNUSED | - |
| 104 | f104 | UNUSED | - |
| 105 | f105 | used | Wheat |
| 106 | f106 | used | Flour |
| 107 | f107 | used | Bannock |
| 108 | f108 | UNUSED | - |
| 109 | f109 | UNUSED | - |
| 110 | f110 | UNUSED | - |
| 111 | (no mesh file!) | UNUSED | - |
| 112 | f112 | UNUSED | - |
| 113 | f113 | used | Ashura, Double Axe, Engetsurin, Flametongue, Gekkabijin, Ice Brand, Kaiser Knuckles, Loaded Dice, Maneater, Masamune, Masquerade, Mjollnir, Murasame, Ogrekiller, Onion Sword, Sasuke's Blade, Shuriken |
| 114 | f114 | used | Book of Light, Dragon's Whisker, Galatyn, Mage Masher, Mage's Staff, Noah's Lute, Rune Bell, Rune Staff, Sage's Staff, Wonder Wand |
| 115 | f115 | used | Chicken Knife, Main Gauche, Save the Queen |
| 116 | f116 | used | Fang Charm, Giant's Glove, Green Beret, Heavy Armband, Power Wristband, Twisted Headband |
| 117 | f117 | used | Candy Ring, Cat's Bell, Dark Matter, Faerie Ring, Gold Hairpin, Kris, Red Slippers, Ribbon, Silver Bracer, Taotie Motif, Tome of Ultima, Winged Cap |
| 118 | f118 | used | Aegis, Black Hood, Buckler, Drill, Elven Mantle, Helm of Arai, Rat's Tail, Ring of Protection, Silver Spectacles, Sparkling Bracer, Teddy Bear, Wonder Bangle |
| 119 | f119 | used | Chocobo Pocket, Gobbie Pocket, Moogle Pocket, Ultimate Pocket |
| 120 | f120 | used | Earth Pendant, Moon Pendant, Star Pendant, Sun Pendant |
| 121 | f121 | used | Ring of Blizzard, Ring of Cure, Ring of Fire, Ring of Life, Ring of Thunder |
| 122 | f122 | used | (1 unnamed recipe/scroll record(s)) |
| 123 | f123 | used | Fish |
| 124 | (no mesh file!) | UNUSED | - |
| 125 | (no mesh file!) | UNUSED | - |
| 126 | f126 | used | Phoenix Down |
| 127 | f127 | UNUSED | - |
| 128 | f128 | UNUSED | - |
| 129 | (no mesh file!) | UNUSED | - |
| 130 | f130 | UNUSED | - |
| 131 | f131 | UNUSED | - |
| 132 | f132 | UNUSED | - |
| 133 | f133 | UNUSED | - |
| 134 | f134 | UNUSED | - |
| 135 | f135 | UNUSED | - |
| 136 | f136 | UNUSED | - |
| 137 | f137 | UNUSED | - |
| 138 | f138 | UNUSED | - |

## Notable groupings

- **All 73 real artifacts (`0x9F`-`0xE7`) only use models 113-121** (9
  meshes total, grouped by stat-family rather than flavor - e.g. Ribbon and
  Dark Matter share model 117 despite being unrelated items).
- **Model 68 is reused by nearly the entire recipe/craft-material system**
  (crafting-recipe scrolls all show the same generic "scroll" mesh).
- **Model 0** (not in this table - no `f000` mesh exists) is the sentinel
  most armor/tribal/accessory equipment uses: these categories are never
  seen as world pickups with a unique shape, consistent with
  `project_ffcc_artifact_effects.md`'s finding that only weapons ever get a
  distinct rendered mesh.
- Plain-text mesh ids with **no gaps in the 1-138 range being "reserved"**
  in any obvious pattern (unused ids are scattered individually, not in one
  contiguous cut block) - these read like leftover assets from a larger
  planned item roster, not one abandoned feature.
