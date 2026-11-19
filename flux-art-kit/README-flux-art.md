# Flux artwork sheet

Open flux-art.aseprite in Aseprite. The 128x80 canvas contains:

- (0,0)–(15,15): Flux Vector icon
- (16,0)–(31,15): string-loop icon (legacy diamond slot)
- (32,0)–(47,15): antenna tower
- (0,16)–(127,79): full 128x64 Vector splash

The remaining top-strip pixels are unused. Keep dimensions unchanged. Black is ON, white/transparent is OFF. This is a pixel adaptation of the concept art. The firmware replaces splash rows 42–63 when custom boot text is set.

Requires Python 3, Pillow (`python -m pip install Pillow`), and Aseprite on PATH for .aseprite files. PNG input needs only Pillow. Keep both Python scripts together.

Import edited artwork:

```sh
python flux_sprite_sheet.py import flux-art.aseprite --output-dir converted
```

Produces logos.py (three 16x16 icons), logos.rs, splash.rs, splash.bin and splash-preview.png. The theme builder previews logos.py and splash.bin directly. The firmware build imports the icons into the branding and Designer renderers, and includes splash.bin as a separate installable boot bitmap. Import does not patch source or flash a radio. Use --force to replace prior outputs, --frame N for a zero-based animation frame, --ink light for white foreground artwork, or --aseprite /path/to/aseprite.

Export from source, optionally including a full splash:

```sh
python flux_sprite_sheet.py export edited.aseprite --source /path/to/apply-theme-splash.py --splash-bin flux-arrays/splash.bin
```

The included flux-arrays directory was imported from the filled sheet and checked for byte-exact splash round-trip. Full-screen binaries are 1024 bytes, page-major: byte[page*128+x], bit b maps to y=page*8+b. Small icons are sixteen u16 rows, leftmost pixel in bit 15.
