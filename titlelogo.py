"""
titlelogo.py - Put the Archipelago logo on the title screen, and the
Archipelago name, banner and description on the disc (what Dolphin's game
list and properties show).

Title screen:
The title screen logo is texture cc_logo01 in dvd/menu/cc_logo.tex. Its FMT
says IA4, but the game draws it as an 8-bit palette image: each pixel byte is
an index into the texture's own 256-colour PALT block. PALT is 1024 bytes:
    bytes   0-511  (G, R) per colour
    bytes 512-1023 (A, B) per colour
and IMAG holds one index byte per pixel in 8x4 tiles (left to right, then top
to bottom, 8 pixels across x 4 down inside each tile). So any image with 256
colours or fewer, transparency included, can replace it at the same size.

Disc:
The disc header's game name is at 0x20. opening.bnr (BNR1) holds the 96x32
banner as RGB5A3 in 4x4 tiles at 0x20, then the text at 0x1820: short name
(32 bytes), short maker (32), long name (64), long maker (64), description
(128). The game ID (GCCE01) stays as it is: the AP client, save files and
Dolphin's per-game settings all go by it, and its "01" is the maker Dolphin
shows under Game Details.

The patcher writes assets/title_logo.bin (the 1024-byte palette followed by
the 576x224 index data) and assets/banner.bin (the banner image) into the ISO,
so it needs no Pillow at run time. Rebuild both from a PNG with `build`.

Usage:
    py titlelogo.py build   <logo.png>
    py titlelogo.py install <game.iso> [player] [seed]
    py titlelogo.py preview <game.iso | file.tex> <out.png>
"""

import os
import struct
import sys

import gciso

DISC = "dvd/menu/cc_logo.tex"
TEXTURE = b"cc_logo01"
WIDTH, HEIGHT = 576, 224
PALETTE_SIZE = 1024
IMAGE_SIZE = WIDTH * HEIGHT
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
ASSET = os.path.join(ASSETS, "title_logo.bin")
BANNER_ASSET = os.path.join(ASSETS, "banner.bin")

BANNER_DISC = "opening.bnr"
BANNER_W, BANNER_H = 96, 32
BANNER_IMAGE = 0x20
BANNER_TEXT = 0x1820
HEADER_NAME = 0x20                 # disc header game name, 0x3E0 bytes

HEADER_NAME_SIZE = 0x3E0
MAKER = "EverydaySimpleDev"


def _fit(size, before, player="", after=""):
    """before + player + after as latin-1 bytes that fit in a `size`-byte
    field with its closing zero. A long player name is shortened first; any
    character the banner font can't show becomes '?'."""
    def encode(name):
        return (before + name + after).encode("latin-1", errors="replace")
    name = player
    while len(encode(name)) >= size and name:
        name = name[:-1]
    return encode(name)[:size - 1]


def texts(player=None, seed=None):
    """(disc name, [short name, short maker, long name, long maker,
    description]) as bytes fitted to their fields. With a player they name
    the AP slot and seed, with only a seed the randomizer seed, and
    otherwise just the game."""
    if player:
        fields = [
            (HEADER_NAME_SIZE, "FINAL FANTASY Crystal Chronicles Archipelago: ", player, f" ({seed})"),
            (32, "FFCC AP: ", player),
            (32, MAKER),
            (64, "FFCC Archipelago: ", player, f" ({seed})"),
            (64, MAKER),
            (128, "Archipelago randomizer\nPlayer: ", player, f"  Seed: {seed}"),
        ]
    elif seed is not None:
        fields = [
            (HEADER_NAME_SIZE, f"FINAL FANTASY Crystal Chronicles Randomizer (seed {seed})"),
            (32, "FFCC Randomizer"),
            (32, MAKER),
            (64, f"FFCC Randomizer (seed {seed})"),
            (64, MAKER),
            (128, f"FINAL FANTASY Crystal Chronicles\nrandomizer, seed {seed}"),
        ]
    else:
        fields = [
            (HEADER_NAME_SIZE, "FINAL FANTASY Crystal Chronicles Archipelago"),
            (32, "FFCC Archipelago"),
            (32, MAKER),
            (64, "FINAL FANTASY Crystal Chronicles Archipelago"),
            (64, MAKER),
            (128, "Archipelago multiworld randomizer\nfor FINAL FANTASY Crystal Chronicles."),
        ]
    fitted = [_fit(*f) for f in fields]
    return fitted[0], fitted[1:]


