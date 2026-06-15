"""
customitem.py - add a custom item to an FFCC ISO by repurposing an unused slot.

No table resize is needed - the game has many unused/placeholder item slots
("Extra N"). Adding an item is four edits, all in fixed-size files:

  1. Definition (stats/type/model/price): copy a DONOR item's param.cfd record
     into the slot, then set the price. Behaviour + 3D model + menu icon come
     from the donor's record, so the new item looks/acts like the donor.
  2. Name: write into the slot's entry in c_system.cfd's name table - a flat,
     id-ordered list of 5 null-terminated strings per item
     [singular, "", plural, Title, article] starting at file offset 0x6f. The
     Title is what menus/shops show. Edits stay in place (same byte span) so the
     file size never changes; that caps the new name's length to the slot's span.
  3. (tooling) register the id in ffcc_items.NAMES and drop it from
     randomizer.EXCLUDE so the randomizer/editor/spoiler carry it - printed as a
     reminder (not auto-applied, to avoid touching source).
  4. (optional) place it in a shop or a dungeon's first chest for testing.

Usage:
  py customitem.py list-free "copy.iso"                 # repurposable slots
  py customitem.py show      "copy.iso" 0x162
  py customitem.py add       "copy.iso" 0x162 "AP Item" --like Gold --gil 10
                             [--article the] [--shop village_0] [--chest river]

ALWAYS run on a COPY - this edits the ISO in place.
"""

import argparse
import os
import re
import struct
import sys
import tempfile

import gciso
import items as itemstats
import ffcc_items as fi

NAME_TABLE_START = 0x6f       # offset of item id 1's name in c_system.cfd
FORMS = 5                     # null-terminated strings per item


# --------------------------------------------------------------------------- #
# file helpers
# --------------------------------------------------------------------------- #
def _disc(iso, suffix):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
    return next((p for p, _, _ in files if p.endswith(suffix)), None)


def _read(iso, disc):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, disc)[0]
        f.seek(off)
        return off, size, f.read(size)


def _write(iso, disc, data):
    off, size, _ = _read(iso, disc)
    if len(data) != size:
        raise ValueError(f"{disc}: size changed ({len(data)} != {size}); refusing to inject")
    with open(iso, "r+b") as f:
        f.seek(off)
        f.write(data)


def _resolve(donor):
    """Donor item name or id-string -> id."""
    if isinstance(donor, int):
        return donor
    try:
        return int(donor, 0)
    except ValueError:
        hit = [v for v in range(1, 0x4b5) if fi.name(v) == donor]
        if not hit:
            raise SystemExit(f"no item named {donor!r}")
        return hit[0]


# --------------------------------------------------------------------------- #
# name table
# --------------------------------------------------------------------------- #
def name_slot(cs, item_id):
    """(start, end, [5 strings]) for item_id's entry in the c_system name table."""
    pos = NAME_TABLE_START
    for _ in range(item_id - 1):
        for _ in range(FORMS):
            pos = cs.index(b"\x00", pos) + 1
    start = pos
    strs = []
    for _ in range(FORMS):
        e = cs.index(b"\x00", pos)
        strs.append(cs[pos:e])
        pos = e + 1
    return start, pos, [s.decode("ascii", "replace") for s in strs]


def _pack_name(span, name, article):
    """Pack [singular, "", plural, Title, article] into exactly `span` bytes."""
    title = name
    singular = name.lower()
    plural = singular + "s"
    forms = [singular, "", plural, title, article]
    need = sum(len(s) + 1 for s in forms)
    if need > span:
        raise SystemExit(f"name too long for this slot: needs {need} bytes, slot has "
                         f"{span}. Pick a shorter name or a slot with a longer placeholder.")
    forms[2] = plural + " " * (span - need)        # pad the (rarely-seen) plural form
    out = b"".join(s.encode("ascii") + b"\x00" for s in forms)
    assert len(out) == span, (len(out), span)
    return out


def set_item_name(iso, item_id, name, article="the"):
    disc = _disc(iso, "c_system.cfd")
    _, _, cs = _read(iso, disc)
    start, end, old = name_slot(cs, item_id)
    new = _pack_name(end - start, name, article)
    cs = cs[:start] + new + cs[end:]
    _write(iso, disc, cs)
    return old, name


