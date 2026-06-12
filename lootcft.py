"""Parse/edit the FFCC dungeon treasure table inside a <dungeon>_0.cft script.

The loot table lives in get_treasure(): sets of 7 records (stride 0x5b), item ID
is a push-int at record+0 (bytes `03 00 00 <id16>`), chest/slot index byte at
record+0x42 counting 1..7. Confirmed across all dungeons.
"""
import struct
import cft

STRIDE = 0x5b
IDXOFF = 0x42
SETLEN = 7

# script basename -> friendly dungeon name (best-effort; '?' = unconfirmed)
DUNGEONS = [
    ("river",  "River Belle Path"),
    ("gob",    "Goblin Wall"),
    ("mine",   "The Mine of Cathuriges"),
    ("kinoko", "The Mushroom Forest"),
    ("cave",   "Selepation Cave"),
    ("water",  "Veo Lu Sluice"),
    ("swamp",  "Conall Curach"),
    ("desert", "Lynari Desert (no Game8 data)"),
    ("lava",   "Mount Kilanda (no Game8 data)"),
    ("ruin",   "Rebena Te Ra"),
    ("meteo",  "Mount Vellenge"),
    ("miya",   "Moschet Manor (?)"),
    ("stream", "Jegon River (?)"),
    ("last",   "Final / Mag Mell (?)"),
]


def _gt_span(cft_path):
    root, _ = cft.parse(cft_path)
    func = next((s for s in root.subtags if s.type == b"FUNC"), None)
    if func is None:
        return None
    names = [k.name() for k in func.subtags]
    if "get_treasure" not in names:
        return None
    gt = func.subtags[names.index("get_treasure")]
    return gt.off, gt.off + 16 + gt.length


def _valid_item(v):
    return 1 <= v <= 0x4b4


def _detect(raw, lo, hi, idxoff):
    pset = set(o for o in range(lo, hi) if raw[o] == 0x03)
    used = set()
    sets = []
    for o in sorted(pset):
        if o in used or raw[o + idxoff] != 1:
            continue
        run = [o]
        p = o
        while p + STRIDE in pset and raw[p + STRIDE + idxoff] == len(run) + 1:
            p += STRIDE
            run.append(p)
        if len(run) == SETLEN:
            slots = [[r, int.from_bytes(raw[r + 1:r + 5], "big")] for r in run]
            sets.append(slots)
            used.update(run)
    return sets


def parse_sets(cft_path):
    """Return the item-bearing treasure sets. Auto-tunes the index offset per
    dungeon by choosing the one whose sets contain the most real item IDs.
    Each set is a list of [file_offset, item_id] (length 7)."""
    span = _gt_span(cft_path)
    if span is None:
        return []
    lo, hi = span
    raw = open(cft_path, "rb").read()
    hi = min(hi, len(raw) - 5)
    best, best_score = [], -1
    for idxoff in range(0x38, STRIDE):
        sets = _detect(raw, lo, hi, idxoff)
        # score = number of sets that look like real loot (>=4 valid item slots)
        score = sum(1 for s in sets if sum(_valid_item(it) for _, it in s) >= 4)
        if score > best_score:
            best, best_score = sets, score
    # keep only sets with real items (drop all-zero / weight tables)
    return [s for s in best if any(_valid_item(it) for _, it in s)]


# Every treasure record starts with the item push `03 00 00 <id16>` immediately
# followed by this constant 10-byte bytecode. Unlike the chest-index byte (whose
# offset shifts between record layouts - e.g. River uses +0x49, Goblin Wall's
# artifact/recipe sets use +0x38), this signature is identical across all
# dungeons and layouts, so matching it finds every treasure slot regardless of
# how the dungeon packs its sets.
REC_SIG = bytes.fromhex("0d0c0300000000010000")


