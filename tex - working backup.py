"""
tex.py - Export and re-import GameCube .tex textures as PNGs.

Usage:
    python tex.py export <file.tex> [output_dir]
    python tex.py import <file.tex> [png_dir] [output.tex]

    # Legacy form (no subcommand) still works and means "export":
    python tex.py <file.tex>

Export reads a .tex, decodes every texture (CMPR / IA4 / I4) and writes one
<name>.png per texture into output_dir (default: the .tex path without ".tex").

Import does the inverse: it re-encodes each matching <name>.png back into the
texture's native GameCube format and patches those bytes directly into a copy
of the original .tex (default output: <file>_repacked.tex).

Because CMPR/IA4/IA8 are fixed-size for given dimensions, re-encoded data is
exactly the same length as the original IMAG block, so it is spliced in place
and every other byte of the file is preserved. Keep replacement PNGs at their
original dimensions (mismatched sizes are resized back to fit, with a warning).

Note: CMPR is lossy block compression, so a re-imported CMPR texture will not
be bit-identical to the original even if the PNG is unchanged. IA4/I4 round
-trip cleanly within their 4-bit precision.
"""

import struct
import sys
import tag
import texture
from PIL import Image
from PIL import ImageFile
import os

ImageFile.LOAD_TRUNCATED_IMAGES = True

# Known FMT bytes (GameCube texture formats used by this game's .tex files)
FMT_CMPR = b"\x06\x01\x01"   # CMPR: 4 bpp block compression (DXT1-like)
FMT_IA4  = b"\x02\x01\x01"   # IA4 : 8 bpp, 4-bit intensity + 4-bit alpha, 8x4 tiles
FMT_I4   = b"\x03\x01\x01"   # I4  : 4 bpp, 4-bit intensity only, 8x8 tiles


class Tex:
    tagtree = None
    texture_set = None
    def __init__(self, root_tag):
        if root_tag.type != b"TEX ":
            raise Exception("File is not a valid TEX file!")
        self.tagtree = root_tag
        self.texture_set = []
        for subtag in self.tagtree.subtags:
            if subtag.type == b"SCEN":
                for tset_tag in subtag.subtags:
                    for txtr_tag in tset_tag.subtags:
                        self.texture_set.append((texture.Texture(txtr_tag), txtr_tag))

    def tex2img(self):
        imgs = []
        for tex_obj, raw_tag in self.texture_set:
            name = getattr(tex_obj, 'name', 'Unknown')
            if isinstance(name, bytes):
                name = name.decode('utf-8', errors='ignore').strip('\x00')

            size_tuple = getattr(tex_obj, 'size', (512, 512))
            if size_tuple and isinstance(size_tuple, tuple) and len(size_tuple) >= 2:
                width, height = size_tuple[0], size_tuple[1]
            else:
                width = getattr(tex_obj, 'width', None) or getattr(tex_obj, 'w', 512)
                height = getattr(tex_obj, 'height', None) or getattr(tex_obj, 'h', 512)

            fmt = getattr(tex_obj, 'fmt', b'') or getattr(tex_obj, 'format', b'')

            tex = None
            try:
                tex = tex_obj.texure2img()
            except Exception:
                pass

            if tex is None or tex.get("data") is None:
                raw_bytes = b""
                for sub in getattr(raw_tag, 'subtags', []):
                    if sub.type in [b"DATA", b"PIXL", b"BODY"]:
                        for key, val in vars(sub).items():
                            if isinstance(val, (bytes, bytearray)) and len(val) > 10:
                                raw_bytes = val
                                break
                    if raw_bytes:
                        break

                if not raw_bytes:
                    for sub in getattr(raw_tag, 'subtags', []):
                        for key, val in vars(sub).items():
                            if isinstance(val, (bytes, bytearray)) and len(val) > len(raw_bytes):
                                raw_bytes = val

                if raw_bytes:
                    tex = {
                        "name": name,
                        "data": raw_bytes,
                        "is_raw": True,
                        "width": width,
                        "height": height,
                        "fmt": fmt
                    }
                else:
                    tex = {"name": name, "data": None}
            else:
                # FIX: If texture.py successfully returned a dictionary but omitted properties, inject them here
                if not isinstance(tex, dict):
                    tex = {"data": tex}
                if "width" not in tex:
                    tex["width"] = width
                if "height" not in tex:
                    tex["height"] = height
                if "fmt" not in tex:
                    tex["fmt"] = fmt
                if "name" not in tex or not tex.get("name"):
                    tex["name"] = name

            imgs.append(tex)
        return imgs


