"""
shopchecks.py - Shop slots as AP checks.

A town script's shopStart(case, player, rate) fills the shop menu: it is a
run of blocks, one per stock list,

    if (arg0 == case) {
        shopRequest(1, item, 0, 0, 0, 0, 0);    one per slot
        ...
    }

compiled as `load arg0, push case, ==, jump-if-false <end of block>` and then
the slots (see shops.py). The shop's NPC calls shopStart with its case, so a
case is one shop's stock. Leuda's stock grows with its story (40/41
recipes, 42/43 materials). For checks every shop must sell the same thing
all game, so fix_stock() changes those tests so every tier shows the
fullest list: 40 and 42 never match, 41 becomes `arg0 <= 41` and 43 becomes
`arg0 >= 42`.

SHOPS lists the shops that are checks. Two shops aren't. The Selkie Peddler
has no stage of its own (it turns up on other stages' maps), so the logic
can't say where it is. Tipa's shop is run by a caravan member's family when
their job is Merchant, so a game without a Merchant family has no shop there. The export writes shop_table.py for the AP world:

    LOCATIONS = {name: (code, shop key, slot, vanilla item id)}
    SHOPS = {shop key: (display name, town, script, case, slot count)}

Usage:
    py shopchecks.py list <game.iso>
    py shopchecks.py export <game.iso> <shop_table.py>
"""

import ast
import os
import struct
import sys
import tempfile

import cft
import cftpatch
import gciso

FIRST_CODE = 3000

# key: (display name, town, town script, case)
SHOPS = {
    "marrs_pass":          ("Marr's Pass Material Shop",   "Marr's Pass",   "weapon_0",  8),
    "alfitaria_food":      ("Alfitaria Food Shop",         "Alfitaria",     "castle_0",  16),
    "alfitaria_materials": ("Alfitaria Material Shop",     "Alfitaria",     "castle_0",  20),
    "shella":              ("Shella Shop",                 "Shella",        "magic_0",   32),
    "fum_food":            ("Fields of Fum Food Shop",     "Fields of Fum", "farm_0",    24),
    "fum_materials":       ("Fields of Fum Material Shop", "Fields of Fum", "farm_0",    28),
    "leuda_recipes":       ("Leuda Recipe Shop",           "Leuda",         "thief_0",   41),
    "leuda_materials":     ("Leuda Material Shop",         "Leuda",         "thief_0",   43),
}

NEVER = 99                       # a case no shop asks for
EQ, LE, GE = 0x2C, 0x2F, 0x31
# script: [(case, new value, new comparison)] - see the module docstring
FIXED_STOCK = {
    "thief_0":   [(40, NEVER, EQ), (41, 41, LE), (42, NEVER, EQ), (43, 42, GE)],
}

_LOAD_ARG0 = (0x00, 1)
_PUSH, _JZ = 0x03, 0x08


def _shop_code(path):
    """(file data, file offset of shopStart's code, disassembly)."""
    s = cftpatch.Script(path)
    code = s.code("shopStart")
    data = open(path, "rb").read()
    base = data.find(code)
    if base < 0:
        raise ValueError(f"{os.path.basename(path)}: shopStart not found")
    return data, base, list(cft.disasm(code))


def cases(path):
    """{case: (offset of its value, offset of its comparison, block start, block end)}
    as file offsets, from shopStart's `arg0 == case` tests."""
    data, base, ops = _shop_code(path)
    out = {}
    for i in range(len(ops) - 3):
        (o0, p0, a0), (o1, p1, a1), (o2, p2, _), (o3, p3, a3) = ops[i:i + 4]
        if (p0, a0) == _LOAD_ARG0 and p1 == _PUSH and p2 in (EQ, LE, GE) and p3 == _JZ:
            out[a1] = (base + o1 + 1, base + o2, base + o3 + 5, base + (a3 & 0xFFFFFFFF))
    return out


def slots(path, case):
    """[(file offset of the item id, item id)] of one case's slots, in order."""
    import shops
    found = cases(path)
    if case not in found:
        # a script fix_stock already changed tests the case by its new value
        fixed = [value for fixes in FIXED_STOCK.values() for c, value, op in fixes if c == case and op != EQ]
        case = fixed[0] if fixed else case
    start, end = found[case][2:]
    return [(off, item) for off, item in shops.find_shop_items(path) if start <= off < end and item]


