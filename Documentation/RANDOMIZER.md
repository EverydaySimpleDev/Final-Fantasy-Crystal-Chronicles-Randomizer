# FFCC Chest Randomizer

Tools for viewing, randomizing, and hand-editing the treasure-chest contents of
**Final Fantasy Crystal Chronicles** (GameCube), straight from an `.iso`.

## Easiest: the all-in-one GUI

```
py ffcc_gui.py
```

One window with tabs for everything:

- **Randomizer** — pick a **Source ISO** (never modified) and an **Output ISO**
  (auto-suggested as `<source> - randomized.iso`, or choose your own), set
  options, then **Preview** / **Randomize!**, and write a spoiler or
  export/patch JSON. Writes only ever go to the output ISO.
- **Chest Editor** — the per-chest / per-cycle editor (below).
- **File Tools** — extract / inject / list files in the ISO, and edit item
  stats in `param.cfd`.
- **Help** — a quick in-app guide.

The command-line tools below do the same things if you prefer a terminal.

## Requirements & ground rules

- Python 3 (invoked as `py` on Windows, or `python3`).
- **Always work on a copy of your ISO.** `run` and `patch` modify the ISO in
  place. Keep your clean original as a backup (and as a `--ref` for chest
  numbering).
- Quote any path that contains spaces.

## What can go in a chest

Chests can hold any **droppable** item: Artifacts, Magicite (real stones),
Phoenix Down, Materials, Food, and Recipes/Scrolls. Craftable **equipment**
(weapons, armor, shields, gauntlets, helmets, belts, accessories) is _not_
grantable from a chest — the chest opens but gives nothing — so the tools never
place it. Item names/IDs come from `ffcc_items.py`.

### How chests, cycles, and slots work

Each chest is a set of slots, and the game rolls among the slots that belong to
the current **cycle** (year). For a 7-slot chest: cycle 1 = slots 1-4, cycle 2 =
slots 5-6, cycle 3 = slot 7. So a chest can give different items in different
cycles, and (depending on `--rolls`) several possible items within one cycle.

---

## `randomizer.py` — main tool

```
py randomizer.py <command> "<iso>" [json] [options]
```

| Command         | What it does                                                    |
| --------------- | --------------------------------------------------------------- |
| `list`          | Show the dungeons in the ISO and how many chest sets each has   |
| `preview`       | Dry run — print what _would_ change, write nothing              |
| `run`           | Randomize the ISO **in place** (auto-writes a spoiler log: chosen options, every chest, and shop stock) |
| `spoiler`       | Write a spoiler log of the ISO's current contents               |
| `export`        | Dump every chest to an editable JSON                            |
| `patch`         | Apply a chest JSON to the ISO                                   |
| `list-shops`    | List the shops in the ISO (Tipa, Alfitaria, …)                  |
| `preview-shops` | Dry run — show how many shop slots _would_ change               |
| `shops`         | Randomize shop inventories **in place** (all, or `--shop` ones; add `--prices` to shuffle prices too) |
| `prices`        | Shuffle item prices only (the gil/price tags shops use)         |

### Options

| Option                  | Values                                                              | Meaning                                                                                                                                                  |
| ----------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--seed N`              | any integer                                                         | Reproducible result (same seed → same layout). Omit for random                                                                                           |
| `--mode`                | `cross` (default) / `category`                                      | `cross` = any droppable item anywhere; `category` = keep each chest's original category                                                                  |
| `--rolls`               | `cycle` (default) / `slot` / `chest`                                | `cycle` = one item per chest per cycle; `slot` = every slot independent (most variety, multiple items per cycle); `chest` = one item for the whole chest |
| `--pool`                | `all` (default) / `artifact` / `magicite` / `consumable` / `recipe` | Restrict which items can appear                                                                                                                          |
| `--max-artifacts N`     | default `4`                                                         | Cap artifacts per dungeon **per cycle** (the player's carry limit); excess chests get a non-artifact item                                                |
| `--dungeon NAME`        | e.g. `river`, `gob`                                                 | Only this dungeon (repeatable). Names come from `list`                                                                                                   |
| `--fill-empty`          | flag                                                                | Also fill placeholder/empty slots                                                                                                                        |
| `--chests-only`         | flag                                                                | Randomize only chests, **not enemy drops** (they share the loot pool). Isolates Game8-identified chests; needs `--ref`; undocumented dungeons skipped    |
| `--ref "<vanilla.iso>"` | path                                                                | Label spoiler/export chests by their Game8 chest number                                                                                                  |

### Examples

```bash
# See what's in the ISO
py randomizer.py list "Hacked Rom.iso"

