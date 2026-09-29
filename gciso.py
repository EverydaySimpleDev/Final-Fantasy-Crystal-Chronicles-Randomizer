"""
gciso.py - List, extract, and re-inject files in a GameCube disc image (.iso/.gcm).

Usage:
    python gciso.py list    <iso> [substring]          # list files (optionally filtered)
    python gciso.py extract <iso> <disc_path> [out]    # pull one file out of the disc
    python gciso.py inject  <iso> <disc_path> <file>   # write a file back IN PLACE (same size)
    python gciso.py rebuild <iso> <disc_path> <file> [out_iso]  # replace at ANY size
    python gciso.py extractall <iso> <out_dir> [substring]
    python gciso.py extract-dol <iso> [out]             # pull the boot executable (main.dol)
    python gciso.py inject-dol  <iso> <file>            # write it back IN PLACE (same size)

Re-injection is IN-PLACE: the replacement file must be EXACTLY the same size as
the file already on the disc, so nothing else has to move and the disc's file
table (FST) stays valid. This pairs perfectly with tex.py's importer, which
re-packs textures at their original byte size.

  Typical texture-modding loop, straight from the ISO:
    python gciso.py extract "Hacked Rom.iso" dvd/menu/world.tex world.tex
    python tex.py export world.tex          # edit the PNGs in world/ ...
    python tex.py import world.tex          # -> world_repacked.tex (same size)
    python gciso.py inject "Hacked Rom.iso" dvd/menu/world.tex world_repacked.tex

IMPORTANT: inject modifies the .iso directly. Keep a backup of your disc image.
"""

import os
import sys
import struct

GC_MAGIC = 0xC2339F3D


def read_header(f):
    f.seek(0)
    hdr = f.read(0x440)
    magic = struct.unpack(">I", hdr[0x1C:0x20])[0]
    if magic != GC_MAGIC:
        raise Exception("Not a GameCube disc image (bad magic 0x%08X)" % magic)
    game_id = hdr[0:6].decode("ascii", "replace")
    fst_off = struct.unpack(">I", hdr[0x424:0x428])[0]
    fst_sz = struct.unpack(">I", hdr[0x428:0x42C])[0]
    return game_id, fst_off, fst_sz


def parse_fst(f):
    """Return list of (disc_path, offset, size) for every file in the disc."""
    game_id, fst_off, fst_sz = read_header(f)
    f.seek(fst_off)
    fst = f.read(fst_sz)
    n_entries = struct.unpack(">I", fst[8:12])[0]
    str_base = n_entries * 12

    def name(noff):
        end = fst.index(b"\x00", str_base + noff)
        return fst[str_base + noff:end].decode("ascii", "replace")

    files = []
    cur_end = [n_entries]      # stack: index just past the current directory
    path_stack = [""]
    idx = 1
    while idx < n_entries:
        e = fst[idx * 12:idx * 12 + 12]
        flag = e[0]
        noff = struct.unpack(">I", b"\x00" + e[1:4])[0]
        off = struct.unpack(">I", e[4:8])[0]
        size = struct.unpack(">I", e[8:12])[0]
        nm = name(noff)
        while len(cur_end) > 1 and idx >= cur_end[-1]:
            cur_end.pop()
            path_stack.pop()
        if flag == 1:                       # directory
            cur_end.append(size)            # 'size' = index of first entry past this dir
            path_stack.append(path_stack[-1] + nm + "/")
        else:                               # file
            files.append((path_stack[-1] + nm, off, size))
        idx += 1
    return game_id, files


def norm(p):
    return p.replace("\\", "/").lstrip("/").lower()


def find_file(files, disc_path):
    want = norm(disc_path)
    matches = [r for r in files if norm(r[0]) == want]
    if not matches:
        # allow matching by suffix (e.g. just "world.tex")
        matches = [r for r in files if norm(r[0]).endswith("/" + want) or norm(r[0]) == want]
    return matches


