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


def validate_theme(theme):
    if not isinstance(theme, str) or (theme not in THEMES and not _CUSTOM_RE.fullmatch(theme)):
        raise ValueError(f'unknown firmware theme: {theme}')
    if theme.startswith("custom-"):
        flags, bitmap = theme.split("-")[1:3]
        if not (int(flags) or int(bitmap, 16)):
            raise ValueError("custom theme needs a visible active VFO indicator")
        if any(int(bitmap[i:i+2], 16) & 1 for i in range(0, 16, 2)):
            raise ValueError("custom marker must be seven pixels wide")
        parts = theme.split("-")
        has_suffix = len(parts) == 5
        if has_suffix:
            if len(parts[3]) != 4 or parts[3][2] != "3" or not parts[4].startswith("m"):
                raise ValueError("custom meter bitmap suffix requires layout meter digit 3")
            _meter_bitmap_rows(parts[4][1:])
        elif len(parts) == 4 and parts[3][2] == "3":
            raise ValueError("layout meter digit 3 requires -m<28 hex digits> bitmap suffix")
    return theme


def theme_layout(theme):
    """Font, horizontal inset, meter style, splash logo; legacy defaults unchanged."""
    validate_theme(theme)
    parts = theme.split("-")
    return tuple(map(int, parts[3])) if len(parts) in (4, 5) else (0, 0, 0, 0)


def theme_meter_bitmap(theme):
    """Two 7-row custom S-meter bitmaps as ((norm rows), (over rows)), else None."""
    validate_theme(theme)
    parts = theme.split("-") if isinstance(theme, str) and theme.startswith("custom-") else []
    if len(parts) != 5:
        return None
    return _meter_bitmap_rows(parts[4][1:])


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


if __name__ == '__main__':
    main()
