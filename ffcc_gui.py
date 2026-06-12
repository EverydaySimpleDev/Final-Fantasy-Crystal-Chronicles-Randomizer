"""
ffcc_gui.py - one window for all the FFCC chest tools.

    python ffcc_gui.py

Tabs:
  * Randomizer  - list / preview / randomize chests, write spoiler, export &
                  patch JSON (wraps randomizer.py).
  * Chest Editor- the per-chest / per-cycle editor (chesteditor.py).
  * File Tools  - extract/inject/list files in the ISO (gciso.py) and edit item
                  stats in param.cfd (items.py).

Nothing here does anything the command-line tools can't; it just exposes them
with buttons and file pickers. The Randomizer never writes your source ISO - it
always creates a separate output ISO (you choose where).
"""
import contextlib
import io
import os
import queue
import random
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import lootcft
import gciso
import items as itemtool
import randomizer as rnd
import chesteditor

DUNGEONS = lootcft.DUNGEONS                      # [(script, friendly)]
POOLS = ["all", "artifact", "magicite", "consumable", "recipe"]


def run_capture(fn, *args, **kwargs):
    """Call fn with stdout captured; return whatever it printed (+ errors)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            fn(*args, **kwargs)
    except SystemExit as e:
        buf.write(f"\n[stopped] {e}\n")
    except Exception as e:
        buf.write(f"\n[error] {type(e).__name__}: {e}\n")
    return buf.getvalue()


def browse_iso(var):
    p = filedialog.askopenfilename(title="Select ISO",
                                   filetypes=[("Disc image", "*.iso *.gcm"), ("All", "*.*")])
    if p:
        var.set(p)


class LogPanel(ttk.Frame):
    """A scrolled text output with a Clear button."""
    def __init__(self, master):
        super().__init__(master)
        bar = ttk.Frame(self); bar.pack(fill="x")
        ttk.Label(bar, text="Output:").pack(side="left")
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="right")
        self.txt = scrolledtext.ScrolledText(self, height=14, wrap="word")
        self.txt.pack(fill="both", expand=True)

    def clear(self):
        self.txt.delete("1.0", "end")

    def write(self, s):
        self.txt.insert("end", s.rstrip() + "\n")
        self.txt.see("end")


def open_file(path):
    try:
        os.startfile(path)            # Windows
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Randomizer tab
# ---------------------------------------------------------------------------
class RandomizerTab(ttk.Frame):
    def __init__(self, nb):
        super().__init__(nb, padding=8)
        self.src = tk.StringVar()      # original ISO - only ever READ
        self.out = tk.StringVar()      # randomized copy - the only thing written
        self.seed = tk.StringVar(value=str(random.randrange(1 << 30)))
        self.rand_seed = tk.BooleanVar(value=True)
        self.mode = tk.StringVar(value="cross")
        self.rolls = tk.StringVar(value="cycle")
        self.pool = tk.StringVar(value="all")
        self.dungeon = tk.StringVar(value="All dungeons")
        self.fill = tk.BooleanVar(value=False)
        self.max_art = tk.StringVar(value="4")

        # Source ISO (read-only) -> Output ISO (created/written). Choosing a
        # source auto-suggests an output path so the original is never touched.
        sf = ttk.Frame(self); sf.pack(fill="x", pady=2)
        ttk.Label(sf, text="Source ISO (your original, never changed):", width=46).pack(side="left")
        ttk.Entry(sf, textvariable=self.src).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(sf, text="Browse…", command=self._browse_src).pack(side="left")
        of = ttk.Frame(self); of.pack(fill="x", pady=2)
        ttk.Label(of, text="Output ISO (the randomized copy):", width=46).pack(side="left")
        ttk.Entry(of, textvariable=self.out).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(of, text="Save as…", command=self._browse_out).pack(side="left")
        self.src.trace_add("write", lambda *_: self._suggest_out())

        opt = ttk.LabelFrame(self, text="Options", padding=8)
        opt.pack(fill="x", pady=6)

        r1 = ttk.Frame(opt); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="Seed:").pack(side="left")
        self.seed_entry = ttk.Entry(r1, textvariable=self.seed, width=12)
        self.seed_entry.pack(side="left", padx=4)
        ttk.Checkbutton(r1, text="Random each run", variable=self.rand_seed,
                        command=self._toggle_seed).pack(side="left")
        self._toggle_seed()

        r2 = ttk.Frame(opt); r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="Mode:").pack(side="left")
        ttk.Radiobutton(r2, text="Any item anywhere", value="cross",
                        variable=self.mode).pack(side="left", padx=4)
        ttk.Radiobutton(r2, text="Keep original category", value="category",
                        variable=self.mode).pack(side="left", padx=4)

        r3 = ttk.Frame(opt); r3.pack(fill="x", pady=2)
        ttk.Label(r3, text="Rolls:").pack(side="left")
        for val, lbl in (("cycle", "One per cycle"), ("slot", "Per slot (most variety)"),
                         ("chest", "One per chest")):
            ttk.Radiobutton(r3, text=lbl, value=val, variable=self.rolls).pack(side="left", padx=4)

        r4 = ttk.Frame(opt); r4.pack(fill="x", pady=2)
        ttk.Label(r4, text="Item pool:").pack(side="left")
        ttk.Combobox(r4, state="readonly", width=12, values=POOLS,
                     textvariable=self.pool).pack(side="left", padx=4)
        ttk.Label(r4, text="Dungeon:").pack(side="left", padx=(10, 0))
        ttk.Combobox(r4, state="readonly", width=28,
                     values=["All dungeons"] + [n for _, n in DUNGEONS],
                     textvariable=self.dungeon).pack(side="left", padx=4)

        r5 = ttk.Frame(opt); r5.pack(fill="x", pady=2)
        ttk.Label(r5, text="Max artifacts per cycle:").pack(side="left")
        ttk.Spinbox(r5, from_=0, to=99, width=4, textvariable=self.max_art).pack(side="left", padx=4)
        ttk.Label(r5, text="(player can carry 4)", foreground="#777").pack(side="left")
        ttk.Checkbutton(r5, text="Also fill empty/placeholder slots",
                        variable=self.fill).pack(side="left", padx=12)

        btns = ttk.Frame(self); btns.pack(fill="x", pady=4)
        self._buttons = []
        b = ttk.Button(btns, text="List dungeons", command=self.do_list); b.pack(side="left"); self._buttons.append(b)
        b = ttk.Button(btns, text="Preview", command=lambda: self.do_run(False)); b.pack(side="left", padx=4); self._buttons.append(b)
        b = ttk.Button(btns, text="Randomize!", command=lambda: self.do_run(True)); b.pack(side="left"); self._buttons.append(b)
        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=8)
        b = ttk.Button(btns, text="Write spoiler", command=self.do_spoiler); b.pack(side="left", padx=2); self._buttons.append(b)
        b = ttk.Button(btns, text="Export JSON", command=self.do_export); b.pack(side="left", padx=2); self._buttons.append(b)
        b = ttk.Button(btns, text="Patch from JSON…", command=self.do_patch); b.pack(side="left", padx=2); self._buttons.append(b)

        pf = ttk.Frame(self); pf.pack(fill="x", pady=(4, 0))
        self.prog_lbl = ttk.Label(pf, text="", anchor="w")
        self.prog_lbl.pack(fill="x")
        self.progress = ttk.Progressbar(pf, mode="determinate")
        self.progress.pack(fill="x")                     # full width of the tab

        self.log = LogPanel(self); self.log.pack(fill="both", expand=True)

    # -- helpers --
    def _browse_src(self):
        browse_iso(self.src)

    def _suggest_out(self, *_):
        """When a source is chosen, default the output to '<src> - randomized.iso'."""
        s = self.src.get().strip()
        if s and not self.out.get().strip():
            self.out.set(os.path.splitext(s)[0] + " - randomized.iso")

    def _browse_out(self):
        s = self.src.get().strip()
        init = os.path.basename(os.path.splitext(s)[0] + " - randomized.iso") if s else "randomized.iso"
        p = filedialog.asksaveasfilename(title="Save randomized ISO as", defaultextension=".iso",
                                         initialfile=init,
                                         filetypes=[("Disc image", "*.iso *.gcm"), ("All", "*.*")])
        if p:
            self.out.set(p)

    def _toggle_seed(self):
        self.seed_entry.config(state="disabled" if self.rand_seed.get() else "normal")

    @staticmethod
    def _same(a, b):
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))

    def _need_src(self):
        s = self.src.get().strip()
        if not s or not os.path.isfile(s):
            messagebox.showwarning("No source ISO", "Pick a valid source ISO first."); return None
        return s

    def _need_out(self, src):
        """Validate the output path and make sure it can never be the source."""
        o = self.out.get().strip()
        if not o:
            messagebox.showwarning("No output", "Choose where to save the randomized ISO."); return None
        if self._same(src, o):
            messagebox.showerror("Same file",
                                 "Output ISO must be different from the source ISO.\n"
                                 "The source is never modified."); return None
        return o

    def _ns(self):
        ns = type("NS", (), {})()
        ns.seed = random.randrange(1 << 30) if self.rand_seed.get() else int(self.seed.get() or 0)
        self.seed.set(str(ns.seed))
        ns.mode = self.mode.get()
        ns.rolls = self.rolls.get()
        ns.pool = self.pool.get()
        ns.fill_empty = self.fill.get()
        try:
            ns.max_artifacts = max(0, int(self.max_art.get()))
        except ValueError:
            ns.max_artifacts = 4
        ns.ref = self.src.get().strip() or None          # source = vanilla reference
        d = self.dungeon.get()
        ns.dungeon = None if d == "All dungeons" else [s for s, n in DUNGEONS if n == d]
        return ns

    def _make_copy(self, src, out):
        """Copy source -> output (the only file we write). Returns True on success."""
        if os.path.isfile(out) and not messagebox.askyesno(
                "Overwrite output", f"{os.path.basename(out)} exists. Overwrite it?"):
            return False
        try:
            shutil.copy2(src, out)
        except Exception as e:
            messagebox.showerror("Copy failed", str(e)); return False
        self.log.write(f"Created {out}")
        return True

    # -- actions --
    def do_list(self):
        src = self._need_src()
        if src:
            self.log.write(run_capture(rnd.cmd_list, src))

    def do_run(self, apply):
        src = self._need_src()
        if not src:
            return
        if not apply:                                    # preview reads the source, writes nothing
            self.log.write(run_capture(rnd.cmd_run, src, self._ns(), False))
            return
        out = self._need_out(src)
        if not out or not self._make_copy(src, out):
            return
        self._randomize(out, self._ns())

    def _set_busy(self, busy):
        for b in self._buttons:
            b.config(state="disabled" if busy else "normal")

    def _randomize(self, out, ns):
        """Randomize the output ISO on a background thread (so the UI stays
        responsive and the progress bar updates), reporting only how many slots
        changed - never the items. A spoiler file is written for later reference."""
        pool = rnd.build_pool(ns.pool)
        if not pool:
            self.log.write(f"[error] empty pool for '{ns.pool}'"); return
        found = rnd.dungeons_in_iso(out)
        if ns.dungeon:
            want = set(ns.dungeon)
            found = [d for d in found if d[0] in want]
        if not found:
            self.log.write("[error] no matching dungeons"); return
        self.progress.config(maximum=len(found) + 1, value=0)
        self.log.write(f"Randomizing {os.path.basename(out)}  "
                       f"(seed {ns.seed}, mode {ns.mode}, rolls {ns.rolls}, "
                       f"max {ns.max_artifacts} artifacts/cycle)")
        self._set_busy(True)
        self._q = queue.Queue()
        worker = threading.Thread(target=self._rand_worker,
                                  args=(out, ns, pool, found), daemon=True)
        worker.start()
        self.after(60, self._poll_rand)

    def _rand_worker(self, out, ns, pool, found):
        """Runs OFF the UI thread. Communicates only via self._q (never touches
        widgets directly - tkinter isn't thread-safe)."""
        rng = random.Random(ns.seed)
        total = 0
        try:
            for i, (script, friendly, disc) in enumerate(found, 1):
                self._q.put(("label", f"Randomizing: {friendly}"))
                try:
                    changes = rnd.randomize_dungeon(out, script, disc, rng, ns.mode, pool,
                                                    ns.fill_empty, True, ns.rolls, ns.max_artifacts)
                except Exception as e:
                    self._q.put(("log", f"  [error] {friendly}: {e}"))
                    changes = []
                total += len(changes)
                self._q.put(("log", f"  {friendly}: {len(changes)} chest slots randomized"))
                self._q.put(("value", i))
            spoiler = os.path.splitext(out)[0] + " - spoiler.txt"
            run_capture(rnd.cmd_spoiler, out, spoiler, ns.ref)
            self._q.put(("value", len(found) + 1))
            self._q.put(("log", f"Done - {total} chest slots randomized into {os.path.basename(out)}."))
            self._q.put(("log", f"Spoiler saved to {os.path.basename(spoiler)} "
                                f"(open it only if you want to see the contents)."))
        except Exception as e:
            self._q.put(("log", f"[error] {e}"))
        finally:
            self._q.put(("done", None))            # always re-enables the buttons

    def _poll_rand(self):
        """Runs ON the UI thread; drains the worker's queue and updates widgets."""
        try:
            while True:
                kind, val = self._q.get_nowait()
                if kind == "label":
                    self.prog_lbl.config(text=val)
                elif kind == "value":
                    self.progress.config(value=val)
                elif kind == "log":
                    self.log.write(val)
                elif kind == "done":
                    self.prog_lbl.config(text="Done")
                    self._set_busy(False)
                    return                           # stop polling
        except queue.Empty:
            pass
        self.after(60, self._poll_rand)

    def do_spoiler(self):
        src = self._need_src()
        if not src:
            return
        # spoiler the randomized output if it exists, else the source
        target = self.out.get().strip() if os.path.isfile(self.out.get().strip()) else src
        out = os.path.splitext(target)[0] + " - spoiler.txt"
        self.log.write(run_capture(rnd.cmd_spoiler, target, out, src))
        if os.path.isfile(out) and messagebox.askyesno("Spoiler written", f"Open {os.path.basename(out)}?"):
            open_file(out)

    def do_export(self):
        src = self._need_src()
        if not src:
            return
        out = os.path.splitext(src)[0] + " - chests.json"
        self.log.write(run_capture(rnd.cmd_export, src, out, src))
        if os.path.isfile(out) and messagebox.askyesno("JSON written", f"Open {os.path.basename(out)}?"):
            open_file(out)

    def do_patch(self):
        src = self._need_src()
        if not src:
            return
        out = self._need_out(src)
        if not out:
            return
        j = filedialog.askopenfilename(title="Select chest JSON",
                                       filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not j:
            return
        # never patch the source: patch the output copy (make it if needed)
        if not os.path.isfile(out):
            if not self._make_copy(src, out):
                return
        elif not messagebox.askyesno("Patch output",
                f"Apply {os.path.basename(j)} to existing {os.path.basename(out)}?"):
            return
        self.log.write(run_capture(rnd.cmd_patch, out, j, self._ns().max_artifacts))


# ---------------------------------------------------------------------------
# File Tools tab (gciso + item stats)
# ---------------------------------------------------------------------------
class FileToolsTab(ttk.Frame):
    def __init__(self, nb):
        super().__init__(nb, padding=8)
        self.iso = tk.StringVar()
        self.disc = tk.StringVar(value="dvd/cft/river_0.cft")
        self.filt = tk.StringVar()

        f = ttk.Frame(self); f.pack(fill="x", pady=2)
        ttk.Label(f, text="ISO:", width=6).pack(side="left")
        ttk.Entry(f, textvariable=self.iso).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(f, text="Browse…", command=lambda: browse_iso(self.iso)).pack(side="left")

        gc = ttk.LabelFrame(self, text="Files inside the ISO (gciso)", padding=8)
        gc.pack(fill="x", pady=6)
        r1 = ttk.Frame(gc); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="Filter:").pack(side="left")
        ttk.Entry(r1, textvariable=self.filt, width=24).pack(side="left", padx=4)
        ttk.Button(r1, text="List files", command=self.do_list).pack(side="left")
        r2 = ttk.Frame(gc); r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="Disc path:").pack(side="left")
        ttk.Entry(r2, textvariable=self.disc, width=34).pack(side="left", padx=4)
        ttk.Button(r2, text="Extract…", command=self.do_extract).pack(side="left", padx=2)
        ttk.Button(r2, text="Inject…", command=self.do_inject).pack(side="left", padx=2)

        it = ttk.LabelFrame(self, text="Item stats (param.cfd - extract it first, then re-inject)",
                            padding=8)
        it.pack(fill="x", pady=6)
        self.cfd = tk.StringVar()
        self.iid = tk.StringVar(value="0x0001")
        self.field = tk.StringVar(value="damage")
        self.fval = tk.StringVar()
        c = ttk.Frame(it); c.pack(fill="x", pady=2)
        ttk.Label(c, text="param.cfd:").pack(side="left")
        ttk.Entry(c, textvariable=self.cfd).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(c, text="Browse…", command=self._browse_cfd).pack(side="left")
        d = ttk.Frame(it); d.pack(fill="x", pady=2)
        ttk.Label(d, text="Item id:").pack(side="left")
        ttk.Entry(d, textvariable=self.iid, width=10).pack(side="left", padx=4)
        ttk.Button(d, text="Show", command=self.item_show).pack(side="left", padx=2)
        ttk.Label(d, text="Field:").pack(side="left", padx=(10, 0))
        ttk.Combobox(d, width=12, textvariable=self.field,
                     values=list(itemtool.FIELDS.keys())).pack(side="left", padx=2)
        ttk.Label(d, text="=").pack(side="left")
        ttk.Entry(d, textvariable=self.fval, width=10).pack(side="left", padx=2)
        ttk.Button(d, text="Set", command=self.item_set).pack(side="left", padx=2)

        self.log = LogPanel(self); self.log.pack(fill="both", expand=True)

    def _iso(self):
        p = self.iso.get().strip()
        if not p or not os.path.isfile(p):
            messagebox.showwarning("No ISO", "Pick a valid ISO."); return None
        return p

    def _browse_cfd(self):
        p = filedialog.askopenfilename(title="Select param.cfd",
                                       filetypes=[("param.cfd", "*.cfd"), ("All", "*.*")])
        if p:
            self.cfd.set(p)

    def do_list(self):
        iso = self._iso()
        if iso:
            self.log.write(run_capture(gciso.cmd_list, iso, self.filt.get().strip() or None))

    def do_extract(self):
        iso = self._iso()
        if not iso:
            return
        out = filedialog.asksaveasfilename(title="Save extracted file as",
                                           initialfile=os.path.basename(self.disc.get()))
        if out:
            self.log.write(run_capture(gciso.cmd_extract, iso, self.disc.get().strip(), out))

    def do_inject(self):
        iso = self._iso()
        if not iso:
            return
        src = filedialog.askopenfilename(title="File to inject (must match original size)")
        if not src:
            return
        if not messagebox.askyesno("Inject", f"Write {os.path.basename(src)} into "
                                   f"{self.disc.get()} in {os.path.basename(iso)}?"):
            return
        self.log.write(run_capture(gciso.cmd_inject, iso, self.disc.get().strip(), src))

    def _cfd(self):
        p = self.cfd.get().strip()
        if not p or not os.path.isfile(p):
            messagebox.showwarning("No param.cfd", "Pick a param.cfd file (extract it from the ISO above)."); return None
        return p

    def item_show(self):
        cfd = self._cfd()
        if cfd:
            self.log.write(run_capture(itemtool.cmd_show, cfd, int(self.iid.get(), 0)))

    def item_set(self):
        cfd = self._cfd()
        if not cfd:
            return
        if not self.fval.get().strip():
            messagebox.showwarning("No value", "Enter a value to set."); return
        self.log.write(run_capture(itemtool.cmd_set, cfd, int(self.iid.get(), 0),
                                   self.field.get(), self.fval.get().strip()))


