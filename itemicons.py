"""
itemicons.py - Export the game's 2D item icons as PNG images.

The menus draw every item with a 32x32 cell of the icon_gc texture
(dvd/menu/shop.tex, 256x160 = 8 x 5 cells), at full brightness
(CMenuPcs::DrawSingleIcon). Which cell an item uses is one byte per item id in
Start.dol: gSingMenuItemIconByType, at customitem.ICON_TABLE_DOL_OFF.

icon_gc's format byte says IA4, but like the title logo (see titlelogo.py) it
is a 256-colour palette image: a 1024-byte PALT ((G, R) per colour, then
(A, B) per colour) and one index byte per pixel in 8x4 tiles. Decoded that
way the icons come out in their real colours.

One image is written per cell (cellNN.png, items that look the same share
one), plus item_icons.json mapping each item id (as "0x09f") to its image.

Usage:
    py itemicons.py export <game.iso> <out_dir> [item ids...]
        (no ids: every item a chest or the bonus screen can give)
"""

import json
import os
import struct
import sys

import customitem
import gciso
import titlelogo

CELL = 32
COLUMNS = 8
TEXTURE = b"icon_gc"


def _atlas(iso):
    """The icon_gc texture, decoded through its palette, as an RGBA image."""
    from PIL import Image
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, "dvd/menu/shop.tex")[0]
        f.seek(off)
        data = f.read(size)

    def find(start, end):
        for kind, at, length in titlelogo._chunks(data, start, end):
            if kind in (b"TEX ", b"SCEN", b"TSET"):
                hit = find(at, at + length)
                if hit:
                    return hit
            elif kind == b"TXTR":
                parts = {k: (o, s) for k, o, s in titlelogo._chunks(data, at, at + length)}
                name_at, name_len = parts[b"NAME"]
                if data[name_at:name_at + name_len].rstrip(b"\0") == TEXTURE:
                    return parts
        return None

    parts = find(0, len(data))
    if parts is None or b"PALT" not in parts:
        raise ValueError("icon_gc with a palette not found in shop.tex")
    width, height = struct.unpack(">II", data[parts[b"SIZE"][0]:parts[b"SIZE"][0] + 8])
    palette = data[parts[b"PALT"][0]:parts[b"PALT"][0] + 1024]
    colours = [(palette[2 * k + 1], palette[2 * k], palette[512 + 2 * k + 1], palette[512 + 2 * k])
               for k in range(256)]
    image = Image.new("RGBA", (width, height))
    pixels, at = image.load(), parts[b"IMAG"][0]
    for tile_y in range(0, height, 4):
        for tile_x in range(0, width, 8):
            for dy in range(4):
                for dx in range(8):
                    pixels[tile_x + dx, tile_y + dy] = colours[data[at]]
                    at += 1
    return image


def export(iso, out_dir, ids=None):
    """Write the icon images and item_icons.json to `out_dir`. Returns the
    {item id: file name} map."""
    import randomizer
    if ids is None:
        ids = randomizer.build_pool("all")
    with open(iso, "rb") as f:
        data = f.read()
    table = customitem._icon_table_base(data)
    atlas = _atlas(iso)
    os.makedirs(out_dir, exist_ok=True)
    mapping, written = {}, set()
    for item_id in ids:
        cell = data[table + item_id]
        name = f"cell{cell:02d}.png"
        if name not in written:
            x, y = cell % COLUMNS * CELL, cell // COLUMNS * CELL
            atlas.crop((x, y, x + CELL, y + CELL)).save(os.path.join(out_dir, name))
            written.add(name)
        mapping[f"0x{item_id:03x}"] = name
    with open(os.path.join(out_dir, "item_icons.json"), "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=1, sort_keys=True)
    return mapping


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "export":
        ids = [int(v, 0) for v in sys.argv[4:]] or None
        mapping = export(sys.argv[2], sys.argv[3], ids)
        print(f"wrote {len(set(mapping.values()))} image(s) for {len(mapping)} item(s) to {sys.argv[3]}")
    else:
        print(__doc__)
