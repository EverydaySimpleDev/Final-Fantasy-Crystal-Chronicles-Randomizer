"""FFCC item ID <-> name tables and category helper (from FFCC Notes)."""

# Curated names for the ranges that appear in chests. Anything not listed gets a
# generated "0xNNN (Category)" label.
NAMES = {}

def _add(start, names):
    for i, n in enumerate(names):
        if n:
            NAMES[start + i] = n

# Weapons 0x01-0x40
_add(0x01, ["Copper Sword","Iron Sword","Steel Blade","Feather Saber","Bastard Sword",
    "Defender","Rune Blade","Excalibur","Ragnarok","Treasured Sword","Father's Sword","Marr Sword",
    "Test1","Test2","Ultima Sword","Equip116","Equip117"])
_add(0x12, ["Iron Lance","Partisan","Sonic Lance","Titan Lance","Halberd","Highwind","Dragon Lance",
    "Dragoon Spear","Gungnir","Longinus","Treasured Spear","Father's Spear","Marr Spear","Ultima Lance",
    "Equip119","Equip120","Equip121","Equip122"])
_add(0x24, ["Orc Hammer","Wave Hammer","Rune Hammer","Goblin Hammer","Sonic Hammer","Prism Hammer",
    "Mythril Hammer","Mystic Hammer","Treasured Hammer","Father's Hammer","Marr Hammer","Ultima Hammer",
    "Equip124","Equip125","Equip126","Equip127"])
_add(0x34, ["Aura Racket","Solid Racket","Dual Shooter","Elemental Cudgel","Steel Cudgel","Prism Bludgeon",
    "Butterfly Head","Queen's Heel","Dreamcatcher","Treasured Maul","Father's Maul","Marr Maul","Ultima Maul"])
# Armor 0x45-0x9e
_add(0x45, ["Travel Clothes","Bronze Plate","Iron Plate","Mythril Hauberk","Flame Mail","Frost Mail",
    "Storm Mail","Time Mail","Eternal Mail","Blessed Mail","Saintly Mail","Gold Mail","Crystal Mail",
    "Diamond Plate","Gaia Plate","Mystic Armor","Taterskin Coat","Coat","Oversized Coat"])
_add(0x58, ["Makeshift Shield","Iron Shield","Mythril Shield","Flame Shield","Frost Shield","Storm Shield",
    "Saintly Shield","Diamond Shield","Rune Shield","Chocobo Shield"])
_add(0x62, ["Gauntlets","Bronze Gauntlets","Iron Gauntlets","Mythril Gauntlets","Flame Armlets",
    "Frost Armlets","Storm Armlets","Gold Armlets","Diamond Armlets"])
_add(0x6b, ["Helm","Bronze Helm","Iron Helm","Mythril Helm","Flame Helm","Frost Helm","Storm Helm",
    "Time Helm","Eternal Helm","Diamond Helm"])
_add(0x75, ["Old Belt","Bronze Belt","Iron Belt","Mythril Belt","Flame Sash","Frost Sash","Storm Sash",
    "Blessed Sash","Winged Belt","Diamond Belt"])
_add(0x7f, ["Flame Badge","Frost Badge","Thunder Badge","Accurate Watch","Unfaltering Watch","Blue Misanga",
    "White Misanga","Gold Necklace","Wisdom Charm","Wisdom Talisman","Flower Bracer","Speed Charm",
    "Speed Talisman","Thief's Emblem","Zeal Headband","Daemon's Earring","Devil's Earring","Pixie's Earring",
    "Angel's Earring","Crystal Ring","Twisted Spectacles","Twisted Scope","Healing Headband","Jade Bracer",
    "Power Goggles","Eagle Goggles","Lion's Heart","Dragon's Heart","Wizard's Soul","Bishop's Soul",
    "Elemental's Soul","Force Ring"])
# Artifacts 0x9f-0xe7
_add(0x9f, ["Shuriken","Maneater","Double Axe","Ashura","Kaiser Knuckles","Flametongue","Ice Brand",
    "Loaded Dice","Ogrekiller","Engetsurin","Sasuke's Blade","Mjollnir","Masquerade","Murasame","Masamune",
    "Gekkabijin","Onion Sword","Power Wristband","Green Beret","Fang Charm","Twisted Headband","Heavy Armband",
    "Giant's Glove","Dragon's Whisker","Mage Masher","Rune Staff","Book of Light","Sage's Staff","Wonder Wand",
    "Rune Bell","Mage's Staff","Noah's Lute","Galatyn","Tome of Ultima","Silver Bracer","Cat's Bell",
    "Faerie Ring","Winged Cap","Candy Ring","Kris","Red Slippers","Dark Matter","Gold Hairpin","Taotie Motif",
    "Ribbon","Main Gauche","Chicken Knife","Save the Queen","Drill","Buckler","Silver Spectacles",
    "Sparkling Bracer","Black Hood","Helm of Arai","Elven Mantle","Wonder Bangle","Ring of Protection","Aegis",
    "Rat's Tail","Teddy Bear","Moogle Pocket","Chocobo Pocket","Gobbie Pocket","Ultimate Pocket","Ring of Fire",
    "Ring of Blizzard","Ring of Thunder","Ring of Cure","Ring of Life","Earth Pendant","Moon Pendant",
    "Star Pendant","Sun Pendant"])
# Magicite / spells 0x100-0x124
_add(0x100, ["Stone of Fire","Stone of Blizzard","Stone of Thunder","Stone of ???","Stone of Slow",
    "Stone of Cure","Stone of Clear","Stone of Life","Stone of Holy","Stone of Stop","Stone of Gravity"])
