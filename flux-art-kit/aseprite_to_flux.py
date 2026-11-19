#!/usr/bin/env python3
"""Convert Aseprite or PNG artwork to Flux firmware arrays. Requires Pillow.

  python aseprite_to_flux.py logo.aseprite --mode logo -o logo.rs
  python aseprite_to_flux.py splash.aseprite --mode splash -o splash.rs --bin splash.bin

Aseprite inputs require the aseprite CLI (or --aseprite /path/to/aseprite).
Visible layers are composited by Aseprite. Frame numbers are zero-based.
No resizing or dithering is performed. Transparent pixels are always OFF.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image


def load_image(path, frame, executable):
    if path.suffix.lower() in ('.ase', '.aseprite'):
        exe = shutil.which(executable)
        if not exe:
            raise ValueError('Aseprite CLI not found; pass --aseprite /path/to/aseprite or export a PNG.')
        # Read frame count to reject out-of-range selections before invoking Aseprite.
        header = path.read_bytes()[:128]
        if len(header) < 128 or header[4:6] != b'\xe0\xa5':
            raise ValueError('Not a valid Aseprite file.')
        count = int.from_bytes(header[6:8], 'little')
        if not 0 <= frame < count:
            raise ValueError(f'Frame {frame} is out of range; this file has {count} frames.')
        with tempfile.TemporaryDirectory(prefix='flux-art-') as tmp:
            sheet = Path(tmp) / 'frame.png'
            result = subprocess.run([exe, '--batch', '--frame-range', f'{frame},{frame}',
                                     str(path.resolve()), '--sheet', str(sheet)],
                                    capture_output=True, text=True)
            if result.returncode or not sheet.is_file():
                raise ValueError('Aseprite export failed:\n' + result.stdout + result.stderr)
            with Image.open(sheet) as im:
                return im.convert('RGBA')
    with Image.open(path) as im:
        im.seek(frame)
        return im.convert('RGBA')


def pixels_for(im, threshold, alpha_threshold, ink):
    # Composite partially transparent pixels against the opposite background.
    background = 'white' if ink == 'dark' else 'black'
    gray = Image.alpha_composite(Image.new('RGBA', im.size, background), im).convert('L')
    return [a > alpha_threshold and (v < threshold if ink == 'dark' else v >= threshold)
            for v, a in zip(gray.getdata(), im.getchannel('A').getdata())]


def pack(pixels, width, height, mode):
    if mode == 'logo':
        return [sum(int(pixels[y * width + x]) << (15-x) for x in range(width))
                for y in range(height)]
    # Matches ui/boot.rs draw_logo(): y = page * 8 + bit.
    return [sum(int(pixels[(page*8+bit)*width+x]) << bit for bit in range(8))
            for page in range(height//8) for x in range(width)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input', type=Path)
    parser.add_argument('--mode', choices=('logo', 'splash'), required=True)
    parser.add_argument('-o', '--output', type=Path, help='Rust array output; default stdout')
    parser.add_argument('--name', help='Rust constant name (default LOGO or BOOT_LOGO)')
    parser.add_argument('--frame', type=int, default=0, help='Zero-based frame (default 0)')
    parser.add_argument('--ink', choices=('dark','light'), default='dark', help='Which pixels turn ON; default dark')
    parser.add_argument('--threshold', type=int, default=128, help='Luminance split, 0..255 (default 128)')
    parser.add_argument('--alpha-threshold', type=int, default=0, help='Alpha at/below this is OFF, 0..255')
    parser.add_argument('--aseprite', default='aseprite', help='Aseprite executable name or path')
    parser.add_argument('--bin', type=Path, help='Write raw 1024-byte splash; only with --mode splash')
    parser.add_argument('--preview', type=Path, help='Write exact-size black-on-white PNG preview')
    args = parser.parse_args()
    try:
        if args.frame < 0 or not 0 <= args.threshold <= 255 or not 0 <= args.alpha_threshold <= 255:
            raise ValueError('Frame must be nonnegative; thresholds must be 0..255.')
        if args.bin and args.mode != 'splash':
            raise ValueError('--bin is supported only for splash mode.')
        name = args.name or ('LOGO' if args.mode == 'logo' else 'BOOT_LOGO')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
            raise ValueError('Constant name must be an ASCII identifier.')
        destinations = [p.resolve() for p in (args.output, args.bin, args.preview) if p]
        if args.input.resolve() in destinations or len(set(destinations)) != len(destinations):
            raise ValueError('Input and output paths must all be distinct.')
        im = load_image(args.input, args.frame, args.aseprite)
        size = (16,16) if args.mode == 'logo' else (128,64)
        if im.size != size:
            raise ValueError(f'{args.mode} requires {size[0]}x{size[1]}; input is {im.width}x{im.height}. No automatic resizing.')
        pixels = pixels_for(im, args.threshold, args.alpha_threshold, args.ink)
        values = pack(pixels, *size, args.mode)
        if args.mode == 'logo':
            body = '\n'.join(f'    0b{v:016b},' for v in values)
            declaration = f'const {name}: [u16; 16]'
        else:
            body = '\n'.join('    '+', '.join(f'0x{v:02X}' for v in values[i:i+16])+',' for i in range(0,1024,16))
            declaration = f'const {name}: [u8; 1024]'
        text = declaration + ' = [\n' + body + '\n];\n'
        if args.output:
            args.output.write_text(text)
        else:
            sys.stdout.write(text)
        if args.bin:
            args.bin.write_bytes(bytes(values))
        if args.preview:
            preview = Image.new('1', size)
            preview.putdata([0 if on else 255 for on in pixels])
            preview.save(args.preview)
    except (OSError, ValueError, EOFError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