# Preview a full randomization (writes nothing)
py randomizer.py preview "Hacked Rom.iso" --seed 42

# Randomize a COPY (also writes "<iso> - spoiler.txt" next to it)
py randomizer.py run "Hacked Rom - randomized.iso" --seed 42 --ref "Hacked Rom.iso"

# Variations
py randomizer.py run "copy.iso" --mode category               # stay in original category
py randomizer.py run "copy.iso" --rolls slot                  # multiple items per cycle
py randomizer.py run "copy.iso" --pool recipe --dungeon river # only recipes, only River

# Spoiler for an already-made ISO (chest numbers need --ref)
py randomizer.py spoiler "Hacked Rom - randomized.iso" --ref "Hacked Rom.iso"
```

### Shop randomization

Shops keep their inventory in the town scripts; each slot's price is derived from
the item, so randomizing a shop just swaps the item (the price follows). Stock is
drawn only from items shops already sell (materials, recipes, food, magicite,
Phoenix Down), so every price stays valid. Equipment/artifacts are never added.

```bash
py randomizer.py list-shops     "copy.iso"                 # Tipa, Alfitaria, ...
py randomizer.py preview-shops  "copy.iso" --seed 42       # dry run, writes nothing
py randomizer.py shops          "copy.iso" --seed 42       # randomize ALL shops
py randomizer.py shops          "copy.iso" --shop village_0 --shop weapon_0  # just these
py randomizer.py shops          "copy.iso" --seed 42 --prices   # items AND prices
py randomizer.py prices         "copy.iso" --seed 42       # shuffle prices only
```

**Prices** live per-item in `param.cfd` (the engine derives each shop price from
the item). Price randomization **shuffles the real prices among the items shops
sell**, so every price stays plausible and valid — Bronze might cost what Mythril
did, etc. It works with or without item randomization. (The 0xFFFF "not for sale"
items are left alone.)

**Stock across years.** Some shops sell more as the story progresses, and
this never happens at random or on a cycle:

| Shop | What changes its stock |
|---|---|
| Tipa | 4 tiers following the village's house-growth level (`m_eventWork[120]`). It can only go up, at most once per year change, when a score passes 40 or 80. |
| Leuda | a lower and higher tier for scrolls and for materials, chosen by Leuda's event state (`m_eventWork[110]`) |
| Shella | a small special stock (Strange Liquid, Shella Mark) during an event |
| Alfitaria, Fields of Fum, Smith, Selkie Peddler | fixed (the Selkie Peddler always sells Tipa's first tier) |

In vanilla each later tier keeps the earlier tier's items and adds more (the
only exception is Spring Water, which leaves Tipa's final tier). Randomization
keeps that: within each shop, every vanilla item is replaced by the **same**
random item in every tier. So something you saw on sale in an early year
stays on sale later, and new stock only gets added. All tiers are in the
shared `shopStart` script function, cases 0–43; each shop calls its own
cases.

In the GUI, on the Randomizer tab tick **"Randomize shop inventories"** (and pick
all shops or specific ones) and/or **"Randomize shop prices"**. (Per-class
restriction for items is planned for the future.)

### JSON workflow (precise hand-editing)

```bash
py randomizer.py export "Hacked Rom.iso" --ref "Hacked Rom.iso"   # -> "Hacked Rom - chests.json"
# ...edit the JSON...
py randomizer.py patch  "Hacked Rom - patched.iso" "Hacked Rom - chests.json"
```

The JSON maps **dungeon script → area → set index → cycle → item** (each dungeon
has one or more area files `_0`, `_1`, …):

```json
{
  "river": {
    "_name": "River Belle Path",
    "0": {
      "13": { "_label": "Chest 1", "_chest": 1, "1": "Phoenix Down", "2": "0x0107", "3": "Stone of Cure" },
      "19": { "_label": "Chest 2", "_chest": 2, "1": ["Gold", "Silver"], "2": "Diamond Ore", "3": "Ultimite" },
      "6":  { "_label": "Monster 1", "_chest": null, "1": "Shuriken", "2": "Ice Brand" },
      "10": { "_label": "Magicite 1", "_chest": null, "1": "Stone of Fire" },
      "0":  { "_label": "Gathering 1", "_chest": null, "1": "Vegetable Seed" }
    },
    "1": { "5": { "_label": "Chest 7", "_chest": 7, "1": "Bronze", "2": "Iron", "3": "Mythril" } }
  }
}
```

- **Area index** (`"0"`, `"1"`, …) selects the dungeon's area file; **set index**
  is the stable key within an area. `_name`, `_label`, `_chest`, and any
  `_`-prefixed key are human-readable metadata, ignored on import.
- **`_label`** mirrors the chest editor: each Game8 chest is numbered **once per
  dungeon** (`"Chest N"`); every other set is classified (validated against the
  GameCube set-list sheet) as **`"Monster N"`** (enemy drop), **`"Magicite N"`**
  (stone/element spawn), or **`"Gathering N"`** (food/seeds), numbered across
  areas. `_chest` is the numeric chest id, or `null` otherwise. (Labels need
  `--ref`; without it every set is just `"Set N"`.)
- **Cycle** is `"1"`, `"2"`, or `"3"`; the value sets every real-item slot in
  that cycle.
- **Item** can be a name (`"Phoenix Down"`), a hex id (`"0x0107"`), or the
  export's `"Name [0xID]"` label (the hex wins). A **list** is spread across the
  cycle's slots (e.g. `["Gold","Silver"]` → Gold/Silver/Gold/Silver).
- Non-droppable or unresolved items are **warned about and skipped** — no silent
  failures. Ambiguous names resolve to the droppable item (e.g. "Iron Shield" →
  the recipe, not the equipment).
- After patching, if any cycle ends up with **more than 4 artifacts** (the
  player's carry limit) you get a warning per dungeon/cycle. The patch still
  applies — you're in control — but it flags the over-limit cycle.
- **The JSON's chest data is always written exactly as given.** Nothing else
  in the import overwrites it:
  - With `"_stage_key_locks": true`, the keys are placed *after* the chest
    data, and only into chests the JSON left unchanged. An entry that still
    holds what the ISO already has counts as "no preference", so an
    unedited export works and your edited chests are never touched.
  - `"_protect_required_stones"` (default `true`) keeps the magicite needed
    for Holy (Lich, Zombie Dragon) and Tida's Fire out of stage-key
    placement and warns if the patched ISO is missing those stones. It
    never changes the JSON's chest data. Set it to `false` to turn both off.
    The GUI checkbox "Keep required magicite obtainable" and the CLI flag
    `--no-stone-protection` control the same protection for random runs.
- The Archipelago modes (`ap-patch`, `ap-hybrid` / "Patch for Archipelago")
  only write the AP placements into chest sets; the protections and stage
  keys don't run there.

---

## `chesteditor.py` — GUI editor

```
py chesteditor.py
```

1. **Open ISO** (back it up first).
2. Pick a dungeon, click **Load**.
3. The table shows **one row per chest**; the three columns are what that chest
   gives in **Cycle 1 / 2 / 3**. Green "Chest N" rows are matched to Game8's
   chest numbers (each chest numbered **once per dungeon**, across all its area
   files). Every other set is classified (validated against the GameCube
   set-list sheet) and colour-coded: **Monster N** (red, enemy drop),
   **Magicite N** (purple, stone/element spawn), **Gathering N** (tan,
   food/seeds).
4. **Double-click a cycle cell** to change what that chest gives that cycle. The
   picker has a category filter and a search box and lists every droppable item.
5. **Game8 Reference** shows the canonical per-chest contents.
6. **Save to ISO** writes the edits in place.

Works for all dungeons (signature-based detection).

---

## Adding a custom item

You can repurpose one of the game's unused "Extra N" item slots into a custom
item (no table resize needed). `customitem.py` does the whole thing — copies a
**donor** item's definition (so the new item reuses its 3D model + menu icon +
behaviour), sets the price, and writes the name into the in-game name table.

```bash
py customitem.py list-free "copy.iso"                          # show repurposable slots
py customitem.py add "copy.iso" 0x162 "AP Item" --like Gold --gil 10
py customitem.py add "copy.iso" 0x162 "AP Item" --like Gold --gil 10 \
                    --shop village_0 --chest river             # also place it for testing
