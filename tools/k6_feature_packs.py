#!/usr/bin/env python3
"""Resolve K6 firmware capability packs and module install plans (no flashing)."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'config/k6-feature-packs.json'


def resolve(spec, selected):
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
    return {'target': spec['target'], 'packs': resolved,
            'cargo_features': collect('cargo_features'),
            'capabilities': collect('capabilities'), 'modules': collect('modules'),
            'module_install': 'explicit post-flash action; no automatic radio writes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packs', nargs='+', help='e.g. scan aprs')
    parser.add_argument('--spec', type=Path, default=DEFAULT)
    args = parser.parse_args()
    try:
        print(json.dumps(resolve(json.loads(args.spec.read_text()), args.packs), indent=2))
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