def dol_span(f):
    """Return (offset, size) of the disc's boot executable (main.dol / Start.dol).
    It is NOT part of the FST - it's a separate blob referenced by boot.bin's
    dolOffset field at 0x420. Size isn't stored either; it's computed from the
    DOL's own header (7 text + 11 data section file-offset/size pairs) as the
    highest (offset + size) among all present sections."""
    f.seek(0x420)
    dol_off = struct.unpack(">I", f.read(4))[0]
    f.seek(dol_off)
    hdr = f.read(0x100)
    text_off = struct.unpack(">7I", hdr[0:28])
    data_off = struct.unpack(">11I", hdr[28:72])
    text_size = struct.unpack(">7I", hdr[144:172])
    data_size = struct.unpack(">11I", hdr[172:216])
    end = 0
    for off, size in list(zip(text_off, text_size)) + list(zip(data_off, data_size)):
        if off:
            end = max(end, off + size)
    return dol_off, end


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(iso, substring=None):
    with open(iso, "rb") as f:
        game_id, files = parse_fst(f)
    print(f"GameID {game_id} - {len(files)} files")
    shown = 0
    for path, off, size in files:
        if substring and substring.lower() not in path.lower():
            continue
        print(f"  {path}  ({size} bytes @ 0x{off:x})")
        shown += 1
    if substring:
        print(f"{shown} file(s) matching '{substring}'")


def cmd_extract(iso, disc_path, out=None):
    with open(iso, "rb") as f:
        game_id, files = parse_fst(f)
        matches = find_file(files, disc_path)
        if not matches:
            print(f"Not found in disc: {disc_path}")
            sys.exit(1)
        if len(matches) > 1:
            print("Ambiguous - matches multiple files:")
            for m in matches:
                print("  ", m[0])
            sys.exit(1)
        path, off, size = matches[0]
        if out is None:
            out = os.path.basename(path)
        f.seek(off)
        data = f.read(size)
    with open(out, "wb") as o:
        o.write(data)
    print(f"Extracted {path} ({size} bytes) -> {out}")


def cmd_inject(iso, disc_path, src):
    with open(src, "rb") as s:
        data = s.read()
    with open(iso, "r+b") as f:
        game_id, files = parse_fst(f)
        matches = find_file(files, disc_path)
        if not matches:
            print(f"Not found in disc: {disc_path}")
            sys.exit(1)
        if len(matches) > 1:
            print("Ambiguous - matches multiple files:")
            for m in matches:
                print("  ", m[0])
            sys.exit(1)
        path, off, size = matches[0]
        if len(data) != size:
            print(f"SIZE MISMATCH: '{src}' is {len(data)} bytes but '{path}' on disc "
                  f"is {size} bytes.")
            print("In-place inject requires identical size. For .tex use tex.py import "
                  "(it preserves size). Different sizes need a full ISO rebuild tool.")
            sys.exit(1)
        f.seek(off)
        f.write(data)
    print(f"Injected {src} -> {path} ({size} bytes) at 0x{off:x} in {os.path.basename(iso)}")


def cmd_extract_dol(iso, out=None):
    with open(iso, "rb") as f:
        off, size = dol_span(f)
        f.seek(off)
        data = f.read(size)
    if out is None:
        out = "main.dol"
    with open(out, "wb") as o:
        o.write(data)
    print(f"Extracted main.dol ({size} bytes @ 0x{off:x}) -> {out}")


def cmd_inject_dol(iso, src):
    with open(src, "rb") as s:
        data = s.read()
    with open(iso, "r+b") as f:
        off, size = dol_span(f)
        if len(data) != size:
            print(f"SIZE MISMATCH: '{src}' is {len(data)} bytes but the disc's main.dol "
                  f"is {size} bytes.")
            print("DOL injection requires identical size - byte-patches only, no size changes.")
            sys.exit(1)
        f.seek(off)
        f.write(data)
    print(f"Injected {src} -> main.dol ({size} bytes) at 0x{off:x} in {os.path.basename(iso)}")


def _fst_entries(data):
    """Like parse_fst but on an in-memory disc image; also returns each file's
    FST entry index (so we can rewrite its offset/size). Returns
    (fst_off, fst_sz, n_entries, [(path, off, size, entry_idx), ...])."""
    fst_off = struct.unpack(">I", data[0x424:0x428])[0]
    fst_sz = struct.unpack(">I", data[0x428:0x42C])[0]
    fst = data[fst_off:fst_off + fst_sz]
    n = struct.unpack(">I", fst[8:12])[0]
    str_base = n * 12

    def nm(noff):
        end = fst.index(b"\x00", str_base + noff)
        return fst[str_base + noff:end].decode("ascii", "replace")

    files, cur_end, path_stack, idx = [], [n], [""], 1
    while idx < n:
        e = fst[idx * 12:idx * 12 + 12]
        flag = e[0]
        noff = struct.unpack(">I", b"\x00" + e[1:4])[0]
        off = struct.unpack(">I", e[4:8])[0]
        size = struct.unpack(">I", e[8:12])[0]
        name = nm(noff)
        while len(cur_end) > 1 and idx >= cur_end[-1]:
            cur_end.pop(); path_stack.pop()
        if flag == 1:
            cur_end.append(size); path_stack.append(path_stack[-1] + name + "/")
        else:
            files.append((path_stack[-1] + name, off, size, idx))
        idx += 1
    return fst_off, fst_sz, n, files


