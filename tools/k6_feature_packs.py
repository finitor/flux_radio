#!/usr/bin/env python3
"""Resolve K6 firmware capability packs and module install plans (no flashing)."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'config/k6-feature-packs.json'


THEMES = {
    'flux': {'name': 'Flux', 'description': 'Factory Flux appearance: original frequency layout, top border and left rail.'},
    'classic': {'name': 'Classic', 'description': 'Traditional active VFO arrow.'},
    'minimal': {'name': 'Minimal', 'description': 'Clean left rail, no horizontal border.'},
}
DEFAULT_THEME = 'flux'
# Editable representations of the exact built-in VFO focus decorations.
THEME_EDITOR_PRESETS = {
    'flux': 'custom-11-0000000000000000',
    'classic': 'custom-00-c0f0fcfefcf0c000',
    'minimal': 'custom-01-0000000000000000',
}


_CUSTOM_RE = re.compile(
    r'custom-[01][01]-[0-9a-f]{16}'
    r'(?:-[01][0-3][0-2][0-2]|-[01][0-3]3[0-2]-m[0-9a-f]{28})?'
    r'(?:-b[0-9a-f]{240})?'
    r'(?:-l(?:0|s[0-9a-f]+|p[0-9a-f]{4096})(?:\.(?:0|s[0-9a-f]+|p[0-9a-f]{4096})){2})?'
    r'(?:-f[0-9a-f]{264})?'
    r'(?:-w(?:[0-9a-f]{30}|[0-9a-f]{100}|[0-9a-f]{150}|[0-9a-f]{290}|[0-9a-f]{320}))?'
)
def _meter_bitmap_rows(suffix_hex):
    """Parse 28 hex digits into two 7-row tuples; enforce byte-per-row shape."""
    raw = bytes(int(suffix_hex[i:i + 2], 16) for i in range(0, 28, 2))
    for byte in raw:
        if byte & 0x07:
            raise ValueError("custom meter bitmap must use one byte per row (low three bits 0)")
    norm, over = tuple(raw[:7]), tuple(raw[7:])
    if not any(norm) or not any(over):
        raise ValueError("custom meter bitmap needs at least one nonzero row per bitmap")
    return (norm, over)


def decode_layer(part):
    """128x64 row-major transparent/on/off pixels. Sparse or packed."""
    pixels = bytearray(8192)
    if part == "0":
        return pixels
    if part.startswith("p") and len(part) == 4097:
        for i, value in enumerate(bytes.fromhex(part[1:])):
            for j in range(4):
                state = (value >> (6 - 2*j)) & 3
                if state == 3:
                    raise ValueError("reserved layer pixel state")
                pixels[i*4+j] = state
        return pixels
    if not part.startswith("s") or len(part) > 4097 or (len(part)-1) % 6 or len(part)==1:
        raise ValueError("invalid layer encoding")
    last = 0
    for i in range(1,len(part),6):
        word = int(part[i:i+4],16)
        start, state = word & 0x7fff, 2 if word & 0x8000 else 1
        length = int(part[i+4:i+6],16)
        if start < last or start >= 8192 or not 1 <= length <= 128-start%128:
            raise ValueError("invalid or overlapping layer run")
        pixels[start:start+length] = bytes([state])*length
        last = start+length
    return pixels


def layer_runs(pixels):
    """Yield horizontal spans, never crossing an LCD row."""
    i = 0
    while i < 8192:
        state = pixels[i]
        if not state:
            i += 1
            continue
        end = i+1
        while end < min(8192, (i//128+1)*128) and pixels[end] == state:
            end += 1
        yield i, end-i, state
        i = end


def encode_layer(pixels):
    if len(pixels)!=8192 or any(p not in (0,1,2) for p in pixels):
        raise ValueError("invalid layer pixels")
    runs = list(layer_runs(pixels))
    if not runs:
        return "0"
    if len(runs)*3 <= 2048:
        return "s" + "".join(f"{start | (0x8000 if state==2 else 0):04x}{length:02x}" for start,length,state in runs)
    return "p" + bytes(sum(pixels[i+j] << (6-2*j) for j in range(4)) for i in range(0,8192,4)).hex()


def validate_theme(theme):
    if not isinstance(theme, str) or len(theme)>13400 or (theme not in THEMES and not _CUSTOM_RE.fullmatch(theme)):
        raise ValueError("unknown firmware theme")
    if theme.startswith("custom-"):
        parts = theme.split("-")
        flags, bitmap = parts[1:3]
        layers = None
        if parts[-1].startswith("w"):
            w=validate_widgets(bytes.fromhex(parts.pop()[1:]))
            if len(w)==160 and any(w[i+3]==2 for i in range(0,len(w),5)) and not parts[-1].startswith("f"):
                raise ValueError("custom frequency font missing")
        if parts[-1].startswith("f"):
            f=bytes.fromhex(parts.pop()[1:])
            if any(not any(f[i:i+12]) for i in range(0,132,12)):raise ValueError("blank digit glyph")
        if parts[-1].startswith("l"):
            layers = tuple(decode_layer(p) for p in parts.pop()[1:].split("."))
        if parts[-1].startswith("b"):
            battery = bytes.fromhex(parts.pop()[1:])
            for i in range(0,120,24):
                glyph=battery[i:i+24]
                if not any(glyph) or any(x&0x7f for x in glyph[2::3]):
                    raise ValueError("battery glyph must be visible and 17 pixels wide")
        if not (int(flags) or int(bitmap,16)):
            if not layers or not all(1 in layer for layer in layers[1:]):
                raise ValueError("custom theme needs visible active VFO indicators")
        if any(int(bitmap[i:i+2],16)&1 for i in range(0,16,2)):
            raise ValueError("custom marker must be seven pixels wide")
        if len(parts)==5:
            _meter_bitmap_rows(parts[4][1:])
        if layers:
            for layer in layers[1:]:
                if any(layer) and 1 not in layer:
                    raise ValueError("cursor layers need at least one on pixel")
    return theme


def theme_layout(theme):
    validate_theme(theme)
    parts = theme.split("-")
    return tuple(map(int,parts[3])) if len(parts)>3 and len(parts[3])==4 else (0,0,0,0)


def theme_meter_bitmap(theme):
    validate_theme(theme)
    parts = theme.split("-")
    return _meter_bitmap_rows(parts[4][1:]) if len(parts)>4 and parts[4].startswith("m") else None


def theme_battery(theme):
    validate_theme(theme)
    return next((bytes.fromhex(p[1:]) for p in theme.split("-")[3:] if p.startswith("b")),None)


def theme_layers(theme):
    validate_theme(theme)
    part = next((p for p in theme.split("-")[3:] if p.startswith("l")), "")
    return tuple(decode_layer(p) for p in part[1:].split(".")) if part.startswith("l") else None


def resolve(spec, selected, theme=DEFAULT_THEME):
    validate_theme(theme)
    packs = spec['packs']
    resolved, visiting = [], set()

    def visit(name):
        if name in resolved:
            return
        if name not in packs:
            raise ValueError(f'unknown pack: {name}')
        if name in visiting:
            raise ValueError(f'cyclic pack dependency: {name}')
        visiting.add(name)
        for dep in packs[name].get('requires', []):
            visit(dep)
        visiting.remove(name)
        resolved.append(name)

    for name in selected:
        visit(name)
    if any(packs[n].get('status', '').startswith('planned') for n in resolved):
        raise ValueError('planned pack is not buildable: ' + ', '.join(
            n for n in resolved if packs[n].get('status', '').startswith('planned')))
    def collect(key):
        return list(dict.fromkeys(item for name in resolved for item in packs[name].get(key, [])))
    capabilities = collect('capabilities')
    for module in collect('modules'):
        required = spec.get('module_requirements', {}).get(module)
        if required is None:
            raise ValueError(f'module {module} has no declared firmware requirements')
        missing = set(required) - set(capabilities)
        if missing:
            raise ValueError(f'module {module} missing capabilities: {sorted(missing)}')
    return {'target': spec['target'], 'theme': theme, 'packs': resolved,
            'cargo_features': collect('cargo_features'),
            'capabilities': capabilities, 'modules': collect('modules'),
            'module_install': 'explicit post-flash action; no automatic radio writes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packs', nargs='+', help='e.g. scan aprs')
    parser.add_argument('--spec', type=Path, default=DEFAULT)
    parser.add_argument('--theme', type=validate_theme, default=DEFAULT_THEME, metavar="THEME")
    args = parser.parse_args()
    try:
        print(json.dumps(resolve(json.loads(args.spec.read_text()), args.packs, args.theme), indent=2))
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))



# K6T v4: ordered source,x,y,font,flags records. All coordinates absolute.
FLAT_SIZES = [(30,8),(10,8),(17,8),(60,8),(65,8)] + [(7,8),(10,8),(30,8),(82,17),(124,6)]*2
MODE_SIZES=[(12,6),(16,6),(24,6),(4,6),(16,6),(4,6),(20,6),(32,6)]
FLAT_V5_SIZES=FLAT_SIZES.copy()
FLAT_V5_SIZES[9]=FLAT_V5_SIZES[14]=MODE_SIZES[0]
FLAT_V5_SIZES+=MODE_SIZES[1:]*2
def validate_flat(data):
    if len(data) not in (75,145,160): raise ValueError("invalid flat layout length")
    seen=set()
    for i in range(0,len(data),5):
        source,x,y,font,flags=data[i:i+5]
        if source>=len(data)//5 or source in seen or flags>1 or font>((2 if len(data)==160 else 1) if source in (8,13) else 0):
            raise ValueError("invalid flat widget")
        seen.add(source)
        w,h=(72,12) if font==2 else (54,10) if font else (FLAT_V5_SIZES+[(10,8),(10,8),(10,8)] if len(data)==160 else FLAT_V5_SIZES if len(data)==145 else FLAT_SIZES)[source]
        if x+w>128 or y+h>64: raise ValueError("widget outside LCD")
    return data

def validate_widgets(data):
    if len(data) in (75,145,160): return validate_flat(data)
    sizes = [(128,8),(128,24),(128,24),(128,8),(17,8)]
    if len(data) not in (15,50):
        raise ValueError("invalid layout length")
    rects=[]
    for i,(w,h) in enumerate(sizes):
        x,y,f=data[3*i:3*i+3]
        if x+w>128 or y+h>64 or f>(2 if i in (1,2) else 0):
            raise ValueError("widget outside screen or unsupported font")
        if i<4:
            if any(x<rx+rw and rx<x+w and y<ry+rh and ry<y+h for rx,ry,rw,rh in rects):
                raise ValueError("live widget groups overlap")
            rects.append((x,y,w,h))
        elif x!=109 or y!=rects[0][1]:
            raise ValueError("battery must remain in status group")
    if len(data)==50:
        # Child bounds inside their native group; frequency reserves 82x17.
        specs=[(30,8,128,8),(10,8,128,8),(17,8,128,8),
               (60,8,128,8),(65,8,128,8)]+[(7,8,128,24),(10,8,128,24),(30,8,128,24),(82,17,128,24),(124,6,128,24)]*2
        # 15 pairs + five reserved bytes; reserved for future fonts.
        for i,(w,h,pw,ph) in enumerate(specs):
            x,y=data[15+2*i:17+2*i]
            if x+w>pw or y+h>ph: raise ValueError("child widget outside parent")
        if any(data[45:]): raise ValueError("unsupported child attributes")
    return data

def theme_widgets(theme):
    part=next((p for p in theme.split("-")[3:] if p.startswith("w")),None)
    return validate_widgets(bytes.fromhex(part[1:])) if part else None

if __name__ == '__main__':
    main()