# ---------------------------------------------------------------------------
# GameCube IA decoders (used by export)
# ---------------------------------------------------------------------------

def unswizzle_ia4(data, width, height):
    """Decodes GameCube IA4 (4-bit, 8x4 tile) texture data into linear RGBA."""
    dest = bytearray(width * height * 4)
    offset = 0
    for ty in range(0, height, 4):
        for tx in range(0, width, 8):
            for dy in range(4):
                for dx in range(8):
                    x = tx + dx
                    y = ty + dy
                    if x < width and y < height and offset < len(data):
                        b = data[offset]
                        offset += 1
                        alpha = (b & 0xF0) | (b >> 4)
                        intensity = ((b & 0x0F) << 4) | (b & 0x0F)

                        idx = (y * width + x) * 4
                        dest[idx:idx+4] = [intensity, intensity, intensity, alpha]
    return bytes(dest)

def unswizzle_i4(data, width, height):
    """Decodes GameCube I4 (4-bit intensity, 8x8 tile) texture data into linear
    RGBA. Two pixels share one byte (high nibble = left pixel). Tiles are always
    a full 8x8, so a byte is consumed for every tile position even when it falls
    outside the image bounds."""
    dest = bytearray(width * height * 4)
    offset = 0
    for ty in range(0, height, 8):
        for tx in range(0, width, 8):
            for dy in range(8):
                for dx in range(0, 8, 2):
                    if offset >= len(data):
                        return bytes(dest)
                    byte = data[offset]
                    offset += 1
                    for k, nib in enumerate(((byte >> 4) & 0xF, byte & 0xF)):
                        x = tx + dx + k
                        y = ty + dy
                        if x < width and y < height:
                            v = nib * 17  # expand 4-bit -> 8-bit (0x0->0, 0xF->255)
                            idx = (y * width + x) * 4
                            dest[idx:idx+4] = [v, v, v, 255]
    return bytes(dest)


# ---------------------------------------------------------------------------
# GameCube encoders (used by import) - inverse of the decoders above
# ---------------------------------------------------------------------------

def rgb_to_565(r, g, b):
    r5 = int(round(r * 31.0 / 255.0)) & 0x1F
    g6 = int(round(g * 63.0 / 255.0)) & 0x3F
    b5 = int(round(b * 31.0 / 255.0)) & 0x1F
    return (r5 << 11) | (g6 << 5) | b5


def c565_to_rgb(c):
    r5 = (c >> 11) & 0x1F
    g6 = (c >> 5) & 0x3F
    b5 = c & 0x1F
    return (255.0 / 31 * r5, 255.0 / 63 * g6, 255.0 / 31 * b5)


def encode_cmpr_subtile(texels):
    """texels: 16 (r,g,b,a) tuples in row-major order (y then x).
    Returns the 8-byte sub-tile (>HH color0,color1 + >I packed 2-bit indices),
    matching texture.py's cmpr decoder exactly."""
    has_alpha = any(a < 128 for (_, _, _, a) in texels)
    opaque = [(r, g, b) for (r, g, b, a) in texels if a >= 128]
    if not opaque:
        opaque = [(0, 0, 0)]

    rs = [c[0] for c in opaque]
    gs = [c[1] for c in opaque]
    bs = [c[2] for c in opaque]
    hi = rgb_to_565(max(rs), max(gs), max(bs))
    lo = rgb_to_565(min(rs), min(gs), min(bs))

    if has_alpha:
        # 3-color + transparent mode requires COLOR0 <= COLOR1
        c0, c1 = (lo, hi) if lo <= hi else (hi, lo)
    else:
        # 4-color opaque mode requires COLOR0 > COLOR1
        if hi == lo:
            if lo > 0:
                lo -= 1
            else:
                hi += 1
        c0, c1 = (hi, lo) if hi > lo else (lo, hi)

    rgb0 = c565_to_rgb(c0)
    rgb1 = c565_to_rgb(c1)
    palette = [rgb0, rgb1]
    if c0 > c1:  # 4-color, all opaque
        palette.append(tuple((2 * a + b) / 3 for a, b in zip(rgb0, rgb1)))
        palette.append(tuple((2 * b + a) / 3 for a, b in zip(rgb0, rgb1)))
        transparent_mode = False
    else:        # 3-color + transparent (index 3 = transparent)
        palette.append(tuple((a + b) / 2 for a, b in zip(rgb0, rgb1)))
        palette.append(tuple((2 * b + a) / 3 for a, b in zip(rgb0, rgb1)))
        transparent_mode = True

    word = 0
    for (r, g, b, a) in texels:
        if transparent_mode and a < 128:
            idx = 3
        else:
            n_choices = 3 if transparent_mode else 4
            best, best_d = 0, None
            for i in range(n_choices):
                pr, pg, pb = palette[i]
                d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
                if best_d is None or d < best_d:
                    best_d, best = d, i
            idx = best
        word = (word << 2) | idx

    return struct.pack(">HH", c0, c1) + struct.pack(">I", word)


