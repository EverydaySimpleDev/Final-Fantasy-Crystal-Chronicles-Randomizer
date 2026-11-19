"""
gbanames.py - Give the GBA the names of the randomizer's new items.

In multiplayer each player's GBA shows their items, and the GBA program
(dvd/gba/ffcc_cli.bin) has its own item name table instead of reading
c_system.cfd. The slots the randomizer turns into new items (AP Item, the
stage keys, the extra spell rings) still have their placeholder names there,
so a GBA shows "Extra 22" for an AP Item and "Equip. 201" for a Gravity Ring.

This copies the name of every such item from c_system.cfd into the GBA
program: the new names go after the end of the program, and the item's entry
in the table points to them. The GBA loads the program at 0x02000000, and
nothing uses the memory between its end and the GBA's download area
(0x02034000), which the GameCube also can't send more than 0x30000 bytes of.

Run it after every patch that adds or renames items.

Usage:
    py gbanames.py apply <game.iso>
"""

import re
import struct
import sys

import customitem
import gciso

GBA_FILE = "dvd/gba/ffcc_cli.bin"
LOAD_ADDRESS = 0x02000000
NAME_TABLE = 0x29C10            # gItemNames_En in the US program
NAME_COUNT = 501
ORIGINAL_SIZE = 188504
MAX_SIZE = 0x30000              # the GameCube's buffer for the program
MAX_NAME = 15                   # the longest name the GBA's own table has
# the names the game's unused slots have on the GBA
PLACEHOLDER = re.compile(r"(Extra|Equip\.|Test) \d+$")
# start of the added names, so a second run can replace them
MARKER = b"AP names\0\0\0\0"


def _read_file(iso, path):
    with open(iso, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, path)[0]
        f.seek(off)
        return f.read(size)


def _c_system_titles(iso):
    """{item id: title} from c_system.cfd for ids 1 to NAME_COUNT - 1."""
    cs = _read_file(iso, customitem._disc(iso, "c_system.cfd"))
    titles, pos = {}, customitem.NAME_TABLE_START
    for item_id in range(1, NAME_COUNT):
        forms = []
        for _ in range(customitem.FORMS):
            end = cs.index(b"\0", pos)
            forms.append(cs[pos:end])
            pos = end + 1
        titles[item_id] = forms[3].decode("ascii", "replace")
    return titles


def _gba_name(image, pointer):
    start = pointer - LOAD_ADDRESS
    return image[start:image.index(b"\0", start)].decode("latin1")


def new_names(iso, image):
    """{item id: name} for the GBA placeholders that are real items on the disc."""
    pointers = struct.unpack_from(f"<{NAME_COUNT}I", image, NAME_TABLE)
    out = {}
    for item_id, title in _c_system_titles(iso).items():
        old = _gba_name(image, pointers[item_id])
        if (PLACEHOLDER.match(old) and title and title != old
                and not title.lower().startswith(("extra", "equip"))):
            out[item_id] = title[:MAX_NAME]
    return out


def _block(image, names, start):
    """The names block placed at `start` in `image`: the marker, the number of
    names and the block's length, (item id, old pointer) for each name, then
    the names. Also points the table at the names."""
    head = len(MARKER) + 4 + 8 * len(names)
    body, pointers = b"", {}
    for item_id, name in sorted(names.items()):
        pointers[item_id] = LOAD_ADDRESS + start + head + len(body)
        body += name.encode("ascii") + b"\0"
    length = head + len(body)
    length += -length % 4
    block = MARKER + struct.pack("<HH", len(names), length)
    for item_id in sorted(names):
        block += struct.pack("<II", item_id, struct.unpack_from("<I", image, NAME_TABLE + 4 * item_id)[0])
        struct.pack_into("<I", image, NAME_TABLE + 4 * item_id, pointers[item_id])
    return (block + body).ljust(length, b"\0")


def apply(iso, log=print):
    """Copy the new item names into the GBA program. Returns the names set."""
    image = bytearray(_read_file(iso, GBA_FILE))
    if (len(image) < ORIGINAL_SIZE
            or _gba_name(image, struct.unpack_from("<I", image, NAME_TABLE)[0]) != "DUMMY-US"):
        raise ValueError("this isn't the US GBA program the patch knows")
    at = image.find(MARKER, ORIGINAL_SIZE - 4)
    room = None                     # where the names can go: (offset, size or None = to the end)
    if at >= 0:
        # a second run: point the table back at the placeholders, which the
        # first run listed after the marker as (item id, old pointer), and
        # clear the old block. Code added after it (gbaloot) stays where it is.
        count, length = struct.unpack_from("<HH", image, at + len(MARKER))
        for n in range(count):
            item_id, pointer = struct.unpack_from("<II", image, at + len(MARKER) + 4 + 8 * n)
            struct.pack_into("<I", image, NAME_TABLE + 4 * item_id, pointer)
        image[at:at + length] = bytes(length)
        if any(image[at + length:]):
            room = (at, length)
        else:
            del image[at:]
    names = new_names(iso, image)
    if names:
        if room and len(_block(bytearray(image), names, room[0])) <= room[1]:
            start = room[0]
        else:
            image += b"\0" * (-len(image) % 4)
            start = len(image)
        block = _block(image, names, start)
        image[start:start + len(block)] = block
    if len(image) > MAX_SIZE:
        raise ValueError("the GBA program would be too big")
    if names or at >= 0:
        gciso.put_file(iso, GBA_FILE, bytes(image))
    for item_id, name in sorted(names.items()):
        log(f"  GBA name 0x{item_id:03x}: {name}")
    return names


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "apply":
        if not apply(sys.argv[2]):
            print("no new item names to give the GBA")
    else:
        print(__doc__)
