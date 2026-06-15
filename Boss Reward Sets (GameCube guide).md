# FFCC Boss / End-of-Dungeon "Dropped Item Sets" (GameCube)

Reference transcription from the **Nintendo Power GameCube guide** (matches the
GameCube ISO, unlike Remaster sources). Each dungeon boss offers **8 artifact
sets**; which set you get is gated by **cycle** + your **bonus points**, with
thresholds that scale by **player count (1P–4P)**.

This is the **end-of-dungeon reward** subsystem — **separate from chest /
enemy-drop loot** (`get_treasure`) and **NOT touched by the randomizer**.
Reference documentation only.

## Fixed structure (same for every dungeon)

Each dungeon defines three point **tiers** — **A**, **B**, **C** — each a set of
four "more than X pts" thresholds (one per player count, 1P/2P/3P/4P). The set ↔
cycle/tier mapping is constant:

| Set | Cycle 1 | Cycle 2 | Cycle 3 |
|-----|---------|---------|---------|
| 1 | >0 | — | — |
| 2 | tier A | — | — |
| 3 | tier B | >0 | — |
| 4 | tier C | tier A | — |
| 5 | — | tier B | >0 |
| 6 | — | tier C | tier A |
| 7 | — | — | tier B |
| 8 | — | — | tier C |

So per dungeon I only record the **artifacts** in each set plus its **A/B/C
tier numbers**.

> Point thresholds transcribed from 300-DPI scans by eye (small numbers may
> carry OCR errors). **Artifact lists cross-checked and corrected against a
> community GameCube set list** (Google Sheet `1cnjy2_sD534IWIzjk6wvxvc7uQfkH4uJ5kV8cA2uNgg`),
> so the items are reliable.

---

## River Belle Path — Giant Crab  (guide p30)

Tiers (1P/2P/3P/4P): **A** = 95/102/116/127 · **B** = 119/128/146/160 · **C** = 149/160/182/200

| Set | Artifacts |
|-----|-----------|
| 1 | Buckler, Dragon's Whisker, Moogle Pocket, Shuriken |
| 2 | Mage Masher, Maneater, Moogle Pocket, Silver Spectacles |
| 3 | Buckler, Double Axe, Iron, Kris |
| 4 | Ice Brand, Iron, Silver Bracer, Silver Spectacles |
| 5 | Loaded Dice, Mage's Staff, Mythril, Wonder Bangle |
| 6 | Black Hood, Flametongue, Legendary Weapon, Sasuke's Blade |
| 7 | Dragon's Whisker, Orichalcum, Shuriken, Silver Spectacles |
| 8 | Ancient Sword, Mage Masher, Maneater, Save the Queen |

---

## Goblin Wall — Goblin King

Tiers (1P/2P/3P/4P): **A** = 110/119/135/148 · **B** = 138/148/169/185 · **C** = 172/186/211/232

| Set | Artifacts |
|-----|-----------|
| 1 | Double Axe, Earth Pendant, Sparkling Bracer, Winged Cap |
| 2 | Earth Pendant, Kaiser Knuckles, Sparkling Bracer, Wonder Wand |
| 3 | Ashura, Faerie Ring, Helm of Arai, Moogle Pocket |
| 4 | Dark Matter, Fang Charm, Moogle Pocket, Sparkling Bracer |
| 5 | Ancient Potion, Helm of Arai, Mjollnir, Red Slippers |
| 6 | Engetsurin, Helm of Arai, Noah's Lute, Orichalcum |
| 7 | Candy Ring, Diamond Belt, Fang Charm, Wonder Bangle |
| 8 | Cursed Crook, Galatyn, Green Beret, Sparkling Bracer |

---

## The Mushroom Forest — Malboro

Tiers (1P/2P/3P/4P): **A** = 108/116/132/145 · **B** = 135/145/165/181 · **C** = 169/182/207/227

