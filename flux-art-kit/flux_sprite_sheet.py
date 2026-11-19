#!/usr/bin/env python3
"""Export/import Flux art as a 128x80 sprite sheet.
Top strip: Vector at (0,0), string loop at (16,0), tower at (32,0).
Full splash: (0,16), 128x64. Unused top-strip pixels are ignored.
Requires Pillow; .ase/.aseprite files also require the Aseprite CLI.
Keep aseprite_to_flux.py alongside this script.
"""
import argparse
import ast
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
from PIL import Image
from aseprite_to_flux import load_image, pixels_for, pack

NAMES = ('FACTORY_LOGO', 'DIAMOND_LOGO', 'ANTENNA_LOGO')
DEFAULT_SOURCE = '/storage5/dev/ag7su-blowfang/firmware/k6-aura/apply-theme-splash.py'


def read_icons(source):
    # Read literals only: do not execute a firmware build script.
    found = {}
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in NAMES:
                    found[target.id] = ast.literal_eval(node.value)
    for name in NAMES:
        rows = found.get(name)
        if not isinstance(rows, list) or len(rows) != 16 or any(type(v) is not int or not 0 <= v <= 65535 for v in rows):
            raise ValueError(f'Missing or invalid {name} in {source}')
    return found


def export_sheet(args):
    icons = read_icons(args.source)
    sheet = Image.new('RGB', (128,80), 'white')
    for i,name in enumerate(NAMES):
        for y,row in enumerate(icons[name]):
            for x in range(16):
                if row & (1 << (15-x)):
                    sheet.putpixel((i*16+x,y),(0,0,0))
    if args.splash_bin:
        data = args.splash_bin.read_bytes()
        if len(data) != 1024:
            raise ValueError('Splash binary must be exactly 1024 bytes.')
        for page in range(8):
            for x in range(128):
                for bit in range(8):
                    if data[page*128+x] & (1<<bit):
                        sheet.putpixel((x,16+page*8+bit),(0,0,0))
    if args.output.resolve() in {args.source.resolve(), args.splash_bin.resolve() if args.splash_bin else None}:
        raise ValueError('Output must not overwrite an input.')
    if args.output.exists() and not args.force:
        raise ValueError('Output exists; use --force to replace it.')
    if args.output.suffix.lower() in ('.ase','.aseprite'):
        exe = shutil.which(args.aseprite)
        if not exe:
            raise ValueError('Aseprite CLI not found; use --aseprite or export a .png.')
        with tempfile.TemporaryDirectory(prefix='flux-sheet-') as tmp:
            png = Path(tmp)/'sheet.png'; sheet.save(png)
            result = subprocess.run([exe,'--batch',str(png),'--save-as',str(args.output.resolve())],capture_output=True,text=True)
            if result.returncode or not args.output.is_file():
                raise ValueError('Aseprite export failed:\n'+result.stdout+result.stderr)
    else:
        sheet.save(args.output,format='PNG')
    print(f'Exported {args.output}: 128x80. Splash area '+('loaded.' if args.splash_bin else 'blank; draw your splash there.'))


def import_sheet(args):
    im = load_image(args.input,args.frame,args.aseprite)
    if im.size != (128,80):
        raise ValueError(f'Sheet must be exactly 128x80; got {im.size}.')
    arrays = {}
    for i,name in enumerate(NAMES):
        tile = im.crop((i*16,0,i*16+16,16))
        arrays[name] = pack(pixels_for(tile,args.threshold,0,args.ink),16,16,'logo')
    splash = im.crop((0,16,128,80))
    pixels = pixels_for(splash,args.threshold,0,args.ink)
    data = bytes(pack(pixels,128,64,'splash'))
    files = {'logos.py': '# Paste these arrays into apply-theme-splash.py.\n',
             'logos.rs': '// Use FACTORY_LOGO as LOGO in draw_flux_splash.\n'}
    for name,rows in arrays.items():
        files['logos.py'] += name+' = [\n'+''.join(f'    0x{v:04X},\n' for v in rows)+']\n\n'
        files['logos.rs'] += f'const {name}: [u16; 16] = [\n'+''.join(f'    0b{v:016b},\n' for v in rows)+'];\n\n'
    files['splash.rs'] = 'const BOOT_LOGO: [u8; 1024] = [\n'+''.join('    '+', '.join(f'0x{v:02X}' for v in data[i:i+16])+',\n' for i in range(0,1024,16))+'];\n'
    targets = [args.output_dir/name for name in [*files,'splash.bin','splash-preview.png']]
    if args.input.resolve() in [p.resolve() for p in targets]:
        raise ValueError('Output must not overwrite input.')
    if not args.force and any(p.exists() for p in targets):
        raise ValueError('An output exists; use --force or choose a fresh output directory.')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name,text in files.items(): (args.output_dir/name).write_text(text)
    (args.output_dir/'splash.bin').write_bytes(data)
    preview=Image.new('1',(128,64));preview.putdata([0 if p else 255 for p in pixels]);preview.save(args.output_dir/'splash-preview.png')
    print(f'Imported all three icons and full splash into {args.output_dir}. Source files were not patched.')
    if all(v==0 for v in data) or all(v==255 for v in data):
        print('Note: firmware treats an all-zero or all-255 stored splash as empty and uses its default splash.')


def main():
    parser = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command',required=True)
    exp=sub.add_parser('export',help='Export current icons plus optional stored splash')
    exp.add_argument('output',type=Path)
    exp.add_argument('--source',type=Path,default=Path(DEFAULT_SOURCE))
    exp.add_argument('--splash-bin',type=Path)
    imp=sub.add_parser('import',help='Import edited sheet to Rust/Python arrays and splash binary')
    imp.add_argument('input',type=Path)
    imp.add_argument('--output-dir',type=Path,required=True)
    imp.add_argument('--frame',type=int,default=0)
    imp.add_argument('--ink',choices=('dark','light'),default='dark')
    imp.add_argument('--threshold',type=int,default=128)
    for p in (exp,imp):
        p.add_argument('--aseprite',default='aseprite')
        p.add_argument('--force',action='store_true',help='Replace existing output files')
    args=parser.parse_args()
    try:
        if args.command=='import' and (args.frame<0 or not 0<=args.threshold<=255):
            raise ValueError('Frame must be nonnegative and threshold must be 0..255.')
        (export_sheet if args.command=='export' else import_sheet)(args)
    except (OSError,ValueError,EOFError) as exc:
        parser.exit(1,f'Error: {exc}\n')


if __name__=='__main__': main()
