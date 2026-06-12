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

| Command   | What it does                                                    |
| --------- | --------------------------------------------------------------- |
| `list`    | Show the dungeons in the ISO and how many chest sets each has   |
| `preview` | Dry run — print what _would_ change, write nothing              |
| `run`     | Randomize the ISO **in place** (also auto-writes a spoiler log) |
| `spoiler` | Write a spoiler log of the ISO's current contents               |
| `export`  | Dump every chest to an editable JSON                            |
| `patch`   | Apply a chest JSON to the ISO                                   |

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

### JSON workflow (precise hand-editing)

```bash
py randomizer.py export "Hacked Rom.iso" --ref "Hacked Rom.iso"   # -> "Hacked Rom - chests.json"
# ...edit the JSON...
py randomizer.py patch  "Hacked Rom - patched.iso" "Hacked Rom - chests.json"
```

The JSON maps **dungeon script → set index → cycle → item**:

```json
{
  "river": {
    "_name": "River Belle Path",
    "13": {
      "_chest": 1,
      "1": "Phoenix Down",
      "2": "0x0107",
      "3": "Stone of Cure"
    },
    "19": {
      "_chest": 2,
      "1": ["Gold", "Silver"],
      "2": "Diamond Ore",
      "3": "Ultimite"
    }
  }
}
```

- **Set index** is the stable key. `_name`, `_chest`, and any `_`-prefixed key
  are human-readable metadata, ignored on import.
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

---

## `chesteditor.py` — GUI editor

```
py chesteditor.py
```

1. **Open ISO** (back it up first).
2. Pick a dungeon, click **Load**.
3. The table shows **one row per chest**; the three columns are what that chest
   gives in **Cycle 1 / 2 / 3**. Green "Chest N" rows are matched to Game8's
   chest numbers; grey "Extra N" rows are the dungeon's other loot tables.
4. **Double-click a cycle cell** to change what that chest gives that cycle. The
   picker has a category filter and a search box and lists every droppable item.
5. **Game8 Reference** shows the canonical per-chest contents.
6. **Save to ISO** writes the edits in place.

Works for all dungeons (signature-based detection).

---

## Supporting / low-level tools

Usually not needed directly, but available:

```bash
py gciso.py list|extract|inject "<iso>" <disc_path> [file]   # raw file in/out of the ISO
py items.py show|list|set <param.cfd> <id> ...               # edit item stats/definitions
py chest.py table|find|setslot|set <file.cft> ...            # CLI single-file chest edits
py cft.py tree|blocks|find|strings|block|calls <file.cft>    # inspect compiled script files
```

---

## Typical end-to-end flow

1. Copy your ISO: `cp "Hacked Rom.iso" "Hacked Rom - randomized.iso"`
2. Randomize: `py randomizer.py run "Hacked Rom - randomized.iso" --seed 42 --ref "Hacked Rom.iso"`
3. Read `Hacked Rom - randomized - spoiler.txt`, then play that ISO.

## Notes & known scope

- The **end-of-dungeon boss/bonus reward** is a separate subsystem (8 artifact
  sets gated by cycle and bonus points) and is **not** touched by these tools —
  chest randomization is independent of it.
- A few dungeons (Moschet Manor, Jegon River, Mag Mell) expose little or no
  standard chest data and are largely skipped.