def encode_cmpr(pixels, width, height):
    out = bytearray()

    def texel(sx, sy):
        sx = min(sx, width - 1)
        sy = min(sy, height - 1)
        return pixels[sy * width + sx]

    for cy in range(0, height, 8):
        for cx in range(0, width, 8):
            for sx_off, sy_off in ((0, 0), (4, 0), (0, 4), (4, 4)):
                texels = []
                for y in range(4):
                    for x in range(4):
                        texels.append(texel(cx + sx_off + x, cy + sy_off + y))
                out += encode_cmpr_subtile(texels)
    return bytes(out)


def encode_ia4(pixels, width, height):
    out = bytearray()
    for ty in range(0, height, 4):
        for tx in range(0, width, 8):
            for dy in range(4):
                for dx in range(8):
                    x, y = tx + dx, ty + dy
                    if x < width and y < height:
                        r, g, b, a = pixels[y * width + x]
                        out.append((a & 0xF0) | (r >> 4))
    return bytes(out)


def encode_i4(pixels, width, height):
    """Inverse of unswizzle_i4. Packs two pixels per byte (high nibble = left
    pixel), emitting a byte for every position in each full 8x8 tile."""
    out = bytearray()
    for ty in range(0, height, 8):
        for tx in range(0, width, 8):
            for dy in range(8):
                for dx in range(0, 8, 2):
                    nibs = []
                    for k in range(2):
                        x, y = tx + dx + k, ty + dy
                        if x < width and y < height:
                            r, g, b, a = pixels[y * width + x]
                            inten = round(0.299 * r + 0.587 * g + 0.114 * b)
                            nibs.append((inten >> 4) & 0xF)
                        else:
                            nibs.append(0)
                    out.append((nibs[0] << 4) | nibs[1])
    return bytes(out)


ENCODERS = {
    FMT_CMPR: ("CMPR", encode_cmpr),
    FMT_IA4:  ("IA4",  encode_ia4),
    FMT_I4:   ("I4",   encode_i4),
}


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

def find_txtr_tags(root):
    """Yield every TXTR tag anywhere in the tree."""
    stack = [root]
    while stack:
        t = stack.pop()
        if t.type == b"TXTR":
            yield t
        for sub in (t.subtags or []):
            stack.append(sub)


def get_txtr_info(txtr):
    """Pull name, fmt, (width,height) and the IMAG sub-tag out of a TXTR tag."""
    name = fmt = size = imag = None
    for sub in txtr.subtags:
        if sub.type == b"NAME":
            name = sub.binary_data[0:sub.length - 1].decode("ascii")
        elif sub.type == b"FMT ":
            fmt = sub.binary_data[0:3]
        elif sub.type == b"SIZE":
            size = struct.unpack(">LL", sub.binary_data[0:8])  # (width, height)
        elif sub.type == b"IMAG":
            imag = sub
    return name, fmt, size, imag