# --------------------------------------------------------------------------- #
# description / help text (c_system.cfd)
# --------------------------------------------------------------------------- #
# Item descriptions are a positional table in c_system.cfd: entry N (the Nth
# `FF A1 00` marker) is item id (N - 500)'s help text. Each entry is exactly 3
# display lines: FF A1 00 <line1> FF A0 00 <line2> FF A0 00 <line3>. The table
# is looked up by counting markers, so the marker COUNT must never change - but
# a line's text length may. To grow one item's text without resizing the
# (fixed-size) file, we "borrow" bytes from a nearby UNUSED placeholder entry
# (its "Help Message" text is shortened to spaces). File size stays identical.
DESC_ITEM0 = 500              # entry index of item id 0's description


def _desc_starts(cs):
    return [m.start() for m in re.finditer(rb"\xff\xa1\x00", cs)]


def _desc_line1(cs, starts, idx):
    s, e = starts[idx], starts[idx + 1]
    b = cs[s + 3:e]
    j = b.find(b"\xff")
    return b[:(j if j >= 0 else len(b))].decode("ascii", "replace")


def _mk_desc(lines):
    """Pack 3 display lines into an entry (FF A1 00 l1 FF A0 00 l2 FF A0 00 l3)."""
    a, b, c = (lines + ["", "", ""])[:3]
    return (b"\xff\xa1\x00" + a.encode("ascii")
            + b"\xff\xa0\x00" + b.encode("ascii")
            + b"\xff\xa0\x00" + c.encode("ascii"))


def set_item_description(iso, item_id, text, donor_id=None):
    """Set an item's in-game description, keeping c_system.cfd the same size by
    borrowing bytes from an unused placeholder ("Help Message") entry after it.
    `donor_id` forces a specific donor slot; None auto-picks the nearest one with
    enough room. Idempotent. `text` may be a string or a list of up to 3 lines."""
    disc = _disc(iso, "c_system.cfd")
    _, _, raw = _read(iso, disc)
    cs = bytearray(raw)
    starts = _desc_starts(cs)
    ai = DESC_ITEM0 + item_id
    lines = text if isinstance(text, list) else [text]
    if _desc_line1(cs, starts, ai) == lines[0]:
        return False                                   # already set - idempotent
    new_ap = _mk_desc(lines)
    grow = len(new_ap) - (starts[ai + 1] - starts[ai])     # extra bytes AP needs
    if donor_id is not None:
        di = DESC_ITEM0 + donor_id
        if not (ai + 1 <= di < len(starts) - 1):
            raise SystemExit("description donor slot out of range")
    else:                                              # auto: nearest unused slot
        di = next((j for j in range(ai + 1, len(starts) - 1)
                   if _desc_line1(cs, starts, j) == "Help Message"
                   and (starts[j + 1] - starts[j] - 9) >= grow), None)
        if di is None:
            raise SystemExit(f"description '{lines[0]}' too long: no unused slot with "
                             f"{grow} spare bytes nearby")
    s_ap, s_mid, s_donor, s_after = starts[ai], starts[ai + 1], starts[di], starts[di + 1]
    mid = bytes(cs[s_mid:s_donor])                     # untouched entries in between
    pad = (s_after - s_ap) - (len(new_ap) + len(mid) + 9)   # 9 = donor's 3 markers
    if pad < 0:
        raise SystemExit(f"description '{lines[0]}' too long to fit by borrowing slot "
                         f"0x{di - DESC_ITEM0:x} ({-pad} bytes over)")
    new_span = new_ap + mid + _mk_desc([" " * pad])
    assert len(new_span) == s_after - s_ap
    cs[s_ap:s_after] = new_span
    _write(iso, disc, bytes(cs))
    return True