| Set | Artifacts |
|-----|-----------|
| 1 | Shuriken, Dragon's Whisker, Buckler, Earth Pendant |
| 2 | Flametongue, Mage Masher, Silver Spectacles, Moogle Pocket |
| 3 | Maneater, Sage's Staff, Buckler, Earth Pendant |
| 4 | Double Axe, Silver Bracer, Black Hood, Moogle Pocket |
| 5 | Sasuke's Blade, Cat's Bell, Wonder Bangle, Ancient Potion |
| 6 | Green Beret, Mage's Staff, Wonder Bangle, Orichalcum |
| 7 | Double Axe, Silver Bracer, Moogle Pocket, Diamond Armor |
| 8 | Ashura, Cat's Bell, Earth Pendant, Malboro Seed |

---

## The Mine of Cathuriges — Orc King

Tiers (1P/2P/3P/4P): **A** = 118/125/142/156 · **B** = 148/158/178/195 · **C** = 185/198/222/244

| Set | Artifacts |
|-----|-----------|
| 1 | Shuriken, Dragon's Whisker, Buckler, Earth Pendant |
| 2 | Loaded Dice, Mage Masher, Silver Spectacles, Moogle Pocket |
| 3 | Maneater, Rune Bell, Buckler, Earth Pendant |
| 4 | Double Axe, Silver Bracer, Black Hood, Moogle Pocket |
| 5 | Sasuke's Blade, Cat's Bell, Wonder Bangle, Legendary Weapon |
| 6 | Green Beret, Mage's Staff, Wonder Bangle, Orichalcum |
| 7 | Kaiser Knuckles, Faerie Ring, Ultimate Pocket, Orc Belt |
| 8 | Onion Sword, Winged Cap, Earth Pendant, Murasame |

---

## Moschet Manor — Gigas Lord

Tiers (1P/2P/3P/4P): **A** = 84/91/103/113 · **B** = 105/113/129/141 · **C** = 132/142/161/177

| Set | Artifacts |
|-----|-----------|
| 1 | Flametongue, Rune Staff, Buckler, Chocobo Pocket |
| 2 | Green Beret, Red Slippers, Silver Spectacles, Earth Pendant |
| 3 | Fang Charm, Book of Light, Black Hood, Moon Pendant |
| 4 | Kaiser Knuckles, Faerie Ring, Helm of Arai, Chocobo Pocket |
| 5 | Ice Brand, Sage's Staff, Chocobo Pocket, Moon Pendant |
| 6 | Masquerade, Mage's Staff, Wonder Bangle, Orichalcum |
| 7 | Power Wristband, Chocobo Pocket, Legendary Weapon, Lord's Robe |
| 8 | Gekkabijin, Candy Ring, Chocobo Pocket, Legendary Shield |

---

## Mount Kilanda — Iron Giant  (guide p85)

Tiers (1P/2P/3P/4P): **A** = 102/110/125/137 · **B** = 127/137/156/171 · **C** = 159/172/195/214

| Set | Artifacts |
|-----|-----------|
| 1 | Engetsurin, Book of Light, Drill, Moon Pendant |
| 2 | Power Wristband, Kris, Drill, Star Pendant |
| 3 | Green Beret, Silver Bracer, Main Gauche, Ring of Fire |
| 4 | Fang Charm, Cat's Bell, Drill, Ring of Fire |
| 5 | Mjollnir, Red Slippers, Chicken Knife, Star Pendant |
| 6 | Flametongue, Mage's Staff, Ring of Fire, Orichalcum |
| 7 | Twisted Headband, Wonder Wand, Legendary Weapon, Red Eye |
| 8 | Masamune, Rune Bell, Main Gauche, Celestial Weapon |

---

## Veo Lu Sluice — Golem

Tiers (1P/2P/3P/4P): **A** = 108/116/132/145 · **B** = 135/145/165/181 · **C** = 169/182/207/227  *(B/C OCR-inferred)*

