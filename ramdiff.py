"""Snapshot / diff the game's save-state block (CGameWork, 0x8021DE88..+0x13E8) live from Dolphin.

  py ramdiff.py snap before.bin     # take a snapshot
  py ramdiff.py diff before.bin     # show every byte that changed since, with its meaning
Needs: pip install dolphin-memory-engine, Dolphin running with the game loaded."""
import sys
import dolphin_memory_engine as d

BASE, SIZE = 0x8021DE88, 0x13E8
STAGES = ["River Belle Path", "Goblin Wall", "Mine of Cathuriges", "Mushroom Forest", "Tida",
          "Moschet Manor", "Mount Kilanda", "Daemon's Court", "Selepation Cave", "Veo Lu Sluice",
          "Lynari Desert", "Conall Curach", "Rebena Te Ra", "Mount Vellenge", "Mag Mell/other"]


def where(off):
    if 0x28 <= off < 0x64:
        return f"stage table A [{STAGES[(off - 0x28) // 4]}]"
    if 0x64 <= off < 0xA0:
        return f"stage table B [{STAGES[(off - 0x64) // 4]}]"
    if 0x10CC <= off < 0x11CC:
        n = (off - 0x10CC) * 8
        return f"event flags {n}-{n + 7}"
    if 0x11CC <= off < 0x13CC:
        return f"m_eventWork[{(off - 0x11CC) // 2}]"
    if off == 0x0B:
        return "year"
    return ""


def main():
    d.hook()
    if not d.is_hooked():
        sys.exit("Dolphin not found - is the game running?")
    cmd, path = sys.argv[1], sys.argv[2]
    now = b"".join(d.read_bytes(BASE + o, min(0x200, SIZE - o)) for o in range(0, SIZE, 0x200))
    if cmd == "snap":
        open(path, "wb").write(now)
        print(f"saved {SIZE:#x} bytes to {path}")
        return
    old = open(path, "rb").read()
    for off in range(SIZE):
        if old[off] != now[off]:
            if 0x14 <= off < 0x18 or 0x0C <= off < 0x14:
                continue  # frame counters/timers change constantly
            print(f"{BASE + off:08X} (+{off:#06x})  {old[off]:02x} -> {now[off]:02x}"
                  f"  bits {old[off]:08b} -> {now[off]:08b}  {where(off)}")


if __name__ == "__main__":
    main()