NAMES[0x125] = "Phoenix Down"
# Materials 0x126-0x172
_add(0x126, ["Bronze","Iron","Mythril","Orichalcum","Diamond Ore","Gold","Silver","Bronze Shard","Iron Shard",
    "Tiny Crystal","Crystal Ball","Ruby","Jade","Alloy","Magma Rock","Chilly Gel","Thunderball","Holy Water",
    "Heavenly Dust","Yellow Feather","Blue Silk","White Silk","Fiend's Claw","Devil's Claw","Faerie's Tear",
    "Angel's Tear","Ancient Sword","Cursed Crook","Orc Belt","King's Scale","Green Sphere","Dragon's Fang",
    "Malboro Seed","Desert Fang","Wind Crystal","Ethereal Orb","Red Eye","Dweomer Spore","Lord's Robe",
    "Griffin's Wing","Cerberus Fang","Needle","Hard Shell","Worm Antenna","Toad Oil","Jagged Scythe",
    "Ogre Fang","Chimera's Horn","Crop Seed","Coeurl Whisker","Zu's Beak","Cockatrice Scale","Ancient Potion",
    "Shiny Shard","Gigas Claw","Gear","Pressed Flower","Remedy","Goddess Statuette","Devil's Mask"])
# Seeds 0x163-0x16b and quest items 0x16c-0x16f
_add(0x163, ["Flower Seed", "Strange Seed", "Fruit Seed", "Fruit Seed", "Fruit Seed",
    "Vegetable Seed", "Vegetable Seed", "Vegetable Seed", "Wheat Seed",
    "Worn Bandanna", "Shella Mark", "Kilanda Sulfur", "Cactus Flower"])
NAMES[0x171] = "Ultimite"; NAMES[0x172] = "Dark Sphere"
# Food 0x17d-0x18e
_add(0x17d, ["Striped Apple","Cherry Cluster","Rainbow Grapes","Star Carrot","Gourd Potato","Round Corn",
    "Meat","Fish","Bannock","Spring Water","Milk","Strange Liquid"])
NAMES[0x18d]="Wheat"; NAMES[0x18e]="Flour"
# Recipes / scrolls 0x191-0x1ed (key ones)
_add(0x191, ["Novice's Weapon","Warrior's Weapon","Valiant Weapon","Mighty Weapon","Victorious Weapon",
    "Master's Weapon","Legendary Weapon","Hero's Weapon","Celestial Weapon","Dark Weapon","Lunar Weapon",
    "Bronze Armor","Iron Armor","Mythril Armor","Flame Armor","Frost Armor","Lightning Armor","Time Armor",
    "Eternal Armor","Pure Armor","Holy Armor","Gold Armor","Radiant Armor","Diamond Armor","Earth Armor",
    "Iron Shield","Mythril Shield","Flame Shield","Frost Shield","Lightning Shield","Holy Shield",
    "Diamond Shield","Magic Shield","Legendary Shield","Bronze Gloves","Iron Gloves","Mythril Gloves",
    "Flame Gloves","Frost Gloves","Lightning Gloves","Gold Gloves","Diamond Gloves","Bronze Sallet",
    "Iron Sallet","Mythril Sallet","Flame Sallet","Frost Sallet","Lightning Sallet","Time Sallet",
    "Eternal Sallet","Diamond Sallet","Bronze Belt","Iron Belt","Mythril Belt","Flame Belt","Frost Belt",
    "Lightning Belt","Pure Belt","Wind Belt","Diamond Belt","Flame Craft","Frost Craft","Lightning Craft",
    "Clockwork","New Clockwork","Blue Yarn","White Yarn","Gold Craft","Wisdom Tome","Wisdom Secrets",
    "Lady's Accessories","Speed Tome","Speed Secrets","Brigandology","Zeal Kit","Fiend Kit","Daemon Kit",
    "Faerie Kit","Angel Kit","Ring of Light","Eyewear Techniques","Designer Glasses","Healing Kit",
    "Fashion Kit","Goggle Techniques","Designer Goggles","Soul of the Lion","Soul of the Dragon","Magic Tome",
    "Sorcery Tome","Forbidden Tome","Greatest Weapon","Ring of Invincibility"])

CAT = [
    (0x001, 0x044, "Weapon"), (0x045, 0x057, "Armor"), (0x058, 0x061, "Shield"),
    (0x062, 0x06a, "Gauntlet"), (0x06b, 0x074, "Helmet"), (0x075, 0x07e, "Belt"),
    (0x07f, 0x09e, "Accessory"), (0x09f, 0x0e7, "Artifact"), (0x100, 0x124, "Magicite"),
    (0x125, 0x125, "PhoenixDown"), (0x126, 0x172, "Material"), (0x17d, 0x18e, "Food"),
    (0x191, 0x1ed, "Recipe"),
]


def category(v):
    for lo, hi, name in CAT:
        if lo <= v <= hi:
            return name
    return "?"


def name(v):
    if v in NAMES:
        return NAMES[v]
    return f"0x{v:04x} ({category(v)})"


def label(v):
    """Human label for a dropdown / cell: 'Stone of Cure (0x105)'."""
    return f"{name(v)}  [0x{v:04x}]"


def all_items_for_category(cat):
    """List of (id, label) for items in a category - used to constrain edits safely."""
    out = []
    for lo, hi, c in CAT:
        if c == cat:
            for v in range(lo, hi + 1):
                out.append((v, label(v)))
    return out
