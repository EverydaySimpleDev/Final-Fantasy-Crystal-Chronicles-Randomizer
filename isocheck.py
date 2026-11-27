"""
isocheck.py - Check that an ISO is the one the patcher supports: a plain,
unmodified image of the North American release (GCCE01, revision 0).

Every patch finds its bytes at fixed places in the North American files, so
another region, an already patched ISO or a compressed image would fail
partway, or worse, patch the wrong bytes. check() looks at, in order:

    the image format   a plain ISO/GCM, not RVZ, WIA, GCZ, CISO, WBFS or NKit
    the game           GCCE01 (not the European GCCP01 or Japanese GCCJGC)
    the revision       0, the only North American one
    Start.dol          its SHA-1 matches the retail one
    the file list      a SHA-1 over every file's name and size matches, so no
                       file was added, removed or resized
    the files          a SHA-1 over every file's contents matches

The first five are errors. A content mismatch is only a warning, since it
could be a dump the patcher hasn't seen. Where the files sit on the disc is
not checked, so full, trimmed and rebuilt images of the same disc all pass.

Usage:
    py isocheck.py <game.iso>
"""

import hashlib
import sys

import gciso

GAME_ID = "GCCE01"
REVISION = 0
DOL_SHA1 = "ba57add3e93ea97b0a93ed77037173217bc89eaa"      # also the decomp's retail hash
FILE_LIST_SHA1 = "8097400410ac80ff5c17821750061e9145185d7f"
CONTENT_SHA1 = "8f9673be108d05fbb6c2994674803c52ca863563"
GAMECUBE_MAGIC = bytes.fromhex("c2339f3d")                 # at 0x1C of every GameCube disc

OTHER_REGIONS = {"GCCP01": "European (PAL)", "GCCJGC": "Japanese", "GCCJ01": "Japanese"}
# first bytes of compressed formats Dolphin can convert back to a plain ISO
COMPRESSED = {
    b"RVZ\x01": "RVZ",
    b"WIA\x01": "WIA",
    bytes.fromhex("01c00bb1"): "GCZ",
    b"CISO": "CISO",
    b"WBFS": "WBFS",
}
CONVERT = ("Convert it to a plain ISO first: in Dolphin, right-click the game, choose "
           "\"Convert File...\" and pick ISO as the format.")
CLEAN_COPY = "Start from a clean, unmodified copy of the North American (NTSC-U) game."


def file_list_sha1(files):
    """SHA-1 over every file's path and size, in path order."""
    h = hashlib.sha1()
    for path, _, size in sorted(files):
        h.update(f"{path}\0{size}\n".encode("utf-8"))
    return h.hexdigest()


def content_sha1(f, files):
    """SHA-1 over every file's path and contents, in path order."""
    h = hashlib.sha1()
    for path, offset, size in sorted(files):
        h.update(path.encode("utf-8") + b"\0")
        f.seek(offset)
        while size:
            n = min(size, 1 << 22)
            h.update(f.read(n))
            size -= n
    return h.hexdigest()


def check(iso, full=True):
    """([errors], [warnings]) for `iso`. With `full`, every file's contents
    are compared too (a second or a few)."""
    try:
        f = open(iso, "rb")
    except OSError as e:
        return [f"The ISO can't be opened: {e}"], []
    with f:
        head = f.read(0x440)
        for magic, name in COMPRESSED.items():
            if head.startswith(magic):
                return [f"This is a compressed {name} image, and the patcher needs a plain ISO. {CONVERT}"], []
        if head[0x200:0x204] == b"NKIT":
            return [f"This is an NKit image, and the patcher needs a plain ISO. {CONVERT}"], []
        if len(head) < 0x440 or head[0x1C:0x20] != GAMECUBE_MAGIC:
            return ["This isn't a GameCube disc image."], []
        game_id = head[0:6].decode("ascii", "replace")
        if game_id != GAME_ID:
            region = OTHER_REGIONS.get(game_id)
            what = f"the {region} version of the game" if region else f"another game ({game_id})"
            return [f"This is {what}. Only the North American version ({GAME_ID}) is supported."], []
        if head[7] != REVISION:
            return [f"This is revision {head[7]} of the game. Only revision {REVISION} is supported."], []

        off, size = gciso.dol_span(f)
        f.seek(off)
        if hashlib.sha1(f.read(size)).hexdigest() != DOL_SHA1:
            return [f"This ISO's game code (Start.dol) has been patched or modified. {CLEAN_COPY}"], []
        _, files = gciso.parse_fst(f)
        if file_list_sha1(files) != FILE_LIST_SHA1:
            return [f"Files on this ISO have been added, removed or resized, so it has already been "
                    f"patched or modified. {CLEAN_COPY}"], []
        if full:
            if content_sha1(f, files) != CONTENT_SHA1:
                return [], ["Some files on this ISO differ from the clean game, so it may have been "
                            "edited (for example with the Chest Editor). Patching a modified ISO can "
                            "leave settings without effect. " + CLEAN_COPY]
    return [], []


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    errors, warnings = check(sys.argv[1])
    for line in errors:
        print("ERROR: " + line)
    for line in warnings:
        print("WARNING: " + line)
    if not errors and not warnings:
        print(f"OK: a clean North American ISO ({GAME_ID}, revision {REVISION}).")
    sys.exit(1 if errors else 0)
