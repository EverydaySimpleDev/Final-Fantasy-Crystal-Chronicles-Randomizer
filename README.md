# FFCC Chest Randomizer

Tools for viewing, randomizing, and hand-editing the treasure-chest contents of
**Final Fantasy Crystal Chronicles** (GameCube), straight from an `.iso`.

Deeper research writeups (dungeon spawn-index tables, custom-item/model
recipes, world-map loading-zone randomization, boss reward-set data, and
more) live in [`Documentation/`](Documentation/) rather than cluttering this
file — check there first if you're looking for byte-level detail on how any
of this actually works.

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
- **Custom Item** — repurpose an unused "Extra N" item slot into your own item.
- **AP Patch** — one-time patch to prep a vanilla ISO for the Archipelago client.
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

| Command         | What it does                                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------------- |
| `list`          | Show the dungeons in the ISO and how many chest sets each has                                           |
| `preview`       | Dry run — print what _would_ change, write nothing                                                      |
| `run`           | Randomize the ISO **in place** (auto-writes a spoiler log: chosen options, every chest, and shop stock) |
| `spoiler`       | Write a spoiler log of the ISO's current contents                                                       |
| `export`        | Dump every chest to an editable JSON                                                                    |
| `patch`         | Apply a chest JSON to the ISO                                                                           |
| `list-shops`    | List the shops in the ISO (Tipa, Alfitaria, …)                                                          |
| `preview-shops` | Dry run — show how many shop slots _would_ change                                                       |
| `shops`         | Randomize shop inventories **in place** (all, or `--shop` ones; add `--prices` to shuffle prices too)   |
| `prices`        | Shuffle item prices only (the gil/price tags shops use)                                                 |

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

In the GUI, on the Randomizer tab tick **"Randomize shop inventories"** (and pick
all shops or specific ones) and/or **"Randomize shop prices"**. (Per-class
restriction for items is planned for the future.)

### Gameplay Tweaks

A few independent, single-purpose toggles live in the GUI's **"Gameplay
Tweaks"** section (and as JSON keys, same idea as the chest data below —
export to see the current state, edit, patch to apply):

| Toggle | JSON key | What it does |
| --- | --- | --- |
| Mog never gets tired | `_mog_never_tired` (bool) | Removes the stamina penalty for running while Mog carries the chalice. Start.dol patch. |
| Starting location | `_starting_location` (name) | Start a new game at Tipa (default), Marr's Pass, Alfitaria, or Fields of Fum instead of always Tipa. Limited to towns where Year 1 is completable. |
| Skip Meteor Parasite → Mio questions → Raem | `_skip_mio_questions` (bool) | Jumps straight from the Meteor Parasite fight to the Raem fight. **Experimental** — not yet confirmed safe across a full playthrough; flagged in red in the GUI. |
| Skip the opening intro cutscene | `_skip_intro_cutscene` (bool) | Jumps straight past the opening cutscene on a new game. Confirmed working in-game. |
| Show Goblin Wall on the map from Year 1 | `_goblin_wall_always_visible` (bool) | Reveals Goblin Wall's road/icon on the world map starting Year 1, instead of waiting for the Year 1→2 transition. Doesn't change the Year value or anything else — patches the two `currentYear >= 2` checks in `world.cft` that gate the reveal. Confirmed working in-game. |
| Randomize Miasma Stream elements | `_randomize_miasma_elements` (bool) | Shuffles which element (Fire/Water/Wind/Earth) each of the 4 rotating Miasma Streams requires each year, seeded like the rest of the randomizer. **Requires `_goblin_wall_always_visible` to also be set** — that's what guarantees Fire and Earth (Goblin Wall's own hotspots) are obtainable from Year 1, alongside River Belle Path's Water/Wind, so every element is always reachable regardless of the shuffle. Patch is skipped (with a log warning) if the other option isn't also enabled. **Experimental** — confirmed working for a single-slot manual test in-game; not yet confirmed safe across a full playthrough. |
| Bonus Pools | `_randomize_bonus_pools` (bool) + `_bonus_pools` (per-dungeon override) | Randomizes the end-of-dungeon score-reward pool (separate from chests/enemy drops — see Notes below). `_bonus_pools` lets you hand-set exact items per dungeon/entry instead of (or on top of) randomizing; export a fresh JSON to see the current pool for every dungeon. |
| Lock stages behind key artifacts | `_stage_key_locks` (bool) | Creates 14 new key artifacts (one per dungeon) and hides each one in a handful of chests (never enemy drops) across a randomized, always-solvable chain — River Belle Path always stays open, and no dungeon's key is ever placed inside that same dungeon. **Experimental** — 6 of the 13 gated dungeons (Goblin Wall, Veo Lu Sluice, Moschet Manor, Tida, Mine of Cathuriges, Mushroom Forest) are confirmed working in-game (covering all three underlying lock mechanisms used); the remaining 7 (Selepation Cave, Daemon's Court, Conall Curach, Rebena Te Ra, Mount Vellenge, Mount Kilanda, Lynari Desert) are statically verified byte-exact but **not yet confirmed in-game** — treat those as unvalidated until spot-checked. Mount Kilanda's own identification also rests on inference (its call site wasn't in the original reference list), so it's worth extra scrutiny. |
| Enable developer debug menu | `_enable_debug_menu` (bool) | Unlocks the game's hidden "Development Mode" debug menu (9 Start.dol patches, derived from published Action Replay codes). **Experimental** — see below for how to use it. |

These are all independent of chest/item randomization and of each other —
mix and match freely.

**The 14 stage keys:**

