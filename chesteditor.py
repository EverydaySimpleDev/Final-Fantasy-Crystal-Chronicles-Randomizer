"""
chesteditor.py - GUI to view and edit FFCC dungeon chest contents.

Run:  python chesteditor.py

  1. Open ISO   - pick your .iso (keep a backup; edits are written in place).
  2. Pick a dungeon and click Load.
  3. The table shows one row per CHEST. The three columns are what that chest
     gives in Cycle 1, Cycle 2, and Cycle 3 (the dungeon's 1st/2nd/3rd visit).
     Numbered "Chest N" rows are matched to Game8's chest list; "Extra N" rows
     are the dungeon's other loot tables.
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
        self.cft_path = None
        self.disc_path = None
        self.dungeon = None
        self.sets = []            # list of sets; each set = list of [offset, id]
        self.rows = []            # ordered [(set_index, title, kind)]
        self.title_of = {}        # set_index -> title
        self.dirty = {}           # file_offset -> new_id

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
                  text="Each row is a chest; columns are what it gives in cycle 1 / 2 / 3. "
                       "Double-click a cell to change it.").pack(fill="x")

        # --- table ---
        wrap = ttk.Frame(master, padding=(8, 4))
        wrap.pack(fill="both", expand=True)
        cols = ("chest", "c1", "c2", "c3")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=18)
        self.tree.heading("chest", text="Chest")
        self.tree.column("chest", width=90, anchor="w")
        for c, label in (("c1", "Cycle 1 (early)"), ("c2", "Cycle 2"), ("c3", "Cycle 3 (late)")):
            self.tree.heading(c, text=label)
            self.tree.column(c, width=200, anchor="w")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.tree.tag_configure("chest", background="#eaf4ea")
        self.tree.tag_configure("extra", background="#f4f4f4")
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
        self.disc_path = f"dvd/cft/{script}_0.cft"
        tmp = os.path.join(tempfile.gettempdir(), f"{script}_0.cft")
        try:
            with open(self.iso, "rb") as f:
                _, files = gciso.parse_fst(f)
                m = gciso.find_file(files, self.disc_path)
                if not m:
                    messagebox.showerror("Not found", f"{self.disc_path} not in ISO"); return
                _, off, size = m[0]
                f.seek(off); data = f.read(size)
            with open(tmp, "wb") as o:
                o.write(data)
            self.cft_path = tmp
            self.sets = [[[o, it] for o, it in s]
                         for s in lootcft.find_sets(tmp, valid=_valid)]
            self.dungeon = g8.SCRIPT_TO_DUNGEON.get(script)
            if not self.dungeon:
                dn, sc = g8.match_dungeon([[it for _, it in s] for s in self.sets])
                self.dungeon = dn if sc >= 3 else None
            labels = g8.label_sets([[it for _, it in s] for s in self.sets],
                                   self.dungeon) if self.dungeon else {}
            self._build_rows(labels)
            self.dirty.clear()
            self.save_btn.config(state="disabled")
            self.refresh()
            n_chest = sum(1 for _, _, k in self.rows if k == "chest")
            dn = self.dungeon or "unknown dungeon"
            self.status.config(text=f"{dn}: {len(self.sets)} chests "
                                    f"({n_chest} matched to Game8 numbers).")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    def _build_rows(self, labels):
        """Order rows: numbered chests first (by number), then 'Extra N'."""
        seen, chest_rows, extra = set(), [], []
        for si in range(len(self.sets)):
            cn = labels.get(si)
            if cn is not None and cn not in seen:
                seen.add(cn); chest_rows.append((cn, si))
            else:
                extra.append(si)
        chest_rows.sort()
        self.rows, self.title_of = [], {}
        for cn, si in chest_rows:
            self.rows.append((si, f"Chest {cn}", "chest")); self.title_of[si] = f"Chest {cn}"
        for k, si in enumerate(extra, 1):
            self.rows.append((si, f"Extra {k}", "extra")); self.title_of[si] = f"Extra {k}"

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
        for si, title, kind in self.rows:
            s = self.sets[si]
            vals = [title] + [self._cycle_names(s, c) for c in CYCLES]
            self.tree.insert("", "end", iid=str(si), values=vals, tags=(kind,))

    # ---- editing ----------------------------------------------------------
    def on_double(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or col == "#1":          # title column, not editable
            return
        cyc = int(col[1:]) - 1              # #2 -> cycle 1, #3 -> 2, #4 -> 3
        self.open_picker(int(row), cyc)

    def open_picker(self, si, cyc):
        s = self.sets[si]
        cm = lootcft.slot_cycles(len(s))
        cyc_slots = [ci for ci in range(len(s)) if cyc in cm[ci]]
        cur_ids = [s[ci][1] for ci in cyc_slots]
        title = self.title_of.get(si, f"Set {si}")
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
            changed = 0
            for ci in cyc_slots:
                off, old = s[ci]
                if new != old:
                    s[ci][1] = new; self.dirty[off] = new; changed += 1
            if changed:
                self.refresh()
                self.save_btn.config(state="normal")
                self.status.config(text=f"{len(self.dirty)} pending edit(s). "
                                        f"Click Save to ISO to apply.")
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
        if not self.dirty:
            messagebox.showinfo("Nothing to save", "No edits pending."); return
        if not messagebox.askyesno("Write to ISO",
                f"Apply {len(self.dirty)} change(s) to {self.disc_path}\n"
                f"in {os.path.basename(self.iso)}?\n\n"
                "This modifies the ISO in place — make sure you have a backup."):
            return
        try:
            lootcft.apply_edits(self.cft_path, self.dirty)
            data = open(self.cft_path, "rb").read()
            with open(self.iso, "r+b") as f:
                _, files = gciso.parse_fst(f)
                _, off, size = gciso.find_file(files, self.disc_path)[0]
                if len(data) != size:
                    raise ValueError("size changed; aborting")
                f.seek(off); f.write(data)
            n = len(self.dirty); self.dirty.clear()
            self.save_btn.config(state="disabled")
            self.status.config(text=f"Saved {n} change(s) to ISO.")
            messagebox.showinfo("Saved", f"Wrote {n} chest change(s) into {self.disc_path}.")
        except Exception as e:
            messagebox.showerror("Save error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