# --------------------------------------------------------------------------- #
# definition (param.cfd)
# --------------------------------------------------------------------------- #
def set_item_def(iso, slot_id, donor_id, gil=None, model=None):
    """Copy the donor's param.cfd record into the slot. `gil` overrides the price;
    `model` (an int) overrides the 3D model id (the donor's is used otherwise)."""
    disc = _disc(iso, "param.cfd")
    _, _, data = _read(iso, disc)
    data = bytearray(data)
    base = itemstats.find_base(data)
    E = itemstats.ENTRY
    rec = bytearray(data[base + donor_id * E: base + donor_id * E + E])  # copy donor
    if gil is not None:
        goff, gsz = itemstats.FIELDS["gil"]
        rec[goff:goff + gsz] = int(gil).to_bytes(gsz, "big")
    if model is not None:
        rec[2:4] = int(model).to_bytes(2, "big")       # model field @0x02:2
    data[base + slot_id * E: base + slot_id * E + E] = rec
    _write(iso, disc, bytes(data))
    return struct.unpack(">H", rec[2:4])[0]


# --------------------------------------------------------------------------- #
# model retexture / recolor
# --------------------------------------------------------------------------- #
# The game loads models from packed dvd/mrg/*.mrg archives, but each model's
# texture is stored there byte-identically to its loose dvd/char/.../<m>_root.tex.
# So to recolor a model we re-encode its loose .tex from a PNG (same byte size,
# tex.py round-trips exactly) and byte-replace the ORIGINAL texture wherever it
# appears - loose file + every .mrg - all in place, no FST/size changes.
# NOTE: many items share one model (e.g. all 64 crafting materials use model
# 0x37), so recoloring a shared model recolors every item that uses it. Override
# the model id first if you want a recolor that affects only your item.
def _model_tex_disc(iso, model_id, prefix="f"):
    """Find a model's loose texture file (e.g. f055_root.tex) in the ISO. Tries
    the given prefix first, then the other char-group prefixes."""
    for pre in [prefix] + [p for p in ("f", "w", "m", "l", "n", "c") if p != prefix]:
        disc = _disc(iso, f"{pre}{model_id:03d}_root.tex")
        if disc:
            return disc
    return None


def _replace_bytes_in_iso(iso, old, new):
    """Overwrite every occurrence of `old` with `new` (must be equal length) in
    the ISO, in place. Returns the number of locations patched."""
    if len(old) != len(new):
        raise ValueError("replacement must be the same length")
    data = open(iso, "rb").read()
    positions, i = [], 0
    while True:
        j = data.find(old, i)
        if j < 0:
            break
        positions.append(j)
        i = j + len(old)
    if positions:
        with open(iso, "r+b") as f:
            for j in positions:
                f.seek(j)
                f.write(new)
    return len(positions)


def retexture_model(iso, model_id, png_path, prefix="f"):
    """Recolor a model's texture from `png_path`, replacing it everywhere it is
    used (loose char file + every .mrg), in place. The PNG is resized to each of
    the model's texture dimensions; the re-encoded .tex must match the original
    byte size (tex.py round-trips exactly). Returns (locations_patched, size)."""
    import glob
    import tex
    from PIL import Image
    disc = _model_tex_disc(iso, model_id, prefix)
    if not disc:
        raise SystemExit(f"no model texture for model 0x{model_id:x} "
                         f"(looked for <prefix>{model_id:03d}_root.tex)")
    _, _, orig = _read(iso, disc)
    tmpd = tempfile.mkdtemp(prefix="retex_")
    texp = os.path.join(tmpd, "m.tex")
    open(texp, "wb").write(orig)
    pngdir = os.path.join(tmpd, "png")
    tex.export_tex(texp, pngdir)
    user = Image.open(png_path).convert("RGBA")
    for p in glob.glob(os.path.join(pngdir, "*.png")):
        w, h = Image.open(p).size
        user.resize((w, h), Image.LANCZOS).save(p)
    outp = os.path.join(tmpd, "out.tex")
    tex.import_tex(texp, pngdir, outp)
    new = open(outp, "rb").read()
    if len(new) != len(orig):
        raise SystemExit(f"retexture changed the .tex size ({len(new)} != {len(orig)}); "
                         "cannot inject without resizing")
    return _replace_bytes_in_iso(iso, orig, new), len(orig)