def rebuild_iso(iso_in, edits, iso_out, align=0x20):
    """Write iso_out = iso_in with each edited file RESIZED. `edits` maps a disc
    path -> replacement bytes (any size). Strategy: APPEND each edited file at the
    end of the image and repoint its FST entry; every other file stays byte-for-
    byte at its original offset (no ripple). Lets files grow or shrink. The old
    data of edited files is left as harmless dead space.

    Returns [(path, new_offset, new_size), ...]. Note: the image grows, so the
    result may exceed the 1.46 GB disc size - fine for emulators (Dolphin)."""
    with open(iso_in, "rb") as f:
        data = bytearray(f.read())
    fst_off, fst_sz, n, files = _fst_entries(data)
    by_norm = {norm(p): (p, idx) for (p, _, _, idx) in files}

    def resolve(path):
        k = norm(path)
        if k in by_norm:
            return by_norm[k]
        cand = [v for kk, v in by_norm.items() if kk.endswith("/" + k)]
        if len(cand) != 1:
            raise ValueError(f"rebuild: {path!r} not found uniquely in disc")
        return cand[0]

    changes = []
    for path, content in edits.items():
        real_path, idx = resolve(path)
        content = bytes(content)
        new_off = (len(data) + align - 1) // align * align
        if new_off > len(data):
            data.extend(b"\x00" * (new_off - len(data)))
        data.extend(content)
        struct.pack_into(">I", data, fst_off + idx * 12 + 4, new_off)   # offset
        struct.pack_into(">I", data, fst_off + idx * 12 + 8, len(content))  # size
        changes.append((real_path, new_off, len(content)))
    # The game rounds read lengths up (to 32 bytes) and Dolphin reads in
    # 32 KB blocks, so a file appended flush with the end of the image gets
    # read past EOF -> "The disc could not be read". Pad the image out.
    tail = (len(data) + 0x7FFF) // 0x8000 * 0x8000
    data.extend(b"\x00" * (tail - len(data)))
    with open(iso_out, "wb") as f:
        f.write(data)
    return changes


def cmd_rebuild(iso, disc_path, src, out=None):
    with open(src, "rb") as s:
        data = s.read()
    if out is None:
        base, ext = os.path.splitext(iso)
        out = base + " - rebuilt" + (ext or ".iso")
    changes = rebuild_iso(iso, {disc_path: data}, out)
    for path, off, size in changes:
        print(f"Rebuilt: {path} -> {size} bytes at 0x{off:x} (appended)")
    print(f"Wrote {out}  ({os.path.getsize(out)} bytes). Other files unchanged. "
          f"Test in an emulator (image may exceed 1.46 GB).")


def cmd_extractall(iso, out_dir, substring=None):
    with open(iso, "rb") as f:
        game_id, files = parse_fst(f)
        count = 0
        for path, off, size in files:
            if substring and substring.lower() not in path.lower():
                continue
            dest = os.path.join(out_dir, path.replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            f.seek(off)
            data = f.read(size)
            with open(dest, "wb") as o:
                o.write(data)
            count += 1
    print(f"Extracted {count} file(s) to {out_dir}")


def usage():
    print(__doc__.strip())


if __name__ == "__main__":
    if len(sys.argv) < 3:
        usage()
        sys.exit(1)
    cmd = sys.argv[1].lower()
    iso = sys.argv[2]
    if cmd == "list":
        cmd_list(iso, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "extract":
        if len(sys.argv) < 4:
            usage(); sys.exit(1)
        cmd_extract(iso, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "inject":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        cmd_inject(iso, sys.argv[3], sys.argv[4])
    elif cmd == "extractall":
        if len(sys.argv) < 4:
            usage(); sys.exit(1)
        cmd_extractall(iso, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "rebuild":
        if len(sys.argv) < 5:
            usage(); sys.exit(1)
        cmd_rebuild(iso, sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None)
    elif cmd == "extract-dol":
        cmd_extract_dol(iso, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "inject-dol":
        if len(sys.argv) < 4:
            usage(); sys.exit(1)
        cmd_inject_dol(iso, sys.argv[3])
    else:
        usage()
        sys.exit(1)