py customitem.py show "copy.iso" 0x162
```

- `--like` is the donor (name or id) — its model/icon/type are copied. `--gil`
  sets the price. `--shop`/`--chest` optionally place it for testing.
- **Name length is capped by the slot** (names are edited in place to keep the
  file size fixed) — the "Extra N" slots fit roughly an 8-character name. Use a
  short name or a slot with a longer placeholder.
- To have the **randomizer/editor** carry the new item, add `NAMES[<id>]` to
  `ffcc_items.py` and remove the id from `randomizer.EXCLUDE` (the tool prints the
  exact lines). Limits: reusing an existing model/icon is easy; a brand-new model
  or a new behaviour type needs graphics/executable work.

## Editing models & textures (Blender round-trip)

Item/character models and textures are GameCube IFF-tag containers
(`.chm/.cha/.chd/.tex`). You can edit them and put them back:

```bash
# textures (needs Pillow):  export -> edit the PNG -> re-import (same size) -> inject
py tex.py export "w001_root.tex" out_png/
py tex.py import "w001_root.tex" out_png/ "w001_root_new.tex"
py gciso.py inject "copy.iso" dvd/char/wep/w001/w001_root.tex "w001_root_new.tex"

# 3D models (Blender round-trip, topology-preserving):
py objimport.py export    "w001_root.chm" w001_obj/     # one OBJ per mesh
#   ...open the OBJ in Blender, MOVE/SCALE/MORPH vertices (Keep Vertex Order,
#   axis Forward Z / Up Y), export the OBJ back...
py objimport.py import    "w001_root.chm" w001_obj/ "w001_root_new.chm"
py objimport.py roundtrip "w001_root.chm"               # self-test (byte-identical)
py gciso.py inject "copy.iso" dvd/char/wep/w001/w001_root.chm "w001_root_new.chm"
```

- `chmio.py` is the byte-exact container reader/writer underneath (verified
  byte-identical on all 3,864 model/texture files).
`import` is topology-preserving (move/scale/morph existing vertices only). To put
in a **completely new mesh** (different vertex/face count), use `newmesh`:

```bash
py objimport.py export  "w001_root.chm" w001_obj/    # OBJ now includes faces (f p/t/n)
#   ...replace/edit the mesh in Blender however you like, export OBJ (with normals+UVs)...
py objimport.py newmesh "w001_root.chm" w001_obj/w001_root.obj "w001_new.chm"
py gciso.py rebuild "copy.iso" dvd/char/wep/w001/w001_root.chm "w001_new.chm" "out.iso"
```

`newmesh` rebuilds the mesh's vertices, UVs, normals **and faces** (writing a
fresh GameCube display list via `dlst.py`), keeping the original material/texture.
The model can be any size — `gciso rebuild` handles it. **Works for static models**
(items, weapons, props); **rigged/animated characters** also store per-vertex bone
weights (SKIN) that `newmesh` doesn't rewrite yet, so don't change their topology.

### Replacing a file at a different size (ISO rebuild)

`gciso inject` is same-size-only. To put back a file that **grew or shrank**, use
`rebuild` — it appends the new file at the end of the image and repoints its FST
entry, leaving every other file byte-identical:

```bash
py gciso.py rebuild "copy.iso" dvd/char/wep/w001/w001_root.chm bigger.chm "out.iso"
```

The output image can exceed the 1.46 GB disc size, so it's for **emulators
(Dolphin)**, not burning. (Repeated rebuilds leave dead space; rebuild from a
clean ISO to stay lean.)

## Supporting / low-level tools

Usually not needed directly, but available:

```bash
py gciso.py list|extract|inject "<iso>" <disc_path> [file]   # raw file in/out of the ISO
py items.py show|list|set <param.cfd> <id> ...               # edit item stats/definitions
py customitem.py list-free|show|add "<iso>" ...              # add a custom item (above)
py tex.py export|import <file.tex> ...                       # edit textures (PNG round-trip)
py objimport.py export|import|newmesh|roundtrip <model.chm>  # edit/replace models (Blender)
py chmio.py <file>          # byte-exact model-container round-trip check
py dlst.py  <model.chm>     # inspect/verify display lists (faces)
py chest.py table|find|setslot|set <file.cft> ...            # CLI single-file chest edits
py cft.py tree|blocks|find|strings|block|calls <file.cft>    # inspect compiled script files
```

---

## Typical end-to-end flow

1. Copy your ISO: `cp "Hacked Rom.iso" "Hacked Rom - randomized.iso"`
2. Randomize: `py randomizer.py run "Hacked Rom - randomized.iso" --seed 42 --ref "Hacked Rom.iso"`
3. Read `Hacked Rom - randomized - spoiler.txt`, then play that ISO.

## Notes & known scope

- **Chests and enemy drops share the same `get_treasure` item pool**, so by
  default randomizing changes both. Use `--chests-only` (or untick "Randomize
  enemy drops too" in the GUI) to limit changes to the Game8-identified chests.
- The **end-of-dungeon boss/bonus reward** is a separate subsystem (8 artifact
  sets gated by cycle and bonus points) and is **not** touched by these tools —
  chest randomization is independent of it. (See
  `Boss Reward Sets (GameCube guide).md` for a transcription.)
- **All 14 dungeons** are covered, including Tida, Moschet Manor, Daemon's Court,
  and Rebena Te Ra. Dungeons span **multiple area files** (`_0`, `_1`, …) and the
  randomizer processes every area, with the 4-artifacts-per-cycle cap applied
  **across the whole dungeon** (all its areas combined).
- **Fire is always obtainable in Tida.** Spider webs block the path there and
  only Fire clears them, so Tida's magicite sets are kept vanilla the same way
  as the Holy dungeons below (Tida's field areas have Fire stone sets), and
  `check_stone_access()` warns if Tida ends up without a Fire set. The list
  lives in `FIRE_DUNGEONS` in `randomizer.py`. In Archipelago the apworld
  already requires the Ring of Fire for Tida.
- **Holy is always obtainable where a boss needs it.** Lich (Rebena Te Ra) and
  Zombie Dragon (Conall Curach) take 1 damage until hit with Holy. Holy isn't
  a droppable stone: it's cast by fusing a Fire, Blizzard or Thunder stone
  followed by a **Stone of Life**, in that order (Life first gives Slow; see
  `Item Records and Magic Fusion.md`). Stones don't carry between dungeons, so both
  must be found in that dungeon. The randomizer therefore never randomizes
  those two dungeons' magicite sets (the per-element stone spawn/drop tables),
  and never uses them for stage keys. Every other set there is still
  randomized. After patching, `check_stone_access()` confirms each dungeon
  still has a Life set and an element set, and prints a warning if not. With
  the experimental boss shuffle, the protection follows Lich and Zombie Dragon
  to whichever dungeons they end up in (`HOLY_BOSS_DUNGEONS` in
  `randomizer.py` is the default when bosses aren't moved). The
  `ap-patch` / `ap-hybrid` modes only
  replace chest sets, and none of these magicite sets are chests, so AP seeds
  keep the stones as well.