# --------------------------------------------------------------------------- #
# optional placement
# --------------------------------------------------------------------------- #
def place_in_shop(iso, base_name, item_id):
    import shops
    disc = _disc(iso, base_name + ".cft")
    if not disc:
        raise SystemExit(f"no shop cft {base_name!r} in ISO")
    off, size, data = _read(iso, disc)
    tmp = os.path.join(tempfile.gettempdir(), "ci_" + os.path.basename(disc))
    with open(tmp, "wb") as f:
        f.write(data)
    slots = shops.find_shop_items(tmp, valid=lambda v: 1 <= v <= 0x1ed)
    if not slots:
        raise SystemExit(f"no shop slots found in {base_name}")
    shops.apply_edits(tmp, {slots[0][0]: item_id})
    _write(iso, disc, open(tmp, "rb").read())
    return slots[0][1]


def place_in_chest(iso, script, item_id):
    import lootcft
    import randomizer as r
    import game8_chests as g8
    disc = _disc(iso, script + "_0.cft")
    if not disc:
        raise SystemExit(f"no {script}_0.cft in ISO")
    off, size, data = _read(iso, disc)
    tmp = os.path.join(tempfile.gettempdir(), "ci_" + os.path.basename(disc))
    with open(tmp, "wb") as f:
        f.write(data)
    sets = lootcft.find_sets(tmp, valid=r.is_item)
    dungeon = g8.SCRIPT_TO_DUNGEON.get(script)
    cmap = g8.label_sets([[v for _, v in s] for s in sets], dungeon) if dungeon else {}
    chest1 = next((si for si, cn in sorted(cmap.items(), key=lambda kv: kv[1])), 0)
    edits = {o: item_id for o, _ in sets[chest1]}
    lootcft.apply_edits(tmp, edits)
    _write(iso, disc, open(tmp, "rb").read())
    return chest1, len(edits)


# --------------------------------------------------------------------------- #
# high-level
# --------------------------------------------------------------------------- #
def add_custom_item(iso, slot_id, name, donor, gil=None, article="the",
                    shop=None, chest=None, description=None, model=None,
                    retexture=None):
    donor_id = _resolve(donor)
    # validate the name FITS the slot before writing anything (no partial edits)
    _, _, cs = _read(iso, _disc(iso, "c_system.cfd"))
    start, end, _ = name_slot(cs, slot_id)
    _pack_name(end - start, name, article)             # raises if too long
    model = set_item_def(iso, slot_id, donor_id, gil, model)
    old, _ = set_item_name(iso, slot_id, name, article)
    out = {"id": slot_id, "name": name, "donor": fi.name(donor_id),
           "model": model, "gil": gil, "old_name": old[3], "placed": [],
           "desc": None, "retex": None}
    if description and description.strip():
        set_item_description(iso, slot_id, description.strip())
        out["desc"] = description.strip()
    if retexture and str(retexture).strip():
        n, sz = retexture_model(iso, model, str(retexture).strip())
        out["retex"] = f"model 0x{model:x} recolored at {n} location(s)"
    if shop:
        was = place_in_shop(iso, shop, slot_id)
        out["placed"].append(f"shop {shop} slot0 (was {fi.name(was)})")
    if chest:
        ci, n = place_in_chest(iso, chest, slot_id)
        out["placed"].append(f"{chest} chest set {ci} ({n} slots)")
    return out


# --------------------------------------------------------------------------- #
# Archipelago "AP Item" - reproducible auto-install on a clean ISO
# --------------------------------------------------------------------------- #
# So the randomizer can be shipped without a pre-patched ISO: install_ap_item()
# bakes the AP Item into a *copy* of any clean Hacked Rom.iso (definition, name,
# a unique menu-icon cell, and the icon art). Pure-Python edits + injecting the
# two pre-baked icon textures from assets/ (no Pillow/tex.py needed at runtime).
AP_SLOT = 0x162                  # repurposed "Extra 22" slot
AP_NAME = "AP Item"
AP_DONOR = 0x12b                 # Gold (model 0x37, type 0x12a Material, renders fine)
AP_GIL = 10
AP_ARTICLE = "the"
AP_DESC = "An Archipelago Item"        # in-game help/description text
AP_DESC_DONOR = 0x173                  # unused "Extra 24" slot to borrow bytes from
# Gold's icon cell (38) is shared by 64 crafting materials, so we give the AP
# Item its OWN unused cell instead - editing it touches nothing else.
AP_CELL = 39
# dol-relative base of the per-item icon-cell byte table (table[id] = cell).
ICON_TABLE_DOL_OFF = 0x1da684
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _icon_table_base(data):
    """Absolute file offset of the per-item icon-cell table (data[base+id]=cell).
    The .dol lives before the FST; its start is in the disc header at 0x420."""
    dol_off = struct.unpack(">I", data[0x420:0x424])[0]
    return dol_off + ICON_TABLE_DOL_OFF