def _chunks(data, start, end):
    """(type, payload offset, payload size) of the chunks in data[start:end]:
    a 16-byte header (type, u32 size, 8 bytes padding), then the payload,
    padded to 16 bytes."""
    off = start
    while off + 16 <= end:
        kind = data[off:off + 4]
        size = struct.unpack(">I", data[off + 4:off + 8])[0]
        yield kind, off + 16, size
        off += 16 + (size + 15) // 16 * 16


def find_logo(tex):
    """(palette offset, image offset) of cc_logo01 inside a cc_logo.tex."""
    def walk(start, end):
        for kind, off, size in _chunks(tex, start, end):
            if kind in (b"TEX ", b"SCEN", b"TSET"):
                hit = walk(off, off + size)
                if hit:
                    return hit
            elif kind == b"TXTR":
                parts = {k: (o, s) for k, o, s in _chunks(tex, off, off + size)}
                name = tex[parts[b"NAME"][0]:parts[b"NAME"][0] + parts[b"NAME"][1]].rstrip(b"\0")
                if name != TEXTURE:
                    continue
                w, h = struct.unpack(">II", tex[parts[b"SIZE"][0]:parts[b"SIZE"][0] + 8])
                if (w, h) != (WIDTH, HEIGHT) or parts[b"PALT"][1] != PALETTE_SIZE \
                        or parts[b"IMAG"][1] != IMAGE_SIZE:
                    raise ValueError("cc_logo01 isn't the expected 576x224 palette texture")
                return parts[b"PALT"][0], parts[b"IMAG"][0]
        return None

    hit = walk(0, len(tex))
    if hit is None:
        raise ValueError("cc_logo01 not found in cc_logo.tex")
    return hit


def _write(f, off, data):
    """Write data at off unless it's already there. True if it wrote."""
    f.seek(off)
    if f.read(len(data)) == data:
        return False
    f.seek(off)
    f.write(data)
    return True


def _banner_text(fields):
    out = bytearray()
    for raw, size in zip(fields, (32, 32, 64, 64, 128)):
        out += raw + bytes(size - len(raw))
    return bytes(out)


def install(iso, player=None, seed=None, asset=ASSET, banner=BANNER_ASSET):
    """Write the title logo, the banner image and text, and the disc name
    into the ISO; the names show `player` and `seed` when given (see texts).
    Returns True if it changed anything, False if the ISO already has it all."""
    logo = open(asset, "rb").read()
    if len(logo) != PALETTE_SIZE + IMAGE_SIZE:
        raise ValueError(f"{asset} should be {PALETTE_SIZE + IMAGE_SIZE} bytes")
    image = open(banner, "rb").read()
    if len(image) != BANNER_W * BANNER_H * 2:
        raise ValueError(f"{banner} should be {BANNER_W * BANNER_H * 2} bytes")
    name, fields = texts(player, seed)
    changed = False
    with open(iso, "r+b") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, DISC)[0]
        f.seek(off)
        pal, img = find_logo(f.read(size))
        changed |= _write(f, off + pal, logo[:PALETTE_SIZE])
        changed |= _write(f, off + img, logo[PALETTE_SIZE:])

        _, off, size = gciso.find_file(files, BANNER_DISC)[0]
        f.seek(off)
        if f.read(4) != b"BNR1" or size < BANNER_TEXT + 320:
            raise ValueError("opening.bnr isn't the expected BNR1 banner")
        changed |= _write(f, off + BANNER_IMAGE, image)
        changed |= _write(f, off + BANNER_TEXT, _banner_text(fields))

        changed |= _write(f, HEADER_NAME, name + bytes(HEADER_NAME_SIZE - len(name)))
    return changed


# Building and previewing need Pillow; installing doesn't.

