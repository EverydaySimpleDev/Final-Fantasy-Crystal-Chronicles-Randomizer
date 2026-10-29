# Title Screen Logo and Disc Banner

The patcher puts the Archipelago logo (`assets/title_logo.png`) on the title
screen of every ISO it makes. It also renames the disc and replaces its banner
and description, which is what Dolphin's game list and game properties show.
This page covers how the logo texture and banner work, and how to make a
replacement image that looks right in game.

## Where it is

The title logo is texture `cc_logo01` in `dvd/menu/cc_logo.tex`, 576 × 224
pixels. The same file has `cc_logo02` ("New Game" / "Load Game" and their
glow) and `cc_logo03` (the copyright lines). The patcher only replaces
`cc_logo01`.

## How the texture is stored

The texture's `FMT` block says IA4 (4-bit grey + 4-bit alpha), and `tex.py`
decodes it that way, but **the game draws it as an 8-bit palette image**.
Each pixel byte is an index into the texture's own 256-colour palette, the
`PALT` block. Read as IA4, it looks like a grey, speckled mess; read with
the palette, it's the real full-colour logo.

| Block | Size | Contents |
|---|---|---|
| `PALT` | 1024 bytes | 256 colours. Bytes 0–511: (G, R) per colour. Bytes 512–1023: (A, B) per colour. |
| `IMAG` | 129,024 bytes | One palette index per pixel, in 8 × 4 tiles: tiles left to right, then top to bottom; inside a tile, 8 pixels across × 4 rows. |

So any picture of up to **256 colours, each with its own transparency**, can
replace it at exactly the same size. Nothing else in the ISO moves.

This was worked out with a test pattern. Bands of each "grey" value showed
up in game as unrelated pastel colours, which only makes sense as a palette
lookup. The palette's channel order was then matched against a screenshot.

## Disc name and banner

| What | Where |
|---|---|
| Game name (Game Details) | disc header, offset `0x20`, 0x3E0 bytes |
| Banner image | `opening.bnr` offset `0x20`: 96 × 32, RGB5A3, 4 × 4 tiles. The patcher puts the logo on white fading to light blue. |
| Banner text | `opening.bnr` offset `0x1820`: short name (32 bytes), short maker (32), long name (64), long maker (64), description (128). Latin-1, ending in a zero byte. |

The names say what the ISO was patched for, so players can tell their ISOs
apart in Dolphin's game list:

| Patched with | Long name (game list) | Short name |
|---|---|---|
| an AP seed (`.ffcc`) | `FFCC Archipelago: <player> (<seed>)` | `FFCC AP: <player>` |
| the Randomize tab | `FFCC Randomizer (seed <seed>)` | `FFCC Randomizer` |
| anything else | `FINAL FANTASY Crystal Chronicles Archipelago` | `FFCC Archipelago` |

The disc name and description carry the same player and seed, and the maker
fields say `EverydaySimpleDev`. Every text is checked against its field. If
it's too long, the player name is shortened, never the seed. AP names can be
16 characters, and AP seeds are 20 digits, so `FFCC Archipelago: <player>
(<seed>)` is at most 58 of the 63 characters. Characters the banner can't
show (outside Latin-1) become `?`. The texts are in `texts()` in
`titlelogo.py`.

The **game ID (`GCCE01`) is never changed**. The AP client, save files and
Dolphin's per-game settings all go by it, and its `01` is the maker Dolphin
shows under Game Details ("Nintendo (01)").

Dolphin caches banners in its game list. If the old banner still shows,
right-click the game list and refresh it, or clear the cache.

The banner is cropped to the logo's visible pixels and then fitted, because
at 96 × 32 every pixel counts. A wide, short logo fills it best.

## Making an image that looks good in game

1. **Start from a PNG with transparency.** The background must be fully
   transparent, or it shows up as a box behind the logo.
2. **Aim for a wide shape.** The texture is 576 × 224 (about 2.6 : 1). The
   image is scaled to fit and centred, so a squarer image gets empty space on
   the left and right and comes out smaller on screen.
3. **Keep the colour count sensible.** Only 256 colours are kept, so smooth
   gradients across large areas can band. Flat colours, outlines and
   textured art (like the original logo) come through cleanly.
4. **Keep soft edges.** Semi-transparent edge pixels each get a palette
   entry, so glows and anti-aliased edges survive. Pixels that are almost
   invisible (alpha under 8 of 255) are made fully clear so they don't use
   up palette entries.
5. **Mind the menu below.** The logo sits above "New Game / Load Game";
   keep important parts out of the bottom few rows.
6. **Mind the background.** The title background is light fog at the bottom
   and dark at the top left. Strong outlines keep the text readable on both.

## Commands

```
py titlelogo.py build   <logo.png>                           # PNG -> assets/title_logo.bin + assets/banner.bin
py titlelogo.py install <game.iso> [player] [seed]           # logo, banner and names into an ISO (the patcher does this itself)
py titlelogo.py preview <game.iso | cc_logo.tex> <out.png>   # how the logo in an ISO will look in game
```

To change the logo:

1. Replace `assets/title_logo.png` with the new image.
2. Run `py titlelogo.py build assets/title_logo.png`. This rewrites
   `assets/title_logo.bin` and `assets/banner.bin`, which needs Pillow. The
   patcher itself only copies those two files into the ISO, so it doesn't
   need Pillow at run time.
3. Check it with `py titlelogo.py preview` on a patched ISO, then boot the
   ISO in Dolphin.

## Notes

- `install` is safe to run on any ISO, more than once. It looks the texture
  up by name and size, checks the banner is BNR1, and only writes what
  differs.
- `tex.py` doesn't know about `PALT` yet, so it decodes and re-encodes these
  menu textures as grey IA4. Use `titlelogo.py` for the title logo. Other
  menu textures with a `PALT` block are probably palette images too.
