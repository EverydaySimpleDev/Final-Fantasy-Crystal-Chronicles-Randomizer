# World Map Water Level (Jegon River)

The world map shows the Jegon River crossing at a normal water level early in
the game and at a lower level later. Both versions are in the world-map
script `world.cft`, in `mainBasha` (the function that runs the caravan's
stops on the world map). A story-progress value picks between them.

**Status:** found in the script and decomp. Not yet confirmed in-game. In
particular, check that the `port_*` stops below really are the Jegon River
crossing and not another port stop.

## The branch

`mainBasha` has two stops (one for each bank) that each choose between a
`port_2` and a `port_0` version. That gives four `MJ_SWING_PADCHECK` sections:

| Code offset in `mainBasha` | Test | If true | If false |
|---|---|---|---|
| `0xA3A8` | `m_eventWork[1] == 5` | `port_2` (string 143), bank arg 0 | `port_0` (string 144), bank arg 0 |
| `0xD77E` | `m_eventWork[1] == 5` | `port_2` (string 159), bank arg 1 | `port_0` (string 160), bank arg 1 |

So `port_0` is the normal-water version and `port_2` the low-water version,
chosen once `m_eventWork[1]` reaches 5.

## Reading the bytecode

Each test compiles to:

```
PUSHI 1
GET   sysval[-455 + <popped index>]    ; opcode 00, flag bit 0x02 = indexed
PUSHI 5
==
JZ    <false branch>
```

System values from −200 to −499 map to
`CGameWork::m_eventWork[value + 0x1C7]`, a `short[256]` array at
`CGameWork + 0x11CC`. So `-455 + 1` is **`m_eventWork[1]`**, which looks like
the main story / world-progress counter.

The same array gates other world-map stops:

- `0xC38E`: `m_eventWork[30] == 80` picks `castle_1` or `castle_0`
- `0x001B`: `m_eventWork[28] == 20`
- `0x0396` and `0x3E3A`: two more `m_eventWork[1] == 5` checks

## Confirming it

1. With dolphin-memory-engine, watch `m_eventWork[1]` (the halfword at
   `CGameWork + 0x11CC + 2`) as the story progresses past the river change.
2. To force a state, patch the `PUSHI 5` literal at code offset `0xA3B2` and
   `0xD788` in `mainBasha`. Make it unreachable (e.g. 99) to keep the normal
   river, or match the current value to show the low river.
