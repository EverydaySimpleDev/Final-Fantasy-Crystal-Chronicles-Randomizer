"""
ffcc_gui.py - one window for all the FFCC chest tools.

    python ffcc_gui.py

Tabs:
  * Randomizer  - list / preview / randomize chests, write spoiler, export &
                  patch JSON (wraps randomizer.py).
  * Chest Editor- the per-chest / per-cycle editor (chesteditor.py).
  * File Tools  - extract/inject/list files in the ISO (gciso.py) and edit item
                  stats in param.cfd (items.py).

Nothing here does anything the command-line tools can't. It just exposes them
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
import subprocess
import sys
import threading
import tkinter as tk
import zipfile as _zipfile
from tkinter import ttk, filedialog, messagebox, scrolledtext

import lootcft
import gciso
import isocheck
import items as itemtool
import randomizer as rnd
import chesteditor
import shops
import customitem
import ffcc_items
import qolpatch

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
    """Call fn with stdout captured and return whatever it printed (+ errors)."""
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
        bar = ttk.Frame(self)
        bar.pack(fill="x")
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


def iso_is_supported(path):
    """Check the source ISO before building a new ISO from it (isocheck.py).
    An error stops with a message, a warning asks whether to go on. True to go on."""
    errors, warnings = isocheck.check(path)
    if errors:
        messagebox.showerror("Unsupported ISO", errors[0])
        return False
    if warnings:
        return messagebox.askyesno("Modified ISO?", warnings[0] + "\n\nPatch it anyway?")
    return True


def open_file(path):
    """Open a file with the program the system uses for it."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
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
        self.trap_visuals = tk.BooleanVar(value=True)
        self.start_loc = tk.StringVar(value="Tipa")
        self.skip_mio = tk.BooleanVar(value=False)
        self.skip_intro = tk.BooleanVar(value=False)
        self.goblin_wall_always_visible = tk.BooleanVar(value=False)
        self.randomize_miasma_elements = tk.BooleanVar(value=False)
        self.stage_key_locks = tk.BooleanVar(value=False)
        self.cycle_select = tk.BooleanVar(value=False)
        self.skip_miasma_streams = tk.BooleanVar(value=False)
        self.all_in_one_radar = tk.BooleanVar(value=False)
        self.gba_bonus_pool = tk.BooleanVar(value=False)
        self.gba_enemy_drops = tk.BooleanVar(value=False)
        self.randomize_bosses = tk.BooleanVar(value=False)
        self.randomize_world_zones = tk.BooleanVar(value=False)
        self.world_zone_icons = tk.BooleanVar(value=True)
        self.progression_logic = tk.BooleanVar(value=True)
        self.protect_stones = tk.BooleanVar(value=True)
        self.debug_menu = tk.BooleanVar(value=False)

        # Source ISO (read-only) -> Output ISO (created/written). Choosing a
        # source auto-suggests an output path so the original is never touched.
        sf = ttk.Frame(self)
        sf.pack(fill="x", pady=2)
        ttk.Label(sf, text="Source ISO (your original, never changed):", width=46).pack(side="left")
        ttk.Entry(sf, textvariable=self.src).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(sf, text="Browse…", command=self._browse_src).pack(side="left")
        of = ttk.Frame(self)
        of.pack(fill="x", pady=2)
        ttk.Label(of, text="Output ISO (the randomized copy):", width=46).pack(side="left")
        ttk.Entry(of, textvariable=self.out).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(of, text="Save as…", command=self._browse_out).pack(side="left")
        self.src.trace_add("write", lambda *_: self._suggest_out())

        opt = ttk.LabelFrame(self, text="Options", padding=8)
        opt.pack(fill="x", pady=6)

        r1 = ttk.Frame(opt)
        r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="Seed:").pack(side="left")
        self.seed_entry = ttk.Entry(r1, textvariable=self.seed, width=12)
        self.seed_entry.pack(side="left", padx=4)
        ttk.Checkbutton(r1, text="Random each run", variable=self.rand_seed,
                        command=self._toggle_seed).pack(side="left")
        self._toggle_seed()

        r2 = ttk.Frame(opt)
        r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="Mode:").pack(side="left")
        ttk.Radiobutton(r2, text="Any item anywhere", value="cross",
                        variable=self.mode).pack(side="left", padx=4)
        ttk.Radiobutton(r2, text="Keep original category", value="category",
                        variable=self.mode).pack(side="left", padx=4)

        r3 = ttk.Frame(opt)
        r3.pack(fill="x", pady=2)
        ttk.Label(r3, text="Rolls:").pack(side="left")
        for val, lbl in (("cycle", "One per cycle"), ("slot", "Per slot (most variety)"),
                         ("chest", "One per chest")):
            ttk.Radiobutton(r3, text=lbl, value=val, variable=self.rolls).pack(side="left", padx=4)

        r4 = ttk.Frame(opt)
        r4.pack(fill="x", pady=2)
        ttk.Label(r4, text="Item pool:").pack(side="left")
        ttk.Combobox(r4, state="readonly", width=12, values=POOLS,
                     textvariable=self.pool).pack(side="left", padx=4)
        ttk.Label(r4, text="Dungeon:").pack(side="left", padx=(10, 0))
        ttk.Combobox(r4, state="readonly", width=28,
                     values=["All dungeons"] + [n for _, n in DUNGEONS],
                     textvariable=self.dungeon).pack(side="left", padx=4)

        r5 = ttk.Frame(opt)
        r5.pack(fill="x", pady=2)
        ttk.Label(r5, text="Max artifacts per cycle:").pack(side="left")
        ttk.Spinbox(r5, from_=0, to=99, width=4, textvariable=self.max_art).pack(side="left", padx=4)
        ttk.Label(r5, text="(player can carry 4)", foreground="#777").pack(side="left")
        ttk.Checkbutton(r5, text="Also fill empty/placeholder slots",
                        variable=self.fill).pack(side="left", padx=12)

        r6 = ttk.Frame(opt)
        r6.pack(fill="x", pady=2)
        ttk.Checkbutton(r6, text="Randomize enemy drops too (uncheck = chests only)",
                        variable=self.include_drops).pack(side="left")
        r7 = ttk.Frame(opt)
        r7.pack(fill="x", pady=2)
        ttk.Checkbutton(r7, text="Keep required magicite obtainable (Holy for Lich / Zombie "
                        "Dragon, Fire for Tida's webs)",
                        variable=self.protect_stones).pack(side="left")

        # --- shops (independent of chest randomization) ---
        sh = ttk.LabelFrame(self, text="Shops", padding=8)
        sh.pack(fill="x", pady=4)
        ttk.Checkbutton(sh, text="Randomize shop inventories (stock swapped within "
                        "sellable items, so prices stay valid)",
                        variable=self.rand_shops, command=self._toggle_shops).pack(anchor="w")
        self.shop_box = ttk.Frame(sh)
        self.shop_box.pack(fill="x", padx=18, pady=(2, 0))
        ttk.Label(self.shop_box, text="Which shops:").pack(side="left")
        self._shop_checks = []
        for base, name in shops.SHOPS.items():
            cb = ttk.Checkbutton(self.shop_box, text=name, variable=self.shop_vars[base])
            cb.pack(side="left", padx=3)
            self._shop_checks.append(cb)
        ttk.Checkbutton(sh, text="Randomize shop prices (shuffles item prices, "
                        "works with or without item randomization)",
                        variable=self.rand_prices).pack(anchor="w", pady=(4, 0))
        self._toggle_shops()

        # --- bonus pools (post-stage rewards, newbattle.cfd - independent file) ---
        bp = ttk.LabelFrame(self, text="Bonus Pools", padding=8)
        bp.pack(fill="x", pady=4)
        ttk.Checkbutton(bp, text="Randomize post-stage bonus rewards (uses the same "
                        "Mode/Item pool settings above, and 13 of 14 dungeons have one - "
                        "Mount Vellenge has no bonus-pool block in the real game)",
                        variable=self.rand_bonus).pack(anchor="w")

        # --- gameplay tweaks (Start.dol patches, independent of item rando) ---
        gt = ttk.LabelFrame(self, text="Gameplay Tweaks", padding=8)
        gt.pack(fill="x", pady=4)
        ttk.Checkbutton(gt, text="Mog never gets tired (removes the stamina penalty for "
                        "running while carrying the chalice)",
                        variable=self.mog_never_tired).pack(anchor="w")
        ttk.Checkbutton(gt, text="Show trap visuals (Archipelago status traps play the game's own freeze/burn/poison/paralysis/slow effects)",
                        variable=self.trap_visuals).pack(anchor="w")
        sl = ttk.Frame(gt)
        sl.pack(fill="x", anchor="w", pady=(6, 0))
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
        ttk.Label(gt, text="EXPERIMENTAL: may leave state the Mio questions would normally "
                  "set unset.",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Skip the opening intro cutscene",
                        variable=self.skip_intro).pack(anchor="w", pady=(6, 0))
        self._goblin_box = ttk.Checkbutton(gt, text="Show Goblin Wall on the world map from Year 1",
                                           variable=self.goblin_wall_always_visible)
        self._goblin_box.pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(gt, text="Randomize Miasma Stream elements per seed",
                        variable=self.randomize_miasma_elements).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="EXPERIMENTAL: also turns on \"Show Goblin Wall...\" above - that's "
                  "what guarantees every element is obtainable from Year 1, so a shuffled "
                  "stream can never demand one you have no way to get yet.",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Lock stages behind key artifacts (per dungeon)",
                        variable=self.stage_key_locks).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="EXPERIMENTAL: creates 14 new key artifacts (one per dungeon) "
                  "and hides each one in a handful of chests in a randomized, always-"
                  "solvable chain of dungeons - River Belle Path always stays open, and "
                  "no dungeon's key is ever placed inside that same dungeon. All 13 "
                  "gated dungeons check for their key on entry.",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Cycle select: pick which reached cycle of a dungeon to play when entering it",
                        variable=self.cycle_select).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(gt, text="Skip Miasma Stream gates: entering one takes the caravan straight to the other side",
                        variable=self.skip_miasma_streams).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="Works whatever element the chalice holds, so a wrong element can't leave "
                  "you stuck behind a stream. The Mystery Miasma Stream still needs Unknown.",
                  wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="All-in-one GBA radar: the map, exits, enemies and chests on one radar",
                        variable=self.all_in_one_radar).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="For a GBA in controller port 2 (in Dolphin: \"GBA (Integrated)\"), or "
                  "each player's GBA in multiplayer.",
                  wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="GBA bonus pool pages: press A on the GBA radar to see the end-of-stage bonus items",
                        variable=self.gba_bonus_pool).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(gt, text="GBA enemy drops pages: press A on the GBA radar to see the artifacts enemies carry",
                        variable=self.gba_enemy_drops).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="Single player, with a GBA in controller port 2. A turns the page, B goes back "
                  "to the radar.",
                  wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Randomize world-map loading zones (which dungeon each map spot leads to)",
                        variable=self.randomize_world_zones).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="EXPERIMENTAL: shuffles 12 dungeons between their world-map spots "
                  "(Mount Kilanda and Mount Vellenge stay put). Each spot keeps its own "
                  "Miasma Stream gating and Myrrh-drop elements, so progression works like "
                  "vanilla. Only the dungeon you enter changes, and its exits return you to "
                  "the spot you came from. Stage-key locks follow the dungeons. Also turns "
                  "on \"Show Goblin Wall...\", since a dungeon may be moved onto its spot. "
                  "For Archipelago seeds, use the AP world's Shuffle Loading Zones option "
                  "instead. To choose dungeons per spot, use Export JSON / Patch from JSON "
                  "and edit \"_world_zones\".",
                  foreground="#a33", wraplength=520, justify="left").pack(anchor="w")
        self.world_zone_icons_box = ttk.Checkbutton(
            gt, text="Also show each spot's new dungeon building on the world map",
            variable=self.world_zone_icons)
        self.world_zone_icons_box.pack(anchor="w", padx=(20, 0))
        def _sync_zone_icons(*_):
            self.world_zone_icons_box.state(["!disabled"] if self.randomize_world_zones.get()
                                            else ["disabled"])
        self.randomize_world_zones.trace_add("write", _sync_zone_icons)
        _sync_zone_icons()
        # The zone and Miasma shuffles rely on Goblin Wall's spot in Year 1, so they
        # tick and lock its box.
        def _sync_goblin(*_):
            forced = self.randomize_world_zones.get() or self.randomize_miasma_elements.get()
            if forced:
                self.goblin_wall_always_visible.set(True)
            self._goblin_box.state(["disabled"] if forced else ["!disabled"])
        self.randomize_world_zones.trace_add("write", _sync_goblin)
        self.randomize_miasma_elements.trace_add("write", _sync_goblin)
        _sync_goblin()
        ttk.Checkbutton(gt, text="Use progression logic for loading zones and stage keys (recommended)",
                        variable=self.progression_logic).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="Picks the zone layout and the stage-key order so every year has "
                  "enough reachable dungeons, following each region's Miasma Stream "
                  "element, the Jegon River crossing and the boats. Imported JSON files "
                  "are never changed by this (set \"_progression_logic\": true in the "
                  "JSON to opt in).",
                  wraplength=520, justify="left").pack(anchor="w")
        ttk.Checkbutton(gt, text="Randomize bosses (shuffle dungeon bosses between arenas)",
                        variable=self.randomize_bosses).pack(anchor="w", pady=(6, 0))
        ttk.Label(gt, text="EXPERIMENTAL: each dungeon's boss room gets another dungeon's "
                  "boss, with its helpers and summons. Goblin King and Lich stay in their "
                  "own arenas (they need their arena's scripts), and Mount Vellenge's final "
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

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=4)
        self._buttons = []
        b = ttk.Button(btns, text="List dungeons", command=self.do_list)
        b.pack(side="left")
        self._buttons.append(b)
        b = ttk.Button(btns, text="Preview", command=lambda: self.do_run(False))
        b.pack(side="left", padx=4)
        self._buttons.append(b)
        b = ttk.Button(btns, text="Randomize!", command=lambda: self.do_run(True))
        b.pack(side="left")
        self._buttons.append(b)
        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=8)
        b = ttk.Button(btns, text="Write spoiler", command=self.do_spoiler)
        b.pack(side="left", padx=2)
        self._buttons.append(b)
        b = ttk.Button(btns, text="Export JSON", command=self.do_export)
        b.pack(side="left", padx=2)
        self._buttons.append(b)
        b = ttk.Button(btns, text="Patch from JSON…", command=self.do_patch)
        b.pack(side="left", padx=2)
        self._buttons.append(b)

        pf = ttk.Frame(self)
        pf.pack(fill="x", pady=(4, 0))
        self.prog_lbl = ttk.Label(pf, text="", anchor="w")
        self.prog_lbl.pack(fill="x")
        self.progress = ttk.Progressbar(pf, mode="determinate")
        self.progress.pack(fill="x")                     # full width of the tab

        self.log = LogPanel(self)
        self.log.pack(fill="both", expand=True)

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
            messagebox.showwarning("No source ISO", "Pick a valid source ISO first.")
            return None
        return s

    def _need_out(self, src):
        """Validate the output path and make sure it can never be the source."""
        o = self.out.get().strip()
        if not o:
            messagebox.showwarning("No output", "Choose where to save the randomized ISO.")
            return None
        if self._same(src, o):
            messagebox.showerror("Same file",
                                 "Output ISO must be different from the source ISO.\n"
                                 "The source is never modified.")
            return None
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
        ns.trap_visuals = self.trap_visuals.get()
        ns.start_loc = self.start_loc.get()
        ns.skip_mio = self.skip_mio.get()
        ns.skip_intro = self.skip_intro.get()
        # forced on by the zone / Miasma shuffles, which rely on Goblin Wall's spot in Year 1
        ns.goblin_wall_always_visible = (self.goblin_wall_always_visible.get()
                                         or self.randomize_world_zones.get()
                                         or self.randomize_miasma_elements.get())
        ns.randomize_miasma_elements = self.randomize_miasma_elements.get()
        ns.stage_key_locks = self.stage_key_locks.get()
        ns.cycle_select = self.cycle_select.get()
        ns.skip_miasma_streams = self.skip_miasma_streams.get()
        ns.all_in_one_radar = self.all_in_one_radar.get()
        ns.gba_bonus_pool = self.gba_bonus_pool.get()
        ns.gba_enemy_drops = self.gba_enemy_drops.get()
        ns.randomize_bosses = self.randomize_bosses.get()
        ns.randomize_world_zones = self.randomize_world_zones.get()
        ns.world_zone_icons = self.world_zone_icons.get()
        ns.progression_logic = self.progression_logic.get()
        ns.protect_stones = self.protect_stones.get()
        ns.debug_menu = self.debug_menu.get()
        return ns

    def _make_copy(self, src, out, seed=None):
        """Copy source -> output (the only file written). Returns True on
        success. The output gets the Archipelago title logo and banner, its
        disc name showing `seed` when given."""
        if os.path.isfile(out) and not messagebox.askyesno(
                "Overwrite output", f"{os.path.basename(out)} exists. Overwrite it?"):
            return False
        try:
            shutil.copy2(src, out)
        except Exception as e:
            messagebox.showerror("Copy failed", str(e))
            return False
        self.log.write(f"Created {out}")
        try:
            import titlelogo
            if titlelogo.install(out, seed=seed):
                self.log.write("Installed the Archipelago title logo, disc name and banner"
                               + (f" (seed {seed})" if seed is not None else ""))
        except Exception as e:
            self.log.write(f"  [note] title logo: {e}")
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
        if not iso_is_supported(src):
            return
        out = self._need_out(src)
        ns = self._ns()                                  # once, so the disc name has this run's seed
        if not out or not self._make_copy(src, out, seed=ns.seed):
            return
        self._randomize(out, ns)

    def _set_busy(self, busy):
        for b in self._buttons:
            b.config(state="disabled" if busy else "normal")

    def _randomize(self, out, ns):
        """Randomize the output ISO on a background thread (so the UI stays
        responsive and the progress bar updates), reporting only how many slots
        changed - never the items. A spoiler file is written for later reference."""
        pool = rnd.build_pool(ns.pool)
        if not pool:
            self.log.write(f"[error] empty pool for '{ns.pool}'")
            return
        found = rnd.dungeons_in_iso(out)
        if ns.dungeon:
            want = set(ns.dungeon)
            found = [d for d in found if d[0] in want]
        if not found:
            self.log.write("[error] no matching dungeons")
            return
        extra = ((1 if ns.rand_shops else 0) + (1 if ns.rand_prices else 0)
                 + (1 if ns.rand_bonus else 0)
                 + (1 if ns.mog_never_tired else 0)
                 + (1 if getattr(ns, "trap_visuals", False) else 0)
                 + (1 if getattr(ns, "start_loc", "Tipa") != "Tipa" else 0)
                 + (1 if getattr(ns, "skip_mio", False) else 0)
                 + (1 if getattr(ns, "skip_intro", False) else 0)
                 + (1 if getattr(ns, "goblin_wall_always_visible", False) else 0)
                 + (1 if getattr(ns, "randomize_miasma_elements", False) else 0)
                 + (1 if getattr(ns, "stage_key_locks", False) else 0)
                 + (1 if getattr(ns, "cycle_select", False) else 0)
                 + (1 if getattr(ns, "skip_miasma_streams", False) else 0)
                 + (1 if getattr(ns, "all_in_one_radar", False) else 0)
                 + (1 if getattr(ns, "gba_bonus_pool", False) or getattr(ns, "gba_enemy_drops", False) else 0)
                 + (1 if getattr(ns, "randomize_bosses", False) else 0)
                 + (1 if getattr(ns, "randomize_world_zones", False) else 0)
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
        zone_plan = None
        if getattr(ns, "randomize_world_zones", False):
            import worldzones
            zone_plan = worldzones.random_plan(random.Random(f"{ns.seed}-zones"))
        holy = rnd.stone_dungeons_for(boss_plan) if getattr(ns, "protect_stones", True) else {}
        try:
            for i, (script, friendly, discs) in enumerate(found, 1):
                self._q.put(("label", f"Randomizing: {friendly}"))
                only_by_disc = None
                if getattr(ns, "chests_only", False):
                    only_by_disc = {d: rnd.chest_set_indices(ns.ref, script, d) for d in discs}
                    if not any(only_by_disc.values()):
                        self._q.put(("log", f"  {friendly}: skipped (no Game8 chest data)"))
                        self._q.put(("value", i))
                        continue
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
            if getattr(ns, "trap_visuals", False):
                self._q.put(("label", "Patching Start.dol (trap visuals)"))
                try:
                    rnd.patch_trap_visuals(out, apply=True)
                    self._q.put(("log", "  Trap visuals: patched"))
                except Exception as e:
                    self._q.put(("log", f"  [error] Trap visuals: {e}"))
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
            # progression logic: after the Miasma Stream step, so the gate
            # elements it plans around are the final ones
            logic_chain = None
            if getattr(ns, "progression_logic", False) and (
                    getattr(ns, "randomize_world_zones", False) or getattr(ns, "stage_key_locks", False)):
                try:
                    plan, logic_chain, report = rnd.logic_plan(
                        out, random.Random(f"{ns.seed}-progression"),
                        getattr(ns, "randomize_world_zones", False),
                        getattr(ns, "stage_key_locks", False),
                        getattr(ns, "goblin_wall_always_visible", False))
                    if zone_plan is not None:
                        zone_plan = plan
                    self._q.put(("log", "  progression logic: " + ", ".join(report)))
                except Exception as e:
                    logic_chain = None
                    self._q.put(("log", f"  [warning] progression logic: {e} - using plain random"))
            if zone_plan is not None:
                # before stage keys: the locks follow each dungeon to its new node
                self._q.put(("label", "Shuffling world-map loading zones"))
                import worldzones
                try:
                    zlog = worldzones.apply_plan(out, zone_plan)
                    moved = sum(1 for n, d in zone_plan.items() if n != d)
                    self._q.put(("log", f"  world-map zones: {moved} node(s) lead to a different "
                                        "dungeon (EXPERIMENTAL - layout is in the spoiler)"))
                    if getattr(ns, "world_zone_icons", False):
                        try:
                            worldzones.apply_icons(out, zone_plan, zlog)
                            self._q.put(("log", "  world-map zones: " + zlog[-1]))
                        except Exception as e:
                            self._q.put(("log", f"  [error] world-map icons: {e}"))
                except Exception as e:
                    self._q.put(("log", f"  [error] world-map zones: {e}"))
                    zone_plan = None
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "stage_key_locks", False):
                self._q.put(("label", "Patching stage-key locks"))
                try:
                    rnd.create_stage_key_items(out)
                    chain = logic_chain or rnd.randomize_stage_key_chain(random.Random())
                    rnd.place_stage_keys(out, chain, random.Random(), holy_dungeons=holy)
                    rnd.patch_stage_key_locks(out, apply=True, sites=rnd.stage_lock_sites_for(zone_plan))
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
            if getattr(ns, "cycle_select", False):
                # after the zone, Miasma and stage-key patches: it grows world.cft
                self._q.put(("label", "Adding the cycle menu"))
                try:
                    import cycleselect
                    cycleselect.apply(out)
                    self._q.put(("log", "  cycle select: a dungeon's reached cycles can be picked when entering it"))
                except Exception as e:
                    self._q.put(("log", f"  [error] cycle select: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "skip_miasma_streams", False):
                self._q.put(("label", "Patching the Miasma Stream skip"))
                try:
                    import miasmaskip
                    miasmaskip.apply(out)
                    self._q.put(("log", "  Miasma Stream skip: entering a stream goes straight to the other side"))
                except Exception as e:
                    self._q.put(("log", f"  [error] Miasma Stream skip: {e}"))
                step += 1
                self._q.put(("value", step))
            if getattr(ns, "all_in_one_radar", False):
                self._q.put(("label", "Patching the GBA radar"))
                try:
                    import gbaradar
                    gbaradar.apply(out)
                    self._q.put(("log", "  all-in-one GBA radar: map, exits, enemies and chests on one radar"))
                except Exception as e:
                    self._q.put(("log", f"  [error] all-in-one GBA radar: {e}"))
                step += 1
                self._q.put(("value", step))
            try:
                import gbanames
                if gbanames.apply(out, log=lambda line: None):
                    self._q.put(("log", "  GBA item names: the new items are named on the GBA too"))
            except Exception as e:
                self._q.put(("log", f"  [error] GBA item names: {e}"))
            pool, drops = getattr(ns, "gba_bonus_pool", False), getattr(ns, "gba_enemy_drops", False)
            if pool or drops:
                # after the GBA item names: the pages' code goes after them
                self._q.put(("label", "Adding the GBA loot pages"))
                try:
                    import gbaloot
                    gbaloot.apply(out, pool, drops)
                    self._q.put(("log", "  GBA loot pages: press A on the GBA radar ("
                                        + ", ".join(n for on, n in ((pool, "bonus pool"), (drops, "enemy drops")) if on)
                                        + ")"))
                except Exception as e:
                    self._q.put(("log", f"  [error] GBA loot pages: {e}"))
                step += 1
                self._q.put(("value", step))
            spoiler = os.path.splitext(out)[0] + " - spoiler.txt"
            run_capture(rnd.cmd_spoiler, out, spoiler, ns.ref, rnd._options_header(ns))
            if zone_plan is not None:
                rnd.append_zone_spoiler(spoiler, zone_plan)
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
            for problem in rnd.check_stone_access(out, holy):
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
        """Runs ON the UI thread. Drains the worker's queue and updates widgets."""
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
        if not src or not iso_is_supported(src):
            return
        out = os.path.splitext(src)[0] + " - chests.json"
        self.log.write(run_capture(rnd.cmd_export, src, out, src))
        if os.path.isfile(out) and messagebox.askyesno("JSON written", f"Open {os.path.basename(out)}?"):
            open_file(out)

    def do_patch(self):
        src = self._need_src()
        if not src or not iso_is_supported(src):
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

        f = ttk.Frame(self)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text="ISO:", width=6).pack(side="left")
        ttk.Entry(f, textvariable=self.iso).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(f, text="Browse…", command=lambda: browse_iso(self.iso)).pack(side="left")

        gc =ttk.LabelFrame(self, text="Files inside the ISO (gciso)", padding=8)
        gc.pack(fill="x", pady=6)
        r1 = ttk.Frame(gc)
        r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="Filter:").pack(side="left")
        ttk.Entry(r1, textvariable=self.filt, width=24).pack(side="left", padx=4)
        ttk.Button(r1, text="List files", command=self.do_list).pack(side="left")
        r2 = ttk.Frame(gc)
        r2.pack(fill="x", pady=2)
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
        c = ttk.Frame(it)
        c.pack(fill="x", pady=2)
        ttk.Label(c, text="param.cfd:").pack(side="left")
        ttk.Entry(c, textvariable=self.cfd).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(c, text="Browse…", command=self._browse_cfd).pack(side="left")
        d = ttk.Frame(it)
        d.pack(fill="x", pady=2)
        ttk.Label(d, text="Item id:").pack(side="left")
        ttk.Entry(d, textvariable=self.iid, width=10).pack(side="left", padx=4)
        ttk.Button(d, text="Show", command=self.item_show).pack(side="left", padx=2)
        ttk.Label(d, text="Field:").pack(side="left", padx=(10, 0))
        ttk.Combobox(d, width=12, textvariable=self.field,
                     values=list(itemtool.FIELDS.keys())).pack(side="left", padx=2)
        ttk.Label(d, text="=").pack(side="left")
        ttk.Entry(d, textvariable=self.fval, width=10).pack(side="left", padx=2)
        ttk.Button(d, text="Set", command=self.item_set).pack(side="left", padx=2)

        self.log = LogPanel(self)
        self.log.pack(fill="both", expand=True)

    def _iso(self):
        p = self.iso.get().strip()
        if not p or not os.path.isfile(p):
            messagebox.showwarning("No ISO", "Pick a valid ISO.")
            return None
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
            messagebox.showwarning("No param.cfd", "Pick a param.cfd file (extract it from the ISO above).")
            return None
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
            messagebox.showwarning("No value", "Enter a value to set.")
            return
        self.log.write(run_capture(itemtool.cmd_set, cfd, int(self.iid.get(), 0),
                                   self.field.get(), self.fval.get().strip()))


