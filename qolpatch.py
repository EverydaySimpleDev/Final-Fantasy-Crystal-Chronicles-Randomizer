"""
qolpatch.py - Quality of life patches on their own, without randomizing
anything: the game plays as normal with only the chosen changes.

Every patch here also exists as an option of the randomizer or the AP world.
This applies them to a plain copy of the game. Patches that only make sense
with the Archipelago client (trap visuals, items dropped at your feet, cycle
locks, grooming tools, hidden collected chests) are not offered.

Usage:
    py qolpatch.py list
    py qolpatch.py apply <game.iso> <option>[=<value>] [...]
e.g.
    py qolpatch.py apply copy.iso other_gender cycle_select show_enemy_health=bar
"""

import sys

import randomizer as rnd
import shortcuts

# On/off patches: option -> (label, description shown under the checkbox).
TOGGLES = {
    "other_gender": ("Other gender choice",
                     "Adds \"Other\" to the gender choice at character creation, with neutral "
                     "wording in the game's gendered text."),
    "cycle_select": ("Cycle select",
                     "After \"Enter\" at a dungeon on the world map, pick which reached cycle to "
                     "play (only once Cycle 1 is cleared). The dungeon's own cycle is kept."),
    "skip_miasma_streams": ("Skip Miasma Stream gates",
                            "Entering a Miasma Stream gate takes the caravan straight to the "
                            "other side, whatever the chalice's element (no softlocks behind a "
                            "gate). The Mystery Miasma Stream still needs Unknown."),
    "all_in_one_radar": ("All-in-one GBA radar",
                         "A GBA in controller port 2 (or each player's GBA) shows the area map, "
                         "its exits, enemies and treasure chests on one radar."),
    "gba_bonus_pool": ("GBA bonus pool pages",
                       "Press A on the GBA radar: the dungeon's end-of-stage bonus items for "
                       "its current cycle, one page per bonus tier, with the points each needs."),
    "gba_enemy_drops": ("GBA enemy drops pages",
                        "Press A on the GBA radar: the artifacts this area's enemies carry, and "
                        "which enemy carries each (drops are picked when an enemy appears)."),
    "mog_never_tired": ("Mog never gets tired",
                        "Removes the stamina penalty for running while Mog carries the chalice."),
    "keep_picked_up_artifacts": ("Keep picked-up artifacts",
                                 "Every artifact picked up in a dungeon is kept, instead of "
                                 "choosing one at the end."),
    "best_bonus_tier": ("Always best bonus tier",
                        "The end-of-dungeon bonus always gives the best tier reached."),
    "skip_intro_cutscene": ("Skip the opening intro cutscene", ""),
    "skip_mio_questions": ("Skip Mio's questions",
                           "EXPERIMENTAL: Meteor Parasite goes straight to Raem."),
    "goblin_wall_year_one": ("Goblin Wall on the world map from Year 1", ""),
    "lynari_desert_north_exit": ("Lynari Desert north exit",
                                 "A quicksand pit at the north end of the first area that drops "
                                 "you into the second."),
    "debug_menu": ("Developer debug menu",
                   "EXPERIMENTAL: a second controller on Port 2 opens the game's QA menu "
                   "(A open, B close, D-pad select, A/B toggle)."),
}

# Dungeon shortcuts (shortcuts.SHORTCUTS), same names as the AP world's options.
SHORTCUT_LABELS = {
    "river_belle_path_bridges": "River Belle Path bridges lowered",
    "goblin_wall_gates": "Goblin Wall gates open",
    "mine_boxes": "Mine of Cathuriges boxes cleared",
    "tida_webs": "Tida webs cleared",
    "moschet_manor_doors": "Moschet Manor doors open",
    "selepation_cave_elevators": "Selepation Cave elevators lowered",
    "conall_curach_log_bridges": "Conall Curach log bridges",
    "rebena_te_ra_gates": "Rebena Te Ra gates open",
    "lynari_desert_unknown": "Unknown element puzzle solved (Lynari Desert)",
}

# Patches with a setting: option -> (label, [values]). The first value leaves
# the game as it is.
CHOICES = {
    "show_enemy_health": ("Show enemy health", ["off", "bar", "text", "both"]),
    "show_play_timer": ("Show play timer", ["off", "play_time", "speedrun", "manual"]),
    "starting_location": ("Starting location", list(rnd.STARTING_LOCATIONS)),
    "starting_hearts": ("Starting hearts", ["default"] + [str(n) for n in range(1, 9)]),
}

# Toggles that patch bytes in place (Start.dol or world.cft), so the order
# among them doesn't matter.
_IN_PLACE_PATCHES = {
    "mog_never_tired": rnd.patch_mog_never_tired,
    "keep_picked_up_artifacts": rnd.patch_keep_artifacts,
    "best_bonus_tier": rnd.patch_best_bonus_tier,
    "debug_menu": rnd.patch_debug_menu,
    "skip_intro_cutscene": rnd.patch_skip_intro_cutscene,
    "skip_mio_questions": rnd.patch_skip_mio_questions,
    "goblin_wall_year_one": rnd.patch_goblin_wall_always_visible,
}