| Set | Artifacts |
|-----|-----------|
| 1 | Ice Brand, Silver Bracer, Buckler, Ring of Blizzard |
| 2 | Green Beret, Sage's Staff, Silver Spectacles, Moon Pendant |
| 3 | Fang Charm, Cat's Bell, Elven Mantle, Moon Pendant |
| 4 | Shuriken, Faerie Ring, Sparkling Bracer, Ring of Blizzard |
| 5 | Heavy Armband, Wonder Wand, Rat's Tail, Moon Pendant |
| 6 | Loaded Dice, Noah's Lute, Ring of Blizzard, Orichalcum |
| 7 | Green Beret, Winged Cap, Diamond Helm, Green Sphere |
| 8 | Fang Charm, Candy Ring, Taotie Motif, Diamond Armor |

---

## Daemon's Court — Lizardman King

Tiers (1P/2P/3P/4P): **A** = 103/111/126/138 · **B** = 128/138/157/172 · **C** = 160/172/197/216

| Set | Artifacts |
|-----|-----------|
| 1 | Loaded Dice, Winged Cap, Buckler, Chocobo Pocket |
| 2 | Shuriken, Wonder Wand, Silver Spectacles, Moon Pendant |
| 3 | Maneater, Candy Ring, Rat's Tail, Chocobo Pocket |
| 4 | Double Axe, Dragon's Whisker, Sparkling Bracer, Moon Pendant |
| 5 | Giant's Glove, Rune Bell, Wonder Bangle, Moon Pendant |
| 6 | Ogrekiller, Dark Matter, Chocobo Pocket, Orichalcum |
| 7 | Flametongue, Kris, Diamond Gloves, King's Scale |
| 8 | Ice Brand, Red Slippers, Aegis, Diamond Shield |

---

## Selepation Cave — Cave Worm

Tiers (1P/2P/3P/4P): **A** ≈ 170/179/199/218 · **B** ≈ 197/212/241/265 · **C** ≈ 248/266/303/332  *(thresholds OCR-approx)*

| Set | Artifacts |
|-----|-----------|
| 1 | Ogrekiller, Dragon's Whisker, Buckler, Chocobo Pocket |
| 2 | Ashura, Rune Bell, Silver Spectacles, Ring of Thunder |
| 3 | Kaiser Knuckles, Mage Masher, Sparkling Bracer, Moon Pendant |
| 4 | Power Wristband, Rune Staff, Teddy Bear, Ring of Thunder |
| 5 | Sasuke's Blade, Kris, Black Hood, Diamond Armor |
| 6 | Twisted Headband, Gold Hairpin, Moon Pendant, Orichalcum |
| 7 | Loaded Dice, Sage's Staff, Ring of Thunder, Wind Crystal |
| 8 | Ogrekiller, Wonder Wand, Earth Armor, Ring of Protection |

---

## Conall Curach — Dragon Zombie

Tiers (1P/2P/3P/4P): **A** ≈ 183/198/237/260 · **B** ≈ 249/268/303/324 · **C** ≈ 301/325/369/406  *(thresholds OCR-approx)*

| Set | Artifacts |
|-----|-----------|
| 1 | Giant's Glove, Gobbie Pocket, Rat's Tail, Sage's Staff |
| 2 | Flametongue, Gold Hairpin, Ring of Cure, Teddy Bear |
| 3 | Ice Brand, Star Pendant, Wonder Wand, Wonder Bangle |
| 4 | Loaded Dice, Rat's Tail, Ring of Cure, Rune Bell |
| 5 | Gold Hairpin, Ogrekiller, Star Pendant, Teddy Bear |
| 6 | Kris, Orichalcum, Ring of Cure, Sasuke's Blade |
| 7 | Dragon's Fang, Lunar Weapon, Red Slippers, Twisted Headband |
| 8 | Diamond Armor, Engetsurin, Ring of Life, Tome of Ultima |

---

## Rebena Te Ra — Lich

Tiers (1P/2P/3P/4P): **A** = 149/160/181/200 · **B** = 186/200/228/250 · **C** = 232/250/284/312

