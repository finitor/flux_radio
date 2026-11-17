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


def validate_theme(theme):
    if not isinstance(theme, str) or (theme not in THEMES and not re.fullmatch(r'custom-[01][01]-[0-9a-f]{16}', theme)):
        raise ValueError(f'unknown firmware theme: {theme}')
    if theme.startswith("custom-"):
        flags, bitmap = theme.split("-")[1:]
        if not (int(flags) or int(bitmap, 16)):
            raise ValueError("custom theme needs a visible active VFO indicator")
        if any(int(bitmap[i:i+2], 16) & 1 for i in range(0, 16, 2)):
            raise ValueError("custom marker must be seven pixels wide")
    return theme


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