| Item name | In-game description | Unlocks |
| --- | --- | --- |
| River Key | River Belle Path Key | *(nothing — River Belle Path is always open)* |
| Gob Key | Goblin Wall Key | Goblin Wall |
| Mine Key | Cathurige Key | The Mine of Cathuriges |
| Shroom Key | The Mushroom Forest Key | The Mushroom Forest |
| Tida Key | Tida Key | Tida |
| Manor Key | Moschet Manor Key | Moschet Manor |
| Lava Key | Kilanda Key | Mount Kilanda |
| Fort Key | Daemon's Court Key | Daemon's Court |
| Selep Key | Selepation Key | Selepation Cave |
| Sluice Key | Veo Lu Sluice Key | Veo Lu Sluice |
| Lynari Key | Lynari Desert Key | Lynari Desert |
| Conall Key | Conall Key | Conall Curach |
| Rebena Key | Rebena Te Ra Key | Rebena Te Ra |
| Vellen Key | Mount Vellenge Key | Mount Vellenge |

Item names are capped at 10 characters by a fixed name-slot size in the
game's own data, hence the abbreviated forms for a few of these.

**Using the debug menu:** it's controlled by a *second* GameCube controller
plugged into Port 2 (in Dolphin: enable a second controller slot and bind it
to a second physical pad, or a second keyboard/controller profile). On Port 2:
`A` opens the debug menu, `B` closes it, D-pad Up/Down moves the selection,
and `A`/`B` toggles the highlighted entry. It's a leftover QA test-flag menu
(invincibility, collision checks, particle/shadow toggles, and more) — it is
**not** confirmed to include a working free-roam camera, and some entries may
do nothing or destabilize the game. Treat it as a fun bonus for explorers, not
a reliable tool.

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
      "13": {
        "_label": "Chest 1",
        "_chest": 1,
        "1": "Phoenix Down",
        "2": "0x0107",
        "3": "Stone of Cure"
      },
      "19": {
        "_label": "Chest 2",
        "_chest": 2,
        "1": ["Gold", "Silver"],
        "2": "Diamond Ore",
        "3": "Ultimite"
      },
      "6": {
        "_label": "Monster 1",
        "_chest": null,
        "1": "Shuriken",
        "2": "Ice Brand"
      },
      "10": { "_label": "Magicite 1", "_chest": null, "1": "Stone of Fire" },
      "0": { "_label": "Gathering 1", "_chest": null, "1": "Vegetable Seed" }
    },
    "1": {
      "5": {
        "_label": "Chest 7",
        "_chest": 7,
        "1": "Bronze",
        "2": "Iron",
        "3": "Mythril"
      }
    }
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
- **`_bonus_pools`** (see Gameplay Tweaks above) is a *separate* top-level key
  with its own shape — `{dungeon: {entry_index("0"-"7"): [item, item, item, item]}}`
  — not part of the per-chest dungeon data above. Any of the 4 items can be
  `null` to leave that one slot untouched.

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
- For the full byte-exact recipe (what actually makes something an "artifact"
  vs. a plain item, the stat-effect family codes, and which item-model IDs
  are already used vs. free) see `Documentation/Adding Custom Items and
  Artifacts.md` and `Documentation/Item Model Reference.md`.

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
py cft.py tree|blocks|find|strings|block|calls|paramset <file.cft>  # inspect compiled script files
py cftpatch.py transplant|group|roundtrip <file.cft> ...     # move monsters/bosses between stages
                                                             # (see Documentation/Monster and Boss Swapping.md)
py spawn_map.py table <file.cft>                             # coordinate-indexed monster/chest table for one file
py spawn_map.py export <cft_dir> <out.json>                  # same, dumped for every dungeon at once
```

---

## Building a standalone executable

For handing the GUI to someone without Python installed, `FFCC-Randomizer.spec`
builds `ffcc_gui.py` (and everything it imports) into a single windowed `.exe`
with [PyInstaller](https://pyinstaller.org/):

```bash
py -m pip install pyinstaller   # once
py -m PyInstaller FFCC-Randomizer.spec --noconfirm
```

The result is `dist/FFCC-Randomizer.exe` — one self-contained file. Hand that
to anyone; they just need their own legally-obtained ISO. `build/` and `dist/`
are gitignored (regenerate them anytime by rerunning the command above).

---

## Typical end-to-end flow

1. Copy your ISO: `cp "Hacked Rom.iso" "Hacked Rom - randomized.iso"`
2. Randomize: `py randomizer.py run "Hacked Rom - randomized.iso" --seed 42 --ref "Hacked Rom.iso"`
3. Read `Hacked Rom - randomized - spoiler.txt`, then play that ISO.

## Notes & known scope

- **Chests and enemy drops share the same `get_treasure` item pool**, so by
  default randomizing changes both. Use `--chests-only` (or untick "Randomize
  enemy drops too" in the GUI) to limit changes to the Game8-identified chests.
- The **end-of-dungeon boss/bonus reward** is a separate subsystem (8 item
  entries per dungeon, gated by cycle and score) - independent of chest/enemy
  randomization, but it now has its own toggle too: see "Bonus Pools" in the
  GUI, or `randomize_bonus_pools()` / the `_bonus_pools` JSON key. Covers 13
  of the 14 dungeons — Mount Vellenge has no bonus-pool block in the real
  game, not a gap in the tooling. (See `Documentation/Boss Reward Sets
  (GameCube guide).md` for a transcription.)
- **All 14 dungeons** are covered, including Tida, Moschet Manor, Daemon's Court,
  and Rebena Te Ra. Dungeons span **multiple area files** (`_0`, `_1`, …) and the
  randomizer processes every area, with the 4-artifacts-per-cycle cap applied
  **across the whole dungeon** (all its areas combined).