def find_item_slots(cft_path, valid=None):
    """Return [(file_offset, item_id)] for every treasure record in the file,
    located by REC_SIG rather than a per-dungeon chest-index offset. Catches
    dungeons whose sets the index-based parse_sets() misses (e.g. Goblin Wall).
    If `valid` is given, only slots where valid(item_id) is true are returned."""
    raw = open(cft_path, "rb").read()
    out = []
    for o in range(len(raw) - 15):
        if raw[o] == 0x03 and raw[o + 5:o + 15] == REC_SIG:
            v = int.from_bytes(raw[o + 1:o + 5], "big")
            if valid is None or valid(v):
                out.append((o, v))
    return out


def group_runs(slots):
    """Group (offset, id) slots into contiguous 0x5b-stride runs for display.
    NOTE: a contiguous run can span several real chests packed back-to-back -
    use find_sets() for chest-accurate grouping. Returns list of lists."""
    runs, cur = [], []
    for off, v in slots:
        if cur and off - cur[-1][0] == STRIDE:
            cur.append((off, v))
        else:
            if cur:
                runs.append(cur)
            cur = [(off, v)]
    if cur:
        runs.append(cur)
    return runs


def _detect_idxoff(run, raw):
    """Each record carries a chest/slot index that counts 1,2,3.. within a set
    and resets at the next set. Its byte offset varies by record layout (River
    +0x49, Goblin +0x38), so detect it per-run: the offset whose column has the
    most consecutive +1 increments."""
    best_off, best_score = 0x49, -1
    for off in range(0x30, STRIDE):
        col = [raw[o + off] for o, _ in run]
        score = sum(1 for i in range(1, len(col)) if col[i] == col[i - 1] + 1)
        if score > best_score:
            best_off, best_score = off, score
    return best_off


def find_sets(cft_path, valid=None, min_len=2):
    """Return the treasure SETS (one per chest), each a list of (offset, id).
    Records are found by REC_SIG, grouped into contiguous 0x5b runs, then each
    run is split into sets wherever the per-record chest index stops ascending.
    `valid` filters which ids count as real items for the min_len test; the
    returned sets still contain every slot (including empty/placeholder ones)."""
    raw = open(cft_path, "rb").read()
    # Only real-item record-starts (id >= 1) sit on the clean 0x5b record lattice;
    # the internal `03 00 00 00 00` pushes inside each record also match REC_SIG
    # but carry id 0, so filtering them out is what makes grouping work.
    allslots = find_item_slots(cft_path, valid=_valid_item)
    sets = []
    for run in group_runs(allslots):
        if len(run) < 2:
            continue                                # lone record / code match
        off = _detect_idxoff(run, raw)
        col = [raw[o + off] for o, _ in run]
        cur = [run[0]]
        for i in range(1, len(run)):
            # new chest when the per-record index stops counting up by 1
            if col[i] == col[i - 1] + 1:
                cur.append(run[i])
            else:
                sets.append(cur)
                cur = [run[i]]
        sets.append(cur)
    pred = valid or _valid_item
    return [s for s in sets if sum(pred(v) for _, v in s) >= min_len]


# Reference 7-slot -> cycle mapping (confirmed against in-game River chests:
# cycle 1 = slots 1-4, cycle 2 = slots 5-6, cycle 3 = slot 7). Each slot maps to
# exactly one cycle (non-overlapping) so "one item per cycle" is well-defined;
# for other set lengths the slot position is scaled onto this reference.
_CYCLE_REF = [1, 1, 1, 1, 2, 2, 3]


def slot_cycles(n):
    """Return a list (length n) of single-element cycle-number sets, one per slot."""
    if n <= 1:
        return [{1}] * n
    return [{_CYCLE_REF[round(i / (n - 1) * 6)]} for i in range(n)]


def apply_edits(cft_path, edits):
    """edits: dict {file_offset: new_item_id}. Writes the item bytes in place."""
    data = bytearray(open(cft_path, "rb").read())
    for off, item in edits.items():
        if data[off] != 0x03:
            raise ValueError(f"offset 0x{off:x} is not a push-int item slot")
        data[off + 1:off + 5] = struct.pack(">I", item)
    open(cft_path, "wb").write(data)