# ---------------------------------------------------------------------------
# Help tab
# ---------------------------------------------------------------------------
HELP = """FFCC Modding Toolkit

The Randomizer never modifies your Source ISO. It always writes a separate
Output ISO (you pick where) - so your original is safe by design.

RANDOMIZER
  1. Browse to your Source ISO (your clean original - only ever read).
  2. The Output ISO path auto-fills to "<source> - randomized.iso"; change it
     with "Save as…" if you like. The output must be a different file.
  3. Choose options:
       Mode  - Any item anywhere, or keep each chest's original category.
       Rolls - One per cycle (each chest gives one item per cycle, the clearest),
               Per slot (more variety, several items possible per cycle), or
               One per chest (the chest always gives the same item).
       Pool  - restrict to a category (artifacts, magicite, etc.).
       Dungeon - limit to a single dungeon.
       Max artifacts per cycle - never place more than this many artifacts in a
               dungeon per cycle (default 4 = the player's carry limit); extra
               chests get a non-artifact item instead.
  4. Preview (reads the source, writes nothing) shows the planned contents.
     Randomize! creates the Output ISO with a progress bar and, to avoid
     spoilers, only reports how many slots changed - not the items. A spoiler
     .txt is still written next to the output if you want to peek later.
  Export JSON / Patch from JSON let you hand-edit exact contents: Export a
     template from the source -> edit the .json -> Patch (writes the output ISO,
     never the source).

CHEST EDITOR
  Open ISO, pick a dungeon, Load. Each row is a chest; the three columns are
  what it gives in cycle 1 / 2 / 3. Double-click a cell to change it. Save to ISO.

FILE TOOLS
  List / Extract / Inject raw files in the ISO (inject must match the original
  size). Item stats edits a param.cfd: extract dvd/cft/param.cfd here, edit a
  field, then inject it back.

Only DROPPABLE items go in chests (artifacts, magicite, phoenix down, materials,
food, recipes). Equipment can't drop from a chest, so it is never offered.
"""


def main():
    root = tk.Tk()
    root.title("FFCC Modding Toolkit")
    root.geometry("900x680")
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    nb.add(RandomizerTab(nb), text="Randomizer")

    ce = ttk.Frame(nb)
    nb.add(ce, text="Chest Editor")
    chesteditor.App(ce)

    nb.add(FileToolsTab(nb), text="File Tools")

    helptab = ttk.Frame(nb, padding=8)
    nb.add(helptab, text="Help")
    h = scrolledtext.ScrolledText(helptab, wrap="word")
    h.insert("1.0", HELP)
    h.config(state="disabled")
    h.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
