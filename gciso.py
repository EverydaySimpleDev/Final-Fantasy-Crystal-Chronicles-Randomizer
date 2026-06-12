"""
gciso.py - List, extract, and re-inject files in a GameCube disc image (.iso/.gcm).

Usage:
    python gciso.py list    <iso> [substring]          # list files (optionally filtered)
    python gciso.py extract <iso> <disc_path> [out]    # pull one file out of the disc
    python gciso.py inject  <iso> <disc_path> <file>   # write a file back IN PLACE
    python gciso.py extractall <iso> <out_dir> [substring]

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
    else:
        usage()
        sys.exit(1)