def get_icon_cell(iso, item_id):
    with open(iso, "rb") as f:
        data = f.read()
    return data[_icon_table_base(data) + item_id]


def set_icon_cell(iso, item_id, cell):
    """Repoint one item's menu/shop icon to a grid cell via a single .dol byte.
    Sanity-checks the table (Gold 0x12b must still read cell 38) before writing."""
    with open(iso, "r+b") as f:
        data = f.read()
        base = _icon_table_base(data)
        if data[base + 0x12b] != 38:
            raise SystemExit("icon-table sanity check failed (Gold != cell 38); "
                             "unexpected ISO/version - refusing to patch icon cell")
        off = base + item_id
        old = data[off]
        f.seek(off)
        f.write(bytes([cell]))
    return old, cell


def _inject_asset_tex(iso, suffix, asset_name):
    """Overwrite a menu texture in the ISO with a pre-baked asset (same byte size).
    Returns False (with a warning) if sizes differ - an unexpected ISO version."""
    disc = _disc(iso, suffix)
    if not disc:
        print(f"  ! {suffix} not in ISO - skipping icon art")
        return False
    off, size, _ = _read(iso, disc)
    payload = open(os.path.join(ASSETS, asset_name), "rb").read()
    if len(payload) != size:
        print(f"  ! {suffix}: ISO size {size} != asset {len(payload)} - skipping icon "
              f"art (unexpected version)")
        return False
    with open(iso, "r+b") as f:
        f.seek(off)
        f.write(payload)
    return True


def is_ap_installed(iso):
    """True if the AP Item is already baked into this ISO (name + icon cell)."""
    try:
        _, _, cs = _read(iso, _disc(iso, "c_system.cfd"))
        _, _, strs = name_slot(cs, AP_SLOT)
        return strs[3] == AP_NAME and get_icon_cell(iso, AP_SLOT) == AP_CELL
    except Exception:
        return False


def install_ap_item(iso, with_icon=True):
    """Bake the AP Item into a (copy of a) clean ISO. Idempotent - safe to re-run.
    Returns a summary dict of the steps performed."""
    out = {"slot": AP_SLOT, "name": AP_NAME, "steps": []}
    out["model"] = set_item_def(iso, AP_SLOT, AP_DONOR, AP_GIL)
    out["steps"].append(f"definition (Gold clone, {AP_GIL} gil)")
    old, _ = set_item_name(iso, AP_SLOT, AP_NAME, AP_ARTICLE)
    out["steps"].append(f"name (was '{old[3]}')")
    if set_item_description(iso, AP_SLOT, AP_DESC, AP_DESC_DONOR):
        out["steps"].append(f"description ('{AP_DESC}')")
    if with_icon:
        oc, _ = set_icon_cell(iso, AP_SLOT, AP_CELL)
        out["steps"].append(f"icon cell {oc} -> {AP_CELL}")
        ok1 = _inject_asset_tex(iso, "shop.tex", "apitem_shop.tex")
        ok2 = _inject_asset_tex(iso, "solo2.tex", "apitem_solo2.tex")
        out["steps"].append(f"icon art (shop.tex={ok1}, solo2.tex={ok2})")
    return out


def ensure_ap_item(iso, with_icon=True):
    """Install the AP Item only if it isn't already present. Returns True if it
    acted, False if it was already installed. Use this from the randomizer/GUI so
    users with a fresh ISO get the AP Item automatically."""
    if is_ap_installed(iso):
        return False
    install_ap_item(iso, with_icon)
    return True


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_list_free(iso):
    disc = _disc(iso, "c_system.cfd")
    _, _, cs = _read(iso, disc)
    print("Repurposable slots (placeholder / empty name, in the collectible range):")
    n = 0
    for v in range(1, 0x1ee):
        try:
            _, _, strs = name_slot(cs, v)
        except ValueError:
            break
        title = strs[3]
        if title == "" or title.lower().startswith("extra"):
            print(f"  0x{v:03x}  name={title!r:14s} category={fi.category(v)}")
            n += 1
    print(f"{n} placeholder slot(s). Each holds a fixed byte span - longer "
          f"placeholders fit longer names.")


