"""
Compile the GBA loot pages (gba_loot.c, for the GBA program) and their
GameCube side (gc_loot.c, for Start.dol) and write the machine code into
gbaloot_code.py, which gbaloot.py patches into an ISO. Players never need
this. Only run it after changing the C files.

Needs devkitPro's devkitARM and devkitPPC (C:/devkitPro by default, or the
DEVKITPRO environment variable).

Usage:
    py gbacode/build.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "gbaloot_code.py")
def _devkitpro():
    """devkitPro's folder. Its installer sets DEVKITPRO to an MSYS path
    (/opt/devkitpro), which Windows programs can't use."""
    for path in (os.environ.get("DEVKITPRO", ""), "C:/devkitPro"):
        if path and os.path.isdir(os.path.join(path, "devkitARM")):
            return path
    sys.exit("devkitPro not found: install it or set DEVKITPRO to its folder")


DEVKITPRO = _devkitpro()
ARM = os.path.join(DEVKITPRO, "devkitARM", "bin", "arm-none-eabi-")
PPC = os.path.join(DEVKITPRO, "devkitPPC", "bin", "powerpc-eabi-")

GBA_AT = 0x0202E800      # after the GBA program and its item names, below its download area
GC_AT = 0x801AA460       # TRKRequestSend and TRKSuppAccessFile, debugger code the game never runs
GC_END = 0x801AA860

GBA_LD = f"""SECTIONS {{
  . = 0x{GBA_AT:08X};
  .text : {{ *(.loot_config) *(.text*) *(.rodata*) *(.data*) *(.bss*) *(COMMON) }}
  /DISCARD/ : {{ *(.comment) *(.ARM.attributes) *(.note*) }}
}}
"""
GC_LD = f"""SECTIONS {{
  . = 0x{GC_AT:08X};
  .text : {{ *(.text*) *(.rodata*) *(.data*) *(.sdata*) *(.sbss*) *(.bss*) }}
  /DISCARD/ : {{ *(.comment) *(.gnu.attributes) *(.note*) *(.eh_frame*) }}
}}
GetScouterInfo = 0x800C9124;
"""
# symbol -> its name in gbaloot_code.py
GBA_ENTRIES = {"gLootPages": "GBA_PAGES", "Loot_RadarFrame": "GBA_RADAR_FRAME",
               "Loot_Main": "GBA_MAIN", "Loot_OnScouterInfo": "GBA_ON_SCOUTER_INFO"}
GC_ENTRIES = {"Loot_ScouterInfo": "GC_SCOUTER_INFO"}


def run(*cmd):
    subprocess.run(cmd, check=True)


def symbols(nm, elf, names):
    out = subprocess.run([nm, elf], check=True, capture_output=True, text=True).stdout
    found = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in names:
            found[parts[2]] = int(parts[0], 16)
    missing = set(names) - set(found)
    if missing:
        sys.exit(f"missing symbols: {sorted(missing)}")
    return found


def build_gba(tmp):
    ld = os.path.join(tmp, "gba.ld")
    open(ld, "w").write(GBA_LD)
    obj, syms, elf, bin_ = (os.path.join(tmp, n) for n in ("gba_loot.o", "gba_syms.o", "gba.elf", "gba.bin"))
    run(ARM + "gcc", "-mcpu=arm7tdmi", "-mthumb", "-mthumb-interwork", "-O2", "-ffreestanding",
        "-fno-builtin", "-nostdlib", "-ffunction-sections", "-Wall", "-Werror",
        "-c", os.path.join(HERE, "gba_loot.c"), "-o", obj)
    run(ARM + "as", "-mcpu=arm7tdmi", os.path.join(HERE, "gba_syms.s"), "-o", syms)
    run(ARM + "ld", "-T", ld, obj, syms, "-o", elf)
    run(ARM + "objcopy", "-O", "binary", elf, bin_)
    found = symbols(ARM + "nm", elf, GBA_ENTRIES)
    if found["gLootPages"] != GBA_AT:
        sys.exit("gLootPages must be the first byte of the GBA code")
    return open(bin_, "rb").read(), found


def build_gc(tmp):
    ld = os.path.join(tmp, "gc.ld")
    open(ld, "w").write(GC_LD)
    obj, elf, bin_ = (os.path.join(tmp, n) for n in ("gc_loot.o", "gc.elf", "gc.bin"))
    run(PPC + "gcc", "-mcpu=750", "-meabi", "-msdata=none", "-G0", "-O2", "-ffreestanding",
        "-fno-builtin", "-nostdlib", "-Wall", "-Werror",
        "-c", os.path.join(HERE, "gc_loot.c"), "-o", obj)
    run(PPC + "ld", "-T", ld, obj, "-o", elf)
    run(PPC + "objcopy", "-O", "binary", elf, bin_)
    code = open(bin_, "rb").read()
    if GC_AT + len(code) > GC_END:
        sys.exit("the GameCube code doesn't fit its space")
    return code, symbols(PPC + "nm", elf, GC_ENTRIES)


def hex_lines(code):
    return "\n".join(f'    "{code[i:i + 32].hex()}"' for i in range(0, len(code), 32))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        gba, gba_syms = build_gba(tmp)
        gc, gc_syms = build_gc(tmp)
    lines = ['"""Machine code of gbacode/gba_loot.c and gbacode/gc_loot.c for gbaloot.py.',
             'Rebuild it with: py gbacode/build.py"""', ""]
    lines.append(f"GBA_AT = 0x{GBA_AT:08X}")
    for name, addr in gba_syms.items():
        lines.append(f"{GBA_ENTRIES[name]} = 0x{addr:08X}")
    lines.append(f"GC_AT = 0x{GC_AT:08X}")
    for name, addr in gc_syms.items():
        lines.append(f"{GC_ENTRIES[name]} = 0x{addr:08X}")
    lines += ["", "GBA_CODE = bytes.fromhex(", hex_lines(gba), ")", "",
              "GC_CODE = bytes.fromhex(", hex_lines(gc), ")", ""]
    open(OUT, "w", newline="\n").write("\n".join(lines))
    print(f"wrote {OUT}: GBA {len(gba)} bytes, GameCube {len(gc)} bytes")


if __name__ == "__main__":
    main()