def load_png(path, width, height):
    img = Image.open(path).convert("RGBA")
    if img.size != (width, height):
        print(f"  (resizing {img.size} -> {(width, height)})")
        img = img.resize((width, height), Image.LANCZOS)
    return list(img.getdata())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def export_tex(tex_path, output_dir=None):
    if output_dir is None:
        output_dir = tex_path[:-4] if tex_path.lower().endswith(".tex") else tex_path + "_extracted"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(tex_path, "rb") as fh:
        tagroot = tag.Tag(fh)
    tex = Tex(tagroot)
    imgs = tex.tex2img()

    count = 0
    for img in imgs:
        if img is None or img.get("data") is None:
            continue

        name = img.get('name', 'Unknown')
        w = img.get("width", 512)
        h = img.get("height", 512)
        data = img["data"]
        fmt = img.get("fmt", b"")

        try:
            if img.get("is_raw"):
                if fmt == FMT_IA4:
                    rgba_bytes = unswizzle_ia4(data, w, h)
                    oimg = Image.frombytes('RGBA', (w, h), rgba_bytes, 'raw')
                    print(f"Decoded IA4 texture: '{name}'")
                elif fmt == FMT_I4:
                    rgba_bytes = unswizzle_i4(data, w, h)
                    oimg = Image.frombytes('RGBA', (w, h), rgba_bytes, 'raw')
                    print(f"Decoded I4 texture: '{name}'")
                else:
                    oimg = Image.frombytes('RGBA', (w, h), data[:w*h*4], 'raw')
            else:
                oimg = Image.fromarray(data, 'RGBA')

            oimg.save(os.path.join(output_dir, f"{name}.png"))
            count += 1
        except Exception as e:
            print(f"Skipping conversion for '{name}': {e}")

    print(f"\nExported {count} texture(s) to: {output_dir}")


def import_tex(tex_path, png_dir=None, out_path=None):
    base = tex_path[:-4] if tex_path.lower().endswith(".tex") else tex_path
    if png_dir is None:
        png_dir = base
    if out_path is None:
        out_path = base + "_repacked.tex"

    if not os.path.isdir(png_dir):
        print(f"PNG directory not found: {png_dir}")
        sys.exit(1)

    with open(tex_path, "rb") as fh:
        buf = bytearray(fh.read())
    with open(tex_path, "rb") as fh:
        tagroot = tag.Tag(fh)

    if tagroot.type != b"TEX ":
        print("File is not a valid TEX file!")
        sys.exit(1)

    patched = skipped = 0
    for txtr in find_txtr_tags(tagroot):
        name, fmt, size, imag = get_txtr_info(txtr)
        if name is None or fmt is None or size is None or imag is None:
            print(f"Skipping incomplete TXTR (name={name})")
            skipped += 1
            continue

        width, height = size
        png_path = os.path.join(png_dir, f"{name}.png")
        if not os.path.exists(png_path):
            print(f"Skipping '{name}': no PNG found at {png_path}")
            skipped += 1
            continue

        if fmt not in ENCODERS:
            print(f"Skipping '{name}': unsupported format {fmt}")
            skipped += 1
            continue

        label, encoder = ENCODERS[fmt]
        pixels = load_png(png_path, width, height)
        data = encoder(pixels, width, height)

        start = imag.offset + 16            # skip type(4)+length(4)+mystery(8)
        orig_len = imag.length
        if len(data) != orig_len:
            print(f"  WARNING: '{name}' encoded {len(data)} bytes but original "
                  f"IMAG is {orig_len} bytes. Padding/truncating to fit.")
            if len(data) < orig_len:
                data = data + bytes(orig_len - len(data))
            else:
                data = data[:orig_len]

        buf[start:start + orig_len] = data
        print(f"Packed '{name}' ({label} {width}x{height}, {orig_len} bytes)")
        patched += 1

    with open(out_path, "wb") as fh:
        fh.write(buf)

    print(f"\nDone. {patched} texture(s) repacked, {skipped} skipped.")
    print(f"Wrote: {out_path}")


def usage():
    print("Usage:")
    print("    python tex.py export <file.tex> [output_dir]")
    print("    python tex.py import <file.tex> [png_dir] [output.tex]")
    print("    python tex.py <file.tex>                 # legacy: same as export")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd in ("export", "unpack"):
        if len(sys.argv) < 3:
            usage()
            sys.exit(1)
        export_tex(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd in ("import", "pack", "repack"):
        if len(sys.argv) < 3:
            usage()
            sys.exit(1)
        import_tex(sys.argv[2],
                   sys.argv[3] if len(sys.argv) > 3 else None,
                   sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        # Legacy form: first arg is the .tex path -> export
        export_tex(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