def apply(iso, options, log=print):
    """Apply `options` ({option: True or a CHOICES value}) to `iso`, in place.
    Returns the number of patches applied."""
    def is_on(key, value):
        if key in CHOICES:
            return value != CHOICES[key][1][0]
        return bool(value)

    opts = {key: value for key, value in options.items() if is_on(key, value)}
    unknown = set(opts) - set(TOGGLES) - set(CHOICES) - set(SHORTCUT_LABELS)
    if unknown:
        raise ValueError("unknown option(s): " + ", ".join(sorted(unknown)))
    done = 0

    def step(label, fn, *args, **kwargs):
        """Run one patch and log the result. A failed patch doesn't stop the rest."""
        nonlocal done
        try:
            fn(*args, **kwargs)
            log(f"  {label}: patched")
            done += 1
        except Exception as e:
            log(f"  [error] {label}: {e}")

    health = opts.get("show_enemy_health")
    if health:
        step(f"Enemy health ({health})", rnd.patch_show_enemy_health, iso, health)
    timer = opts.get("show_play_timer")
    if timer:
        step(f"Play timer ({timer})", rnd.patch_play_timer, iso, timer)
    for key, patch in _IN_PLACE_PATCHES.items():
        if opts.get(key):
            step(TOGGLES[key][0], patch, iso, apply=True)
    if opts.get("all_in_one_radar"):
        import gbaradar
        step(TOGGLES["all_in_one_radar"][0], gbaradar.apply, iso)
    if opts.get("gba_bonus_pool") or opts.get("gba_enemy_drops"):
        import gbaloot
        wanted = [key for key in ("gba_bonus_pool", "gba_enemy_drops") if opts.get(key)]
        step(" and ".join(TOGGLES[key][0] for key in wanted), gbaloot.apply, iso,
             bool(opts.get("gba_bonus_pool")), bool(opts.get("gba_enemy_drops")))
    loc = opts.get("starting_location")
    if loc and loc != "Tipa":
        step(f"Starting location ({loc})", rnd.patch_starting_location, iso, loc, apply=True)
    hearts = opts.get("starting_hearts")
    if hearts:
        import tribestats
        step(f"Starting hearts ({hearts})", tribestats.apply, iso, None, int(hearts))

    # The patches below make files longer, which moves the bytes the patches
    # above look for at fixed offsets, so they go last. Both the shortcuts and
    # the Lynari exit edit desert_0.cft, in that order.
    wanted = [name for name in shortcuts.SHORTCUTS if opts.get(name)]
    if wanted:
        step("Dungeon shortcuts (" + ", ".join(SHORTCUT_LABELS.get(n, n) for n in wanted) + ")",
             shortcuts.apply, iso, wanted)
    if opts.get("lynari_desert_north_exit"):
        import lynarinorth
        step(TOGGLES["lynari_desert_north_exit"][0], lynarinorth.patch, iso)
    if opts.get("other_gender"):
        import othergender
        step(TOGGLES["other_gender"][0], othergender.apply, iso)
    if opts.get("skip_miasma_streams"):
        import miasmaskip
        step(TOGGLES["skip_miasma_streams"][0], miasmaskip.apply, iso)
    if opts.get("cycle_select"):
        import cycleselect
        step(TOGGLES["cycle_select"][0], cycleselect.apply, iso)
    return done


def _parse(args):
    """Command-line options ("name" or "name=value") as an apply() dict."""
    opts = {}
    for a in args:
        key, _, value = a.partition("=")
        if key in CHOICES:
            if value not in CHOICES[key][1]:
                sys.exit(f"{key} must be one of: {', '.join(CHOICES[key][1])}")
            opts[key] = value
        elif value:
            sys.exit(f"{key} takes no value")
        else:
            opts[key] = True
    return opts


if __name__ == "__main__":
    if sys.argv[1:2] == ["list"]:
        for key, (label, _) in TOGGLES.items():
            print(f"  {key:28s} {label}")
        for key, label in SHORTCUT_LABELS.items():
            print(f"  {key:28s} {label}")
        for key, (label, values) in CHOICES.items():
            print(f"  {key}=<{'|'.join(values)}>  {label}")
    elif len(sys.argv) >= 4 and sys.argv[1] == "apply":
        import isocheck
        errors, warnings = isocheck.check(sys.argv[2])
        if errors:
            sys.exit("ERROR: " + errors[0])
        for line in warnings:
            print("WARNING: " + line)
        n = apply(sys.argv[2], _parse(sys.argv[3:]))
        print(f"{n} patch(es) applied.")
    else:
        sys.exit(__doc__)