def build(png, out=ASSET):
    """Fit a PNG into 576x224 (centred, aspect kept), reduce it to 256
    colours with transparency and write the palette + index data."""
    from PIL import Image
    src = Image.open(png).convert("RGBA")
    scale = min(WIDTH / src.width, HEIGHT / src.height)
    fitted = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    img.paste(fitted, ((WIDTH - fitted.width) // 2, (HEIGHT - fitted.height) // 2))
    # nearly see-through pixels all share one clear colour
    px = img.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if px[x, y][3] < 8:
                px[x, y] = (0, 0, 0, 0)
    q = img.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    colours = (q.getpalette("RGBA") or [])[:1024]
    colours += [0] * (1024 - len(colours))
    gr, ab = bytearray(), bytearray()
    for k in range(256):
        r, g, b, a = colours[4 * k:4 * k + 4]
        gr += bytes((g, r))
        ab += bytes((a, b))
    idx = q.load()
    data = bytearray()
    for ty in range(0, HEIGHT, 4):
        for tx in range(0, WIDTH, 8):
            for dy in range(4):
                for dx in range(8):
                    data.append(idx[tx + dx, ty + dy])
    with open(out, "wb") as f:
        f.write(bytes(gr + ab + data))


def banner_image(png):
    """The 96x32 banner: the logo fitted onto a white background that fades
    to light blue at the bottom, like the original banner."""
    from PIL import Image
    src = Image.open(png).convert("RGBA")
    src = src.crop(src.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox())
    scale = min((BANNER_W - 2) / src.width, (BANNER_H - 2) / src.height)
    fitted = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    img = Image.new("RGBA", (BANNER_W, BANNER_H))
    for y in range(BANNER_H):
        t = y / (BANNER_H - 1)
        for x in range(BANNER_W):
            img.putpixel((x, y), (round(255 - 40 * t), round(255 - 25 * t), 255, 255))
    img.alpha_composite(fitted, ((BANNER_W - fitted.width) // 2, (BANNER_H - fitted.height) // 2))
    return img


def build_banner(png, out=BANNER_ASSET):
    """Write the banner image as opaque RGB5A3 in 4x4 tiles."""
    px = banner_image(png).load()
    data = bytearray()
    for ty in range(0, BANNER_H, 4):
        for tx in range(0, BANNER_W, 4):
            for dy in range(4):
                for dx in range(4):
                    r, g, b, _ = px[tx + dx, ty + dy]
                    data += struct.pack(">H", 0x8000 | (r >> 3) << 10 | (g >> 3) << 5 | b >> 3)
    with open(out, "wb") as f:
        f.write(bytes(data))


def decode(tex):
    """cc_logo01 of a cc_logo.tex as an RGBA image, the way the game draws it."""
    from PIL import Image
    pal_off, img_off = find_logo(tex)
    p = tex[pal_off:pal_off + PALETTE_SIZE]
    colours = [(p[2 * k + 1], p[2 * k], p[512 + 2 * k + 1], p[512 + 2 * k]) for k in range(256)]
    img = Image.new("RGBA", (WIDTH, HEIGHT))
    px = img.load()
    i = img_off
    for ty in range(0, HEIGHT, 4):
        for tx in range(0, WIDTH, 8):
            for dy in range(4):
                for dx in range(8):
                    px[tx + dx, ty + dy] = colours[tex[i]]
                    i += 1
    return img


def _read_tex(path):
    if path.lower().endswith(".tex"):
        return open(path, "rb").read()
    with open(path, "rb") as f:
        _, files = gciso.parse_fst(f)
        _, off, size = gciso.find_file(files, DISC)[0]
        f.seek(off)
        return f.read(size)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        build(sys.argv[2])
        build_banner(sys.argv[2])
        print("wrote", ASSET, "and", BANNER_ASSET)
    elif 3 <= len(sys.argv) <= 5 and sys.argv[1] == "install":
        player = sys.argv[3] if len(sys.argv) > 3 else None
        seed = sys.argv[4] if len(sys.argv) > 4 else None
        print("installed" if install(sys.argv[2], player, seed) else "already installed")
    elif len(sys.argv) == 4 and sys.argv[1] == "preview":
        from PIL import Image
        logo = decode(_read_tex(sys.argv[2]))
        shown = Image.new("RGBA", logo.size, (90, 85, 75, 255))
        shown.alpha_composite(logo)
        shown.save(sys.argv[3])
        print("wrote", sys.argv[3])
    else:
        print(__doc__)