def fix_stock(path, script):
    """Make every tier of the script's shops show the fullest list (FIXED_STOCK).
    Only tests still in their vanilla `arg0 == case` form are changed, so it
    can run again safely. Returns the number of tests changed."""
    found = cases(path)
    data = bytearray(open(path, "rb").read())
    changed = 0
    for case, value, op in FIXED_STOCK.get(script, []):
        if case not in found or data[found[case][1]] != EQ:
            continue        # already patched
        value_at, op_at, _, _ = found[case]
        data[value_at:value_at + 4] = struct.pack(">i", value)
        data[op_at] = op
        changed += 1
    open(path, "wb").write(data)
    return changed


def set_slots(path, case, items):
    """Write `items` into one case's slots, in order."""
    data = bytearray(open(path, "rb").read())
    for (off, _), item in zip(slots(path, case), items):
        data[off:off + 2] = struct.pack(">H", item)
    open(path, "wb").write(data)


def _extract(iso, script):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, f"dvd/cft/{script}.cft")[0]
        f.seek(off)
        path = os.path.join(tempfile.gettempdir(), f"shopchecks_{script}.cft")
        open(path, "wb").write(f.read(size))
    return path


def vanilla_stock(iso):
    """{shop key: [item id per slot]}."""
    return {key: [item for _, item in slots(_extract(iso, script), case)]
            for key, (_, _, script, case) in SHOPS.items()}


def patch(iso, stock):
    """Fix the shops' stock tiers and write `stock` ({shop key: [item id per
    slot]}) into them. Shops missing from `stock` keep their items."""
    for script in sorted({info[2] for info in SHOPS.values()}):
        path = _extract(iso, script)
        size = os.path.getsize(path)
        # slots first: they are found by the vanilla case values, which
        # fix_stock changes
        for key, (_, _, s, case) in SHOPS.items():
            if s == script and key in stock:
                set_slots(path, case, stock[key])
        fix_stock(path, script)
        content = open(path, "rb").read()
        if len(content) != size:
            raise ValueError(f"{script}: size changed")
        gciso.put_file(iso, f"dvd/cft/{script}.cft", content)


def location_name(key, slot):
    return f"{SHOPS[key][0]} - Slot {slot}"


def _previous_codes(path):
    if not os.path.exists(path):
        return {}
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == "LOCATIONS":
            return {name: row[0] for name, row in ast.literal_eval(node.value).items()}
    return {}


def export(iso, out_path):
    stock = vanilla_stock(iso)
    codes = _previous_codes(out_path)
    next_code = max(list(codes.values()) + [FIRST_CODE - 1]) + 1
    lines = []
    for key, items in stock.items():
        for slot, item in enumerate(items, 1):
            name = location_name(key, slot)
            if name not in codes:
                codes[name] = next_code
                next_code += 1
            lines.append(f"    {name!r}: ({codes[name]}, {key!r}, {slot}, {item:#05x}),")
    shop_lines = [f"    {key!r}: ({name!r}, {town!r}, {script!r}, {case}, {len(stock[key])}),"
                  for key, (name, town, script, case) in SHOPS.items()]
    header = '''"""
Written by shopchecks.py (Final-Fantasy-Crystal-Chronicles-Randomizer) from
the town scripts - make it again instead of editing it.

Shop slots that are checks with "Shop Checks":
    LOCATIONS = {name: (code, shop key, slot, vanilla item id)}
    SHOPS = {shop key: (display name, town, town script, stock case, slots)}

code    the location's AP code (AP id = 2326528 + code)
slot    the slot's place in the shop's list, from 1
"""

'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + "LOCATIONS = {\n" + "\n".join(lines) + "\n}\n\nSHOPS = {\n"
                + "\n".join(shop_lines) + "\n}\n")
    return len(lines)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "list":
        import ffcc_items
        for key, items in vanilla_stock(sys.argv[2]).items():
            print(f"{SHOPS[key][0]} ({len(items)}): " + ", ".join(ffcc_items.NAMES.get(i, hex(i)) for i in items))
    elif len(sys.argv) == 4 and sys.argv[1] == "export":
        print(f"wrote {export(sys.argv[2], sys.argv[3])} shop slots to {sys.argv[3]}")
    else:
        print(__doc__)
