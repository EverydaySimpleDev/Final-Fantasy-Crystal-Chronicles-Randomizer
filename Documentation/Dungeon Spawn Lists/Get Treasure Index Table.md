# get_treasure Index Table (per dungeon)

`A` (`SPAWN_TBOX` chests) and `E` (`SPAWN` monsters) are both **confirmed**
`get_treasure` indices — swapping either between two records swaps what they
drop (verified in-game; each index has 4 item slots, matching
`PutDropItem`'s `m_dropItemCodes[4]`).

Generated from `spawn_map.py` against the real `.cft` data. Regenerate with:

```
py spawn_map.py export <dungeon_cfts_dir> "Dungeon Spawn Lists/spawn_coordinates.json"
```

then re-run the summarizing script (see the bottom of this file) against
that JSON.

A few `A`/`E` values per dungeon are far larger than the rest — these look
like they carry an encoded tag in the high bits over a small low index
(shapes seen: `tag<<16 | index` for a handful of chests, `tag<<28 | index`
for a handful of monsters) rather than being plain `get_treasure` table
rows. They're listed separately as **"tagged"** rather than mixed into the
plain-index columns, since what the tag actually means is not yet decoded.

| Dungeon | Chest indices (A) | Chest "tagged" values | Monster indices (E) | Monster "tagged" values |
|---|---|---|---|---|
| River Belle Path | 13, 18, 19, 29, 30, 31, 32 | (none) | 0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 26, 27, 28, 50, 51, 52 | 268435474, 536870931, 805306369 |
| Goblin Wall | 2, 11, 12, 13, 14, 31, 32, 33, 34 | (none) | 0, 1, 2, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 21, 28, 29, 30 | 268435486, 536870912, 805306368 |
| The Mine of Cathuriges | 2, 13, 14, 18, 19, 20, 30, 31 | (none) | 0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 15, 16, 17, 18, 19, 21, 26, 27, 28, 29, 30, 31 | 268435468 |
| The Mushroom Forest | 1, 11, 12, 13, 14, 37, 38, 39 | (none) | 0, 1, 2, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 21, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36 | (none) |
| Tida | 2, 10, 11, 12, 13, 14, 20, 31, 32, 33, 34 | (none) | 0, 1, 2, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 21, 26, 27, 28, 29, 30, 31, 34, 51, 52 | 268435456, 536870942, 805306377, 1073741825, 1073741850 |
| Moschet Manor | 1, 11, 12, 13, 18, 19 | (none) | 0, 1, 5, 6, 7, 8, 14, 15, 16, 17, 18, 19, 20, 26, 27, 28, 30 | (none) |
| Mount Kilanda | 21, 29, 30, 31, 32, 33, 34 | (none) | 0, 1, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 26, 27, 28 | (none) |
| Daemon's Court | 11, 21, 32 | 131082, 131084, 131085, 131086, 131090, 131091, 131103 | 0, 1, 2, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 26, 27, 28 | 268435456, 536870912 |
| Selepation Cave | 11, 12, 13, 14, 30, 31, 32, 33 | (none) | 0, 1, 2, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 26, 27, 28, 29 | (none) |
| Veo Lu Sluice | (none) | 65537, 65546, 65547, 65548, 65549, 65557, 65566, 65567, 65568, 65569, 65570 | 0, 1, 2, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 18, 19, 20, 25, 26, 27, 28, 29, 50, 51, 52 | 1073741824 |
| Lynari Desert | 2, 11, 14, 31, 32, 33, 34 | (none) | 0, 1, 2, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 26, 27, 28, 29 | (none) |
| Conall Curach | 2, 10, 11, 12, 13, 14, 31, 32, 33, 34 | (none) | 0, 1, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 21, 26, 27, 28, 29, 30 | (none) |
| Rebena Te Ra | 11, 12, 13, 14, 16, 19, 31, 32, 33, 34 | (none) | 0, 1, 6, 7, 8, 9, 10, 15, 16, 17, 18, 20, 21, 27, 28, 29, 30 | 268435465 |
| Mount Vellenge | 11, 12, 13, 14 | (none) | 0, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 21 | (none) |

## Notes

- Values are the union across every area file belonging to that dungeon
  (e.g. River Belle Path's list merges `river_0` and `river_1`).
- Duplicate index values ARE expected — several different physical
  chests/monsters legitimately share the same `get_treasure` index (they
  draw from the same 4-item pool), so a value repeating within a dungeon
  is normal, not a data error.
- Veo Lu Sluice and Daemon's Court are the only two dungeons whose CHESTS
  exclusively use "tagged" values (no plain low-index chests at all) - worth
  investigating first if the tag scheme gets decoded, since they're the
  cleanest isolated cases.
- Per-record detail (coordinates, monster names, raw B/C/D fields) is in
  `spawn_coordinates.json` in this same folder, via `spawn_map.py`.

## Regeneration script

```python
import json
data = json.load(open("Dungeon Spawn Lists/spawn_coordinates.json", encoding="utf-8"))
for dungeon, files in data.items():
    chest_all = sorted({c["A"] for f in files.values() for c in f["chests"]})
    chest_plain = [v for v in chest_all if v < 65536]
    chest_tagged = [v for v in chest_all if v >= 65536]
    mon_all = sorted({m["E"] for f in files.values() for m in f["monsters"] if isinstance(m["E"], int)})
    mon_plain = [v for v in mon_all if v < 1000]
    mon_tagged = [v for v in mon_all if v >= 1000]
    print(dungeon, chest_plain, chest_tagged, mon_plain, mon_tagged)
```
