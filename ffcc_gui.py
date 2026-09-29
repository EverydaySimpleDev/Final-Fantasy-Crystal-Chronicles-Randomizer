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
import datetime
import io
import json
import os
import queue
import random
import shutil
import threading
import tkinter as tk
import zipfile as _zipfile
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

# Warm parchment/gold palette (evoking FFCC's world-map/caravan look) instead
# of Tk's default battleship gray. Module-level so both the ttk style setup
# and the few plain (non-ttk) widgets below - the log's ScrolledText, the
# ScrollableTab canvases - can share the exact same colors.
THEME_BG = "#f3e8d0"        # main parchment background
THEME_FIELD_BG = "#fffdf6"  # entries/text areas - slightly lighter, readable
THEME_TEXT = "#3b2a1a"      # warm dark brown instead of pure black
THEME_ACCENT = "#7a4a1e"    # borders / labelframe titles
THEME_GOLD = "#c9962c"      # selected tab / active accents
THEME_BTN_BG = "#e8d3a0"
THEME_BTN_ACTIVE = "#d9bd78"


def apply_theme(root):
    """Recolor every ttk widget app-wide (global effect - covers tabs defined
    in other modules too, e.g. chesteditor.App, with no changes needed there)
    to the warm palette above, replacing Tk's default gray theme."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")   # base theme that actually honors custom colors
    except tk.TclError:
        pass
    root.configure(background=THEME_BG)
    style.configure(".", background=THEME_BG, foreground=THEME_TEXT)
    for cls in ("TFrame", "TLabelframe", "TLabel", "TCheckbutton", "TRadiobutton",
                "TNotebook", "TPanedwindow"):
        style.configure(cls, background=THEME_BG, foreground=THEME_TEXT)
    style.map("TCheckbutton", background=[("active", THEME_BG)])
    style.map("TRadiobutton", background=[("active", THEME_BG)])
    style.configure("TLabelframe.Label", background=THEME_BG, foreground=THEME_ACCENT,
                     font=("Segoe UI", 9, "bold"))
    style.configure("TButton", background=THEME_BTN_BG, foreground=THEME_TEXT,
                     bordercolor=THEME_ACCENT, focuscolor=THEME_GOLD)
    style.map("TButton", background=[("active", THEME_BTN_ACTIVE), ("pressed", THEME_GOLD)])
    style.configure("TEntry", fieldbackground=THEME_FIELD_BG, foreground=THEME_TEXT)
    style.configure("TCombobox", fieldbackground=THEME_FIELD_BG, foreground=THEME_TEXT)
    style.map("TCombobox", fieldbackground=[("readonly", THEME_FIELD_BG)])
    style.configure("TNotebook.Tab", background=THEME_BTN_BG, foreground=THEME_TEXT,
                     padding=(10, 4))
    style.map("TNotebook.Tab", background=[("selected", THEME_GOLD)],
              foreground=[("selected", THEME_FIELD_BG)])
    style.configure("Vertical.TScrollbar", background=THEME_BTN_BG, troughcolor=THEME_BG,
                     bordercolor=THEME_ACCENT)
    style.configure("Horizontal.TScrollbar", background=THEME_BTN_BG, troughcolor=THEME_BG,
                     bordercolor=THEME_ACCENT)


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
        self.txt = scrolledtext.ScrolledText(self, height=14, wrap="word",
                                              background=THEME_FIELD_BG, foreground=THEME_TEXT,
                                              insertbackground=THEME_TEXT, relief="flat")
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


class ScrollableTab(ttk.Frame):
    """Wraps `inner_cls(<parent>, *args, **kwargs)` in a vertically
    scrollable canvas, so a tab whose content is taller than the window
    gets a scrollbar instead of being clipped/hidden below the fold. The
    inner tab class needs no changes - it's just built with this frame's
    internal canvas as its parent instead of the notebook directly."""
    def __init__(self, master, inner_cls, *args, **kwargs):
        super().__init__(master)
        canvas = tk.Canvas(self, highlightthickness=0, background=THEME_BG)
        vbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        self.inner = inner_cls(canvas, *args, **kwargs)
        win = canvas.create_window((0, 0), window=self.inner, anchor="nw")

        def _on_inner_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self.inner.bind("<Configure>", _on_inner_configure)

        def _on_canvas_configure(event):
            canvas.itemconfig(win, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel only scrolls this canvas while the pointer is over it,
        # so it doesn't hijack scrolling in the log panel or other widgets.
        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_wheel(_event):
            canvas.bind_all("<MouseWheel>", _on_wheel)
        def _unbind_wheel(_event):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)


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
        self.rand_bonus = tk.BooleanVar(value=False)
        self.mog_never_tired = tk.BooleanVar(value=False)
        self.start_loc = tk.StringVar(value="Tipa")
        self.skip_mio = tk.BooleanVar(value=False)
        self.skip_intro = tk.BooleanVar(value=False)
        self.goblin_wall_always_visible = tk.BooleanVar(value=False)
        self.randomize_miasma_elements = tk.BooleanVar(value=False)
        self.stage_key_locks = tk.BooleanVar(value=False)
        self.randomize_bosses = tk.BooleanVar(value=False)
        self.debug_menu = tk.BooleanVar(value=False)

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

        # --- bonus pools (post-stage rewards, newbattle.cfd - independent file) ---
        bp = ttk.LabelFrame(self, text="Bonus Pools", padding=8); bp.pack(fill="x", pady=4)
        ttk.Checkbutton(bp, text="Randomize post-stage bonus rewards (uses the same "
                        "Mode/Item pool settings above; 13 of 14 dungeons have one - "
                        "Mount Vellenge has no bonus-pool block in the real game)",
                        variable=self.rand_bonus).pack(anchor="w")

        # --- gameplay tweaks (Start.dol patches, independent of item rando) ---
        gt = ttk.LabelFrame(self, text="Gameplay Tweaks", padding=8); gt.pack(fill="x", pady=4)
        ttk.Checkbutton(gt, text="Mog never gets tired (removes the stamina penalty for "
                        "running while carrying the chalice)",
                        variable=self.mog_never_tired).pack(anchor="w")
        sl = ttk.Frame(gt); sl.pack(fill="x", anchor="w", pady=(6, 0))
        ttk.Label(sl, text="Starting location:").pack(side="left")
        self.start_loc_box = ttk.Combobox(sl, state="readonly", width=16,
                                          values=list(rnd.STARTING_LOCATIONS),
                                          textvariable=self.start_loc)
        self.start_loc_box.pack(side="left", padx=4)
        self.start_loc_box.bind("<<ComboboxSelected>>", self._on_start_loc_change)
        ttk.Label(sl, text="(only towns with a completable Year 1 are offered)",
                  foreground="#777").pack(side="left")
        self.start_loc_warn = ttk.Label(gt, foreground="#a33", wraplength=520, justify="left")
        self.start_loc_warn.pack(anchor="w", pady=(2, 0))
        self._update_start_loc_warning()
        ttk.Checkbutton(gt, text="Skip Meteor Parasite -> Mio questions -> jump straight to Raem",
                        variable=self.skip_mio).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="EXPERIMENTAL: not yet confirmed safe by a full playthrough - "
                  "may leave state the Mio questions would normally set unset.",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Skip the opening intro cutscene",
                        variable=self.skip_intro).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(gt, text="Show Goblin Wall on the world map from Year 1",
                        variable=self.goblin_wall_always_visible).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(gt, text="Randomize Miasma Stream elements per seed",
                        variable=self.randomize_miasma_elements).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="EXPERIMENTAL: REQUIRES \"Show Goblin Wall...\" above to also be "
                  "checked - that's what guarantees every element is obtainable from Year 1, "
                  "so a shuffled stream can never demand one you have no way to get yet. "
                  "Randomization will be skipped (with a log message) if the other box isn't "
                  "checked too.",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Lock stages behind key artifacts (per dungeon)",
                        variable=self.stage_key_locks).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="EXPERIMENTAL: creates 14 new key artifacts (one per dungeon) "
                  "and hides each one in a handful of chests in a randomized, always-"
                  "solvable chain of dungeons - River Belle Path always stays open, and "
                  "no dungeon's key is ever placed inside that same dungeon. All 13 "
                  "gated dungeons now check for their key on entry, but this hasn't yet "
                  "been confirmed by a full in-game playthrough of every dungeon.",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Randomize bosses (shuffle dungeon bosses between arenas)",
                        variable=self.randomize_bosses).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="EXPERIMENTAL: each dungeon's boss room gets another dungeon's "
                  "boss, with its helpers and summons. Goblin King and Lich stay in their "
                  "own arenas (they need their arena's scripts); Mount Vellenge's final "
                  "boss isn't moved. A moved boss may still play the old boss's entrance. "
                  "Holy stays obtainable wherever Lich and Zombie Dragon end up. To choose "
                  "bosses per dungeon (any boss, including Lich), use Export JSON / Patch "
                  "from JSON and edit \"_bosses\". Source ISO must have unmoved bosses.",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Enable developer debug menu (Development Mode)",
                        variable=self.debug_menu).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="Plug in a SECOND GameCube controller (Port 2) to use it: "
                  "A opens the debug menu, B closes it, D-pad Up/Down selects an entry, "
                  "A/B toggles it. EXPERIMENTAL QA menu (invincibility, collision, "
                  "particle/shadow toggles, etc.) - some entries may do nothing or "
                  "destabilize the game.",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")

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
    FIELDS_OF_FUM_WARNING = (
        "⚠ Fields of Fum: do NOT change your chalice element away from Fire "
        "before you're ready to cross back. The Miasma Stream on that side is Fire, "
        "and switching away from Fire (e.g. to Wind in Selepation Cave) can soft-lock "
        "your only way home, forcing a new save file.")

    def _update_start_loc_warning(self):
        fum = self.start_loc.get() == "Fields of Fum"
        self.start_loc_warn.config(text=self.FIELDS_OF_FUM_WARNING if fum else "")

    def _on_start_loc_change(self, _event=None):
        self._update_start_loc_warning()
        if self.start_loc.get() == "Fields of Fum":
            messagebox.showwarning("Soft-lock risk", self.FIELDS_OF_FUM_WARNING)

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
        ns.rand_bonus = self.rand_bonus.get()
        ns.mog_never_tired = self.mog_never_tired.get()
        ns.start_loc = self.start_loc.get()
        ns.skip_mio = self.skip_mio.get()
        ns.skip_intro = self.skip_intro.get()
        ns.goblin_wall_always_visible = self.goblin_wall_always_visible.get()
        ns.randomize_miasma_elements = self.randomize_miasma_elements.get()
        ns.stage_key_locks = self.stage_key_locks.get()
        ns.randomize_bosses = self.randomize_bosses.get()
        ns.debug_menu = self.debug_menu.get()
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
        extra = ((1 if ns.rand_shops else 0) + (1 if ns.rand_prices else 0)
                 + (1 if ns.rand_bonus else 0)
                 + (1 if ns.mog_never_tired else 0)
                 + (1 if getattr(ns, "start_loc", "Tipa") != "Tipa" else 0)
                 + (1 if getattr(ns, "skip_mio", False) else 0)
                 + (1 if getattr(ns, "skip_intro", False) else 0)
                 + (1 if getattr(ns, "goblin_wall_always_visible", False) else 0)
                 + (1 if getattr(ns, "randomize_miasma_elements", False) else 0)
                 + (1 if getattr(ns, "stage_key_locks", False) else 0)
                 + (1 if getattr(ns, "randomize_bosses", False) else 0)
                 + (1 if getattr(ns, "debug_menu", False) else 0))
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
        boss_plan = None
        if getattr(ns, "randomize_bosses", False):
            import bossshuffle
            boss_plan = bossshuffle.random_plan(random.Random(f"{ns.seed}-bosses"))
        holy = rnd.holy_dungeons_for(boss_plan)
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
                                                    ns.max_artifacts, only_by_disc,
                                                    holy_dungeons=holy)
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
            if getattr(ns, "rand_bonus", False):
                self._q.put(("label", "Randomizing bonus pools"))
                try:
                    changes = rnd.randomize_bonus_pools(out, random.Random(ns.seed),
                                                        mode=ns.mode, pool=pool, apply=True)
                    self._q.put(("log", f"  bonus pools: {len(changes)} slot(s) "
                                        f"across {len(rnd.NEWBATTLE_BLOCKS)} dungeon(s)"))
                except Exception as e:
                    self._q.put(("log", f"  [error] bonus pools: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "mog_never_tired", False):
                self._q.put(("label", "Patching Start.dol (Mog never tired)"))
                try:
                    rnd.patch_mog_never_tired(out, apply=True)
                    self._q.put(("log", "  Mog never tired: patched"))
                except Exception as e:
                    self._q.put(("log", f"  [error] Mog never tired: {e}"))
                step += 1
                self._q.put(("value", step))
            start_loc = getattr(ns, "start_loc", "Tipa")
            if start_loc and start_loc != "Tipa":
                self._q.put(("label", f"Patching starting location ({start_loc})"))
                try:
                    rnd.patch_starting_location(out, start_loc, apply=True)
                    self._q.put(("log", f"  starting location: patched to {start_loc}"))
                    if start_loc == "Fields of Fum":
                        self._q.put(("log", f"  {self.FIELDS_OF_FUM_WARNING}"))
                except Exception as e:
                    self._q.put(("log", f"  [error] starting location: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "skip_mio", False):
                self._q.put(("label", "Patching Meteor Parasite -> Raem skip"))
                try:
                    rnd.patch_skip_mio_questions(out, apply=True)
                    self._q.put(("log", "  Mio-questions skip: patched (EXPERIMENTAL)"))
                except Exception as e:
                    self._q.put(("log", f"  [error] Mio-questions skip: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "skip_intro", False):
                self._q.put(("label", "Patching intro-cutscene skip"))
                try:
                    rnd.patch_skip_intro_cutscene(out, apply=True)
                    self._q.put(("log", "  intro cutscene skip: patched"))
                except Exception as e:
                    self._q.put(("log", f"  [error] intro cutscene skip: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "goblin_wall_always_visible", False):
                self._q.put(("label", "Patching Goblin Wall always-visible"))
                try:
                    rnd.patch_goblin_wall_always_visible(out, apply=True)
                    self._q.put(("log", "  Goblin Wall always visible: patched"))
                except Exception as e:
                    self._q.put(("log", f"  [error] Goblin Wall always visible: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "randomize_miasma_elements", False):
                if not getattr(ns, "goblin_wall_always_visible", False):
                    self._q.put(("log", "  [skipped] Randomize Miasma Stream elements: "
                                        "also requires \"Show Goblin Wall...\" to be checked "
                                        "(guarantees every element is obtainable from Year 1) "
                                        "- check both boxes and re-run."))
                else:
                    self._q.put(("label", "Patching Miasma Stream elements"))
                    try:
                        groups = rnd.randomize_miasma_elements(out, random.Random(), apply=True)
                        self._q.put(("log", f"  Miasma Stream elements: randomized {groups}"))
                    except Exception as e:
                        self._q.put(("log", f"  [error] Miasma Stream elements: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "stage_key_locks", False):
                self._q.put(("label", "Patching stage-key locks"))
                try:
                    rnd.create_stage_key_items(out)
                    chain = rnd.randomize_stage_key_chain(random.Random())
                    rnd.place_stage_keys(out, chain, random.Random(), holy_dungeons=holy)
                    rnd.patch_stage_key_locks(out, apply=True)
                    self._q.put(("log", f"  stage-key artifacts: created 14, placed via chain {chain} "
                                        "- all 13 gated dungeons now check for their key on entry"))
                except Exception as e:
                    self._q.put(("log", f"  [error] stage-key locks: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "debug_menu", False):
                self._q.put(("label", "Patching Start.dol (debug menu unlock)"))
                try:
                    rnd.patch_debug_menu(out, apply=True)
                    self._q.put(("log", "  debug menu: patched (EXPERIMENTAL - use a "
                                        "second controller on Port 2: A=open, B=close, "
                                        "D-pad Up/Down=select, A/B=toggle entry)"))
                except Exception as e:
                    self._q.put(("log", f"  [error] debug menu: {e}"))
                step += 1
                self._q.put(("value", step))
            spoiler = os.path.splitext(out)[0] + " - spoiler.txt"
            run_capture(rnd.cmd_spoiler, out, spoiler, ns.ref, rnd._options_header(ns))
            if boss_plan is not None:
                # last: this rebuilds the ISO (arena files change size), after
                # every in-place patch above
                self._q.put(("label", "Shuffling bosses (rebuilding ISO)"))
                import bossshuffle
                try:
                    blog = bossshuffle.apply_boss_plan(out, boss_plan)
                    moved = sum(1 for l in blog if not l.startswith("    ") and "->" in l
                                and not l.startswith("Start.dol"))
                    self._q.put(("log", f"  bosses: {moved} arena(s) got a different boss "
                                        "(EXPERIMENTAL - placement is in the spoiler)"))
                    with open(spoiler, "a", encoding="utf-8") as f:
                        f.write("\n" + "\n".join(bossshuffle.plan_text(boss_plan)) + "\n")
                except Exception as e:
                    self._q.put(("log", f"  [error] boss shuffle: {e}"))
                step += 1
                self._q.put(("value", step))
            for problem in rnd.check_holy_access(out, holy):
                self._q.put(("log", f"  [warning] {problem}"))
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

GAMEPLAY TWEAKS (Randomizer tab)
  A few independent, single-purpose toggles - mix and match freely, and
  independent of chest/item randomization:
    Mog never gets tired  - removes the stamina penalty for running while
       carrying the chalice.
    Starting location  - start a new game somewhere other than Tipa (only
       towns where Year 1 is completable are offered).
    Skip Meteor Parasite -> Mio questions -> Raem  - EXPERIMENTAL, not yet
       confirmed safe across a full playthrough.
    Skip the opening intro cutscene  - jumps straight past it on a new game.
    Show Goblin Wall on the world map from Year 1  - reveals its road/icon
       from the start instead of waiting for the Year 1->2 transition.
    Randomize Miasma Stream elements  - EXPERIMENTAL, shuffles which element
       each of the 4 rotating streams needs per year. REQUIRES "Show Goblin
       Wall..." above to also be checked (guarantees every element is
       obtainable from Year 1) - skipped with a log warning otherwise.
    Randomize post-stage bonus rewards (Bonus Pools section)  - randomizes
       the end-of-dungeon score-reward pool, separate from chests/enemy
       drops. 13 of 14 dungeons have one (Mount Vellenge has none in the
       real game).
    Lock stages behind key artifacts  - EXPERIMENTAL, creates 14 new key
       artifacts (one per dungeon) placed via a randomized, always-solvable
       chest chain (River Belle Path always stays open; chests only, never
       enemy drops; no dungeon's key is ever in that same dungeon). 6 of the
       13 gated dungeons (Goblin Wall, Veo Lu Sluice, Moschet Manor, Tida,
       Mine of Cathuriges, Mushroom Forest) are confirmed working in-game;
       the other 7 (Selepation Cave, Daemon's Court, Conall Curach, Rebena Te
       Ra, Mount Vellenge, Mount Kilanda, Lynari Desert) are only statically
       verified so far, NOT yet confirmed in-game - treat as unvalidated
       until spot-checked.
       The 14 keys: River/Gob/Mine/Shroom/Tida/Manor/Lava/Fort/Selep/
       Sluice/Lynari/Conall/Rebena/Vellen Key, unlocking River Belle Path
       (never actually locked)/Goblin Wall/Mine of Cathuriges/Mushroom
       Forest/Tida/Moschet Manor/Mount Kilanda/Daemon's Court/Selepation
       Cave/Veo Lu Sluice/Lynari Desert/Conall Curach/Rebena Te Ra/Mount
       Vellenge respectively - see the README for the full name/
       description table.
    Randomize bosses  - EXPERIMENTAL, shuffles the 13 dungeon bosses between
       boss arenas, each with its helpers and summons. Goblin King and Lich
       stay home in a random shuffle; Mount Vellenge's final boss never moves.
       A moved boss may play the old boss's entrance. Holy (Life + an element
       stone) stays obtainable wherever Lich and Zombie Dragon end up.
       JSON: "_randomize_bosses": true shuffles on patch; "_bosses" maps each
       dungeon to a boss (any of the names in "_boss_choices", Lich included:
       it brings its orbs, and its teleport points are estimated for the new
       arena). Entries naming a dungeon's own boss mean "no preference".
       Placement is written to the spoiler. Needs a source ISO whose bosses
       haven't been moved yet.
    Enable developer debug menu  - EXPERIMENTAL, unlocks a hidden QA menu.
       Needs a second GameCube controller on Port 2 (A=open, B=close, D-pad
       Up/Down=select, A/B=toggle). Some entries may do nothing or
       destabilize the game.
  Each toggle round-trips through Export JSON / Patch from JSON the same way
  as chest data, under its own `_`-prefixed key - export to see the exact
  key names and current state.

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

AP PATCH
  Prepares a copy of your vanilla ISO for use with the FFCC Archipelago client.
  1. Browse to your clean, unmodified vanilla ISO (source — never touched).
  2. The output path auto-fills to "<source> - AP.iso"; change it with "Save as…".
  3. Click "Patch for Archipelago". The tool copies the vanilla ISO, installs the
     AP Item definition (0x162), then overwrites every game8-identified chest slot
     with that item ID. The patched ISO is identical for every AP seed — the
     Archipelago client delivers the actual randomized items via Dolphin memory
     writes when each chest is opened at runtime.
  You only need to run this once. Use the same AP-patched ISO for any future
  Archipelago seeds; the client handles all per-seed item differences.

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


# ---------------------------------------------------------------------------
# AP Patch tab
# ---------------------------------------------------------------------------
class APPatchTab(ttk.Frame):
    """Copies a vanilla ISO and patches all game8 chests for Archipelago.

    Standard mode: every chest becomes AP Item (0x162); client delivers real items.
    Hybrid mode  : add a .ffcc file — your own items appear physically in chests
                   while items belonging to other players still show as AP Item.
    """

    def __init__(self, nb):
        super().__init__(nb, padding=8)
        self.src  = tk.StringVar()   # vanilla ISO — read only, never modified
        self.out  = tk.StringVar()   # AP-patched copy — what gets written
        self.ffcc = tk.StringVar()   # optional .ffcc placement file (hybrid mode)

        ttk.Label(self, text=(
            "Creates an Archipelago-ready ISO.\n\n"
            "Standard patch  (no .ffcc file): every game8 chest is replaced with AP Item.\n"
            "  The client intercepts each pickup and writes the real item to memory.\n\n"
            "Hybrid patch  (with .ffcc file): your own items appear as real item models\n"
            "  in the chest.  Items for other players still show as AP Item.  The game\n"
            "  engine gives your items on pickup; the client skips those to avoid doubles."
        ), justify="left", foreground="#444").pack(anchor="w", pady=(0, 8))

        sf = ttk.Frame(self); sf.pack(fill="x", pady=2)
        ttk.Label(sf, text="Vanilla ISO (source, never changed):", width=36).pack(side="left")
        ttk.Entry(sf, textvariable=self.src).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(sf, text="Browse…", command=self._browse_src).pack(side="left")
        self.src.trace_add("write", lambda *_: self._suggest_out())

        of = ttk.Frame(self); of.pack(fill="x", pady=2)
        ttk.Label(of, text="Output ISO (AP-patched copy):", width=36).pack(side="left")
        ttk.Entry(of, textvariable=self.out).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(of, text="Save as…", command=self._browse_out).pack(side="left")

        ff = ttk.Frame(self); ff.pack(fill="x", pady=2)
        ttk.Label(ff, text=".ffcc placement file (optional — hybrid mode):", width=36).pack(side="left")
        ttk.Entry(ff, textvariable=self.ffcc).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(ff, text="Browse…", command=self._browse_ffcc).pack(side="left")

        bf = ttk.Frame(self); bf.pack(fill="x", pady=8)
        self._btn = ttk.Button(bf, text="Patch for Archipelago", command=self.do_patch)
        self._btn.pack(side="left")
        self._mode_lbl = ttk.Label(bf, text="  Mode: standard (all chests → AP Item)",
                                   foreground="#666")
        self._mode_lbl.pack(side="left")
        self.ffcc.trace_add("write", lambda *_: self._update_mode_label())

        self.log = LogPanel(self)
        self.log.pack(fill="both", expand=True)

    def _update_mode_label(self, *_):
        f = self.ffcc.get().strip()
        if f and os.path.isfile(f):
            self._mode_lbl.config(text="  Mode: hybrid (own items in chest, others → AP Item)",
                                  foreground="#0a0")
        elif f:
            self._mode_lbl.config(text="  Mode: hybrid (file not found yet)", foreground="#a60")
        else:
            self._mode_lbl.config(text="  Mode: standard (all chests → AP Item)", foreground="#666")

    @staticmethod
    def _same(a, b):
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))

    def _browse_src(self):
        browse_iso(self.src)

    def _browse_out(self):
        s = self.src.get().strip()
        init = os.path.basename(os.path.splitext(s)[0] + " - AP.iso") if s else "AP.iso"
        p = filedialog.asksaveasfilename(
            title="Save AP-patched ISO as", defaultextension=".iso",
            initialfile=init,
            filetypes=[("Disc image", "*.iso *.gcm"), ("All", "*.*")])
        if p:
            self.out.set(p)

    def _browse_ffcc(self):
        p = filedialog.askopenfilename(
            title="Select Archipelago .ffcc placement file",
            filetypes=[("FFCC placement file", "*.ffcc"), ("ZIP container", "*.zip"), ("All", "*.*")])
        if p:
            self.ffcc.set(p)
            self._suggest_out_from_ffcc(p)

    def _suggest_out_from_ffcc(self, ffcc_path):
        """Update the output ISO path to include seed + timestamp from the .ffcc file."""
        s = self.src.get().strip()
        if not s:
            return
        seed = None
        try:
            try:
                with _zipfile.ZipFile(ffcc_path) as zf:
                    for name in zf.namelist():
                        if name.endswith(".ffcc"):
                            seed = json.loads(zf.read(name)).get("seed")
                            break
            except _zipfile.BadZipFile:
                with open(ffcc_path, "r", encoding="utf-8") as fh:
                    seed = json.load(fh).get("seed")
        except Exception:
            pass
        stem = os.path.splitext(s)[0]
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if seed:
            self.out.set(f"{stem} - AP_{seed}_{ts}.iso")
        else:
            self.out.set(f"{stem} - AP_{ts}.iso")

    def _suggest_out(self, *_):
        s = self.src.get().strip()
        if s and not self.out.get().strip():
            self.out.set(os.path.splitext(s)[0] + " - AP.iso")

    def do_patch(self):
        src = self.src.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("No vanilla ISO",
                                   "Browse to your clean, unmodified FFCC ISO first.")
            return
        out = self.out.get().strip()
        if not out:
            messagebox.showwarning("No output path",
                                   "Choose where to save the AP-patched ISO.")
            return
        if self._same(src, out):
            messagebox.showerror("Same file",
                                 "Output must be a different file from the source.\n"
                                 "The vanilla ISO is never modified.")
            return

        ffcc = self.ffcc.get().strip()
        hybrid = bool(ffcc and os.path.isfile(ffcc))
        if ffcc and not hybrid:
            messagebox.showerror(".ffcc file not found",
                                 f"The .ffcc file was not found:\n{ffcc}\n\n"
                                 "Clear the field to use standard mode, or fix the path.")
            return

        if (os.path.isfile(out) and
                not messagebox.askyesno("Overwrite?",
                                        f"{os.path.basename(out)} already exists. Overwrite it?")):
            return

        try:
            shutil.copy2(src, out)
        except Exception as e:
            messagebox.showerror("Copy failed", str(e))
            return

        mode_str = "hybrid" if hybrid else "standard"
        self.log.write(f"Copied {os.path.basename(src)}  →  {os.path.basename(out)}")
        self.log.write(f"Patching chests ({mode_str} mode) — this may take a moment…")
        self._btn.config(state="disabled")
        self._q = queue.Queue()
        if hybrid:
            threading.Thread(target=self._worker_hybrid, args=(out, src, ffcc),
                             daemon=True).start()
        else:
            threading.Thread(target=self._worker_standard, args=(out, src),
                             daemon=True).start()
        self.after(100, self._poll)

    def _worker_standard(self, out, src):
        result = run_capture(rnd.cmd_ap_patch, out, src)
        self._q.put(result)

    def _worker_hybrid(self, out, src, ffcc):
        result = run_capture(rnd.cmd_hybrid_patch, out, src, ffcc)
        self._q.put(result)

    def _poll(self):
        try:
            result = self._q.get_nowait()
            self.log.write(result)
            self.log.write("Done!  Load the output ISO in Dolphin, then connect the FFCC Archipelago client.")
            self._btn.config(state="normal")
        except queue.Empty:
            self.after(100, self._poll)


def main():
    root = tk.Tk()
    root.title("FFCC Modding Toolkit")
    root.geometry("900x820")
    root.minsize(700, 480)
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    try:
        root.iconbitmap(os.path.join(assets_dir, "icon.ico"))
    except Exception:
        pass  # missing/unsupported icon file - fall back to Tk's default
    apply_theme(root)

    banner = tk.Frame(root, background=THEME_ACCENT)
    banner.pack(fill="x", side="top")
    try:
        # kept as a root attribute - PhotoImage is garbage-collected otherwise
        root._logo_img = tk.PhotoImage(file=os.path.join(assets_dir, "logo.png"))
        tk.Label(banner, image=root._logo_img, background=THEME_ACCENT).pack(
            side="left", padx=10, pady=6)
    except Exception:
        pass  # missing/unsupported logo file - banner still shows the title text
    tk.Label(banner, text="FFCC Modding Toolkit", background=THEME_ACCENT,
             foreground=THEME_FIELD_BG, font=("Segoe UI", 14, "bold")).pack(side="left")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    nb.add(ScrollableTab(nb, RandomizerTab), text="Randomizer")

    ce = ttk.Frame(nb)
    nb.add(ce, text="Chest Editor")
    chesteditor.App(ce)

    nb.add(ScrollableTab(nb, FileToolsTab), text="File Tools")

    nb.add(ScrollableTab(nb, CustomItemTab), text="Custom Item")

    nb.add(ScrollableTab(nb, APPatchTab), text="AP Patch")

    helptab = ttk.Frame(nb, padding=8)
    nb.add(helptab, text="Help")
    h = scrolledtext.ScrolledText(helptab, wrap="word", background=THEME_FIELD_BG,
                                   foreground=THEME_TEXT, relief="flat")
    h.insert("1.0", HELP)
    h.config(state="disabled")
    h.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
