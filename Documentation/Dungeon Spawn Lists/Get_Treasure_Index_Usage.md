# get_treasure Index Usage — Reverse Lookup

For each stage: every `get_treasure` index in use, what it actually
grants (8 slots, same resolution as `Get_Treasure_Index_Tables.md`),
and every chest/monster spawn that references it, individually
addressed. Chest indices with a high flag bit (cycle-gating) are
shown masked to their real index (`& 0xFFFF`); raw value kept in
parentheses where it differs. Monster `E` values above 1,000,000 are
the known JSON-extraction garbage values and are listed separately.

---

## River Belle Path (`river_0`)

### Index 1

**Items:** Sonic Lance (!) / Halberd (!) / Dragoon Spear (!) / Treasured Spear (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Goblin (Sword) @ `0x48801`
- Mu @ `0x48848`
- Hedgehog Pie @ `0x48890`
- Mu @ `0x48966`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Vegetable Seed

**Monsters:**
- Goblin (Sword) @ `0x47f8d`
- Goblin (Sword) @ `0x47fd5`
- Goblin (Mace) @ `0x48187`
- Goblin (Sword) @ `0x482ab`
- Goblin (Mage) @ `0x482f3`
- Dark Hedgehog @ `0x48652`
- Goblin (Mage) @ `0x487ba`
- Mu @ `0x48da8`
- Mu @ `0x48e86`
- Goblin (Mage) @ `0x48fad`
- Goblin (Sword) @ `0x48ff6`

### Index 5

**Items:** Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed

**Monsters:**
- Goblin (Sword) @ `0x4857a`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Stone Hedgehog @ `0x480ae`
- Dark Hedgehog @ `0x480f6`
- Goblin (Sword) @ `0x481d0`
- Mu @ `0x48ace`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Hedgehog Pie @ `0x4833b`
- Stone Hedgehog @ `0x48383`
- Dark Hedgehog @ `0x483cb`
- Mu @ `0x489ae`
- Mu @ `0x48c39`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Hedgehog Pie @ `0x48413`
- Dark Hedgehog @ `0x4845b`
- Hedgehog Pie @ `0x485c2`
- Stone Hedgehog @ `0x4860a`
- Mu @ `0x48bf0`
- Goblin (Sword) @ `0x48f1a`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Mu @ `0x48ed0`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Goblin (Sword) @ `0x4801e`
- Hedgehog Pie @ `0x4872a`
- Stone Hedgehog @ `0x48772`
- Mu @ `0x48a3e`
- Goblin (Sword) @ `0x48b16`

### Index 11

**Items:** Shuriken / Maneater / Double Axe / Green Beret / Flametongue / Ice Brand / Loaded Dice / Sasuke's Blade

**Monsters:**
- Goblin Chieftain @ `0x484ea`
- Griffin @ `0x48532`

### Index 12

**Items:** Dragon's Whisker / Mage Masher / Silver Bracer / Cat's Bell / Sage's Staff / Kris / Rune Bell / Mage's Staff

**Monsters:**
- Goblin Chieftain @ `0x48b5e`
- Griffin @ `0x48ba7`

### Index 13

**Items:** Buckler / Buckler / Silver Spectacles / Silver Spectacles / Black Hood / Buckler / Wonder Bangle / Wonder Bangle

**Chests:**
- `0x49328`

### Index 14

**Items:** Moogle Pocket / Moogle Pocket / Moogle Pocket / Moogle Pocket / Earth Pendant / Moogle Pocket / Earth Pendant / Moogle Pocket

**Monsters:**
- Goblin Chieftain @ `0x48d5e`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Hedgehog Pie @ `0x48066`
- Goblin (Spear) @ `0x48219`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Goblin (Sword) @ `0x48262`
- Hedgehog Pie @ `0x48c82`
- Goblin (Sword) @ `0x48d14`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Mu @ `0x4891e`
- Goblin (Sword) @ `0x489f6`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Chests:**
- `0x492c9`

**Monsters:**
- Hedgehog Pie @ `0x4869a`
- Dark Hedgehog @ `0x486e2`
- Goblin (Sword) @ `0x48f64`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Chests:**
- `0x49356`

### Index 26

**Items:** (empty) / (empty) / Iron / Iron / Iron / Iron / Mythril / Mythril

**Monsters:**
- Stone Hedgehog @ `0x488d7`

### Index 27

**Items:** Bronze / Bronze / Bronze / Bronze / Iron / Iron / Mythril / Mythril

**Monsters:**
- Goblin Chieftain @ `0x48a86`

### Index 28

**Items:** (empty) / Flame Craft / Flame Craft / Mythril / Flame Craft / Griffin's Wing / Mythril / Griffin's Wing

**Monsters:**
- Griffin @ `0x48ccb`
- Griffin @ `0x48e3c`

### Index 29

**Items:** Bronze Belt / Bronze Belt / Iron Shield / Iron Shield / Iron Belt / Iron Belt / Mythril Belt / Mythril Shield

**Chests:**
- `0x492f9`

### Index 30

**Items:** Bronze Gloves / Bronze Sallet / Bronze Gloves / Bronze Sallet / Iron Gloves / Iron Sallet / Mythril Gloves / Mythril Sallet

**Chests:**
- `0x49387`

### Index 31

**Items:** Novice's Weapon / Novice's Weapon / Novice's Weapon / Novice's Weapon / Frost Craft / Frost Craft / Valiant Weapon / Valiant Weapon

**Chests:**
- `0x493b6`

### Index 32

**Items:** Bronze Armor / Bronze Armor / Bronze Armor / Bronze Armor / Lightning Craft / Lightning Craft / Mythril Armor / Mythril Armor

**Chests:**
- `0x493e5`

### Index 50

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Monsters:**
- Hedgehog Pie @ `0x47d84`
- Goblin (Sword) @ `0x47dcd`

### Index 51

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Goblin (Mage) @ `0x47e17`
- Goblin Chieftain @ `0x47f3e`

### Index 52

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Treasured Maul (!)

**Monsters:**
- Mu @ `0x47e61`
- Mu @ `0x47eab`
- Goblin (Sword) @ `0x47ef5`

### Garbage E-value entries (JSON extraction artifacts)

- Goblin (Sword) (E=268435474) @ `0x4813e`
- Goblin (Sword) (E=536870931) @ `0x484a3`
- Mu (E=805306369) @ `0x48df2`

## The Mushroom Forest (`kinoko_0`)

### Index 1

**Items:** Dragoon Spear (!) / Marr Spear (!) / Equipment 122 (Unused) (!) / Sonic Hammer (!) / Dreamcatcher (!) / Gold Mail (!) / Jade Bracer (Female) (!) / Dark Matter (!)

**Chests:**
- `0x48ef5`

**Monsters:**
- Hell Plant @ `0x47b84`
- Gremlin @ `0x480a3`

### Index 2

**Items:** (empty) / (empty) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fruit Seed

**Monsters:**
- Hell Plant @ `0x47aaa`
- Tiny Worm @ `0x48059`
- Hedgehog Pie @ `0x480ed`
- Tiny Worm @ `0x4825c`
- Gremlin @ `0x4837c`
- Stone Plant @ `0x4885b`
- Stone Plant @ `0x488a5`
- Gremlin @ `0x488ef`
- Gremlin @ `0x48983`
- Gremlin @ `0x489ce`
- Mushroom Forest Carrion Worm @ `0x48b44`
- Tiny Worm @ `0x48b8d`
- Tiny Worm @ `0x48bd6`
- Mushroom Forest Carrion Worm @ `0x48c1f`
- Tiny Worm @ `0x48c66`
- Tiny Worm @ `0x48cf6`
- Tiny Worm @ `0x48d3e`

### Index 5

**Items:** Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed

**Monsters:**
- Hell Plant @ `0x47c5c`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Gremlin @ `0x48214`
- Stone Plant @ `0x48aae`

### Index 7

**Items:** Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes

**Monsters:**
- Gremlin @ `0x481cb`
- Gremlin @ `0x48a19`

### Index 8

**Items:** Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn

**Monsters:**
- Gremlin @ `0x48181`

### Index 9

**Items:** Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid

**Monsters:**
- Stone Plant @ `0x48af9`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Hell Plant @ `0x47c13`
- Gremlin @ `0x47d83`

### Index 11

**Items:** Shuriken / Maneater / Double Axe / Green Beret / Flametongue / Ice Brand / Loaded Dice / Sasuke's Blade

**Chests:**
- `0x48f85`

### Index 12

**Items:** Dragon's Whisker / Mage Masher / Silver Bracer / Cat's Bell / Sage's Staff / Kris / Rune Bell / Mage's Staff

**Chests:**
- `0x48f56`

### Index 13

**Items:** Buckler / Buckler / Silver Spectacles / Silver Spectacles / Black Hood / Black Hood / Wonder Bangle / Wonder Bangle

**Chests:**
- `0x48f26`

### Index 14

**Items:** Moogle Pocket / Moogle Pocket / Earth Pendant / Earth Pendant / Earth Pendant / Earth Pendant / Moogle Pocket / Moogle Pocket

**Chests:**
- `0x4907b`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Hell Plant @ `0x47b3c`
- Gremlin @ `0x47eec`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Gremlin @ `0x47ea3`
- Hell Plant @ `0x47fc5`
- Hedgehog Pie @ `0x483c4`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Tiny Worm @ `0x4800f`
- Tiny Worm @ `0x482a4`
- Hedgehog Pie @ `0x48532`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Tiny Worm @ `0x47dcb`
- Ahriman @ `0x47e13`
- Ahriman @ `0x482ec`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Hell Plant @ `0x47af3`
- Hell Plant @ `0x47ca5`
- Ahriman @ `0x48454`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Hell Plant @ `0x47bcb`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Monsters:**
- Hedgehog Pie @ `0x47e5b`

### Index 26

**Items:** Iron / Iron / Iron / Iron / Bastard Sword (!) / Mythril / Mythril / Mythril

**Monsters:**
- Ahriman @ `0x48137`
- Ochu @ `0x48334`
- Mushroom Forest Carrion Worm @ `0x48cad`

### Index 27

**Items:** (empty) / Strange Seed / Strange Seed / Flower Seed / (empty) / Flower Seed / Flower Seed / Strange Seed

**Monsters:**
- Hell Plant @ `0x47cef`
- Hell Plant @ `0x48734`

### Index 28

**Items:** Gold / Silver / Crystal Ball / Gold / Gold / Silver / Crystal Ball / (empty)

**Monsters:**
- Hedgehog Pie @ `0x47f35`
- Hedgehog Pie @ `0x4849e`
- Hedgehog Pie @ `0x4857b`
- Hedgehog Pie @ `0x4860d`
- Hedgehog Pie @ `0x4877e`

### Index 29

**Items:** (empty) / Chilly Gel / Chilly Gel / Faerie's Tear / Chilly Gel / Chilly Gel / Angel's Tear / Bronze

**Monsters:**
- Ice Ahriman @ `0x48810`
- Ice Ahriman @ `0x48939`

### Index 30

**Items:** Bronze / Iron / Wheat Seed / Tiny Crystal / Mythril / Mythril / Tiny Crystal / Wheat Seed

**Monsters:**
- Ochu @ `0x487c7`
- Ochu @ `0x48a64`

### Index 31

**Items:** Bronze / Bronze / Novice's Weapon / Novice's Weapon / Master's Weapon / Valiant Weapon / Mighty Weapon / Victorious Weapon

**Monsters:**
- Hell Plant @ `0x486a0`

### Index 32

**Items:** Bronze / Bronze / Bronze Armor / Bronze Armor / Mythril Armor / Mythril Armor / Pure Armor / Holy Armor

**Monsters:**
- Hell Plant @ `0x486ea`

### Index 33

**Items:** Bronze / Bronze Gloves / Bronze Gloves / Bronze / Mythril Shield / Mythril Gloves / Gold Gloves / Magic Shield

**Monsters:**
- Hell Plant @ `0x47d3a`

### Index 34

**Items:** Bronze / Bronze / Bronze Sallet / Bronze Belt / Mythril Belt / Mythril Sallet / Time Sallet / Pure Belt

**Monsters:**
- Gremlin @ `0x48656`

### Index 35

**Items:** (empty) / (empty) / (empty) / Tome of Speed / Tome of Speed / Ruby / Jade / Fiend Kit

**Monsters:**
- Dark Hedgehog @ `0x47f7d`
- Dark Hedgehog @ `0x485c4`

### Index 36

**Items:** (empty) / (empty) / (empty) / Alloy / Alloy / Ruby / Jade / Diamond Ore

**Monsters:**
- Stone Hedgehog @ `0x4840c`
- Stone Hedgehog @ `0x484e8`

### Index 37

**Items:** (empty) / Iron Shield / Iron Shield / Iron Gloves / Mythril Shield / Mythril Gloves / Holy Shield / Gold Gloves

**Chests:**
- `0x4901a`

### Index 38

**Items:** (empty) / Iron Sallet / Iron Sallet / Iron Belt / Mythril Sallet / Mythril Belt / Time Sallet / Pure Belt

**Chests:**
- `0x48fb6`

### Index 39

**Items:** (empty) / (empty) / (empty) / Fiend Kit / Fiend Kit / Fiend Kit / Daemon Kit / Daemon Kit

**Chests:**
- `0x48fe8`
- `0x4904c`

## Goblin Wall - Area 1 (`gob_0`)

### Index 1

**Items:** Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Iron Lance (!) / Marr Spear (!) / Sonic Hammer (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Bat @ `0x46a5b`
- Bat @ `0x46b39`
- Bat @ `0x46c15`
- Bat @ `0x46c5f`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Vegetable Seed

**Monsters:**
- Bat @ `0x4644e`
- Flan @ `0x46498`
- Goblin (Sword) @ `0x4652d`

### Index 5

**Items:** Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed

**Monsters:**
- Flan @ `0x46aa5`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Bat @ `0x46404`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Goblin (Sword) @ `0x4685b`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Goblin (Mage) @ `0x46a12`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Flan @ `0x466eb`
- Goblin (Sword) @ `0x468ee`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Goblin (Sword) @ `0x4660d`
- Goblin (Mace) @ `0x46657`
- Goblin (Spear) @ `0x466a1`

### Index 11

**Items:** Shuriken / Maneater / Double Axe / Green Beret / Flametongue / Ice Brand / Loaded Dice / Sasuke's Blade

**Chests:**
- `0x46e04`

### Index 14

**Items:** Earth Pendant / Earth Pendant / Earth Pendant / Moogle Pocket / Earth Pendant / Moogle Pocket / Earth Pendant / Moogle Pocket

**Chests:**
- `0x46da2`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Goblin (Sword) @ `0x464e2`
- Goblin (Sword) @ `0x4677d`
- Goblin (Mace) @ `0x467c7`
- Goblin (Spear) @ `0x46811`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Flan @ `0x465c2`
- Flan @ `0x46bcc`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Flan @ `0x468a5`
- Goblin (Mace) @ `0x469c9`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Goblin (Sword) @ `0x46578`
- Goblin (Spear) @ `0x46980`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Goblin (Mage) @ `0x463ba`

### Index 29

**Items:** (empty) / (empty) / Iron / Iron / Mythril / Cerberus Fang / Mythril / Cerberus Fang

**Monsters:**
- Cerberus @ `0x46734`
- Cerberus @ `0x46937`

### Index 30

**Items:** Bronze / Bronze / Iron / Iron / Alloy / Alloy / Mythril / Mythril

**Monsters:**
- Goblin Chieftain @ `0x46aef`
- Goblin Chieftain @ `0x46b83`

### Index 31

**Items:** Warrior's Weapon / Warrior's Weapon / Warrior's Weapon / Master's Weapon / Master's Weapon / Victorious Weapon / Valiant Weapon / Mighty Weapon

**Chests:**
- `0x46dd3`

### Index 32

**Items:** Iron Shield / Iron Gloves / Mythril Gloves / Mythril Shield / Mythril Gloves / Mythril Shield / Flame Gloves / Flame Shield

**Chests:**
- `0x46d40`

### Index 33

**Items:** Bronze / Bronze / Iron / Tome of Wisdom / Tome of Wisdom / Tome of Wisdom / Secrets of Wisdom / Secrets of Wisdom

**Chests:**
- `0x46d71`

### Index 34

**Items:** (empty) / Master's Weapon / Master's Weapon / Master's Weapon / Master's Weapon / Victorious Weapon / Valiant Weapon / Mighty Weapon

**Chests:**
- `0x46e34`

## Goblin Wall - Area 2 (`gob_1`)

### Index 1

**Items:** Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Iron Lance (!) / Marr Spear (!) / Sonic Hammer (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Goblin (Sword) @ `0x4345e`
- Goblin (Spear) @ `0x434a7`
- Flan @ `0x4365c`
- Goblin (Sword) @ `0x43737`
- Goblin (Mace) @ `0x4377f`
- Goblin (Spear) @ `0x437c7`
- Electric Jellyfish @ `0x43858`
- Goblin (Sword) @ `0x438ea`
- Goblin (Mace) @ `0x43933`
- Goblin (Sword) @ `0x4397c`
- Goblin (Spear) @ `0x439c5`
- Goblin (Sword) @ `0x43b32`
- Ghost @ `0x43b7a`
- Goblin (Sword) @ `0x43c54`
- Ghost @ `0x43c9d`
- Goblin (Sword) @ `0x43dbe`
- Goblin (Mage) @ `0x43e06`
- Goblin (Mage) @ `0x44049`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fruit Seed

**Chests:**
- `0x44157`
- `0x44187`

**Monsters:**
- Flan @ `0x43bc2`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Goblin (Sword) @ `0x43582`
- Goblin (Sword) @ `0x43f27`
- Goblin (Spear) @ `0x43f6f`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Goblin (Mage) @ `0x435cb`
- Goblin (Sword) @ `0x43e97`
- Goblin (Mace) @ `0x43edf`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Goblin (Sword) @ `0x436ee`
- Goblin (Sword) @ `0x44000`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Electric Jellyfish @ `0x43a58`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Goblin (Sword) @ `0x433ca`
- Goblin (Mace) @ `0x43414`
- Electric Jellyfish @ `0x436a5`
- Ghost @ `0x43ce6`

### Index 12

**Items:** Dragon's Whisker / Mage Masher / Silver Bracer / Cat's Bell / Sage's Staff / Kris / Rune Bell / Mage's Staff

**Chests:**
- `0x44273`

### Index 13

**Items:** Buckler / Buckler / Silver Spectacles / Silver Spectacles / Black Hood / Black Hood / Wonder Bangle / Wonder Bangle

**Chests:**
- `0x44127`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Flan @ `0x43539`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Flan @ `0x43aea`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Goblin (Sword) @ `0x43aa1`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Electric Jellyfish @ `0x43d2e`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Monsters:**
- Electric Jellyfish @ `0x43fb7`

### Index 28

**Items:** Shiny Shard / Shiny Shard / Crystal Ball / Thunderball / Ruby / Jade / Thunderball / Thunderball

**Monsters:**
- Electric Jellyfish @ `0x438a1`
- Electric Jellyfish @ `0x43e4e`

### Index 29

**Items:** (empty) / (empty) / Blue Silk / Blue Silk / Diamond Ore / Diamond Ore / White Silk / White Silk

**Monsters:**
- Ghost @ `0x43613`
- Ghost @ `0x43a0e`
- Ghost @ `0x43c0b`
- Ghost @ `0x43d76`

### Index 30

**Items:** Bronze / Bronze / Iron / Iron / Alloy / Alloy / Mythril / Mythril

**Monsters:**
- Goblin Chieftain @ `0x434f0`

### Index 31

**Items:** Warrior's Weapon / Warrior's Weapon / Warrior's Weapon / Master's Weapon / Master's Weapon / Mighty Weapon / Valiant Weapon / Victorious Weapon

**Chests:**
- `0x441b7`

### Index 32

**Items:** Iron Shield / Iron Gloves / Mythril Gloves / Mythril Shield / Lightning Gloves / Lightning Shield / Gold Gloves / Holy Shield

**Chests:**
- `0x441e6`

### Index 33

**Items:** Iron Armor / Iron Armor / Iron Armor / Mythril Armor / Mythril Armor / Time Armor / Pure Armor / Holy Armor

**Chests:**
- `0x44215`

### Index 34

**Items:** Iron Sallet / Iron Belt / Mythril Sallet / Mythril Belt / Lightning Sallet / Lightning Belt / Time Sallet / Pure Belt

**Chests:**
- `0x44244`

### Garbage E-value entries (JSON extraction artifacts)

- Goblin Chieftain (E=268435486) @ `0x4380f`

## The Mine of Cathuriges - Area 1 (`mine_0`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Bomb @ `0x452e7`
- Orc (Axe) @ `0x45330`
- Orc (Mage) @ `0x45378`
- Bomb @ `0x45409`
- Orc (Axe) @ `0x455be`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Vegetable Seed

**Chests:**
- `0x45883`

**Monsters:**
- Orc (Axe) @ `0x450e9`
- Orc (Axe) @ `0x45132`
- Bomb @ `0x451c4`
- Orc (Axe) @ `0x45255`
- Bomb @ `0x4529e`
- Cockatrice @ `0x4549a`
- Orc (Axe) @ `0x454e3`
- Orc (Axe) @ `0x4552b`
- Orc (Axe) @ `0x45607`
- Orc (Axe) @ `0x457bd`

### Index 5

**Items:** Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed

**Monsters:**
- Orc (Axe) @ `0x4572b`
- Orc (Mage) @ `0x45774`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Orc (Axe) @ `0x45059`
- Orc (Spear) @ `0x450a1`

### Index 8

**Items:** Star Carrot / Round Corn / Gourd Potato / Star Carrot / Round Corn / Gourd Potato / Star Carrot / Round Corn

**Monsters:**
- Orc (Axe) @ `0x44f7e`
- Orc (Mace) @ `0x44fc7`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Orc (Mage) @ `0x45010`
- Orc (Axe) @ `0x453c0`
- Orc (Axe) @ `0x45575`

### Index 11

**Items:** Shuriken / Maneater / Double Axe / Green Beret / Flametongue / Ice Brand / Loaded Dice / Sasuke's Blade

**Monsters:**
- Ogre @ `0x4520d`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Orc (Axe) @ `0x4517b`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Orc (Mage) @ `0x44f35`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Orc (Axe) @ `0x44e5a`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Orc (Axe) @ `0x44ea3`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Chests:**
- `0x458b3`

### Index 26

**Items:** Bronze / Novice's Weapon / Bronze Armor / Iron / Master's Weapon / Mythril Armor / Mythril / Mythril

**Monsters:**
- Orc (Axe) @ `0x45699`
- Orc (Axe) @ `0x456e2`

### Index 27

**Items:** Bronze / Bronze Shard / Iron Shard / Iron / Flame Craft / Magma Rock / Flame Armor / Magma Rock

**Monsters:**
- Bomb @ `0x44eec`
- Bomb @ `0x45650`

### Index 29

**Items:** (empty) / Crystal Ball / Crystal Ball / Cockatrice Scale / Mythril / Mythril / Diamond Ore / Cockatrice Scale

**Monsters:**
- Cockatrice @ `0x45452`

### Index 30

**Items:** (empty) / Alloy / Alloy / Shiny Shard / Mythril / Mythril / Tiny Crystal / Diamond Ore

**Chests:**
- `0x458e2`

### Index 31

**Items:** Copper Sword (!) / Iron Sword (!) / Tome of Speed / Tome of Speed / Tome of Speed / Secrets of Speed / Secrets of Speed / Secrets of Speed

**Chests:**
- `0x45912`
- `0x45942`

## The Mine of Cathuriges - Area 2 (`mine_1`)

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fish

**Chests:**
- `0x40c3f`

**Monsters:**
- Orc (Axe) @ `0x4081d`
- Orc (Axe) @ `0x4093e`
- Orc (Axe) @ `0x40987`
- Orc (Mage) @ `0x40a18`
- Bomb @ `0x40a61`
- Bomb @ `0x40aa9`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Orc (Axe) @ `0x4066a`

### Index 7

**Items:** Striped Apple / Rainbow Grapes / Cherry Cluster / Striped Apple / Rainbow Grapes / Cherry Cluster / Striped Apple / Rainbow Grapes

**Monsters:**
- Cockatrice @ `0x40865`

### Index 8

**Items:** Star Carrot / Round Corn / Gourd Potato / Star Carrot / Round Corn / Gourd Potato / Star Carrot / Round Corn

**Monsters:**
- Orc (Axe) @ `0x406b3`

### Index 9

**Items:** Spring Water / Strange Liquid / Milk / Spring Water / Strange Liquid / Milk / Spring Water / Strange Liquid

**Monsters:**
- Bomb @ `0x40af1`
- Orc (Axe) @ `0x40b39`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Orc (Axe) @ `0x40745`
- Orc (Mage) @ `0x4078d`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Orc (Axe) @ `0x407d5`
- Orc (Axe) @ `0x409d0`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Chests:**
- `0x40c0f`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Chests:**
- `0x40c6e`

### Index 27

**Items:** Bronze / Bronze Shard / Iron Shard / Iron / Flame Craft / Magma Rock / Flame Armor / Magma Rock

**Monsters:**
- Bomb @ `0x408ad`

### Index 29

**Items:** (empty) / Crystal Ball / Crystal Ball / Cockatrice Scale / Mythril / Mythril / Diamond Ore / Cockatrice Scale

**Monsters:**
- Cockatrice @ `0x406fc`

### Index 30

**Items:** (empty) / Alloy / Alloy / Shiny Shard / Mythril / Mythril / Tiny Crystal / Diamond Ore

**Chests:**
- `0x40b81`
- `0x40bb0`
- `0x40be0`

### Garbage E-value entries (JSON extraction artifacts)

- Ogre (E=268435468) @ `0x408f5`

## The Mine of Cathuriges - Area 3 (`mine_2`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Orc (Axe) @ `0x4066b`
- Orc (Axe) @ `0x406fd`
- Orc (Axe) @ `0x407d7`
- Orc (Axe) @ `0x40867`
- Orc (Axe) @ `0x40988`
- Ice Bomb @ `0x409d1`
- Orc (Axe) @ `0x40aab`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fish

**Monsters:**
- Bat @ `0x4054a`
- Wraith @ `0x40593`
- Wraith @ `0x40623`
- Thunder Bomb @ `0x40a1a`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Orc (Mage) @ `0x4093f`

### Index 7

**Items:** Striped Apple / Rainbow Grapes / Cherry Cluster / Striped Apple / Rainbow Grapes / Cherry Cluster / Striped Apple / Rainbow Grapes

**Monsters:**
- Orc (Mage) @ `0x405db`

### Index 8

**Items:** Star Carrot / Round Corn / Gourd Potato / Star Carrot / Round Corn / Gourd Potato / Star Carrot / Round Corn

**Monsters:**
- Orc (Axe) @ `0x40502`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Orc (Axe) @ `0x404ba`

### Index 13

**Items:** Buckler / Buckler / Silver Spectacles / Silver Spectacles / Black Hood / Black Hood / Wonder Bangle / Wonder Bangle

**Chests:**
- `0x40b6a`

### Index 14

**Items:** Earth Pendant / Earth Pendant / Earth Pendant / Earth Pendant / Moogle Pocket / Earth Pendant / (empty) / Stone of Fire

**Chests:**
- `0x40b99`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Orc (Axe) @ `0x4078f`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Orc (Axe) @ `0x408f7`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Chests:**
- `0x40b3b`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Monsters:**
- Orc (Axe) @ `0x40a63`

### Index 28

**Items:** (empty) / Iron / Iron / Alloy / Alloy / Ogre Fang / Mythril / Ogre Fang

**Monsters:**
- Ogre @ `0x40af3`

### Index 30

**Items:** Bronze / Bronze Shard / Iron Shard / Iron / Frost Craft / Chilly Gel / Frost Armor / Chilly Gel

**Monsters:**
- Ice Bomb @ `0x406b4`
- Ice Bomb @ `0x40746`

### Index 31

**Items:** Bronze / Bronze Shard / Iron Shard / Iron / Lightning Craft / Thunderball / Lightning Armor / Thunderball

## Tida - Area 1 (`ruin_0`)

### Index 1

**Items:** Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Iron Lance (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Hell Plant @ `0x47fdc`
- Hell Plant @ `0x48025`
- Skeleton (Sword) @ `0x4806e`
- Skeleton (Mage) @ `0x480b8`
- Skeleton (Mage) @ `0x48101`
- Skeleton (Mage) @ `0x48270`
- Skeleton (Sword) @ `0x48741`
- Skeleton (Sword) @ `0x48990`
- Skeleton (Spear) @ `0x489d9`
- Skeleton (Mace) @ `0x48a22`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fish

**Chests:**
- `0x49212`

**Monsters:**
- Hell Plant @ `0x4814f`
- Gremlin @ `0x48300`
- Skeleton (Sword) @ `0x484b2`
- Skeleton (Mace) @ `0x48543`
- Skeleton (Spear) @ `0x4858b`
- Skeleton (Mage) @ `0x48665`
- Skeleton (Mage) @ `0x486ae`
- Skeleton (Mage) @ `0x4886a`
- Mushroom Forest Carrion Worm @ `0x488b3`
- Bomb @ `0x48c26`
- Hell Plant @ `0x48cbb`
- Skeleton (Sword) @ `0x48de0`
- Hell Plant @ `0x48f03`
- Hell Plant @ `0x48f4b`
- Hell Plant @ `0x48fdb`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Gremlin @ `0x48392`
- Skeleton (Sword) @ `0x488fe`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Skeleton (Mage) @ `0x4834a`
- Gremlin @ `0x48948`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Skeleton (Sword) @ `0x48a6b`
- Skeleton (Spear) @ `0x48ab5`
- Skeleton (Mace) @ `0x48aff`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Gremlin @ `0x48197`
- Skeleton (Mage) @ `0x48e29`
- Skeleton (Mage) @ `0x48e72`
- Hell Plant @ `0x48ebb`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Chests:**
- `0x491b3`

**Monsters:**
- Hell Plant @ `0x48f93`

### Index 11

**Items:** Maneater / Ashura / Kaiser Knuckles / Ice Brand / Ogrekiller / Fang Charm / Engetsurin / Mjollnir

**Chests:**
- `0x492a1`

### Index 13

**Items:** Sparkling Bracer / Sparkling Bracer / Helm of Arai / Helm of Arai / Elven Mantle / Elven Mantle / Rune Staff / Wonder Bangle

**Chests:**
- `0x492d3`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Gremlin @ `0x481e0`
- Bomb @ `0x48bdc`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Gremlin @ `0x48421`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Skeleton (Sword) @ `0x4861c`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Tida Carrion Worm @ `0x48228`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Skeleton (Mage) @ `0x482b8`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Chests:**
- `0x491e2`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Monsters:**
- Skeleton (Mage) @ `0x48b49`

### Index 26

**Items:** Bronze Shard / Crystal Ball / Iron Shard / Shiny Shard / Blue Silk / Ruby / Jade / Tiny Crystal

**Monsters:**
- Gremlin @ `0x4846a`
- Gremlin @ `0x48822`

### Index 27

**Items:** Copper Sword (!) / Iron / Iron / Worm Antenna / Bastard Sword (!) / Defender (!) / Worm Antenna / Worm Antenna

**Monsters:**
- Tida Carrion Worm @ `0x483d9`
- Tida Carrion Worm @ `0x486f8`
- Mushroom Forest Carrion Worm @ `0x48b91`

### Index 28

**Items:** Copper Sword (!) / Iron Sword (!) / Gear / Gear / Bastard Sword (!) / Defender (!) / Gear / Gear

**Monsters:**
- Skeleton (Sword) @ `0x484fb`
- Skeleton (Sword) @ `0x485d4`
- Skeleton (Sword) @ `0x48d96`

### Index 29

**Items:** Copper Sword (!) / Flower Seed / Flower Seed / Strange Seed / Bastard Sword (!) / Flower Seed / Flower Seed / Strange Seed

**Monsters:**
- Hell Plant @ `0x48d04`
- Hell Plant @ `0x48d4d`
- Hell Plant @ `0x49024`

### Index 30

**Items:** Bronze / Bronze Shard / Iron Shard / Iron / Flame Craft / Magma Rock / Flame Armor / Magma Rock

**Monsters:**
- Bomb @ `0x4878c`

### Index 31

**Items:** Warrior's Weapon / Warrior's Weapon / Warrior's Weapon / Master's Weapon / Master's Weapon / Victorious Weapon / Valiant Weapon / Mighty Weapon

**Chests:**
- `0x49271`

### Index 32

**Items:** Iron Armor / Iron Armor / Iron Armor / Mythril Armor / Mythril Armor / Time Armor / Pure Armor / Holy Armor

**Chests:**
- `0x49242`

### Index 51

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Hell Plant @ `0x47eb4`

### Index 52

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / ?

**Monsters:**
- Skeleton (Sword) @ `0x47dd4`
- Bomb @ `0x47e1f`
- Bomb @ `0x47e69`
- Skeleton (Sword) @ `0x47efd`
- Skeleton (Sword) @ `0x47f47`

### Garbage E-value entries (JSON extraction artifacts)

- Mushroom Forest Carrion Worm (E=268435456) @ `0x47f91`
- Bomb (E=536870942) @ `0x487d7`
- Mushroom Forest Carrion Worm (E=268435456) @ `0x48c70`

## Tida - Area 2 (`ruin_1`)

### Index 1

**Items:** Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Iron Lance (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Skeleton (Mage) @ `0x44fda`
- Tida Carrion Worm @ `0x450fb`
- Skeleton (Mage) @ `0x453cc`
- Skeleton (Mage) @ `0x454a5`
- Skeleton (Mage) @ `0x454ee`
- Tida Carrion Worm @ `0x45580`
- Hell Plant @ `0x4577c`
- Hell Plant @ `0x45857`
- Skeleton (Mage) @ `0x45932`
- Tida Carrion Worm @ `0x45a58`
- Mushroom Forest Carrion Worm @ `0x45aa1`
- Abaddon @ `0x45aeb`
- Mushroom Forest Carrion Worm @ `0x45e9f`
- Mushroom Forest Carrion Worm @ `0x45ee6`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fruit Seed

**Monsters:**
- Skeleton (Mage) @ `0x44f92`
- Tida Carrion Worm @ `0x451d2`
- Skeleton (Mage) @ `0x4521a`
- Stone Plant @ `0x45414`
- Tida Carrion Worm @ `0x45611`
- Hell Plant @ `0x456a2`
- Stone Plant @ `0x45b35`
- Stone Plant @ `0x45b7f`
- Hell Plant @ `0x45ca7`
- Magic Plant @ `0x45cef`
- Hell Plant @ `0x45d7f`
- Magic Plant @ `0x45dc7`

### Index 5

**Items:** Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed

**Monsters:**
- Hell Plant @ `0x4580e`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Skeleton (Mage) @ `0x45022`
- Tida Carrion Worm @ `0x45735`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Tida Carrion Worm @ `0x450b2`
- Tida Carrion Worm @ `0x455c8`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Skeleton (Mage) @ `0x4506a`
- Skeleton (Mage) @ `0x456ec`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Skeleton (Mage) @ `0x4597b`

### Index 12

**Items:** Dragon's Whisker / Mage Masher / Silver Bracer / Cat's Bell / Sage's Staff / Kris / Rune Bell / Mage's Staff

**Chests:**
- `0x46114`

### Index 14

**Items:** Chocobo Pocket / Chocobo Pocket / Chocobo Pocket / Moogle Pocket / Bastard Sword (!) / Chocobo Pocket / Chocobo Pocket / Moogle Pocket

**Chests:**
- `0x460b6`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Skeleton (Mage) @ `0x45143`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Skeleton (Mage) @ `0x4518b`
- Hell Plant @ `0x45537`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Skeleton (Mage) @ `0x4565a`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Monsters:**
- Skeleton (Mage) @ `0x459c4`

### Index 26

**Items:** Copper Sword (!) / Iron Sword (!) / Jagged Scythe / Jagged Scythe / Mythril / Diamond Ore / Diamond Ore / Jagged Scythe

**Monsters:**
- Abaddon @ `0x45bc9`
- Abaddon @ `0x45e57`
- Abaddon @ `0x45f2d`

### Index 27

**Items:** Copper Sword (!) / Iron / Iron / Worm Antenna / Bastard Sword (!) / Defender (!) / Worm Antenna / Worm Antenna

**Monsters:**
- Tida Carrion Worm @ `0x44f4a`
- Tida Carrion Worm @ `0x4545c`

### Index 28

**Items:** Copper Sword (!) / Iron Sword (!) / Gear / Gear / Bastard Sword (!) / Defender (!) / Gear / Gear

**Monsters:**
- Skeleton (Mage) @ `0x45383`

### Index 29

**Items:** Copper Sword (!) / Flower Seed / Flower Seed / Strange Seed / Bastard Sword (!) / Flower Seed / Flower Seed / Strange Seed

**Monsters:**
- Magic Plant @ `0x452f3`
- Hell Plant @ `0x45a0e`

### Index 30

**Items:** Bronze / Bronze Shard / Iron Shard / Iron / Flame Craft / Magma Rock / Flame Armor / Magma Rock

**Monsters:**
- Bomb @ `0x452ab`
- Bomb @ `0x4533b`

### Index 31

**Items:** (empty) / (empty) / (empty) / Mythril / Mythril / Alloy / Tiny Crystal / Diamond Ore

**Monsters:**
- Stone Plant @ `0x457c5`
- Stone Plant @ `0x458a0`
- Stone Plant @ `0x45d37`
- Stone Plant @ `0x45e0f`

### Index 32

**Items:** Iron Shield / Iron Gloves / Mythril Gloves / Mythril Shield / Frost Gloves / Frost Shield / Gold Gloves / Magic Shield

**Chests:**
- `0x46174`

### Index 33

**Items:** Iron Sallet / Iron Belt / Mythril Sallet / Mythril Belt / Frost Sallet / Frost Belt / Eternal Sallet / Wind Belt

**Chests:**
- `0x460e5`

### Index 34

**Items:** Copper Sword (!) / Iron Sword (!) / Faerie Kit / Faerie Kit / Faerie Kit / Angel Kit / Angel Kit / Angel Kit

**Chests:**
- `0x46085`
- `0x46144`

**Monsters:**
- Tida Carrion Worm @ `0x458e8`

### Garbage E-value entries (JSON extraction artifacts)

- Bomb (E=805306377) @ `0x45263`
- Mushroom Forest Carrion Worm (E=1073741825) @ `0x45c13`
- Abaddon (E=1073741850) @ `0x45c5d`

## Moschet Manor - Area 1 (`gigas_0`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Gargoyle @ `0x433f7`
- Gargoyle @ `0x43440`

### Index 14

**Items:** Chocobo Pocket / Chocobo Pocket / Earth Pendant / Earth Pendant / Earth Pendant / Earth Pendant / Moon Pendant / Moon Pendant

**Monsters:**
- Coeurl @ `0x4311a`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Gremlin @ `0x431f8`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Gargoyle @ `0x432d3`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Gremlin @ `0x431ad`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Chests:**
- `0x434b9`

**Monsters:**
- Coeurl @ `0x43164`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Chests:**
- `0x43489`

**Monsters:**
- Gargoyle @ `0x4331c`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Coeurl @ `0x4328a`

### Index 26

**Items:** Iron / Iron / Alloy / Alloy / Alloy / Alloy / Mythril / Mythril

**Monsters:**
- Gargoyle @ `0x43365`
- Gargoyle @ `0x433ae`

### Index 30

**Items:** Bronze / Iron / Tiny Crystal / Tiny Crystal / Mythril / Mythril / Tiny Crystal / ?

**Monsters:**
- Ochu @ `0x43241`

## Moschet Manor - Area 2 (`gigas_1`)

### Index 1

**Items:** Copper Sword (!) / Lady's Accessories / Lady's Accessories / Fashion Kit / Bastard Sword (!) / Fashion Kit / Fashion Kit / Lady's Accessories

**Chests:**
- `0x3a0b8`

## Moschet Manor - Area 3 (`gigas_2`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Coeurl @ `0x3c254`

### Index 5

**Items:** Wheat Seed / Wheat Seed / Wheat Seed / Wheat Seed / Wheat Seed / Wheat Seed / Wheat Seed / Wheat Seed

**Monsters:**
- Tonberry Chef @ `0x3c20a`

### Index 11

**Items:** Shuriken / Ashura / Kaiser Knuckles / Flametongue / Fang Charm / Ogrekiller / Engetsurin / Mjollnir

**Chests:**
- `0x3c29e`

## Moschet Manor - Area 4 (`gigas_3`)

### Index 12

**Items:** Rune Staff / Faerie Ring / Winged Cap / Wonder Wand / Candy Ring / Red Slippers / Noah's Lute / Dark Matter

**Chests:**
- `0x3c2f8`

### Index 27

**Items:** Silver / Holy Water / Ruby / Coeurl Whisker / Ruby / Silver / Holy Water / Coeurl Whisker

**Monsters:**
- Coeurl @ `0x3c2ae`

### Index 28

**Items:** Equipment 119 (Unused) (!) / Equipment 122 (Unused) (!) / Sonic Hammer (!) / Mythril Hammer (!) / Ultima Maul (!) / Gold Mail (!) / Yellow Feather / Yellow Feather

**Monsters:**
- Tonberry Chef @ `0x3c21a`
- Tonberry Chef @ `0x3c264`

## Moschet Manor - Area 5 (`gigas_4`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Gremlin @ `0x3ca3d`
- Gremlin @ `0x3ca85`
- Gargoyle @ `0x3cb18`
- Gargoyle @ `0x3cbf3`

### Index 26

**Items:** Bronze / Iron / Alloy / Alloy / Alloy / Alloy / Mythril / Mythril

**Monsters:**
- Gargoyle @ `0x3cb61`
- Gargoyle @ `0x3cbaa`

### Index 27

**Items:** Silver / Holy Water / Ruby / Coeurl Whisker / Ruby / Silver / Holy Water / Coeurl Whisker

**Monsters:**
- Coeurl @ `0x3cacf`

### Index 28

**Items:** Equipment 119 (Unused) (!) / Equipment 122 (Unused) (!) / Sonic Hammer (!) / Mythril Hammer (!) / Ultima Maul (!) / Gold Mail (!) / Yellow Feather / Yellow Feather

**Monsters:**
- Tonberry Chef @ `0x3c9aa`
- Tonberry Chef @ `0x3c9f4`

## Moschet Manor - Area 6 (`gigas_5`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Chests:**
- `0x3b5fb`

### Index 27

**Items:** Silver / Holy Water / Ruby / Coeurl Whisker / Ruby / Silver / Holy Water / Coeurl Whisker

**Monsters:**
- Coeurl @ `0x3b5b3`

### Index 28

**Items:** Equipment 119 (Unused) (!) / Equipment 122 (Unused) (!) / Sonic Hammer (!) / Mythril Hammer (!) / Ultima Maul (!) / Gold Mail (!) / Yellow Feather / Yellow Feather

**Monsters:**
- Tonberry Chef @ `0x3b56a`

## Moschet Manor - Area 7 (`gigas_6`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Gremlin @ `0x3cf25`
- Coeurl @ `0x3cf6e`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Tonberry Chef @ `0x3cedc`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Tonberry Chef @ `0x3ce93`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Tonberry Chef @ `0x3ce4a`

## Moschet Manor - Area 8 (`gigas_7`)

### Index 13

**Items:** Sparkling Bracer / Sparkling Bracer / Helm of Arai / Helm of Arai / Elven Mantle / Elven Mantle / Wonder Bangle / Wonder Bangle

**Chests:**
- `0x3b2f9`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Gremlin @ `0x3b2b1`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Tonberry Chef @ `0x3b26a`

## Veo Lu Sluice - Area 1 (`water_0`)

### Index 0

**Items:** NOT FOUND IN SWITCH

**Monsters:**
- Water Flan @ `0x4a600`

### Index 1

**Items:** Mythril Shield (!) / Diamond Shield (!) / Iron Gauntlets (!) / Gold Armlets (!) / Jade Bracer (Female) (!) / Dark Matter (!) / Item Gil (Unused) (!) / design 100 (Unused) (!)

**Chests:**
- `0x4b9c0` (raw A=65537)
- `0x4b9f0` (raw A=65537)

**Monsters:**
- Lizardman (Mage) @ `0x4adbc`
- Lizardman (Axe) @ `0x4ae50`
- Lizardman (Javelin) @ `0x4ae99`
- Ice Bomb @ `0x4aee2`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fruit Seed

**Monsters:**
- Lizardman (Mage) @ `0x4a7c1`
- Lizardman (Axe) @ `0x4a809`
- Water Flan @ `0x4a89a`
- Ice Bomb @ `0x4a9be`
- Lizardman (Javelin) @ `0x4abbc`
- Ice Bomb @ `0x4ac97`
- Ice Bomb @ `0x4b4a8`
- Griffin @ `0x4b53a`
- Lizardman (Axe) @ `0x4b8b6`

### Index 5

**Items:** Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed

**Monsters:**
- Water Flan @ `0x4b12c`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Lizardman (Axe) @ `0x4aa08`
- Lizardman (Javelin) @ `0x4aa51`
- Griffin @ `0x4b661`
- Lizardman (Axe) @ `0x4b78a`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Griffin @ `0x4b740`
- Gigan Toad @ `0x4b7d5`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Lizardman (Axe) @ `0x4ab2c`
- Griffin @ `0x4b617`
- Lizardman (Axe) @ `0x4b820`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Ice Bomb @ `0x4ad73`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Chests:**
- `0x4b901` (raw A=65546)

**Monsters:**
- Gigan Toad @ `0x4ac4e`

### Index 11

**Items:** Ashura / Kaiser Knuckles / Power Wristband / Twisted Headband / Ogrekiller / Engetsurin / Masquerade / Onion Sword

**Chests:**
- `0x4b930` (raw A=65547)

### Index 12

**Items:** Dragon's Whisker / Book of Light / Silver Bracer / Kris / Sage's Staff / Red Slippers / Dark Matter / Tome of Ultima

**Chests:**
- `0x4bb44` (raw A=65548)

### Index 13

**Items:** Drill / Drill / Main Gauche / Main Gauche / Rat's Tail / Rat's Tail / Chicken Knife / Chicken Knife

**Chests:**
- `0x4b991` (raw A=65549)

### Index 14

**Items:** Moon Pendant / Moon Pendant / Moon Pendant / Ring of Blizzard / Ring of Blizzard / Ring of Blizzard / Ring of Blizzard / Ring of Blizzard

**Monsters:**
- Griffin @ `0x4b20c`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Lizardman (Axe) @ `0x4a92c`
- Water Flan @ `0x4a975`
- Lizardman (Mage) @ `0x4afbd`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Gigan Toad @ `0x4a851`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Lizardman (Axe) @ `0x4af2b`
- Lizardman (Javelin) @ `0x4af74`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Lizardman (Axe) @ `0x4a731`
- Lizardman (Mace) @ `0x4a779`
- Lizardman (Axe) @ `0x4b006`
- Gigan Toad @ `0x4b04f`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Lizardman (Mage) @ `0x4ab74`
- Griffin @ `0x4b098`
- Ice Bomb @ `0x4b3c9`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Gigan Toad @ `0x4a8e3`
- Ice Bomb @ `0x4b335`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Chests:**
- `0x4b960` (raw A=65557)

### Index 25

**Items:** Shella Mark / Shella Mark / Shella Mark / Shella Mark / Shella Mark / Shella Mark / Shella Mark / Shella Mark

**Monsters:**
- Gigan Toad @ `0x4aae3`
- Griffin @ `0x4b2eb`

### Index 26

**Items:** Alloy / Alloy / Shella Mark / Griffin's Wing / Bastard Sword (!) / Shella Mark / Shella Mark / Griffin's Wing

**Monsters:**
- Griffin @ `0x4aa9a`
- Griffin @ `0x4ae07`
- Griffin @ `0x4b0e1`
- Griffin @ `0x4b380`
- Griffin @ `0x4b45d`
- Griffin @ `0x4b6ab`
- Griffin @ `0x4b6f5`

### Index 27

**Items:** Copper Sword (!) / Alloy / Alloy / Toad Oil / Bastard Sword (!) / Defender (!) / Toad Oil / Toad Oil

**Monsters:**
- Gigan Toad @ `0x4ac05`
- Gigan Toad @ `0x4b257`
- Gigan Toad @ `0x4b2a1`
- Gigan Toad @ `0x4b86b`

### Index 28

**Items:** Copper Sword (!) / Iron Sword (!) / Chilly Gel / Chilly Gel / Bastard Sword (!) / Defender (!) / Chilly Gel / Chilly Gel

**Monsters:**
- Water Flan @ `0x4ace0`
- Water Flan @ `0x4ad29`
- Water Flan @ `0x4b177`
- Water Flan @ `0x4b1c2`

### Index 29

**Items:** Copper Sword (!) / Iron Shard / Iron Shard / Chilly Gel / Bastard Sword (!) / Iron Shard / Iron Shard / Chilly Gel

**Monsters:**
- Ice Bomb @ `0x4b413`
- Ice Bomb @ `0x4b4f1`
- Ice Bomb @ `0x4b583`
- Ice Bomb @ `0x4b5cd`

### Index 30

**Items:** (empty) / (empty) / Frost Belt / Frost Belt / Frost Belt / Frost Belt / (empty) / (empty)

**Chests:**
- `0x4bb13` (raw A=65566)

### Index 31

**Items:** (empty) / (empty) / Frost Shield / Frost Shield / Frost Shield / Frost Shield / (empty) / (empty)

**Chests:**
- `0x4ba20` (raw A=65567)

### Index 32

**Items:** (empty) / Frost Gloves / Frost Gloves / Frost Gloves / Frost Gloves / Defender (!) / (empty) / (empty)

**Chests:**
- `0x4ba51` (raw A=65568)

### Index 33

**Items:** (empty) / Frost Armor / Frost Armor / Frost Armor / Frost Armor / Defender (!) / (empty) / (empty)

**Chests:**
- `0x4bab1` (raw A=65569)
- `0x4bae1` (raw A=65569)

### Index 34

**Items:** (empty) / Frost Sallet / Frost Sallet / Frost Sallet / Frost Sallet / Defender (!) / (empty) / (empty)

**Chests:**
- `0x4ba81` (raw A=65570)

### Index 50

**Items:** (empty) / (empty) / (empty) / (empty) / (empty) / (empty) / (empty) / Stone of Fire

**Monsters:**
- Lizardman (Axe) @ `0x4a64b`
- Lizardman (Axe) @ `0x4a696`

### Index 51

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Gigan Toad @ `0x4a56a`

### Index 52

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / ?

**Monsters:**
- Lizardman (Axe) @ `0x4a4d4`
- Lizardman (Mage) @ `0x4a51f`
- Lizardman (Mage) @ `0x4a5b5`

### Garbage E-value entries (JSON extraction artifacts)

- Griffin (E=1073741824) @ `0x4a6e1`

## Selepation Cave - Area 1 (`cave_0`)

### Index 1

**Items:** Sonic Lance (!) / Dragoon Spear (!) / Treasured Spear (!) / Marr Spear (!) / Equipment 126 (Unused) (!) / Gold Mail (!) / Mythril Belt (!) / Jade Bracer (Female) (!)

**Monsters:**
- Killer Bee @ `0x46c47`
- Lizardman (Mage) @ `0x46eda`
- Killer Bee @ `0x472e8`
- Lizardman (Axe) @ `0x474ec`
- Lizardman (Mace) @ `0x47536`
- Electric Jellyfish @ `0x479ce`
- Gigas @ `0x47aac`
- Gigas @ `0x47b3f`
- Killer Bee @ `0x47b87`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fish

**Monsters:**
- Killer Bee @ `0x46cd9`
- Killer Bee @ `0x46dfe`
- Lizardman (Axe) @ `0x46f23`
- Lizardman (Mace) @ `0x46f6d`
- Lizardman (Javelin) @ `0x470df`
- Killer Bee @ `0x4720a`
- Lizardman (Mage) @ `0x4737c`
- Lizardman (Axe) @ `0x47410`
- Lizardman (Mace) @ `0x47459`
- Lizardman (Javelin) @ `0x47580`
- Lizardman (Javelin) @ `0x475ca`
- Lizardman (Axe) @ `0x47786`
- Lizardman (Mace) @ `0x477cf`
- Lizardman (Mace) @ `0x478aa`
- Lizardman (Javelin) @ `0x478f3`
- Lizardman (Javelin) @ `0x4793c`
- Electric Jellyfish @ `0x47a18`
- Gigas @ `0x47a62`
- Killer Bee @ `0x47af6`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Lizardman (Axe) @ `0x47332`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Lizardman (Axe) @ `0x46b6c`
- Lizardman (Mace) @ `0x46bb5`
- Lizardman (Axe) @ `0x473c6`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Killer Bee @ `0x47129`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Electric Jellyfish @ `0x46d6c`
- Lizardman (Axe) @ `0x47861`
- Lizardman (Mage) @ `0x47985`

### Index 11

**Items:** Green Beret / Green Beret / Power Wristband / Twisted Headband / Heavy Armband / Mjollnir / Masquerade / Onion Sword

**Chests:**
- `0x47dd1`

### Index 14

**Items:** Moon Pendant / Moon Pendant / Moon Pendant / Ring of Thunder / Ring of Thunder / Ring of Thunder / Ring of Thunder / Ring of Thunder

**Chests:**
- `0x47cde`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Killer Bee @ `0x46e47`
- Lizardman (Mage) @ `0x46e90`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Lizardman (Axe) @ `0x46ada`
- Blazer Beetle @ `0x47254`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Electric Jellyfish @ `0x46b23`
- Electric Jellyfish @ `0x46d22`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Lizardman (Mage) @ `0x46bfe`
- Blazer Beetle @ `0x46db5`
- Lizardman (Javelin) @ `0x47095`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Lizardman (Axe) @ `0x47001`
- Lizardman (Mace) @ `0x4704b`

### Index 26

**Items:** Copper Sword (!) / Iron Sword (!) / Hard Shell / Hard Shell / Bastard Sword (!) / Defender (!) / Hard Shell / Hard Shell

**Monsters:**
- Blazer Beetle @ `0x46c90`
- Blazer Beetle @ `0x47614`
- Blazer Beetle @ `0x4765e`
- Blazer Beetle @ `0x476a8`

### Index 27

**Items:** Copper Sword (!) / Iron Sword (!) / Thunderball / Thunderball / Bastard Sword (!) / Defender (!) / Thunderball / Thunderball

**Monsters:**
- Electric Jellyfish @ `0x47174`
- Electric Jellyfish @ `0x471bf`
- Electric Jellyfish @ `0x4729e`
- Electric Jellyfish @ `0x476f2`
- Electric Jellyfish @ `0x47c1a`
- Electric Jellyfish @ `0x47c64`

### Index 28

**Items:** Copper Sword (!) / Iron Sword (!) / Gigas Claw / Gigas Claw / Bastard Sword (!) / Defender (!) / Gigas Claw / Gigas Claw

**Monsters:**
- Gigas @ `0x4773c`
- Gigas @ `0x47bd0`

### Index 29

**Items:** Alloy / Alloy / Mythril / Mythril / Alloy / Alloy / Mythril / Mythril

**Monsters:**
- Lizardman Captain @ `0x46fb7`
- Lizardman Captain @ `0x474a2`
- Lizardman Captain @ `0x47818`

### Index 30

**Items:** Iron Shield / Iron Gloves / Mythril Gloves / Mythril Shield / Lightning Gloves / Lightning Shield / Gold Gloves / Holy Shield

**Chests:**
- `0x47d0e`

### Index 31

**Items:** Iron Sallet / Iron Belt / Mythril Sallet / Mythril Belt / Lightning Sallet / Lightning Belt / Time Sallet / Pure Belt

**Chests:**
- `0x47d3f`

### Index 32

**Items:** Iron Armor / Iron Armor / Iron Armor / Mythril Armor / Mythril Armor / Time Armor / Pure Armor / Holy Armor

**Chests:**
- `0x47d6f`

### Index 33

**Items:** Copper Sword (!) / Iron Sword (!) / Ring of Light / Ring of Light / Bastard Sword (!) / Defender (!) / Ring of Light / Ring of Light

**Chests:**
- `0x47cae`
- `0x47da1`

## Selepation Cave - Area 2 (`cave_1`)

### Index 1

**Items:** Sonic Lance (!) / Dragoon Spear (!) / Treasured Spear (!) / Marr Spear (!) / Equipment 126 (Unused) (!) / Gold Mail (!) / Mythril Belt (!) / Jade Bracer (Female) (!)

**Monsters:**
- Electric Jellyfish @ `0x40db4`
- Sonic Bat @ `0x40ed5`
- Sonic Bat @ `0x40faf`
- Cockatrice @ `0x4108a`
- Cockatrice @ `0x4128d`
- Electric Jellyfish @ `0x413fd`
- Sahagin @ `0x41648`
- Sahagin @ `0x41690`
- Cockatrice @ `0x4176b`
- Electric Jellyfish @ `0x41922`
- Sonic Bat @ `0x4196c`
- Electric Jellyfish @ `0x419b6`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fish

**Monsters:**
- Sahagin @ `0x40cdb`
- Sonic Bat @ `0x40e44`
- Electric Jellyfish @ `0x411af`
- Sonic Bat @ `0x41243`
- Sahagin @ `0x41525`
- Cockatrice @ `0x416d8`
- Sonic Bat @ `0x4188f`
- Gigas @ `0x41a48`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Gigas @ `0x40f65`
- Sahagin @ `0x4156e`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Sonic Bat @ `0x41043`
- Sahagin @ `0x415b7`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Electric Jellyfish @ `0x4111c`
- Sahagin @ `0x41321`
- Sahagin @ `0x41600`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Sahagin @ `0x40d23`
- Sahagin @ `0x40d6b`
- Sahagin @ `0x417b5`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Cockatrice @ `0x411f9`
- Sahagin @ `0x4136a`
- Sonic Bat @ `0x41721`

### Index 12

**Items:** Mage Masher / Book of Light / Cat's Bell / Wonder Wand / Faerie Ring / Rune Bell / Gold Hairpin / Tome of Ultima

**Chests:**
- `0x41c02`

### Index 13

**Items:** Drill / Drill / Main Gauche / Main Gauche / Rat's Tail / Rat's Tail / Chicken Knife / Chicken Knife

**Chests:**
- `0x41c32`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Cockatrice @ `0x412d7`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Sahagin @ `0x413b3`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Electric Jellyfish @ `0x40ff9`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Sahagin @ `0x40c93`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Cockatrice @ `0x40dfb`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Cockatrice @ `0x40c4a`

### Index 26

**Items:** Copper Sword (!) / Iron Sword (!) / Cockatrice Scale / Cockatrice Scale / Bastard Sword (!) / Defender (!) / Cockatrice Scale / Cockatrice Scale

**Monsters:**
- Cockatrice @ `0x40e8d`
- Cockatrice @ `0x41165`
- Cockatrice @ `0x41491`
- Cockatrice @ `0x417fd`
- Cockatrice @ `0x419ff`

### Index 27

**Items:** Copper Sword (!) / Iron Sword (!) / Thunderball / Thunderball / Bastard Sword (!) / Defender (!) / Thunderball / Thunderball

**Monsters:**
- Electric Jellyfish @ `0x40f1e`
- Electric Jellyfish @ `0x41447`
- Cockatrice @ `0x414db`
- Electric Jellyfish @ `0x41846`
- Cockatrice @ `0x418d8`

### Index 28

**Items:** Copper Sword (!) / Iron Sword (!) / Gigas Claw / Gigas Claw / Bastard Sword (!) / Defender (!) / Gigas Claw / Gigas Claw

**Monsters:**
- Gigas @ `0x410d3`
- Gigas @ `0x41a92`
- Gigas @ `0x41adc`
- Gigas @ `0x41b26`
- Gigas @ `0x41b70`
- Gigas @ `0x41bb9`

### Index 30

**Items:** Warrior's Weapon / Warrior's Weapon / Master's Weapon / Master's Weapon / Master's Weapon / Valiant Weapon / Mighty Weapon / Victorious Weapon

**Chests:**
- `0x41c62`

## Daemon's Court (`fort_0`)

### Index 0

**Items:** NOT FOUND IN SWITCH

**Monsters:**
- Bomb @ `0x4776a`
- No enemy was visible @ `0x477e7`
- No enemy was visible @ `0x4782f`
- No enemy was visible @ `0x47878`

### Index 1

**Items:** Rune Hammer (!) / Sonic Hammer (!) / Mythril Hammer (!) / Father's Hammer (!) / Gold Mail (!) / Iron Gauntlets (!) / Dark Matter (!) / Silver (!)

**Monsters:**
- Killer Bee @ `0x47d12`
- Killer Bee @ `0x47d5c`
- Lizard Soldier @ `0x480bf`
- Killer Bee @ `0x4819c`
- Lizard Wizard @ `0x4834c`
- Lizard Soldier @ `0x48394`
- Lizard Skirmisher @ `0x48424`
- Lizard Skirmisher @ `0x4858d`
- Lizard Soldier @ `0x485d6`
- Lizard Soldier @ `0x48668`
- Lizard Soldier @ `0x48744`
- Lizard Skirmisher @ `0x4878e`
- Lizard Soldier @ `0x48820`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fish

**Monsters:**
- Coeurl @ `0x47dec`
- Lizard Soldier @ `0x4846c`
- Lizard Soldier @ `0x484fc`
- Lizard Soldier @ `0x488f9`
- Lizard Soldier @ `0x4898b`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Lizard Soldier @ `0x48152`
- Lizard Soldier @ `0x48274`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Killer Bee @ `0x47c35`
- Lizard Skirmisher @ `0x48544`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Killer Bee @ `0x47b5a`
- Lizard Skirmisher @ `0x487d8`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Lizard Wizard @ `0x48076`
- Lizard Wizard @ `0x48108`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Chests:**
- `0x48b50` (raw A=131082)

**Monsters:**
- Wraith @ `0x47cc9`
- Wraith @ `0x47e7b`

### Index 11

**Items:** Power Wristband / Fang Charm / Engetsurin / Twisted Headband / Masquerade / Heavy Armband / Giant's Glove / Onion Sword

**Chests:**
- `0x489d4`

### Index 12

**Items:** Rune Staff / Book of Light / Faerie Ring / Cat's Bell / Mage's Staff / Book of Light / Noah's Lute / Tome of Ultima

**Chests:**
- `0x48a32` (raw A=131084)

### Index 13

**Items:** Drill / Drill / Main Gauche / Main Gauche / Rat's Tail / Rat's Tail / Chicken Knife / Chicken Knife

**Chests:**
- `0x48a61` (raw A=131085)

### Index 14

**Items:** Moon Pendant / Moon Pendant / Chocobo Pocket / Chocobo Pocket / Moon Pendant / Chocobo Pocket / Moon Pendant / Chocobo Pocket

**Chests:**
- `0x48ac1` (raw A=131086)

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Lizard Warrior @ `0x47ec3`
- Lizard Wizard @ `0x48304`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Lizard Warrior @ `0x47f53`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Lizard Warrior @ `0x47fe4`
- Lizard Wizard @ `0x488b0`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Chests:**
- `0x48b20` (raw A=131090)

**Monsters:**
- Coeurl @ `0x47ba3`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Chests:**
- `0x48b81` (raw A=131091)

**Monsters:**
- Wraith @ `0x47da4`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Chests:**
- `0x48a03`

### Index 26

**Items:** Copper Sword (!) / Iron Sword (!) / Coeurl Whisker / Coeurl Whisker / Bastard Sword (!) / Defender (!) / Coeurl Whisker / Coeurl Whisker

**Monsters:**
- Coeurl @ `0x47c7f`
- Coeurl @ `0x47e33`
- Coeurl @ `0x47f9c`
- Coeurl @ `0x4822c`

### Index 27

**Items:** Iron / Iron / Mythril / Mythril / (empty) / Alloy / Alloy / Mythril

**Monsters:**
- Lizard Warrior @ `0x482bc`
- Lizard Warrior @ `0x483dc`
- Lizard Warrior @ `0x484b4`
- Lizard Warrior @ `0x4861f`
- Lizard Warrior @ `0x486b1`
- Lizard Warrior @ `0x486fa`
- Lizard Warrior @ `0x48868`
- Lizard Warrior @ `0x48942`

### Index 28

**Items:** Copper Sword (!) / Heavenly Dust / Heavenly Dust / Holy Water / Bastard Sword (!) / Heavenly Dust / Heavenly Dust / Holy Water

**Monsters:**
- Wraith @ `0x47bec`
- Wraith @ `0x47f0b`
- Wraith @ `0x4802d`
- Wraith @ `0x481e4`

### Index 31

**Items:** Warrior's Weapon / Warrior's Weapon / Master's Weapon / Master's Weapon / Master's Weapon / Victorious Weapon / Mighty Weapon / Valiant Weapon

**Chests:**
- `0x48a90` (raw A=131103)

### Index 32

**Items:** Copper Sword (!) / Eyewear Techniques / Eyewear Techniques / Eyewear Techniques / Bastard Sword (!) / Designer Glasses / Designer Glasses / Designer Glasses

**Chests:**
- `0x48af1`

### Garbage E-value entries (JSON extraction artifacts)

- Gold Lizard Skirmisher (E=268435456) @ `0x47972`
- Gold Lizard Skirmisher (E=536870912) @ `0x479b9`
- Gold Lizard Skirmisher (E=268435456) @ `0x47a18`
- Gold Lizard Skirmisher (E=536870912) @ `0x47a61`
- Gold Lizard Skirmisher (E=268435456) @ `0x47ac0`
- Gold Lizard Skirmisher (E=536870912) @ `0x47b07`

## Conall Curach - Area 1 (`swamp_0`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Snow Mu @ `0x43b22`
- Sahagin @ `0x43c42`
- Magic Plant @ `0x43c8a`
- Sahagin @ `0x43d1a`
- Magic Plant @ `0x43fa7`
- Magic Plant @ `0x44038`
- Sahagin @ `0x44111`
- Sahagin @ `0x441a2`
- Sahagin @ `0x44234`
- Sahagin @ `0x442c6`
- Sahagin @ `0x44357`
- Sahagin @ `0x443e8`
- Snow Mu @ `0x4459a`
- Snow Mu @ `0x445e2`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fruit Seed

**Chests:**
- `0x446e6`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Sahagin @ `0x440c8`
- Sahagin @ `0x4427d`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Sahagin @ `0x4415a`
- Sahagin @ `0x4430e`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Sahagin @ `0x441eb`
- Sahagin @ `0x4439f`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Magic Plant @ `0x43ff0`
- Magic Plant @ `0x44080`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Chests:**
- `0x4462a`

**Monsters:**
- Snow Mu @ `0x43b6b`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Ice Bomb @ `0x43bb2`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Ice Bomb @ `0x43dab`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Magic Plant @ `0x43cd2`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Snow Mu @ `0x43ada`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Sahagin @ `0x43d63`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Magic Plant @ `0x43e85`

### Index 26

**Items:** Chilly Gel / Chilly Gel / Chilly Gel / Chilly Gel / Chilly Gel / Chilly Gel / Chilly Gel / Chilly Gel

**Monsters:**
- Ice Bomb @ `0x43bfa`
- Ice Bomb @ `0x43df4`
- Ice Bomb @ `0x43e3d`

### Index 27

**Items:** Thunderball / Thunderball / Thunderball / Thunderball / Thunderball / Thunderball / Thunderball / Thunderball

**Monsters:**
- Thunder Bomb @ `0x44430`
- Thunder Bomb @ `0x44479`
- Thunder Bomb @ `0x444c2`
- Thunder Bomb @ `0x4450a`
- Thunder Bomb @ `0x44552`

### Index 28

**Items:** Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Vegetable Seed / Fruit Seed

**Monsters:**
- Magic Plant @ `0x43ecd`

### Index 29

**Items:** Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / Fruit Seed / (empty)

**Monsters:**
- Magic Plant @ `0x43f16`

### Index 30

**Items:** (empty) / (empty) / Wheat Seed / Wheat Seed / (empty) / (empty) / Wheat Seed / Wheat Seed

**Monsters:**
- Magic Plant @ `0x43f5e`

### Index 31

**Items:** Valiant Weapon / Mighty Weapon / Victorious Weapon / Master's Weapon / Valiant Weapon / Mighty Weapon / Victorious Weapon / Master's Weapon

**Chests:**
- `0x44688`

### Index 32

**Items:** Mythril Shield / Mythril Shield / Lightning Shield / Lightning Shield / Magic Shield / Holy Shield / Diamond Shield / Diamond Shield

**Chests:**
- `0x44659`

### Index 34

**Items:** Mythril Sallet / Mythril Sallet / Lightning Sallet / Lightning Sallet / Time Sallet / Eternal Sallet / Diamond Sallet / Diamond Sallet

**Chests:**
- `0x446b7`

## Conall Curach - Area 2 (`swamp_1`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Magic Plant @ `0x4197a`
- Sahagin @ `0x419c4`
- Sahagin @ `0x41a0d`
- Sahagin @ `0x41a57`
- Conall Curach Flan @ `0x41aa1`
- Sahagin @ `0x41b7f`
- Sahagin @ `0x41bc9`
- Conall Curach Flan @ `0x41c13`
- Magic Plant @ `0x41ca7`
- Sahagin @ `0x41d3b`
- Magic Plant @ `0x41dcf`
- Magic Plant @ `0x41e18`
- Magic Plant @ `0x41e62`
- Conall Curach Gigan Toad @ `0x41f86`
- Conall Curach Flan @ `0x4201a`
- Sahagin @ `0x420ae`
- Magic Plant @ `0x420f7`
- Conall Curach Flan @ `0x42141`
- Conall Curach Flan @ `0x421d5`
- Conall Curach Flan @ `0x42268`
- Conall Curach Flan @ `0x42343`
- Conall Curach Flan @ `0x4238b`
- Stone Sahagin @ `0x423d4`
- Stone Sahagin @ `0x4241d`
- Stone Sahagin @ `0x42466`
- Stone Sahagin @ `0x424b0`
- Magic Plant @ `0x42544`
- Magic Plant @ `0x4258d`
- Magic Plant @ `0x425d6`
- Magic Plant @ `0x4261f`
- Sahagin @ `0x42668`
- Magic Plant @ `0x42786`
- Magic Plant @ `0x427cd`
- Sahagin @ `0x4285e`
- Sahagin @ `0x428f2`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fruit Seed

**Chests:**
- `0x42adb`
- `0x42b0b`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Conall Curach Flan @ `0x4218b`
- Sahagin @ `0x42814`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Conall Curach Flan @ `0x4221f`
- Sahagin @ `0x428a8`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Conall Curach Flan @ `0x422b2`
- Sahagin @ `0x4293c`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Sahagin @ `0x41d85`
- Sahagin @ `0x42064`

### Index 11

**Items:** Kaiser Knuckles / Maneater / Green Beret / Loaded Dice / Flametongue / Mjollnir / Heavy Armband / Giant's Glove

**Chests:**
- `0x42c5b`

### Index 12

**Items:** Faerie Ring / Mage Masher / Candy Ring / Red Slippers / Sage's Staff / Noah's Lute / Dark Matter / Tome of Ultima

**Chests:**
- `0x42b3b`

### Index 13

**Items:** Sparkling Bracer / Sparkling Bracer / Main Gauche / Main Gauche / Teddy Bear / Teddy Bear / Chicken Knife / Chicken Knife

**Chests:**
- `0x42aaa`

### Index 14

**Items:** Star Pendant / Star Pendant / Star Pendant / Ring of Cure / Star Pendant / Ring of Cure / Star Pendant / Ring of Cure

**Chests:**
- `0x42c8c`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Magic Plant @ `0x41f3d`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Sahagin @ `0x41cf1`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Conall Curach Flan @ `0x422fb`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Magic Plant @ `0x41c5d`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Conall Curach Gigan Toad @ `0x41eab`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Conall Curach Gigan Toad @ `0x41fd0`

### Index 21

**Items:** (empty) / Pressed Flower / Pressed Flower / Remedy / (empty) / Pressed Flower / Pressed Flower / Remedy

**Monsters:**
- Sahagin Lord @ `0x424fa`

### Index 26

**Items:** Copper Sword (!) / Iron Sword (!) / Toad Oil / Toad Oil / Bastard Sword (!) / Toad Oil / Toad Oil / Ancient Potion

**Monsters:**
- Conall Curach Gigan Toad @ `0x41aeb`
- Conall Curach Gigan Toad @ `0x41b35`
- Conall Curach Gigan Toad @ `0x41ef4`
- Conall Curach Gigan Toad @ `0x42986`
- Conall Curach Gigan Toad @ `0x429cf`
- Conall Curach Gigan Toad @ `0x42a18`
- Conall Curach Gigan Toad @ `0x42a61`

### Index 27

**Items:** Copper Sword (!) / Jagged Scythe / Jagged Scythe / Jagged Scythe / Jagged Scythe / Jagged Scythe / Jagged Scythe / Legendary Weapon

**Monsters:**
- Abaddon @ `0x426b0`
- Abaddon @ `0x426f7`
- Abaddon @ `0x4273e`

### Index 31

**Items:** Soul of the Lion / Soul of the Lion / Soul of the Lion / Soul of the Lion / Soul of the Dragon / Soul of the Dragon / Soul of the Dragon / Soul of the Dragon

**Chests:**
- `0x42c2a`

### Index 32

**Items:** Mythril Gloves / Mythril Gloves / Lightning Gloves / Lightning Gloves / Gold Gloves / Gold Gloves / Diamond Gloves / Diamond Gloves

**Chests:**
- `0x42b9c`

### Index 33

**Items:** Mythril Armor / Mythril Armor / Mythril Armor / Eternal Armor / Pure Armor / Holy Armor / Diamond Armor / Diamond Armor

**Chests:**
- `0x42b6c`
- `0x42bfa`

### Index 34

**Items:** Mythril Belt / Mythril Belt / Lightning Belt / Lightning Belt / Wind Belt / Pure Belt / Diamond Belt / Diamond Belt

**Chests:**
- `0x42bcb`

## Conall Curach - Area 3 (`swamp_2`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Magic Plant @ `0x3fafa`
- Stone Sahagin @ `0x3fb8c`
- Stone Sahagin @ `0x3fbd5`
- Stone Sahagin @ `0x3fc67`
- Stone Sahagin @ `0x3fd42`
- Stone Sahagin @ `0x3fd8b`
- Dark Flan @ `0x3fe80`
- Magic Plant @ `0x3ff5b`
- Magic Plant @ `0x40036`
- Dark Flan @ `0x4007f`
- Magic Plant @ `0x400c8`
- Dark Flan @ `0x4015a`
- Dark Flan @ `0x40235`
- Stone Sahagin @ `0x40310`
- Dark Flan @ `0x403a2`
- Dark Flan @ `0x40434`
- Dark Flan @ `0x404c6`
- Magic Plant @ `0x405a1`
- Magic Plant @ `0x40633`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Stone Sahagin @ `0x402c7`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Dark Flan @ `0x40359`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Dark Flan @ `0x401a3`
- Magic Plant @ `0x405ea`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Chests:**
- `0x40757`
- `0x40845`

**Monsters:**
- Ghost @ `0x3fec9`
- Ghost @ `0x40558`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Magic Plant @ `0x3ff12`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Ghost @ `0x3ffa4`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Stone Sahagin @ `0x3fc1e`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Magic Plant @ `0x40111`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Stone Sahagin @ `0x3fe37`

### Index 26

**Items:** Worn Bandanna / Worn Bandanna / Worn Bandanna / Worn Bandanna / Worn Bandanna / Worn Bandanna / Worn Bandanna / Worn Bandanna

**Monsters:**
- Stone Sahagin @ `0x3fde9`

### Index 28

**Items:** Copper Sword (!) / Iron Sword (!) / Blue Silk / Blue Silk / Diamond Ore / Diamond Ore / White Silk / White Silk

**Monsters:**
- Ghost @ `0x3fcb0`
- Ghost @ `0x3fcf9`
- Ghost @ `0x3ffed`
- Ghost @ `0x4050f`

### Index 29

**Items:** Copper Sword (!) / Iron Sword (!) / Orichalcum / Orichalcum / Diamond Ore / Diamond Ore / Diamond Ore / Orichalcum

**Monsters:**
- Behemoth @ `0x3fb43`
- Behemoth @ `0x401ec`
- Behemoth @ `0x4027e`
- Behemoth @ `0x403eb`
- Behemoth @ `0x4047d`
- Behemoth @ `0x4067c`

### Index 30

**Items:** Bronze / Bronze / Iron / Iron / Alloy / Alloy / Mythril / Mythril

**Monsters:**
- Stone Sahagin @ `0x406c5`
- Stone Sahagin @ `0x4070e`

### Index 31

**Items:** Valiant Weapon / Mighty Weapon / Victorious Weapon / Master's Weapon / Valiant Weapon / Mighty Weapon / Victorious Weapon / Legendary Weapon

**Chests:**
- `0x40786`

### Index 32

**Items:** Mythril Shield / Mythril Gloves / Lightning Gloves / Lightning Gloves / Gold Gloves / Holy Shield / Diamond Gloves / Diamond Shield

**Chests:**
- `0x407b6`

### Index 33

**Items:** Mythril Armor / Mythril Armor / Mythril Armor / Eternal Armor / Pure Armor / Gold Armor / Diamond Armor / Diamond Armor

**Chests:**
- `0x407e5`

### Index 34

**Items:** Mythril Sallet / Mythril Belt / Lightning Sallet / Lightning Belt / Time Sallet / Pure Belt / Diamond Sallet / Diamond Belt

**Chests:**
- `0x40815`

## Rebena Te Ra - Area 1 (`city_0`)

### Index 0

**Items:** NOT FOUND IN SWITCH

**Monsters:**
- Mimic @ `0x4899f`
- Mimic @ `0x48a29`
- Mimic @ `0x48ab3`
- Mimic @ `0x48b3e`
- Mimic @ `0x48bc9`
- Mimic @ `0x48c50`
- Mimic @ `0x48cd7`
- Mimic @ `0x48d5e`

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Ghost @ `0x4782a`
- Ghost @ `0x478bb`
- Skeleton (Sword?) in Lich boss fight @ `0x47a26`
- Skeleton (Spear?) in Lich boss fight @ `0x47a6f`
- Skeleton (Sword?) in Lich boss fight @ `0x47b95`
- Skeleton (Spear?) in Lich boss fight @ `0x47bdf`
- Ghost @ `0x47c73`
- Skeleton (Sword?) in Lich boss fight @ `0x47d51`
- Skeleton (Spear?) in Lich boss fight @ `0x47d9b`
- Ghost @ `0x47de5`
- Skeleton (Sword?) in Lich boss fight @ `0x48280`
- Gargoyle @ `0x482ca`
- Gargoyle @ `0x4835d`
- Gargoyle @ `0x483a7`
- Gargoyle @ `0x483f1`
- Gargoyle @ `0x4843b`
- Rebena Te Ra Skeleton Mage @ `0x485ac`
- Rebena Te Ra Skeleton Mage @ `0x485f4`
- Gargoyle @ `0x48688`
- Gargoyle @ `0x486d1`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Skeleton (Sword?) in Lich boss fight @ `0x47994`
- Skeleton (Mace) in Lich boss fight @ `0x479dd`
- Vampire Bat @ `0x47f06`
- Sonic Bat @ `0x480c3`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Skeleton (Sword?) in Lich boss fight @ `0x47cbd`
- Skeleton (Mace) in Lich boss fight @ `0x47d07`
- Vampire Bat @ `0x47f50`
- Sonic Bat @ `0x4810d`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Skeleton (Sword?) in Lich boss fight @ `0x47b01`
- Skeleton (Mace) in Lich boss fight @ `0x47b4b`
- Vampire Bat @ `0x4802e`
- Sonic Bat @ `0x481eb`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Vampire Bat @ `0x48078`
- Sonic Bat @ `0x48235`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Ghost @ `0x47c29`
- Vampire Bat @ `0x47f99`
- Sonic Bat @ `0x48156`

### Index 11

**Items:** Shuriken / Power Wristband / Ice Brand / Fang Charm / Engetsurin / Heavy Armband / Giant's Glove / Onion Sword

**Chests:**
- `0x48886`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Skeleton (Sword?) in Lich boss fight @ `0x4794b`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Chests:**
- `0x48c11`
- `0x48c98`
- `0x48d1f`
- `0x48da6`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Skeleton (Sword?) in Lich boss fight @ `0x47873`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Ghost @ `0x47903`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Chests:**
- `0x489e9`
- `0x48a72`
- `0x48afd`
- `0x48b88`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Rebena Te Ra Skeleton Mage @ `0x48762`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Monsters:**
- Rebena Te Ra Skeleton Mage @ `0x47e2e`
- Rebena Te Ra Skeleton Mage @ `0x47ebe`

### Index 27

**Items:** (empty) / (empty) / Gear / Gear / (empty) / (empty) / Gear / Gear

**Monsters:**
- Ghost @ `0x47e76`
- Rebena Te Ra Skeleton Mage @ `0x4863e`

### Index 28

**Items:** (empty) / (empty) / Tiny Crystal / Tiny Crystal / Alloy / Alloy / Diamond Ore / Diamond Ore

**Monsters:**
- Gargoyle @ `0x48313`
- Gargoyle @ `0x48719`

### Index 29

**Items:** (empty) / (empty) / Blue Silk / Blue Silk / Diamond Ore / Diamond Ore / White Silk / White Silk

**Monsters:**
- Ghost @ `0x47ab8`
- Ghost @ `0x48563`
- Ghost @ `0x487ac`

### Index 30

**Items:** (empty) / (empty) / Fiend's Claw / Fiend's Claw / Mythril / Mythril / Mythril / Devil's Claw

**Monsters:**
- Nightmare @ `0x48485`
- Nightmare @ `0x484cf`
- Nightmare @ `0x48519`
- Nightmare @ `0x487f4`
- Nightmare @ `0x4883d`

### Index 31

**Items:** Copper Sword (!) / Iron Sword (!) / Tome of Magic / Tome of Magic / Tome of Magic / Tome of Sorcery / Tome of Sorcery / Tome of Sorcery

**Chests:**
- `0x488e6`

### Index 32

**Items:** Copper Sword (!) / Blue Yarn / Blue Yarn / White Yarn / Blue Yarn / White Yarn / Ancient Potion / Ancient Potion

**Chests:**
- `0x488b6`

### Garbage E-value entries (JSON extraction artifacts)

- Vampire Bat (E=268435465) @ `0x47fe3`
- Sonic Bat (E=268435465) @ `0x481a0`

## Rebena Te Ra - Area 2 (`city_1`)

### Index 0

**Items:** NOT FOUND IN SWITCH

**Monsters:**
- Skeleton Ice Mage @ `0x4657b`
- Skeleton Ice Mage @ `0x46a47`
- Skeleton Fire Mage @ `0x46a8f`
- Skeleton Fire Mage @ `0x46bf5`
- Skeleton Lightning Mage @ `0x46c3d`
- Mimic @ `0x46ca9`
- Mimic @ `0x46cf2`
- Mimic @ `0x46d3b`
- Mimic @ `0x46dca`
- Mimic @ `0x46e13`
- Mimic @ `0x46e8b`
- Mimic @ `0x46eeb`
- Mimic @ `0x46f64`
- Mimic @ `0x46fac`
- Mimic @ `0x4703c`
- Mimic @ `0x47085`
- Mimic @ `0x470cd`

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Gargoyle @ `0x45d51`
- Skeleton (Sword?) in Lich boss fight @ `0x45e6e`
- Skeleton (Spear?) in Lich boss fight @ `0x45eb7`
- Rebena Te Ra Skeleton Mage @ `0x45f48`
- Gargoyle @ `0x46020`
- Skeleton (Sword?) in Lich boss fight @ `0x460b1`
- Skeleton (Mace) in Lich boss fight @ `0x460f9`
- Rebena Te Ra Skeleton Mage @ `0x46189`
- Skeleton (Sword?) in Lich boss fight @ `0x461d1`
- Skeleton (Mace) in Lich boss fight @ `0x4621a`
- Skeleton (Sword?) in Lich boss fight @ `0x462ac`
- Skeleton (Spear?) in Lich boss fight @ `0x462f5`
- Gargoyle @ `0x4645f`
- Gargoyle @ `0x464ed`
- Gargoyle @ `0x46534`
- Skeleton (Sword?) in Lich boss fight @ `0x465c3`
- Cerberus @ `0x46652`
- Wraith @ `0x466e2`
- Skeleton (Sword?) in Lich boss fight @ `0x46803`
- Skeleton (Mace) in Lich boss fight @ `0x4684c`
- Skeleton (Sword?) in Lich boss fight @ `0x46895`
- Skeleton (Spear?) in Lich boss fight @ `0x46927`
- Skeleton (Sword?) in Lich boss fight @ `0x46970`
- Rebena Te Ra Skeleton Mage @ `0x469b9`
- Rebena Te Ra Skeleton Mage @ `0x46a00`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Cerberus @ `0x45f00`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Skeleton (Sword?) in Lich boss fight @ `0x46263`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Rebena Te Ra Skeleton Mage @ `0x4633e`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Wraith @ `0x4669a`
- Wraith @ `0x4672a`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Wraith @ `0x45e27`
- Wraith @ `0x464a6`

### Index 12

**Items:** Rune Staff / Silver Bracer / Winged Cap / Rune Bell / Mage Masher / Cat's Bell / Gold Hairpin / Mage's Staff

**Chests:**
- `0x4717e`

### Index 13

**Items:** Silver Spectacles / Silver Spectacles / Elven Mantle / Elven Mantle / Teddy Bear / Teddy Bear / Chicken Knife / Chicken Knife

**Chests:**
- `0x4720a`

### Index 14

**Items:** Star Pendant / Star Pendant / Gobbie Pocket / Gobbie Pocket / Star Pendant / Gobbie Pocket / Star Pendant / Gobbie Pocket

**Chests:**
- `0x4714f`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Wraith @ `0x45f90`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Rebena Te Ra Skeleton Mage @ `0x45fd8`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Gargoyle @ `0x46069`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Gargoyle @ `0x45d0a`

### Index 27

**Items:** (empty) / (empty) / Gear / Gear / (empty) / (empty) / Gear / Gear

**Monsters:**
- Skeleton (Sword?) in Lich boss fight @ `0x45d99`
- Skeleton (Mace) in Lich boss fight @ `0x45de0`
- Skeleton (Sword?) in Lich boss fight @ `0x468de`
- Gargoyle @ `0x46ad7`
- Gargoyle @ `0x46b1f`

### Index 29

**Items:** (empty) / Holy Water / Holy Water / Heavenly Dust / Diamond Ore / Diamond Ore / Holy Water / Heavenly Dust

**Monsters:**
- Wraith @ `0x46141`
- Wraith @ `0x4660a`
- Rebena Te Ra Skeleton Mage @ `0x46772`
- Rebena Te Ra Skeleton Mage @ `0x467ba`
- Wraith @ `0x46b67`
- Wraith @ `0x46bae`

### Index 30

**Items:** (empty) / (empty) / Cerberus Fang / Cerberus Fang / Mythril / Mythril / Mythril / Cerberus Fang

**Monsters:**
- Cerberus @ `0x46386`
- Cerberus @ `0x463cf`
- Cerberus @ `0x46417`

### Index 31

**Items:** Copper Sword (!) / Iron Sword (!) / Tome of Magic / Tome of Magic / Tome of Magic / Tome of Sorcery / Tome of Sorcery / Tome of Sorcery

**Chests:**
- `0x471db`

### Index 32

**Items:** Copper Sword (!) / Blue Yarn / Blue Yarn / White Yarn / Blue Yarn / White Yarn / Ancient Potion / Ancient Potion

**Chests:**
- `0x47121`
- `0x471ad`

### Index 33

**Items:** Copper Sword (!) / Holy Shield / Holy Shield / Pure Belt / Holy Armor / Pure Armor / Diamond Armor / Diamond Armor

**Chests:**
- `0x46d83`
- `0x46e5c`
- `0x46f34`
- `0x4700c`

### Index 34

**Items:** Copper Sword (!) / Eternal Sallet / Eternal Sallet / Gold Gloves / Pure Armor / Holy Armor / Diamond Armor / Diamond Armor

**Chests:**
- `0x47239`

## Mount Kilanda - Area 1 (`lava_0`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Lava Mu @ `0x44544`
- Lava Mu @ `0x445d5`
- Lamia @ `0x446fa`
- Lava Mu @ `0x447d5`
- Lamia @ `0x448f9`
- Lava Mu @ `0x449d5`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Lava Ahriman @ `0x44668`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Lava Mu @ `0x4481e`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Blazer Beetle @ `0x44867`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Lava Mu @ `0x4458d`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Blazer Beetle @ `0x4498c`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Blazer Beetle @ `0x44743`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Lava Ahriman @ `0x444fa`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Lamia @ `0x446b1`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Chests:**
- `0x44abf`

### Index 26

**Items:** (empty) / Magma Rock / Magma Rock / Faerie's Tear / (empty) / Magma Rock / Magma Rock / Faerie's Tear

**Monsters:**
- Lava Ahriman @ `0x4461f`
- Lava Ahriman @ `0x44942`
- Lava Ahriman @ `0x44a1f`

### Index 27

**Items:** (empty) / (empty) / Hard Shell / Hard Shell / (empty) / (empty) / Hard Shell / Hard Shell

**Monsters:**
- Blazer Beetle @ `0x4478c`
- Blazer Beetle @ `0x448b0`

### Index 31

**Items:** (empty) / Flame Craft / Flame Craft / Flame Craft / Zeal Kit / Flame Armor / Flame Armor / Healing Kit

**Chests:**
- `0x44aee`
- `0x44b1e`

### Index 32

**Items:** Flame Sallet / Flame Shield / Flame Gloves / Flame Belt / Flame Sallet / Flame Shield / Flame Gloves / Flame Belt

**Chests:**
- `0x44b4d`

### Index 33

**Items:** Warrior's Weapon / Warrior's Weapon / Master's Weapon / Master's Weapon / Master's Weapon / Mighty Weapon / Valiant Weapon / Victorious Weapon

**Chests:**
- `0x44b7d`

### Index 34

**Items:** Iron / Iron / Iron / Mythril / Mythril / Alloy / Mythril / Diamond Ore

**Chests:**
- `0x44bad`

## Mount Kilanda - Area 2 (`lava_1`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Coeurl @ `0x40f03`
- Kilanda Ogre @ `0x410b8`
- Coeurl @ `0x411db`
- Kilanda Ogre @ `0x41225`
- Coeurl @ `0x41471`
- Coeurl @ `0x414ba`
- Coeurl @ `0x4154d`
- Coeurl @ `0x41629`
- Coeurl @ `0x416b9`
- Kilanda Ogre @ `0x41701`
- Kilanda Ogre @ `0x417db`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Kilanda Ogre @ `0x40eba`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Coeurl @ `0x40f4c`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Lava Ahriman @ `0x40fdf`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Coeurl @ `0x41394`
- Coeurl @ `0x41427`
- Lava Ahriman @ `0x415e0`
- Coeurl @ `0x41824`

### Index 11

**Items:** Power Wristband / Flametongue / Engetsurin / Giant's Glove / Twisted Headband / Heavy Armband / Masquerade / Onion Sword

**Monsters:**
- Lava Ahriman @ `0x41070`

### Index 12

**Items:** Cat's Bell / Faerie Ring / Sage's Staff / Noah's Lute / Red Slippers / Kris / Wonder Wand / Gold Hairpin

**Monsters:**
- Kilanda Ogre @ `0x4134a`

### Index 13

**Items:** Buckler / Buckler / Black Hood / Black Hood / Chicken Knife / Chicken Knife / Teddy Bear / Teddy Bear

**Monsters:**
- Kilanda Ogre @ `0x40f96`

### Index 14

**Items:** Ring of Fire / Ring of Fire / Moon Pendant / Moon Pendant / Ring of Fire / Moon Pendant / Star Pendant / Ring of Fire

**Monsters:**
- Kilanda Ogre @ `0x4114a`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Lava Ahriman @ `0x41671`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Coeurl @ `0x41503`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Coeurl @ `0x413de`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Kilanda Ogre @ `0x41301`

### Index 26

**Items:** (empty) / Magma Rock / Magma Rock / Faerie's Tear / (empty) / Magma Rock / Magma Rock / Angel's Tear

**Monsters:**
- Lava Ahriman @ `0x41192`
- Lava Ahriman @ `0x412b8`
- Lava Ahriman @ `0x4186d`

### Index 27

**Items:** (empty) / (empty) / Ogre Fang / Ogre Fang / (empty) / Ogre Fang / Ogre Fang / Diamond Armor

**Monsters:**
- Kilanda Ogre @ `0x41027`
- Kilanda Ogre @ `0x41597`
- Kilanda Ogre @ `0x41749`

### Index 28

**Items:** (empty) / (empty) / Coeurl Whisker / Coeurl Whisker / (empty) / Coeurl Whisker / Coeurl Whisker / Ancient Potion

**Monsters:**
- Coeurl @ `0x41101`
- Coeurl @ `0x4126e`
- Coeurl @ `0x41792`

### Index 29

**Items:** (empty) / (empty) / Kilanda Sulfur / Kilanda Sulfur / Kilanda Sulfur / Kilanda Sulfur / Kilanda Sulfur / Kilanda Sulfur

**Chests:**
- `0x41916`

### Index 30

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Legendary Weapon / Legendary Weapon

**Chests:**
- `0x418b5`
- `0x418e6`

## Lynari Desert - Area 1 (`desert_0`)

### Index 0

**Items:** NOT FOUND IN SWITCH

**Monsters:**
- Scorpion in Antlion boss fight @ `0x480ea`
- Scorpion in Antlion boss fight @ `0x48133`

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Lamia @ `0x481c6`
- Scorpion @ `0x4820f`
- Scorpion @ `0x482a1`
- Lamia @ `0x482ea`
- Lamia @ `0x4837d`
- Lamia @ `0x48412`
- Electric Scorpion @ `0x484a5`
- Rock Scorpion @ `0x484ee`
- Electric Scorpion @ `0x485cb`
- Scorpion @ `0x4865e`
- Rock Scorpion @ `0x486a7`
- Cactuar @ `0x4873a`
- Rock Scorpion @ `0x487cb`
- Cactuar @ `0x488eb`
- Scorpion @ `0x489c9`
- Electric Scorpion @ `0x48a13`
- Scorpion @ `0x48b3b`
- Rock Scorpion @ `0x48b84`
- Scorpion @ `0x48c15`
- Rock Scorpion @ `0x48c5e`
- Lamia @ `0x48cef`
- Scorpion @ `0x48dcf`
- Scorpion @ `0x48e62`
- Scorpion @ `0x48ef4`
- Rock Scorpion @ `0x48f3d`
- Scorpion @ `0x48f86`
- Electric Scorpion @ `0x48fcf`
- Scorpion @ `0x49018`
- Scorpion @ `0x490aa`
- Electric Scorpion @ `0x490f3`
- Scorpion @ `0x4913c`
- Scorpion @ `0x491ce`
- Scorpion @ `0x49262`
- Lamia @ `0x492f6`

### Index 2

**Items:** Copper Sword (!) / Iron Sword (!) / Steel Blade (!) / Feather Saber (!) / Bastard Sword (!) / Defender (!) / Rune Blade (!) / Fruit Seed

**Chests:**
- `0x49860`
- `0x49891`
- `0x498c1`

**Monsters:**
- Zu @ `0x493d4`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Scorpion @ `0x48783`
- Scorpion @ `0x488a3`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Lamia @ `0x48813`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Cactuar @ `0x4885b`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Lamia @ `0x48ca7`
- Lamia @ `0x48d85`
- Lamia @ `0x48e19`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Scorpion @ `0x48935`
- Electric Scorpion @ `0x4897f`
- Scorpion @ `0x48aa7`
- Electric Scorpion @ `0x48af1`
- Zu @ `0x49185`

### Index 14

**Items:** Star Pendant / Gobbie Pocket / Star Pendant / Gobbie Pocket / Star Pendant / Gobbie Pocket / Star Pendant / Gobbie Pocket

**Chests:**
- `0x497d1`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Lamia @ `0x48334`
- Scorpion @ `0x48537`
- Rock Scorpion @ `0x48581`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Lamia @ `0x483c7`
- Cactuar @ `0x48a5d`
- Scorpion @ `0x4961e`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Scorpion @ `0x4845c`
- Cactuar @ `0x486f0`
- Lamia @ `0x48d3a`
- Scorpion @ `0x49667`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Lamia @ `0x48258`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Scorpion @ `0x4817d`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Zu @ `0x4938a`

### Index 26

**Items:** (empty) / (empty) / Zu's Beak / Zu's Beak / (empty) / Zu's Beak / Zu's Beak / Orichalcum

**Monsters:**
- Zu @ `0x49340`
- Zu @ `0x4941c`
- Zu @ `0x49467`
- Zu @ `0x494b0`
- Zu @ `0x494f8`
- Zu @ `0x49541`
- Zu @ `0x4958b`
- Zu @ `0x495d4`

### Index 27

**Items:** (empty) / (empty) / Needle / Needle / (empty) / (empty) / Needle / Needle

**Monsters:**
- Cactuar @ `0x48615`
- Cactuar @ `0x48bcd`

### Index 28

**Items:** (empty) / (empty) / Thunderball / Thunderball / (empty) / (empty) / Thunderball / Thunderball

**Monsters:**
- Electric Scorpion @ `0x48eab`
- Electric Scorpion @ `0x49218`

### Index 29

**Items:** (empty) / Alloy / Alloy / Alloy / (empty) / Alloy / Alloy / Diamond Ore

**Monsters:**
- Rock Scorpion @ `0x49061`
- Rock Scorpion @ `0x492ac`

### Index 31

**Items:** Valiant Weapon / Mighty Weapon / Victorious Weapon / Master's Weapon / Valiant Weapon / Mighty Weapon / Victorious Weapon / Legendary Weapon

**Chests:**
- `0x4976f`

### Index 32

**Items:** Flame Craft / Frost Craft / Lightning Craft / Flame Craft / Flame Craft / Frost Craft / Lightning Craft / Mythril Armor

**Chests:**
- `0x49801`

### Index 33

**Items:** Mythril Armor / Mythril Armor / Mythril Armor / Eternal Armor / Pure Armor / Gold Armor / Diamond Armor / Diamond Armor

**Chests:**
- `0x4979f`

### Index 34

**Items:** Clockwork / New Clockwork / Gold Craft / Clockwork / Clockwork / New Clockwork / Gold Craft / (empty)

**Chests:**
- `0x49831`

## Lynari Desert - Area 2 (`desert_1`)

### Index 1

**Items:** Excalibur (!) / Treasured Sword (!) / Marr Sword (!) / Ultima Sword (!) / Sonic Hammer (!) / Equipment 126 (Unused) (!) / Iron Gauntlets (!) / Dark Matter (!)

**Monsters:**
- Lamia @ `0x40bdd`
- Lamia @ `0x40c71`
- Lamia @ `0x40cbb`
- Chimera @ `0x40e74`
- Chimera @ `0x40ebd`
- Lamia @ `0x4102d`
- Sand Sahagin @ `0x410c0`
- Sand Sahagin @ `0x4122d`
- Sand Sahagin @ `0x41276`
- Lamia @ `0x412bf`
- Lamia @ `0x41351`

### Index 6

**Items:** Fish / Meat / Fish / Meat / Fish / Meat / Fish / Meat

**Monsters:**
- Sand Sahagin @ `0x40e2a`
- Lamia @ `0x4139a`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster / Rainbow Grapes / Striped Apple / Cherry Cluster

**Monsters:**
- Sand Sahagin @ `0x40f07`
- Lamia @ `0x4142c`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato / Round Corn / Star Carrot / Gourd Potato

**Monsters:**
- Sand Sahagin @ `0x40f51`
- Lamia @ `0x41476`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / Spring Water / Milk / Strange Liquid / Spring Water / Milk

**Monsters:**
- Cactuar @ `0x41152`
- Cactuar @ `0x411e4`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down

**Monsters:**
- Cactuar @ `0x41077`

### Index 11

**Items:** Ashura / Fang Charm / Double Axe / Loaded Dice / Ogrekiller / Ice Brand / Giant's Glove / Masquerade

**Chests:**
- `0x41540`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Cactuar @ `0x4119b`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Lamia @ `0x413e3`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Sand Sahagin @ `0x40d05`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Sand Sahagin @ `0x40b4a`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Sand Sahagin @ `0x40b94`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Lamia @ `0x40d4e`

### Index 26

**Items:** (empty) / (empty) / Chimera's Horn / Chimera's Horn / (empty) / Chimera's Horn / Chimera's Horn / Legendary Weapon

**Monsters:**
- Chimera @ `0x40c27`
- Chimera @ `0x40f9a`
- Chimera @ `0x41109`
- Chimera @ `0x41308`

### Index 27

**Items:** (empty) / (empty) / Needle / Needle / (empty) / (empty) / Needle / Needle

**Monsters:**
- Cactuar @ `0x40d97`
- Cactuar @ `0x40de0`
- Cactuar @ `0x40fe3`

### Index 31

**Items:** Copper Sword (!) / Iron Sword (!) / Goggle Techniques / Goggle Techniques / Goggle Techniques / Goggle Techniques / Designer Goggles / Designer Goggles

**Chests:**
- `0x41571`

## Mount Vellenge - Area 1 (`meteo_0`)

### Index 0

**Items:** NOT FOUND IN SWITCH

**Monsters:**
- Shade (Spear) @ `0x4484e`
- Shade (Mace) @ `0x448e1`
- Shade (Spear) @ `0x44973`
- Shade (Spear) @ `0x44a07`
- Shade (Sword) @ `0x44a51`
- Sphere @ `0x44bc3`
- Chimera @ `0x44c56`
- Shade (Sword) @ `0x44c9f`
- Shade (Sword) @ `0x44d33`
- Sphere @ `0x44d7d`
- Shade (Mace) @ `0x44e5a`
- Death Knight @ `0x44eec`
- Sphere @ `0x44f35`
- Death Knight @ `0x44fc7`
- Sphere @ `0x450a3`
- Sphere @ `0x450ec`
- Shade (Sword) @ `0x451c7`
- Sphere @ `0x45210`
- Shade (Spear) @ `0x45259`
- Chimera @ `0x45331`
- Shade (Sword) @ `0x45379`
- Chimera @ `0x4540a`
- Shade (Sword) @ `0x45453`
- Shade (Sword) @ `0x4549c`
- Chimera @ `0x4552c`
- Shade (Spear) @ `0x45604`
- Shade (Spear) @ `0x45695`
- Chimera @ `0x45728`
- Sphere @ `0x4584c`

### Index 6

**Items:** Fish / Meat / Fish / Meat / (empty) / (empty) / (empty) / Striped Apple

**Monsters:**
- Shade (Spear) @ `0x44c0d`

### Index 7

**Items:** Striped Apple / Cherry Cluster / Rainbow Grapes / (empty) / (empty) / (empty) / (empty) / Star Carrot

**Monsters:**
- Chimera @ `0x449bd`
- Shade (Spear) @ `0x44dc7`

### Index 8

**Items:** Star Carrot / Gourd Potato / Round Corn / (empty) / (empty) / (empty) / (empty) / Spring Water

**Monsters:**
- Shade (Sword) @ `0x44b79`
- Chimera @ `0x452a1`

### Index 9

**Items:** Spring Water / Milk / Strange Liquid / (empty) / (empty) / (empty) / (empty) / Phoenix Down

**Monsters:**
- Shade (Mace) @ `0x455bc`
- Shade (Sword) @ `0x45803`

### Index 10

**Items:** Phoenix Down / Phoenix Down / Phoenix Down / Phoenix Down / (empty) / (empty) / (empty) / Flametongue

**Monsters:**
- Sphere @ `0x44a9b`
- Shade (Sword) @ `0x45010`
- Shade (Sword) @ `0x4505a`
- Shade (Sword) @ `0x45135`
- Shade (Sword) @ `0x454e4`
- Sphere @ `0x45574`
- Shade (Sword) @ `0x456df`
- Shade (Sword) @ `0x457ba`

### Index 11

**Items:** Flametongue / Ice Brand / Sasuke's Blade / Mjollnir / (empty) / (empty) / (empty) / Kris

**Chests:**
- `0x458dd`
- `0x459fd`

### Index 12

**Items:** Kris / Sage's Staff / Mage's Staff / Dark Matter / (empty) / (empty) / (empty) / Elven Mantle

**Chests:**
- `0x4596c`
- `0x459cd`

### Index 13

**Items:** Elven Mantle / Elven Mantle / Wonder Bangle / Wonder Bangle / (empty) / (empty) / (empty) / Masamune

**Chests:**
- `0x4590c`
- `0x45a2c`

### Index 14

**Items:** Masamune / Aegis / Ribbon / (empty) / (empty) / (empty) / (empty) / Stone of Fire

**Chests:**
- `0x4593c`
- `0x4599c`

### Index 15

**Items:** Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire / Stone of Fire

**Monsters:**
- Death Knight @ `0x44ae5`

### Index 16

**Items:** Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard / Stone of Blizzard

**Monsters:**
- Death Knight @ `0x4517e`

### Index 17

**Items:** Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder / Stone of Thunder

**Monsters:**
- Chimera @ `0x44e10`
- Sphere @ `0x44ea3`

### Index 18

**Items:** Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure / Stone of Cure

**Monsters:**
- Shade (Sword) @ `0x447ba`
- Shade (Sword) @ `0x44898`

### Index 19

**Items:** Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life / Stone of Life

**Monsters:**
- Chimera @ `0x44804`
- Chimera @ `0x4492a`

### Index 20

**Items:** Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear / Stone of Clear

**Monsters:**
- Shade (Spear) @ `0x44b2f`
- Sphere @ `0x44f7e`

### Index 21

**Items:** Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure / Stone of Fire / Stone of Blizzard / Stone of Thunder / Stone of Cure

**Monsters:**
- Death Knight @ `0x44ce9`
- Death Knight @ `0x452e9`
- Death Knight @ `0x453c1`
- Death Knight @ `0x4564c`
- Death Knight @ `0x45771`
- Death Knight @ `0x45895`

## Mount Vellenge - Area 2 (`meteo_1`)

### Index 0

**Items:** NOT FOUND IN SWITCH

**Monsters:**
- Shade (Mace) @ `0x40d1a`
- Shade (Spear) @ `0x40d65`
- Tentacle (Fire) @ `0x40db0`
- Tonberry @ `0x40dfb`
- Tonberry @ `0x40e45`
- Shade (Sword) @ `0x40e8f`
- Tentacle (Lightning) @ `0x40ed9`
- Shade (Spear) @ `0x40f23`
- Tonberry @ `0x40f6d`
- Shade (Spear) @ `0x40fb7`
- Shade (Sword) @ `0x41000`
- Shade (Spear) @ `0x41049`
- Tentacle (Ice) @ `0x41092`
- Shade (Sword) @ `0x410dc`
- Tentacle (Dark) @ `0x41126`
- Tonberry @ `0x41170`
- Shade (Mace) @ `0x411ba`
- Shade (Spear) @ `0x41203`
- Tonberry @ `0x4124c`
- Shade (Sword) @ `0x41295`
- Shade (Mace) @ `0x412de`
- Tonberry @ `0x41327`
- Shade (Spear) @ `0x41371`
- Shade (Sword) @ `0x413bb`
- Tonberry @ `0x41404`
- Shade (Spear) @ `0x4144d`
- Shade (Mace) @ `0x41497`
- Tentacle (Ice) @ `0x414e1`
- Shade (Mace) @ `0x4152b`
- Tonberry @ `0x41575`
- Shade (Spear) @ `0x415bf`
- Shade (Spear) @ `0x41609`
- Shade (Spear) @ `0x41653`
- Tentacle (Dark) @ `0x4169d`
- Shade (Mace) @ `0x416e7`
- Tonberry @ `0x4172f`
- Shade (Sword) @ `0x41778`
- Shade (Sword) @ `0x417c1`
- Shade (Spear) @ `0x4180a`
- Tentacle (Fire) @ `0x41853`
- Tentacle (Lightning) @ `0x4189c`
- Shade (Spear) @ `0x418e5`
- Tonberry @ `0x4192e`

### Index 11

**Items:** Flametongue / Ice Brand / Sasuke's Blade / Mjollnir / (empty) / (empty) / (empty) / Kris

**Chests:**
- `0x41977`
- `0x41a38`

### Index 12

**Items:** Kris / Sage's Staff / Mage's Staff / Dark Matter / (empty) / (empty) / (empty) / Elven Mantle

**Chests:**
- `0x419a8`
- `0x41a08`

### Index 13

**Items:** Elven Mantle / Elven Mantle / Wonder Bangle / Wonder Bangle / (empty) / (empty) / (empty) / Stone of Fire

**Chests:**
- `0x419d8`
- `0x41a69`

**Monsters:**
- Thunder Bomb @ `0x4081f`
- Thunder Bomb @ `0x408af`
