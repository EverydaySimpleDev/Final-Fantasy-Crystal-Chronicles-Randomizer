# Map Folders by Stage

Which `dvd/map/stgNNN/` folder each dungeon, town and other area loads. Use
it to find a stage's level geometry (for example to line up
`spawn_map.py blender` labels on the real map).

## How the mapping was found

Every stage script (`dvd/cft/<name>_<n>.cft`) has a `Map_Load_<NAME>`
function that calls

```
loadMapX(stage, map, colour, colour, float, float, float, float)
```

Stage *S* and map *M* mean the files `dvd/map/stgSSS/mapMMM*`. For example,
River Belle Path's field `river_0` calls `loadMapX(23, 0, …)`, which is
`dvd/map/stg023/map000*`. The tables below were read from those calls in
all stage scripts on the NTSC-US disc.

## Files in a map folder

| File | Contents |
|---|---|
| `mapMMM.otm` | Scene graph: nodes, transforms, materials, animations. For dungeon maps it holds **no** geometry. |
| `mapMMM_K.mpl` | Geometry parts. Each is a `MESH` chunk holding `VSET` (vertex set: `VERT` float x/y/z in world coordinates, `NORM`, `COLR`, `UV`) and `DSET` (display lists: `DLHD` > `DLST`, the same GameCube display-list format as character models, decodable with `dlst.py`) pairs. |
| `mapMMM.mtx`, `mapMMM_K.mtx` | Textures for the matching parts. |
| `mapMMM.mid` | `MID` > `SCEN` > `HIT`: probably the collision data. Not decoded yet. |

In River Belle Path, the two largest `.mpl` parts (about 2,900 units across)
are the sky/backdrop shells. Leave them out when viewing the level from
above.

Map vertices use the same world coordinates as the `SPAWN` records.
Blender's OBJ importer (default axes) plus a 1/10 scale puts a map exactly
under the `spawn_map.py blender` labels.

## Dungeons

| Dungeon | Folder | Script → map |
|---|---|---|
| River Belle Path | `stg023` | `river_0` → map000; `river_1` (boss) → map001 |
| Goblin Wall | `stg024` | `gob_0` → map000; `gob_1` → map001; `gob_2` (boss) → map002 |
| The Mine of Cathuriges | `stg003` | `mine_0`–`mine_3` → map000–map003 (boss: map003) |
| The Mushroom Forest | `stg016` | `kinoko_0` → map000; `kinoko_1` (boss) → map001 |
| Tida | `stg025` | `ruin_0`–`ruin_2` → map000–map002 (boss: map002) |
| Moschet Manor | `stg026` | `gigas_0`–`gigas_7` → map000–map007; **`gigas_8` (boss) reuses map000** |
| Veo Lu Sluice | `stg029` | `water_0` → map000 **and** map002; `water_1` (boss) → map001 |
| Selepation Cave | `stg027` | `cave_0`–`cave_2` → map000–map002 (boss: map002) |
| Daemon's Court | `stg028` | `fort_0` → map000; `fort_1` (boss) → map001 |
| Mount Kilanda | `stg015` | `lava_0`–`lava_2` → map000–map002 (boss: map002) |
| Lynari Desert | `stg014` | `desert_0`–`desert_2` → map000–map002 (boss: map002) |
| Conall Curach | `stg002` | `swamp_0`–`swamp_3` → map000–map003 (boss: map003) |
| Rebena Te Ra | `stg030` | `city_0`–`city_2` → map000–map002 (boss: map002) |
| Mount Vellenge | `stg031` | `meteo_0` → map000; `meteo_1` → map001; `meteo_2` → map002; **`meteo_3` also uses map002** |
| Final battle | `stg032` | `last_0`–`last_5` → map000–map005; `last_6` reuses map005 |

The boss room is the last map in each list except Moschet Manor, whose boss
room reuses the entrance map.

## Towns and other areas

| Area | Folder | Scripts → map |
|---|---|---|
| Tipa | `stg001` | `village_0`, `farewell_0/1`, `mail` → map001; `ff44_1` → map000; `festa_0` → map002; map003 is also used (see `miya_0`) |
| Marr's Pass (Smith) | `stg004` | `weapon_0` → map000 |
| Alfitaria | `stg005` | `castle_0`, `castle_1` → map000 |
| Fields of Fum | `stg006` | `farm_0` → map000 |
| Shella | `stg007` | `magic_0` → map000 |
| Leuda | `stg008` | `thief_0`, `thief_1` → map000 |
| Mag Mell | `stg009` | `magmell_0` → map000 |
| Port / river crossing | `stg010` | `port_1` → map000; `tutorial_0` → map001 |
| Port / river crossing | `stg011` | `port_0` → map000; `port_2` → map001 |
| Miasma Stream | `stg017` | `stream_0` → map000 |
| Miasma Stream | `stg021` | `stream_1` → map000 |
| Roads between areas | `stg034` | every `kai_*` script → map000, map001 or map002 |
| World map | `stg033` | `world` → map000 |
| Moogle house | `stg035` | `mog_0` → map000 |
| Event scenes | `stg012` | `ff44_3` → map001; `ffcc_4` → map002 (map000, map003, map004 also exist) |

`port_0` and `port_2` are the normal- and low-water versions of the world-map
stop described in
[World Map Water Level (Jegon River).md](World%20Map%20Water%20Level%20%28Jegon%20River%29.md),
and here they load map000 and map001 of the same folder. That fits them
being two states of one place. `ff44_2` (an event script) loads Mount
Vellenge's `stg031` map000.

## Notes

- `stg000` (map000 and map002) isn't loaded by any stage script. Its
  `map000.otm` is the only `.otm` checked so far that holds meshes directly;
  the repo's older `map000_terrain.obj` export came from it.
- `miya_0`–`miya_3` (the test/debug scripts that support nearly every
  monster) contain a `Map_Load_*` function for every stage in the game. They
  are a quick index of all `stage, map` pairs.
- Scripts with no `Map_Load_*` call: `ffcc_0`, `ffcc_2`, `ffcc_5`,
  `map_test`, `startmap`, `stream_2`, `uma_1` (the Selkie Peddler, which
  appears on other stages' maps).
