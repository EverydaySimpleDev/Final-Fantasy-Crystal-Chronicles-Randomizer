"""
chesteditor.py - GUI to view and edit FFCC dungeon chest contents.

Run:  python chesteditor.py

  1. Open ISO   - pick your .iso (keep a backup; edits are written in place).
  2. Pick a dungeon and click Load.
  3. The table shows one row per CHEST. The three columns are what that chest
     gives in Cycle 1, Cycle 2, and Cycle 3 (the dungeon's 1st/2nd/3rd visit).
     "Chest N" rows (green) match Game8's chest list (each chest numbered once
     per dungeon). Other sets are classified like the GameCube set-list sheet:
     "Monster N" (red, enemy drop), "Magicite N" (purple, stone/element spawn),
     "Gathering N" (tan, food/seeds). Dungeons span several AREA files; Save
     writes every edited area.
  4. Double-click a cycle cell to change what that chest gives that cycle. The
     picker lists every DROPPABLE item (artifact / magicite / phoenix down /
     material / food / recipe). Equipment is intentionally excluded - a chest
     can't grant it (it opens but gives nothing).
  5. Game8 Reference shows the canonical per-chest contents.
  6. Save to ISO writes your edits back in place.

Chests are detected with lootcft.find_sets() (layout-independent), so every
dungeon is editable. A cycle covers several internal slots; editing a cycle
sets all of that cycle's slots to your chosen item.
"""
import os
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import gciso
import lootcft
import ffcc_items as items
import game8_chests as g8
import randomizer as rnd

CYCLES = (1, 2, 3)

# Every droppable item (id, label). Equipment is excluded because chests can't
# grant it. Used to populate the item picker.
DROPPABLE = [(v, items.label(v)) for v in rnd.build_pool("all")]
CATEGORIES = ["All"] + sorted({items.category(v) for v, _ in DROPPABLE})


def _valid(v):
    return 1 <= v <= 0x4b4