# ---------------------------------------------------------------------------
# Help tab
# ---------------------------------------------------------------------------
HELP = """FFCC Modding Toolkit

None of the tools ever change your Source ISO. They always write a separate
Output ISO (you pick where), so your original is safe. Start from a clean,
unmodified NTSC-US copy of the game.

The patcher checks the Source ISO first. It has to be a plain ISO (not RVZ,
WIA, GCZ, CISO, WBFS or NKit, which Dolphin can convert: right-click the game,
"Convert File...", ISO) of the North American release (GCCE01, revision 0)
that hasn't been patched yet. An ISO made by this patcher isn't accepted as a
source, so always patch from your clean copy. If only some files differ from
the clean game (for example after the Chest Editor), it asks before going on.

WHICH TAB DO I NEED?
  Play the normal game with a few improvements .......... Quality of Life
  Play a randomized single-player game ................... Randomizer
  Play an Archipelago (multiworld) seed .................. AP Patch
  Hand-pick what each chest gives ........................ Chest Editor
  Advanced: raw files, item stats, new items ............. File Tools,
                                                           Custom Item

QUALITY OF LIFE
  The normal game with only the changes you tick - no chests, shops or bosses
  are randomized.
  1. Browse to your clean Source ISO. The Output ISO fills in as
     "<source> - QoL.iso". Change it with "Save as…" if you like.
  2. Tick what you want, then press "Create patched ISO".
  Patches:
    Other gender choice (on by default)  - adds "Other" at character creation,
       with neutral wording wherever the game's text depends on gender.
    Cycle select (on by default)  - on the world map, after you choose "Enter"
       at a dungeon (the element menu still comes first), pick which cycle to
       play: any cycle the dungeon has reached. Only asks once Cycle 1 is
       cleared. "Never mind" (or B) goes back. The dungeon's real cycle is put
       back when you leave, so replaying an old cycle costs nothing.
    Skip Miasma Stream gates (off by default)  - entering a Miasma Stream
       takes the caravan straight to the stop on the other side, whatever
       element the chalice holds, so a wrong element can never leave you
       stuck. You still choose to enter the stream as usual, then a black
       loading screen of about 20-30 seconds takes you across. The Mystery
       Miasma Stream to the Abyss still needs Unknown.
    All-in-one GBA radar (off by default)  - the GBA radar shows the area
       map, its exits, enemies and treasure chests together, instead of the
       one kind the game hands out (in single player, picked by how you
       brushed the Moogle). Needs a GBA in controller port 2 for single
       player (in Dolphin: Controllers > Port 2 > "GBA (Integrated)", with a
       GBA BIOS set), or each player's GBA in multiplayer.
    GBA bonus pool pages / GBA enemy drops pages (off by default)  - press A
       on the GBA radar (single player, GBA in port 2) to open pages. A turns
       the page, B goes back to the radar.
         Bonus pool: one page per bonus tier with the 4 items the end-of-
         stage bonus offers from it on the dungeon's current cycle, and the
         points it needs (single player multiplies your points by 1.35
         first, so you need a little less).
         Enemy drops: the artifacts this area's living enemies carry, each
         with the kind of enemy carrying it. An enemy's drop is picked when
         it appears, so this is what they will drop. The list is made when
         the area loads, so enemies you defeat stay on it until the next area.
    Mog never gets tired  - no stamina penalty for running with the chalice.
    Keep picked-up artifacts  - every artifact you pick up in a dungeon is
       kept, instead of choosing one at the end.
    Always best bonus tier  - the end-of-dungeon bonus always gives the best
       tier reached.
    Skip the opening intro cutscene.
    Skip Mio's questions  - EXPERIMENTAL: Meteor Parasite goes straight to Raem.
    Goblin Wall on the world map from Year 1  - instead of from Year 2.
    Lynari Desert north exit  - a quicksand pit at the north end of the first
       area that drops you into the second.
    Developer debug menu  - EXPERIMENTAL, see GAMEPLAY TWEAKS below.
  Display and start:
    Show enemy health  - a bar, the numbers (hp/max), or both, over each enemy.
       Bosses are left out.
    Show play timer  - a clock in the top-right corner. "play_time" shows the
       save's play time. "speedrun" keeps its own count: it starts at 0 on New
       Game or when a save is loaded and stops on the final blow to Memoira.
       "manual" is the same count, started and stopped only by hand.
       Speedrun controls (hold L + R + Z): D-pad Up pauses/resumes, Down
       resets to 0, Left hides/shows the timer.
    Starting location  - start a new game in another town (only towns where
       Year 1 can be completed are offered). Fields of Fum: don't change your
       chalice away from Fire until you're ready to cross back - you can get
       stuck on that side.
    Starting hearts  - 1 to 8 hearts for every tribe on a new character.
  Dungeon shortcuts: open a dungeon's gates, bridges or puzzles from the start
    (River Belle Path bridges, Goblin Wall gates, Mine of Cathuriges boxes,
    Tida webs, Moschet Manor doors, Selepation Cave elevators, Conall Curach
    log bridges, Rebena Te Ra gates, Lynari Desert's Unknown element puzzle).
  Command line: py qolpatch.py list   /   py qolpatch.py apply <iso> <option>...
    e.g. py qolpatch.py apply copy.iso other_gender cycle_select show_enemy_health=bar

RANDOMIZER
  1. Browse to your Source ISO (your clean original - only ever read).
  2. The Output ISO path fills in as "<source> - randomized.iso". Change it
     with "Save as…" if you like. The output must be a different file.
  3. Choose options:
       Seed  - the same seed and options give the same result. "Random each
               run" picks a new one every time.
       Mode  - Any item anywhere, or keep each chest's original category.
       Rolls - One per cycle (each chest gives one item per cycle, the clearest),
               Per slot (more variety, several items possible per cycle), or
               One per chest (the chest always gives the same item).
       Item pool - restrict to a category (artifacts, magicite, etc.).
       Dungeon - limit to a single dungeon.
       Max artifacts per cycle - never place more than this many artifacts in a
               dungeon per cycle (default 4 = the player's carry limit). Extra
               chests get a non-artifact item instead.
       Also fill empty/placeholder slots - put items in loot slots that give
               nothing in the real game.
       Randomize enemy drops too - chests and enemy drops share the same item
               pool. Checked (default) randomizes both. Uncheck to randomize
               only the Game8-identified chests and leave enemy drops alone
               (dungeons without Game8 data are skipped in that mode).
       Keep required magicite obtainable - on by default. Leaves the magicite
               vanilla in the dungeons that need their own stones: Holy for
               Lich and Zombie Dragon (element stone THEN Life), Fire for
               Tida's spider webs. Untick for fully random magicite (those
               fights/paths may then be impossible). JSON: "_protect_required_
               stones". A JSON's own chest data is never changed by it.
       Shops - "Randomize shop inventories" shuffles what the shops sell
               (Tipa, Alfitaria, Fields of Fum, Selkie Peddler, Shella, Leuda,
               Smith). Choose all shops or just some. Stock is swapped only
               among items shops already sell, so prices stay valid, and each
               item is swapped the same way in every stock tier, so stock seen
               in an early year stays on sale as the selection grows.
               "Randomize shop prices" shuffles the price tags among those
               items (Bronze might cost what Mythril did). It works with or
               without the stock shuffle.
       Bonus Pools - randomizes the end-of-dungeon score rewards, using the
               same Mode and Item pool. 13 of 14 dungeons have one (Mount
               Vellenge has none in the real game).
  4. Preview (reads the source, writes nothing) shows the planned contents.
     Randomize! creates the Output ISO with a progress bar and, to avoid
     spoilers, only reports how many slots changed - not the items. A spoiler
     .txt is still written next to the output if you want to peek later. It
     starts with the exact options you chose, then lists every chest and each
     shop's stock. "Write spoiler" writes one again for the output (or the
     source when there's no output yet).
  Export JSON / Patch from JSON let you hand-edit exact contents: Export a
     template from the source -> edit the .json -> Patch (writes the output ISO,
     never the source).

GAMEPLAY TWEAKS (Randomizer tab)
  Independent toggles - mix and match freely. The ones that don't randomize
  anything are also on the Quality of Life tab.
    Mog never gets tired  - removes the stamina penalty for running while
       carrying the chalice.
    Show trap visuals (on by default)  - for Archipelago: the status traps
       the client sends play the game's own freeze/burn/poison/paralysis/slow
       effects. Does nothing without the client.
    Starting location  - start a new game somewhere other than Tipa (only
       towns where Year 1 is completable are offered). See the Fields of Fum
       warning under QUALITY OF LIFE.
    Skip Meteor Parasite -> Mio questions -> Raem  - EXPERIMENTAL, may leave
       state the Mio questions would normally set unset.
    Skip the opening intro cutscene  - jumps straight past it on a new game.
    Show Goblin Wall on the world map from Year 1  - reveals its road/icon
       from the start instead of waiting for the Year 1->2 transition.
    Randomize Miasma Stream elements  - EXPERIMENTAL, shuffles which element
       each of the 4 rotating streams needs per year. Also turns on "Show
       Goblin Wall..." above (guarantees every element is obtainable from
       Year 1).
    Lock stages behind key artifacts  - EXPERIMENTAL, creates 14 new key
       artifacts (one per dungeon) placed via a randomized, always-solvable
       chest chain (River Belle Path always stays open, keys are in chests
       only, never enemy drops, and no dungeon's key is ever in that same
       dungeon). All 13 gated dungeons check for their key on entry, and the
       boatmen won't take you to Mount Kilanda without its key.
       The 14 keys: River/Gob/Mine/Shroom/Tida/Manor/Lava/Fort/Selep/
       Sluice/Lynari/Conall/Rebena/Vellen Key, unlocking River Belle Path
       (never actually locked)/Goblin Wall/Mine of Cathuriges/Mushroom
       Forest/Tida/Moschet Manor/Mount Kilanda/Daemon's Court/Selepation
       Cave/Veo Lu Sluice/Lynari Desert/Conall Curach/Rebena Te Ra/Mount
       Vellenge respectively - see the README for the full name/
       description table.
    Cycle select  - the "Which cycle?" menu when entering a dungeon (see
       QUALITY OF LIFE).
    Skip Miasma Stream gates  - a stream takes the caravan straight across,
       whatever the chalice holds (see QUALITY OF LIFE).
    All-in-one GBA radar  - map, exits, enemies and chests on one GBA radar
       (see QUALITY OF LIFE).
    GBA bonus pool pages / GBA enemy drops pages  - press A on the GBA radar
       to see the end-of-stage bonus items or the artifacts enemies carry
       (see QUALITY OF LIFE).
    Randomize world-map loading zones  - EXPERIMENTAL, shuffles which dungeon
       each world-map spot leads to (12 dungeons, Mount Kilanda and Mount
       Vellenge stay). A spot keeps its Miasma Stream gating and Myrrh-drop
       elements, and the dungeon's exits return the caravan to that spot. Stage-key
       locks follow the dungeons. Also turns on "Show Goblin Wall...".
       For Archipelago seeds, use the AP world's Shuffle Loading Zones option.
       JSON: "_randomize_world_zones": true shuffles on patch. "_world_zones"
       maps each spot (named by its vanilla dungeon) to a dungeon from
       "_world_zone_choices". An entry naming the spot's own dungeon means
       "no preference". Needs a source ISO whose zones are still vanilla.
       Also show each spot's new dungeon building (on by default): the
       world-map building at each spot changes to the dungeon it now leads
       to. JSON: "_world_zone_icons": true/false.
    Use progression logic (on by default)  - the zone layout and the stage-key
       order are picked so every year has enough reachable dungeons (Miasma
       Stream elements per year, the Jegon River crossing and the boats. The
       chalice keeps its element across the year change). Imported JSON files
       are applied as written unless they set "_progression_logic": true, and
       even then only their random parts follow the logic.
    Randomize bosses  - EXPERIMENTAL, shuffles the 13 dungeon bosses between
       boss arenas, each with its helpers and summons. Goblin King and Lich
       stay home in a random shuffle, and Mount Vellenge's final boss never moves.
       A moved boss may play the old boss's entrance. Holy (Life + an element
       stone) stays obtainable wherever Lich and Zombie Dragon end up.
       JSON: "_randomize_bosses": true shuffles on patch. "_bosses" maps each
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

AP PATCH (Archipelago)
  Makes the ISO for one Archipelago seed. Each seed needs its own ISO.
  1. Browse to your clean, unmodified vanilla ISO (never changed).
  2. Choose your seed file: the .apffcc file from the multiworld host (older
     .ffcc files work too), or the .zip it came in.
  3. The output name fills in as "<source> - AP_<seed>_<time>.iso". Pick your
     own with "Save as…" if you like.
  4. Click "Patch for Archipelago". If the seed was made with a different
     apworld version you're warned first. Patching anyway usually works, but
     update the apworld or the patcher if anything looks wrong.
  What the patch does:
    - Your own items appear as their real models in chests. Items for other
      players, traps and gil leave the chest empty, and the chest shows the
      Archipelago logo. The client sends them. Artifacts, Spell Rings and
      stage keys always come through the client so they can't be lost.
    - Every option of the seed is applied (stage keys, Goblin Wall in Year 1,
      Miasma Streams, loading zones, shortcuts, enemy health, play timer,
      cycle select / cycle locks, starting stats, ...), so the seed file is
      required.
    - The title screen shows the Archipelago logo, and the disc name your
      player name and seed, so it's easy to pick the right ISO in Dolphin.
    - The Other gender choice is always added.
  Then load the output ISO in Dolphin and connect the FFCC Archipelago client.

CHEST EDITOR
  Open ISO, pick a dungeon, Load. Each row is a loot set, and the three columns
  are what it gives in cycle 1 / 2 / 3. Double-click a cell to pick an item
  (filter by category or search by name). "Game8 Reference" shows the
  dungeon's chest list from Game8 to find a chest by its number. Save to ISO
  writes the changes - use it on a copy.

FILE TOOLS
  Files inside the ISO: List (with a filter) / Extract / Inject raw files by
  their disc path (an injected file must match the original size).
  Item stats edits a param.cfd: extract dvd/cft/param.cfd here, Show an item
  id, Set a field, then inject the file back.

CUSTOM ITEM
  Repurpose an unused "Extra N" slot into your own item (edits the ISO in
  place - point it at a COPY).
  - "List free slots" shows repurposable slots. Pick one as the Slot id.
    "Show slot" shows what a slot holds now.
  - Name: keep it short (~8 chars fit an Extra slot - names are written in place
    so the file stays the same size). Description is the in-game help text
    (blank leaves it as it is).
  - Looks like: a donor item whose 3D model / menu icon / type are copied (e.g.
    Gold). Model id (optional) uses another 3D model instead. Retexture
    (optional) recolors the model from a PNG. Price sets the gil. Article is
    the word ("a", "an" or "the") the game's messages put before its name.
  - Optionally place it in a shop and/or a dungeon's first chest for testing.
    To have the randomizer/editor carry it, follow the printed note (add it to
    ffcc_items NAMES, drop it from randomizer EXCLUDE).

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

        f = ttk.Frame(self)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text="ISO:", width=6).pack(side="left")
        ttk.Entry(f, textvariable=self.iso).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(f, text="Browse…", command=lambda: browse_iso(self.iso)).pack(side="left")
        ttk.Label(self, foreground="#a33",
                  text="Edits the ISO in place — point it at a COPY (e.g. your randomized "
                       "output), never your clean original.").pack(anchor="w")

        ni = ttk.LabelFrame(self, text="New item (repurposes an unused 'Extra' slot)", padding=8)
        ni.pack(fill="x", pady=6)
        r = ttk.Frame(ni)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Slot id:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.slot, width=10).pack(side="left", padx=4)
        ttk.Button(r, text="List free slots", command=self.do_listfree).pack(side="left", padx=2)
        ttk.Button(r, text="Show slot", command=self.do_show).pack(side="left", padx=2)
        r = ttk.Frame(ni)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Name:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.name, width=20).pack(side="left", padx=4)
        ttk.Label(r, text="(short — about 8 chars fit an 'Extra' slot)",
                  foreground="#777").pack(side="left")
        r = ttk.Frame(ni)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Description:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.desc, width=36).pack(side="left", padx=4)
        ttk.Label(r, text="(in-game help text, blank = leave as-is)",
                  foreground="#777").pack(side="left")
        r = ttk.Frame(ni)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Looks like:", width=12).pack(side="left")
        ttk.Combobox(r, textvariable=self.donor, width=18,
                     values=self._donor_list()).pack(side="left", padx=4)
        ttk.Label(r, text="(donor item — copies its model / icon / type)",
                  foreground="#777").pack(side="left")
        r = ttk.Frame(ni)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Model id:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.model, width=10).pack(side="left", padx=4)
        ttk.Label(r, text="(optional — override the 3D model, e.g. 0x37, blank = donor's)",
                  foreground="#777").pack(side="left")
        r = ttk.Frame(ni)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Retexture:", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.retex, width=30).pack(side="left", padx=4)
        ttk.Button(r, text="Browse…",
                   command=lambda: self._browse_png(self.retex)).pack(side="left", padx=2)
        ttk.Label(self, foreground="#777",
                  text="Retexture recolors the model's texture from a PNG. Note: every "
                       "item using that model is recolored — set a unique Model id first "
                       "to affect only this item.").pack(anchor="w")
        r = ttk.Frame(ni)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Price (gil):", width=12).pack(side="left")
        ttk.Entry(r, textvariable=self.gil, width=10).pack(side="left", padx=4)
        ttk.Label(r, text="Article:").pack(side="left", padx=(10, 0))
        ttk.Combobox(r, textvariable=self.article, width=5, state="readonly",
                     values=["a", "an", "the"]).pack(side="left", padx=4)

        pl = ttk.LabelFrame(self, text="Place for testing (optional)", padding=8)
        pl.pack(fill="x", pady=4)
        r = ttk.Frame(pl)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="In shop:", width=12).pack(side="left")
        ttk.Combobox(r, textvariable=self.shop, width=18, state="readonly",
                     values=list(self._shop_map)).pack(side="left", padx=4)
        ttk.Label(r, text="In dungeon's 1st chest:").pack(side="left", padx=(10, 0))
        ttk.Combobox(r, textvariable=self.chest, width=20, state="readonly",
                     values=list(self._chest_map)).pack(side="left", padx=4)

        ttk.Button(self, text="Add custom item", command=self.do_add).pack(anchor="w", pady=4)
        self.log = LogPanel(self)
        self.log.pack(fill="both", expand=True)

    def _donor_list(self):
        return sorted({n for n in ffcc_items.NAMES.values()
                       if not n.startswith(("Equip", "Extra")) and "Test" not in n})

    def _iso(self):
        p = self.iso.get().strip()
        if not p or not os.path.isfile(p):
            messagebox.showwarning("No ISO", "Pick a valid ISO (a copy).")
            return None
        return p

    def _slot(self):
        try:
            return int(self.slot.get(), 0)
        except ValueError:
            messagebox.showwarning("Bad slot", "Slot id must look like 0x162.")
            return None

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
        iso = self._iso()
        sid = self._slot()
        if iso and sid is not None:
            self.log.write(run_capture(customitem.cmd_show, iso, sid))

    def do_add(self):
        iso = self._iso()
        sid = self._slot()
        if not iso or sid is None:
            return
        name = self.name.get().strip()
        if not name:
            messagebox.showwarning("No name", "Enter an item name.")
            return
        try:
            gil = int(self.gil.get()) if self.gil.get().strip() else None
        except ValueError:
            messagebox.showwarning("Bad price", "Price must be a number.")
            return
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
                messagebox.showwarning("Bad model", "Model id must look like 0x37 or 55.")
                return
        retex = self.retex.get().strip() or None
        if retex and not os.path.isfile(retex):
            messagebox.showwarning("No PNG", "Retexture file not found.")
            return

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
# Quality of Life tab: standalone patches, nothing randomized
# ---------------------------------------------------------------------------
class QolTab(ttk.Frame):
    """Copies an ISO and applies only the ticked quality of life patches, so
    the game plays as normal otherwise (see qolpatch.py)."""

    DEFAULT_ON = {"other_gender", "cycle_select"}

    def __init__(self, nb):
        super().__init__(nb, padding=8)
        self.src = tk.StringVar()
        self.out = tk.StringVar()

        ttk.Label(self, text=(
            "Play the normal game with only the changes you pick: no chests, shops or "
            "bosses are randomized.\nWorks on a clean ISO. The source is never changed."
        ), justify="left", foreground="#444").pack(anchor="w", pady=(0, 8))

        sf = ttk.Frame(self)
        sf.pack(fill="x", pady=2)
        ttk.Label(sf, text="Source ISO (never changed):", width=30).pack(side="left")
        ttk.Entry(sf, textvariable=self.src).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(sf, text="Browse…", command=lambda: browse_iso(self.src)).pack(side="left")
        self.src.trace_add("write", lambda *_: self._suggest_out())
        of = ttk.Frame(self)
        of.pack(fill="x", pady=2)
        ttk.Label(of, text="Output ISO (patched copy):", width=30).pack(side="left")
        ttk.Entry(of, textvariable=self.out).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(of, text="Save as…", command=self._browse_out).pack(side="left")

        # option name -> its variable, which qolpatch.apply takes as they are
        self.toggles = {}
        box = ttk.LabelFrame(self, text="Patches", padding=8)
        box.pack(fill="x", pady=6)
        for key, (label, desc) in qolpatch.TOGGLES.items():
            var = tk.BooleanVar(value=key in self.DEFAULT_ON)
            self.toggles[key] = var
            ttk.Checkbutton(box, text=label, variable=var).pack(anchor="w", pady=(4, 0))
            if desc:
                ttk.Label(box, text=desc, foreground="#a33" if desc.startswith("EXPERIMENTAL")
                          else "#777", wraplength=620, justify="left").pack(anchor="w", padx=(20, 0))

        self.choices = {}
        ch = ttk.LabelFrame(self, text="Display and start", padding=8)
        ch.pack(fill="x", pady=4)
        for key, (label, values) in qolpatch.CHOICES.items():
            row = ttk.Frame(ch)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label + ":", width=20).pack(side="left")
            var = tk.StringVar(value=values[0])
            self.choices[key] = var
            ttk.Combobox(row, state="readonly", width=16, values=values,
                         textvariable=var).pack(side="left", padx=4)

        sc = ttk.LabelFrame(self, text="Dungeon shortcuts (opened from the start)", padding=8)
        sc.pack(fill="x", pady=4)
        for key, label in qolpatch.SHORTCUT_LABELS.items():
            var = tk.BooleanVar(value=False)
            self.toggles[key] = var
            ttk.Checkbutton(sc, text=label, variable=var).pack(anchor="w")

        bf = ttk.Frame(self)
        bf.pack(fill="x", pady=8)
        self._btn = ttk.Button(bf, text="Create patched ISO", command=self.do_patch)
        self._btn.pack(side="left")
        self.log = LogPanel(self)
        self.log.pack(fill="both", expand=True)

    def _suggest_out(self, *_):
        s = self.src.get().strip()
        if s and not self.out.get().strip():
            self.out.set(os.path.splitext(s)[0] + " - QoL.iso")

    def _browse_out(self):
        s = self.src.get().strip()
        init = os.path.basename(os.path.splitext(s)[0] + " - QoL.iso") if s else "QoL.iso"
        p = filedialog.asksaveasfilename(title="Save patched ISO as", defaultextension=".iso",
                                         initialfile=init,
                                         filetypes=[("Disc image", "*.iso *.gcm"), ("All", "*.*")])
        if p:
            self.out.set(p)

    def do_patch(self):
        src, out = self.src.get().strip(), self.out.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("No source ISO", "Pick a valid source ISO first.")
            return
        if not out:
            messagebox.showwarning("No output", "Choose where to save the patched ISO.")
            return
        if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(out)):
            messagebox.showerror("Same file", "Output ISO must be different from the source ISO.")
            return
        if not iso_is_supported(src):
            return
        opts = {k: v.get() for k, v in self.toggles.items()}
        opts.update({k: v.get() for k, v in self.choices.items()})
        if os.path.isfile(out) and not messagebox.askyesno(
                "Overwrite output", f"{os.path.basename(out)} exists. Overwrite it?"):
            return
        try:
            shutil.copy2(src, out)
        except Exception as e:
            messagebox.showerror("Copy failed", str(e))
            return
        self.log.write(f"Copied {os.path.basename(src)}  →  {os.path.basename(out)}")
        self._btn.config(state="disabled")
        self._q = queue.Queue()

        def work():
            """Runs off the UI thread and only talks to it through self._q
            (None = finished)."""
            try:
                n = qolpatch.apply(out, opts, log=lambda s: self._q.put(s))
                self._q.put(f"Done - {n} patch(es) applied to {os.path.basename(out)}.")
            except Exception as e:
                self._q.put(f"[error] {e}")
            self._q.put(None)
        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self):
        """Runs on the UI thread: shows the worker's log lines until it's done."""
        try:
            while True:
                msg = self._q.get_nowait()
                if msg is None:
                    self._btn.config(state="normal")
                    return
                self.log.write(msg)
        except queue.Empty:
            self.after(100, self._poll)


# ---------------------------------------------------------------------------
# AP Patch tab
# ---------------------------------------------------------------------------
class APPatchTab(ttk.Frame):
    """Copies a vanilla ISO and patches it for Archipelago from the seed's
    .ffcc file: your own items appear in chests, other players' items show as
    AP Item, and the seed's options (stage keys, Goblin Wall in Year 1, Miasma
    Streams, ...) are applied."""

    def __init__(self, nb):
        super().__init__(nb, padding=8)
        self.src  = tk.StringVar()   # vanilla ISO — read only, never modified
        self.out  = tk.StringVar()   # AP-patched copy — what gets written
        self.ffcc = tk.StringVar()   # the seed's .ffcc placement file (required)
        self._out_chosen = False     # True once a custom output file name was picked

        ttk.Label(self, text=(
            "Creates an Archipelago-ready ISO from your seed's .ffcc file\n"
            "(or the .zip it came in, from the multiworld host).\n\n"
            "Your own items appear as real item models in chests. Items for other players\n"
            "show as AP Item, and the client delivers what you receive.  Artifacts, Spell\n"
            "Rings and stage keys always come through the client so they can't be lost.\n"
            "The seed's options (stage keys, Goblin Wall in Year 1, Miasma Streams, ...)\n"
            "come from the .ffcc file too, so the patch needs it."
        ), justify="left", foreground="#444").pack(anchor="w", pady=(0, 8))

        sf = ttk.Frame(self)
        sf.pack(fill="x", pady=2)
        ttk.Label(sf, text="Vanilla ISO (source, never changed):", width=36).pack(side="left")
        ttk.Entry(sf, textvariable=self.src).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(sf, text="Browse…", command=self._browse_src).pack(side="left")
        self.src.trace_add("write", lambda *_: self._suggest_out())

        of = ttk.Frame(self)
        of.pack(fill="x", pady=2)
        ttk.Label(of, text="Output ISO (AP-patched copy):", width=36).pack(side="left")
        ttk.Entry(of, textvariable=self.out).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(of, text="Save as…", command=self._browse_out).pack(side="left")

        ff = ttk.Frame(self)
        ff.pack(fill="x", pady=2)
        ttk.Label(ff, text="Seed file (.apffcc / .ffcc or its .zip):", width=36).pack(side="left")
        ttk.Entry(ff, textvariable=self.ffcc).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(ff, text="Browse…", command=self._browse_ffcc).pack(side="left")

        bf = ttk.Frame(self)
        bf.pack(fill="x", pady=8)
        self._btn = ttk.Button(bf, text="Patch for Archipelago", command=self.do_patch)
        self._btn.pack(side="left")
        self._mode_lbl = ttk.Label(bf, text="  Choose your seed's .ffcc file",
                                   foreground="#a60")
        self._mode_lbl.pack(side="left")
        self.ffcc.trace_add("write", lambda *_: self._update_mode_label())

        self.log = LogPanel(self)
        self.log.pack(fill="both", expand=True)

    def _update_mode_label(self, *_):
        f = self.ffcc.get().strip()
        if f and os.path.isfile(f):
            try:
                problem = rnd.ap_world_version_problem(rnd.load_ffcc(f))
            except ValueError:
                self._mode_lbl.config(text="  Not a readable seed file", foreground="#a33")
                return
            if problem:
                self._mode_lbl.config(text="  Seed file found - apworld version mismatch (see Patch)",
                                      foreground="#a60")
            else:
                self._mode_lbl.config(text="  Seed file found (apworld "
                                      f"{'.'.join(map(str, rnd.AP_WORLD_VERSION))})", foreground="#0a0")
        elif f:
            self._mode_lbl.config(text="  Seed file not found", foreground="#a60")
        else:
            self._mode_lbl.config(text="  Choose your seed's .ffcc file", foreground="#a60")

    @staticmethod
    def _same(a, b):
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))

    def _browse_src(self):
        browse_iso(self.src)

    def _browse_out(self):
        init = self._suggested_name()
        p = filedialog.asksaveasfilename(
            title="Save AP-patched ISO as", defaultextension=".iso",
            initialfile=init,
            filetypes=[("Disc image", "*.iso *.gcm"), ("All", "*.*")])
        if p:
            self.out.set(p)
            # keeping the suggested name only picks the folder, the seed name
            # still follows when a .ffcc file is chosen later
            self._out_chosen = os.path.basename(p) != init

    def _seed_of(self, ffcc_path):
        """The seed name stored in a .ffcc file (or its .zip container), or None."""
        try:
            try:
                with _zipfile.ZipFile(ffcc_path) as zf:
                    for name in zf.namelist():
                        if name.endswith(".ffcc"):
                            return json.loads(zf.read(name)).get("seed")
            except _zipfile.BadZipFile:
                with open(ffcc_path, "r", encoding="utf-8") as fh:
                    return json.load(fh).get("seed")
        except Exception:
            return None
        return None

    def _suggested_name(self):
        """Default output file name: '<source> - AP_<seed>_<time>.iso' when a .ffcc
        file is selected, otherwise '<source> - AP.iso'."""
        s = self.src.get().strip()
        base = os.path.splitext(os.path.basename(s))[0] if s else "FFCC"
        f = self.ffcc.get().strip()
        if f and os.path.isfile(f):
            seed = self._seed_of(f)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{base} - AP_{seed}_{ts}.iso" if seed else f"{base} - AP_{ts}.iso"
        return f"{base} - AP.iso"

    def _browse_ffcc(self):
        p = filedialog.askopenfilename(
            title="Select your Archipelago seed file (.apffcc)",
            filetypes=[("FFCC seed file", "*.apffcc *.ffcc"), ("ZIP container", "*.zip"), ("All", "*.*")])
        if p:
            self.ffcc.set(p)
            self._suggest_out_from_ffcc(p)

    def _suggest_out_from_ffcc(self, ffcc_path):
        """Name the output ISO after the seed + timestamp from the .ffcc file, in
        the folder already chosen for the output (or the source's folder if
        none). A custom file name picked with "Save as..." is left as it is."""
        s = self.src.get().strip()
        if not s or self._out_chosen:
            return
        cur = self.out.get().strip()
        folder = os.path.dirname(cur) if cur else os.path.dirname(s)
        self.out.set(os.path.join(folder, self._suggested_name()))

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
        if not iso_is_supported(src):
            return

        ffcc = self.ffcc.get().strip()
        if not ffcc:
            messagebox.showwarning("No seed file",
                                   "Choose your seed's .ffcc file (or the .zip it came in).\n\n"
                                   "It holds your item placements and the seed's options, "
                                   "such as stage keys and Goblin Wall in Year 1.")
            return
        if not os.path.isfile(ffcc):
            messagebox.showerror("Seed file not found", f"The seed file was not found:\n{ffcc}")
            return
        try:
            problem = rnd.ap_world_version_problem(rnd.load_ffcc(ffcc))
        except ValueError as e:
            messagebox.showerror("Can't read seed file", str(e))
            return
        if problem and not messagebox.askyesno("Apworld version", problem + "\n\nPatch anyway?"):
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

        self.log.write(f"Copied {os.path.basename(src)}  →  {os.path.basename(out)}")
        self.log.write("Patching for Archipelago — this may take a moment…")
        self._btn.config(state="disabled")
        self._q = queue.Queue()
        threading.Thread(target=self._worker_hybrid, args=(out, src, ffcc),
                         daemon=True).start()
        self.after(100, self._poll)

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
        if sys.platform == "win32":
            root.iconbitmap(os.path.join(assets_dir, "icon.ico"))
        else:
            # Tk only takes .ico files on Windows
            root._icon_img = tk.PhotoImage(file=os.path.join(assets_dir, "icon.png"))
            root.iconphoto(True, root._icon_img)
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

    nb.add(ScrollableTab(nb, QolTab), text="Quality of Life")

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
