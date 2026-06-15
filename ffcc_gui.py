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
import shops
import customitem
import ffcc_items

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
        self.include_drops = tk.BooleanVar(value=True)
        self.rand_shops = tk.BooleanVar(value=False)
        self.shop_vars = {base: tk.BooleanVar(value=True) for base in shops.SHOPS}
        self.rand_prices = tk.BooleanVar(value=False)

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

        r6 = ttk.Frame(opt); r6.pack(fill="x", pady=2)
        ttk.Checkbutton(r6, text="Randomize enemy drops too (uncheck = chests only)",
                        variable=self.include_drops).pack(side="left")

        # --- shops (independent of chest randomization) ---
        sh = ttk.LabelFrame(self, text="Shops", padding=8); sh.pack(fill="x", pady=4)
        ttk.Checkbutton(sh, text="Randomize shop inventories (stock swapped within "
                        "sellable items; prices stay valid)",
                        variable=self.rand_shops, command=self._toggle_shops).pack(anchor="w")
        self.shop_box = ttk.Frame(sh); self.shop_box.pack(fill="x", padx=18, pady=(2, 0))
        ttk.Label(self.shop_box, text="Which shops:").pack(side="left")
        self._shop_checks = []
        for base, name in shops.SHOPS.items():
            cb = ttk.Checkbutton(self.shop_box, text=name, variable=self.shop_vars[base])
            cb.pack(side="left", padx=3); self._shop_checks.append(cb)
        ttk.Checkbutton(sh, text="Randomize shop prices (shuffles item prices; "
                        "works with or without item randomization)",
                        variable=self.rand_prices).pack(anchor="w", pady=(4, 0))
        self._toggle_shops()

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
    def _toggle_shops(self):
        state = "normal" if self.rand_shops.get() else "disabled"
        for cb in self._shop_checks:
            cb.config(state=state)

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
        ns.chests_only = not self.include_drops.get()
        try:
            ns.max_artifacts = max(0, int(self.max_art.get()))
        except ValueError:
            ns.max_artifacts = 4
        ns.ref = self.src.get().strip() or None          # source = vanilla reference
        d = self.dungeon.get()
        ns.dungeon = None if d == "All dungeons" else [s for s, n in DUNGEONS if n == d]
        ns.rand_shops = self.rand_shops.get()
        # selected shop bases (None = all) when shop randomization is on
        ns.shops = [b for b, v in self.shop_vars.items() if v.get()] if ns.rand_shops else []
        ns.rand_prices = self.rand_prices.get()
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
        extra = (1 if ns.rand_shops else 0) + (1 if ns.rand_prices else 0)
        self.progress.config(maximum=len(found) + 1 + extra, value=0)
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
            for i, (script, friendly, discs) in enumerate(found, 1):
                self._q.put(("label", f"Randomizing: {friendly}"))
                only_by_disc = None
                if getattr(ns, "chests_only", False):
                    only_by_disc = {d: rnd.chest_set_indices(ns.ref, script, d) for d in discs}
                    if not any(only_by_disc.values()):
                        self._q.put(("log", f"  {friendly}: skipped (no Game8 chest data)"))
                        self._q.put(("value", i)); continue
                try:
                    changes = rnd.randomize_dungeon(out, script, discs, rng, ns.mode, pool,
                                                    ns.fill_empty, True, ns.rolls,
                                                    ns.max_artifacts, only_by_disc)
                except Exception as e:
                    self._q.put(("log", f"  [error] {friendly}: {e}"))
                    changes = []
                total += len(changes)
                self._q.put(("log", f"  {friendly}: {len(changes)} slots randomized "
                                    f"across {len(discs)} area(s)"))
                self._q.put(("value", i))
            step = len(found)
            if getattr(ns, "rand_shops", False):
                self._q.put(("label", "Randomizing shops"))
                only = set(ns.shops) if ns.shops else None
                try:
                    res = rnd.randomize_shops(out, random.Random(ns.seed), only=only, apply=True)
                    nshop = sum(res.values())
                    detail = ", ".join(f"{k} {v}" for k, v in res.items()) or "none selected"
                    self._q.put(("log", f"  shops: {nshop} slots across {len(res)} shop(s) "
                                        f"({detail})"))
                except Exception as e:
                    self._q.put(("log", f"  [error] shops: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "rand_prices", False):
                self._q.put(("label", "Randomizing shop prices"))
                try:
                    # pool from the vanilla source so prices shuffle among real
                    # shop items regardless of whether stock was randomized first
                    vpool = rnd.shop_pool(ns.ref) if ns.ref else None
                    n = rnd.randomize_prices(out, random.Random(ns.seed), apply=True, pool=vpool)
                    self._q.put(("log", f"  prices: {n} item price(s) shuffled"))
                except Exception as e:
                    self._q.put(("log", f"  [error] prices: {e}"))
                step += 1
                self._q.put(("value", step))
            spoiler = os.path.splitext(out)[0] + " - spoiler.txt"
            run_capture(rnd.cmd_spoiler, out, spoiler, ns.ref, rnd._options_header(ns))
            self._q.put(("value", step + 1))
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
       Randomize enemy drops too - chests and enemy drops share the same item
               pool. Checked (default) randomizes both; uncheck to randomize
               only the Game8-identified chests and leave enemy drops alone
               (dungeons without Game8 data are skipped in that mode).
       Shops - tick "Randomize shop inventories" to also shuffle what the towns
               sell (Tipa, Alfitaria, Fields of Fum, Selkie Peddler, Shella,
               Leuda, Smith). Choose all shops or just specific ones. Stock is
               swapped only among items shops already sell, so prices stay valid.
               "Randomize shop prices" shuffles the price tags among those items
               (Bronze might cost what Mythril did); works with or without item
               randomization.
  4. Preview (reads the source, writes nothing) shows the planned contents.
     Randomize! creates the Output ISO with a progress bar and, to avoid
     spoilers, only reports how many slots changed - not the items. A spoiler
     .txt is still written next to the output if you want to peek later; it
     starts with the exact options you chose, then lists every chest and each
     shop's stock.
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

CUSTOM ITEM
  Repurpose an unused "Extra N" slot into your own item (edits a COPY in place).
  - "List free slots" shows repurposable slots; pick one as the Slot id.
  - Name: keep it short (~8 chars fit an Extra slot - names are written in place
    so the file stays the same size).
  - Looks like: a donor item whose 3D model / menu icon / type are copied (e.g.
    Gold). Price sets the gil. Optionally place it in a shop and/or a dungeon's
    first chest for testing. To have the randomizer/editor carry it, follow the
    printed note (add it to ffcc_items NAMES, drop it from randomizer EXCLUDE).

Only DROPPABLE items go in chests (artifacts, magicite, phoenix down, materials,
food, recipes). Equipment can't drop from a chest, so it is never offered.
"""


class CustomItemTab(ttk.Frame):
    """Repurpose an unused 'Extra N' item slot into a custom item (customitem.py)."""

    def __init__(self, nb):
        super().__init__(nb, padding=8)
        self.iso = tk.StringVar()
        self.slot = tk.StringVar(value="0x162")
        self.name = tk.StringVar(value="AP Item")
        self.desc = tk.StringVar(value="An Archipelago Item")
        self.donor = tk.StringVar(value="Gold")
        self.model = tk.StringVar(value="")
        self.retex = tk.StringVar(value="")
        self.gil = tk.StringVar(value="10")
        self.article = tk.StringVar(value="the")
        self.shop = tk.StringVar(value="(none)")
        self.chest = tk.StringVar(value="(none)")
        self._shop_map = {"(none)": None}
        self._shop_map.update({name: base for base, name in shops.SHOPS.items()})
        self._chest_map = {"(none)": None}
        self._chest_map.update({n: s for s, n in DUNGEONS})

        f = ttk.Frame(self); f.pack(fill="x", pady=2)
        ttk.Label(f, text="ISO:", width=6).pack(side="left")
        ttk.Entry(f, textvariable=self.iso).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(f, text="Browse…", command=lambda: browse_iso(self.iso)).pack(side="left")
        ttk.Label(self, foreground="#a33",
                  text="Edits the ISO in place — point it at a COPY (e.g. your randomized "
                       "output), never your clean original.").pack(anchor="w")

        ni = ttk.LabelFrame(self, text="New item (repurposes an unused 'Extra' slot)", padding=8)
        ni.pack(fill="x", pady=6)
        r = ttk.Frame(ni); r.pack(fill="x", pady=2)
        ttk.Label(r, text="Slot id:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.slot, width=10).pack(side="left", padx=4)
        ttk.Button(r, text="List free slots", command=self.do_listfree).pack(side="left", padx=2)
        ttk.Button(r, text="Show slot", command=self.do_show).pack(side="left", padx=2)
        r = ttk.Frame(ni); r.pack(fill="x", pady=2)
        ttk.Label(r, text="Name:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.name, width=20).pack(side="left", padx=4)
        ttk.Label(r, text="(short — about 8 chars fit an 'Extra' slot)",
                  foreground="#777").pack(side="left")
        r = ttk.Frame(ni); r.pack(fill="x", pady=2)
        ttk.Label(r, text="Description:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.desc, width=36).pack(side="left", padx=4)
        ttk.Label(r, text="(in-game help text; blank = leave as-is)",
                  foreground="#777").pack(side="left")
        r = ttk.Frame(ni); r.pack(fill="x", pady=2)
        ttk.Label(r, text="Looks like:", width=12).pack(side="left")
        ttk.Combobox(r, textvariable=self.donor, width=18,
                     values=self._donor_list()).pack(side="left", padx=4)
        ttk.Label(r, text="(donor item — copies its model / icon / type)",
                  foreground="#777").pack(side="left")
        r = ttk.Frame(ni); r.pack(fill="x", pady=2)
        ttk.Label(r, text="Model id:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.model, width=10).pack(side="left", padx=4)
        ttk.Label(r, text="(optional — override the 3D model, e.g. 0x37; blank = donor's)",
                  foreground="#777").pack(side="left")
        r = ttk.Frame(ni); r.pack(fill="x", pady=2)
        ttk.Label(r, text="Retexture:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.retex, width=30).pack(side="left", padx=4)
        ttk.Button(r, text="Browse…",
                   command=lambda: self._browse_png(self.retex)).pack(side="left", padx=2)
        ttk.Label(self, foreground="#777",
                  text="Retexture recolors the model's texture from a PNG. Note: every "
                       "item using that model is recolored — set a unique Model id first "
                       "to affect only this item.").pack(anchor="w")
        r = ttk.Frame(ni); r.pack(fill="x", pady=2)
        ttk.Label(r, text="Price (gil):", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.gil, width=10).pack(side="left", padx=4)
        ttk.Label(r, text="Article:").pack(side="left", padx=(10, 0))
        ttk.Combobox(r, textvariable=self.article, width=5, state="readonly",
                     values=["a", "an", "the"]).pack(side="left", padx=4)

        pl = ttk.LabelFrame(self, text="Place for testing (optional)", padding=8)
        pl.pack(fill="x", pady=4)
        r = ttk.Frame(pl); r.pack(fill="x", pady=2)
        ttk.Label(r, text="In shop:", width=12).pack(side="left")
        ttk.Combobox(r, textvariable=self.shop, width=18, state="readonly",
                     values=list(self._shop_map)).pack(side="left", padx=4)
        ttk.Label(r, text="In dungeon's 1st chest:").pack(side="left", padx=(10, 0))
        ttk.Combobox(r, textvariable=self.chest, width=20, state="readonly",
                     values=list(self._chest_map)).pack(side="left", padx=4)

        ttk.Button(self, text="Add custom item", command=self.do_add).pack(anchor="w", pady=4)
        self.log = LogPanel(self); self.log.pack(fill="both", expand=True)

    def _donor_list(self):
        return sorted({n for n in ffcc_items.NAMES.values()
                       if not n.startswith(("Equip", "Extra")) and "Test" not in n})

    def _iso(self):
        p = self.iso.get().strip()
        if not p or not os.path.isfile(p):
            messagebox.showwarning("No ISO", "Pick a valid ISO (a copy)."); return None
        return p

    def _slot(self):
        try:
            return int(self.slot.get(), 0)
        except ValueError:
            messagebox.showwarning("Bad slot", "Slot id must look like 0x162."); return None

    def _browse_png(self, var):
        p = filedialog.askopenfilename(title="Choose a texture PNG",
                                       filetypes=[("PNG image", "*.png"), ("All files", "*.*")])
        if p:
            var.set(p)

    def do_listfree(self):
        iso = self._iso()
        if iso:
            self.log.write(run_capture(customitem.cmd_list_free, iso))

    def do_show(self):
        iso = self._iso(); sid = self._slot()
        if iso and sid is not None:
            self.log.write(run_capture(customitem.cmd_show, iso, sid))

    def do_add(self):
        iso = self._iso(); sid = self._slot()
        if not iso or sid is None:
            return
        name = self.name.get().strip()
        if not name:
            messagebox.showwarning("No name", "Enter an item name."); return
        try:
            gil = int(self.gil.get()) if self.gil.get().strip() else None
        except ValueError:
            messagebox.showwarning("Bad price", "Price must be a number."); return
        shop = self._shop_map.get(self.shop.get())
        chest = self._chest_map.get(self.chest.get())
        if not messagebox.askyesno("Add item",
                f"Write '{name}' into slot 0x{sid:x} of {os.path.basename(iso)}?\n"
                "This edits the ISO in place — make sure it's a copy."):
            return
        donor, article = self.donor.get().strip(), self.article.get()
        desc = self.desc.get().strip()
        model = None
        if self.model.get().strip():
            try:
                model = int(self.model.get().strip(), 0)
            except ValueError:
                messagebox.showwarning("Bad model", "Model id must look like 0x37 or 55."); return
        retex = self.retex.get().strip() or None
        if retex and not os.path.isfile(retex):
            messagebox.showwarning("No PNG", "Retexture file not found."); return

        def work():
            info = customitem.add_custom_item(iso, sid, name, donor, gil, article,
                                              shop, chest, desc, model, retex)
            print(f"Added 0x{sid:03x} '{info['name']}' (was '{info['old_name']}') — "
                  f"model 0x{info['model']:04x} from {info['donor']}, "
                  f"gil={info['gil'] if info['gil'] is not None else 'donor'}")
            if info.get("desc"):
                print(f"  description: {info['desc']!r}")
            if info.get("retex"):
                print("  retexture:", info["retex"])
            for p in info["placed"]:
                print("  placed in", p)
            print(f"Tooling: add  NAMES[0x{sid:03x}] = \"{info['name']}\"  to ffcc_items.py and "
                  f"remove 0x{sid:03x} from randomizer.EXCLUDE for randomizer/editor support.")
        self.log.write(run_capture(work))


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

    nb.add(CustomItemTab(nb), text="Custom Item")

    helptab = ttk.Frame(nb, padding=8)
    nb.add(helptab, text="Help")
    h = scrolledtext.ScrolledText(helptab, wrap="word")
    h.insert("1.0", HELP)
    h.config(state="disabled")
    h.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