class App:
    def __init__(self, master):
        # `master` may be the root window (standalone) or a frame (embedded in a
        # tab). Widgets pack into `master`; dialogs hang off the real window.
        self.root = master.winfo_toplevel()
        if master is self.root:
            self.root.title("FFCC Chest Editor")
            self.root.geometry("760x560")
        self.iso = None
        self.dungeon = None
        self.areas = []           # [{"area","disc","cft","sets"}] - one per area file
        self.chest_of = {}        # (area_idx, set_idx) -> Game8 chest number (dungeon-wide)
        self.rows = []            # ordered [(area_idx, set_idx, title, kind)]
        self.title_of = {}        # (area_idx, set_idx) -> title
        self.dirty = {}           # area_idx -> {file_offset: new_id}

        # --- top bar: ISO ---
        top = ttk.Frame(master, padding=(8, 8, 8, 2))
        top.pack(fill="x")
        ttk.Button(top, text="Open ISO…", command=self.open_iso).pack(side="left")
        self.iso_lbl = ttk.Label(top, text="No ISO loaded")
        self.iso_lbl.pack(side="left", padx=8)

        # --- second bar: dungeon + actions ---
        bar = ttk.Frame(master, padding=(8, 2))
        bar.pack(fill="x")
        ttk.Label(bar, text="Dungeon:").pack(side="left")
        self.dsel = ttk.Combobox(bar, state="readonly", width=34,
                                 values=[n for _, n in lootcft.DUNGEONS])
        self.dsel.pack(side="left", padx=6)
        ttk.Button(bar, text="Load", command=self.load).pack(side="left")
        ttk.Button(bar, text="Game8 Reference", command=self.show_ref).pack(side="left", padx=6)
        self.save_btn = ttk.Button(bar, text="Save to ISO", command=self.save, state="disabled")
        self.save_btn.pack(side="right")

        # --- help line ---
        ttk.Label(master, padding=(8, 2), foreground="#444",
                  text="Each row is a loot set; columns are what it gives in cycle 1 / 2 / 3. "
                       "Green = Chest, red = Monster (enemy drop), purple = Magicite, "
                       "tan = Gathering. Double-click a cell to change it.").pack(fill="x")

        # --- table ---
        wrap = ttk.Frame(master, padding=(8, 4))
        wrap.pack(fill="both", expand=True)
        cols = ("chest", "c1", "c2", "c3")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=18)
        self.tree.heading("chest", text="Chest")
        self.tree.column("chest", width=140, anchor="w")
        for c, label in (("c1", "Cycle 1 (early)"), ("c2", "Cycle 2"), ("c3", "Cycle 3 (late)")):
            self.tree.heading(c, text=label)
            self.tree.column(c, width=200, anchor="w")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.tree.tag_configure("chest", background="#eaf4ea")      # green
        self.tree.tag_configure("monster", background="#fdecec")    # red
        self.tree.tag_configure("magicite", background="#f1eaf8")   # purple
        self.tree.tag_configure("gathering", background="#fbf3e0")  # tan
        self.tree.tag_configure("extra", background="#f4f4f4")      # (fallback)
        self.tree.bind("<Double-1>", self.on_double)

        self.status = ttk.Label(master, text="Open an ISO to begin.", relief="sunken", anchor="w")
        self.status.pack(fill="x")

    # ---- ISO / dungeon loading -------------------------------------------
    def open_iso(self):
        p = filedialog.askopenfilename(title="Select FFCC ISO",
                                       filetypes=[("Disc image", "*.iso *.gcm"), ("All", "*.*")])
        if not p:
            return
        try:
            with open(p, "rb") as f:
                gid, _ = gciso.parse_fst(f)
        except Exception as e:
            messagebox.showerror("ISO error", str(e)); return
        self.iso = p
        self.iso_lbl.config(text=f"{os.path.basename(p)}  [{gid}]")
        self.status.config(text="ISO loaded. Pick a dungeon and click Load.")

    def load(self):
        if not self.iso:
            messagebox.showwarning("No ISO", "Open an ISO first."); return
        sel = self.dsel.current()
        if sel < 0:
            messagebox.showwarning("No dungeon", "Choose a dungeon."); return
        script = lootcft.DUNGEONS[sel][0]
        try:
            with open(self.iso, "rb") as f:
                _, files = gciso.parse_fst(f)
                discs = rnd._area_discs(files, script)   # all area files _0, _1, ...
                if not discs:
                    messagebox.showerror("Not found", f"No {script}_*.cft in ISO"); return
            self.dungeon = g8.SCRIPT_TO_DUNGEON.get(script)
            self.areas = []
            for disc in discs:
                with open(self.iso, "rb") as f:
                    _, files = gciso.parse_fst(f)
                    _, off, size = gciso.find_file(files, disc)[0]
                    f.seek(off); data = f.read(size)
                cft = os.path.join(tempfile.gettempdir(), os.path.basename(disc))
                with open(cft, "wb") as o:
                    o.write(data)
                sets = [[[o, it] for o, it in s] for s in lootcft.find_sets(cft, valid=_valid)]
                self.areas.append({"area": rnd._area_no(disc), "disc": disc,
                                   "cft": cft, "sets": sets})
            # Label chests across the WHOLE dungeon at once so each Game8 chest
            # number is assigned to a single best-matching set (no per-area dups).
            flat = [(ai, si) for ai, a in enumerate(self.areas)
                    for si in range(len(a["sets"]))]
            combined = [[it for _, it in self.areas[ai]["sets"][si]] for ai, si in flat]
            labels = g8.label_sets(combined, self.dungeon) if self.dungeon else {}
            self.chest_of = {flat[fi]: cn for fi, cn in labels.items()}
            self._build_rows()
            self.dirty.clear()
            self.save_btn.config(state="disabled")
            self.refresh()
            n_chest = sum(1 for _, _, _, k in self.rows if k == "chest")
            n_sets = sum(len(a["sets"]) for a in self.areas)
            dn = self.dungeon or "unknown dungeon"
            self.status.config(text=f"{dn}: {n_sets} sets across {len(self.areas)} area(s) "
                                    f"({n_chest} matched to Game8 chest numbers).")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    def _build_rows(self):
        """Build the row list across the whole dungeon. Each Game8 chest appears
        once as 'Chest N' (numbered once per dungeon). Every other set is then
        classified (validated against the GameCube set-list sheet) and labelled
        'Monster N' (enemy drop), 'Magicite N' (element/stone spawn) or
        'Gathering N' (food / seeds), each numbered sequentially across areas."""
        self.rows, self.title_of = [], {}
        # numbered chests first, ordered by Game8 chest number
        for cn, (ai, si) in sorted((cn, k) for k, cn in self.chest_of.items()):
            t = f"Chest {cn}"
            self.rows.append((ai, si, t, "chest")); self.title_of[(ai, si)] = t
        # everything else, grouped by kind (Monster / Magicite / Gathering)
        buckets = {"monster": [], "magicite": [], "gathering": []}
        for ai, a in enumerate(self.areas):
            for si in range(len(a["sets"])):
                if (ai, si) in self.chest_of:
                    continue
                kind = rnd.set_kind([it for _, it in a["sets"][si]])
                buckets[kind].append((ai, si))
        names = {"monster": "Monster", "magicite": "Magicite", "gathering": "Gathering"}
        for kind in ("monster", "magicite", "gathering"):
            for n, (ai, si) in enumerate(buckets[kind], 1):
                t = f"{names[kind]} {n}"
                self.rows.append((ai, si, t, kind)); self.title_of[(ai, si)] = t

    # ---- table rendering --------------------------------------------------
    def _cycle_names(self, s, cyc):
        cm = lootcft.slot_cycles(len(s))
        seen, names = set(), []
        for ci, (_, v) in enumerate(s):
            if cyc in cm[ci] and v not in seen:
                seen.add(v); names.append(items.name(v))
        return " / ".join(names) if names else "—"

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for ai, si, title, kind in self.rows:
            s = self.areas[ai]["sets"][si]
            vals = [title] + [self._cycle_names(s, c) for c in CYCLES]
            self.tree.insert("", "end", iid=f"{ai}.{si}", values=vals, tags=(kind,))

    # ---- editing ----------------------------------------------------------
    def on_double(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or col == "#1":          # title column, not editable
            return
        cyc = int(col[1:]) - 1              # #2 -> cycle 1, #3 -> 2, #4 -> 3
        ai, si = (int(x) for x in row.split("."))
        self.open_picker(ai, si, cyc)

    def open_picker(self, ai, si, cyc):
        s = self.areas[ai]["sets"][si]
        cm = lootcft.slot_cycles(len(s))
        cyc_slots = [ci for ci in range(len(s)) if cyc in cm[ci]]
        cur_ids = [s[ci][1] for ci in cyc_slots]
        title = self.title_of.get((ai, si), f"Set {si}")
        cur_txt = " / ".join(dict.fromkeys(items.name(i) for i in cur_ids)) or "—"

        win = tk.Toplevel(self.root)
        win.title(f"{title} — Cycle {cyc + 1}")
        win.transient(self.root); win.grab_set()
        ttk.Label(win, padding=(10, 8, 10, 2), justify="left",
                  text=f"{title} · Cycle {cyc + 1}\nCurrently: {cur_txt}").pack(anchor="w")
        ttk.Label(win, padding=(10, 0), foreground="#444",
                  text="Pick the item this chest gives in this cycle:").pack(anchor="w")

        filt = ttk.Frame(win, padding=(10, 6)); filt.pack(fill="x")
        ttk.Label(filt, text="Category:").pack(side="left")
        catvar = tk.StringVar(value=items.category(cur_ids[0]) if cur_ids else "All")
        catcb = ttk.Combobox(filt, state="readonly", width=12, values=CATEGORIES,
                             textvariable=catvar)
        catcb.pack(side="left", padx=4)
        ttk.Label(filt, text="Search:").pack(side="left", padx=(10, 0))
        searchvar = tk.StringVar()
        se = ttk.Entry(filt, textvariable=searchvar, width=18); se.pack(side="left", padx=4)

        body = ttk.Frame(win, padding=(10, 0)); body.pack(fill="both", expand=True)
        lb = tk.Listbox(body, height=15, width=46, activestyle="none")
        sb = ttk.Scrollbar(body, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")

        state = {"filtered": []}

        def repop(*_):
            cat, q = catvar.get(), searchvar.get().lower()
            state["filtered"] = [(i, l) for i, l in DROPPABLE
                                 if (cat == "All" or items.category(i) == cat) and q in l.lower()]
            lb.delete(0, "end")
            for _, l in state["filtered"]:
                lb.insert("end", l)
            for idx, (i, _) in enumerate(state["filtered"]):
                if cur_ids and i == cur_ids[0]:
                    lb.selection_set(idx); lb.see(idx); break

        def apply():
            sel = lb.curselection()
            if not sel:
                return
            new = state["filtered"][sel[0]][0]
            area_dirty = self.dirty.setdefault(ai, {})
            changed = 0
            for ci in cyc_slots:
                off, old = s[ci]
                if new != old:
                    s[ci][1] = new; area_dirty[off] = new; changed += 1
            if changed:
                self.refresh()
                self.save_btn.config(state="normal")
                n = sum(len(d) for d in self.dirty.values())
                self.status.config(text=f"{n} pending edit(s). Click Save to ISO to apply.")
            win.destroy()

        catcb.bind("<<ComboboxSelected>>", repop)
        searchvar.trace_add("write", repop)
        lb.bind("<Double-1>", lambda e: apply())
        repop()

        btns = ttk.Frame(win, padding=10); btns.pack(fill="x")
        ttk.Button(btns, text="Set item", command=apply).pack(side="right")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=6)
        se.focus_set()

    # ---- reference / save -------------------------------------------------
    def show_ref(self):
        if not self.dungeon:
            messagebox.showinfo("Game8 reference",
                                "Load a dungeon first (or no Game8 data for it)."); return
        win = tk.Toplevel(self.root)
        win.title(f"Game8 chest reference — {self.dungeon}")
        txt = tk.Text(win, width=80, height=28, wrap="word")
        txt.insert("1.0", g8.reference_text(self.dungeon))
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)

    def save(self):
        n = sum(len(d) for d in self.dirty.values())
        if not n:
            messagebox.showinfo("Nothing to save", "No edits pending."); return
        n_areas = sum(1 for d in self.dirty.values() if d)
        if not messagebox.askyesno("Write to ISO",
                f"Apply {n} change(s) across {n_areas} area file(s)\n"
                f"in {os.path.basename(self.iso)}?\n\n"
                "This modifies the ISO in place — make sure you have a backup."):
            return
        try:
            for ai, edits in self.dirty.items():
                if not edits:
                    continue
                a = self.areas[ai]
                lootcft.apply_edits(a["cft"], edits)
                data = open(a["cft"], "rb").read()
                with open(self.iso, "r+b") as f:
                    _, files = gciso.parse_fst(f)
                    _, off, size = gciso.find_file(files, a["disc"])[0]
                    if len(data) != size:
                        raise ValueError(f"{a['disc']}: size changed; aborting")
                    f.seek(off); f.write(data)
            self.dirty.clear()
            self.save_btn.config(state="disabled")
            self.status.config(text=f"Saved {n} change(s) to ISO.")
            messagebox.showinfo("Saved", f"Wrote {n} chest change(s) across {n_areas} area file(s).")
        except Exception as e:
            messagebox.showerror("Save error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