def cmd_show(iso, item_id):
    _, _, cs = _read(iso, _disc(iso, "c_system.cfd"))
    start, end, strs = name_slot(cs, item_id)
    _, _, pc = _read(iso, _disc(iso, "param.cfd"))
    base = itemstats.find_base(pc)
    rec = pc[base + item_id * itemstats.ENTRY: base + item_id * itemstats.ENTRY + itemstats.ENTRY]
    g = lambda nm: int.from_bytes(rec[itemstats.FIELDS[nm][0]:
                                      itemstats.FIELDS[nm][0] + itemstats.FIELDS[nm][1]], "big")
    print(f"id 0x{item_id:03x}  name forms {strs}  (slot {end - start} bytes)")
    print(f"  type=0x{g('type'):04x} model=0x{g('model'):04x} gil={g('gil')} "
          f"category={fi.category(item_id)}")


def main():
    p = argparse.ArgumentParser(description="Add a custom item to an FFCC ISO (edit a COPY).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("list-free"); sp.add_argument("iso")
    sp = sub.add_parser("show"); sp.add_argument("iso"); sp.add_argument("id")
    sp = sub.add_parser("install-ap", help="bake the Archipelago AP Item into a COPY of a clean ISO")
    sp.add_argument("iso"); sp.add_argument("--no-icon", action="store_true",
                                            help="skip the menu-icon art (still sets the definition/name)")
    sp = sub.add_parser("add")
    sp.add_argument("iso"); sp.add_argument("id"); sp.add_argument("name")
    sp.add_argument("--like", required=True, help="donor item (name or id) to copy model/behaviour from")
    sp.add_argument("--gil", type=int, help="price (default: keep donor's)")
    sp.add_argument("--article", default="the", help="grammar article (a/an/the); default 'the'")
    sp.add_argument("--desc", help="in-game description / help text")
    sp.add_argument("--model", type=lambda s: int(s, 0),
                    help="override the 3D model id (e.g. 0x37); default copies the donor's")
    sp.add_argument("--retexture", help="recolor the model's texture from this PNG "
                    "(affects every item using that model)")
    sp.add_argument("--shop", help="also place in this shop (base name, e.g. village_0)")
    sp.add_argument("--chest", help="also place in this dungeon's first chest (script, e.g. river)")
    a = p.parse_args()

    if not os.path.isfile(a.iso):
        sys.exit(f"ISO not found: {a.iso}")
    if a.cmd == "list-free":
        cmd_list_free(a.iso)
    elif a.cmd == "show":
        cmd_show(a.iso, int(a.id, 0))
    elif a.cmd == "install-ap":
        info = install_ap_item(a.iso, with_icon=not a.no_icon)
        print(f"Installed '{info['name']}' (0x{info['slot']:03x}, model 0x{info['model']:04x}):")
        for s in info["steps"]:
            print("   -", s)
        print("Place it via the chest JSON import (randomizer.py patch) - it appears "
              "only where the JSON lists it.")
    elif a.cmd == "add":
        slot = int(a.id, 0)
        info = add_custom_item(a.iso, slot, a.name, a.like, a.gil, a.article, a.shop,
                               a.chest, a.desc, a.model, a.retexture)
        print(f"Added 0x{slot:03x} '{info['name']}' (was '{info['old_name']}') - "
              f"model 0x{info['model']:04x} from {info['donor']}, "
              f"gil={info['gil'] if info['gil'] is not None else 'donor'}")
        if info.get("desc"):
            print(f"  description: {info['desc']!r}")
        if info.get("retex"):
            print("  retexture:", info["retex"])
        for pl in info["placed"]:
            print("  placed in", pl)
        print(f"Tooling: to have the randomizer/editor carry it, add "
              f'`NAMES[0x{slot:03x}] = \"{info["name"]}\"` to ffcc_items.py and remove '
              f"0x{slot:03x} from randomizer.EXCLUDE (if listed).")


if __name__ == "__main__":
    main()