| Set | Artifacts |
|-----|-----------|
| 1 | Main Gauche, Mjollnir, Sage's Staff, Star Pendant |
| 2 | Black Hood, Flametongue, Gobbie Pocket, Mage's Staff |
| 3 | Chicken Knife, Ice Brand, Star Pendant, Wonder Wand |
| 4 | Gobbie Pocket, Helm of Arai, Loaded Dice, Rune Bell |
| 5 | Elven Mantle, Kris, Masquerade, Star Pendant |
| 6 | Gobbie Pocket, Noah's Lute, Ogrekiller, Orichalcum |
| 7 | Dark Weapon, Engetsurin, Ethereal Orb, Red Slippers |
| 8 | Drill, Forbidden Tome, Ribbon, Twisted Headband |

---

## Lynari Desert — Antlion

Tiers (1P/2P/3P/4P): **A** = 144/156/177/194 · **B** = 180/195/221/243 · **C** = 226/244/277/304

| Set | Artifacts |
|-----|-----------|
| 1 | Main Gauche, Masquerade, Star Pendant, Sage's Staff |
| 2 | Black Hood, Flametongue, Gobbie Pocket, Noah's Lute |
| 3 | Chicken Knife, Gobbie Pocket, Ice Brand, Wonder Wand |
| 4 | Heavy Armband, Helm of Arai, Rune Bell, Star Pendant |
| 5 | Dark Matter, Elven Mantle, Hero's Weapon, Loaded Dice |
| 6 | Kris, Ogrekiller, Orichalcum, Wonder Bangle |
| 7 | Desert Fang, Engetsurin, Gobbie Pocket, Red Slippers |
| 8 | Diamond Armor, Sun Pendant, Tome of Ultima, Twisted Headband |

---

## Mount Vellenge — final dungeon (NO cycles)

The game's last dungeon has **no 8-set / cycle table** — it has a single set of
artifacts found in its chests (you can't remove them; they only help in the
final fight). Artifacts available:

Aegis, Dark Matter, Elven Mantle, Flametongue, Ice Brand, Kris, Mage's Staff,
Masamune, Mjollnir, Ribbon, Sage's Staff, Sasuke's Blade, Wonder Bangle.

---

## Tida — Wild Abaddon

Tiers (1P/2P/3P/4P): **A** = 155/167/190/208 · **B** = 193/206/237/260 · **C** = 241/260/295/325

| Set | Artifacts |
|-----|-----------|
| 1 | Twisted Headband, Dragon's Whisker, Silver Spectacles, Chocobo Pocket |
| 2 | Shuriken, Kris, Sparkling Bracer, Moogle Pocket |
| 3 | Maneater, Silver Bracer, Elven Mantle, Chocobo Pocket |
| 4 | Power Wristband, Cat's Bell, Sparkling Bracer, Sasuke's Blade |
| 5 | Giant's Glove, Flametongue, Wonder Bangle, Ancient Potion |
| 6 | Rune Bell, Gold Hairpin, Wonder Bangle, Orichalcum |
| 7 | Power Wristband, Silver Bracer, Chocobo Pocket, Legendary Weapon |
| 8 | Green Beret, Cat's Bell, Brigandology, Dweomer Spore |

---

## Coverage

All **13 boss dungeons** are transcribed: River Belle Path, Goblin Wall, The
Mushroom Forest, The Mine of Cathuriges, Tida, Moschet Manor, Veo Lu Sluice,
Daemon's Court, Selepation Cave, Mount Kilanda, Conall Curach, Rebena Te Ra,
Lynari Desert — plus **Mount Vellenge** (final dungeon, no cycles).

Areas with **no boss reward table**: Mag Mell (peaceful town), Jegon River and
Cave of the Lethargon (connecting passages) — confirmed they have no 8-set table.

Note: artifact lists are read confidently; the small per-player **point
thresholds** are the OCR-risky part (entries marked *OCR-approx* especially —
re-check against the guide pages if you need exact qualifying scores).
