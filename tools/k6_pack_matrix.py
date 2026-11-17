#!/usr/bin/env python3
"""Build and budget-check purpose-built K6 profiles, never flash a radio."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
from k6_feature_packs import DEFAULT, resolve
from k6_flash_policy import assess, flash_bytes


def profiles(spec, features):
    """Base, individual optional packs, and every available combination."""
    available = [p for p in features if not spec['packs'][p].get('status', '').startswith('planned')]
    for count in range(len(available) + 1):
        for subset in itertools.combinations(available, count):
            yield ('base',) + subset, resolve(spec, subset or ('base',))


def report(profile_sizes, *, required=('scan', 'aprs')):
    rows = []
    for names, used in profile_sizes:
        packs = list(names)
        result = assess(used, packs)
        rows.append({'packs': packs, 'bytes': used, 'remaining': result['remaining'],
                     'limit': result['limit'], 'pass': result['pass']})
    combo = next((r for r in rows if set(r['packs']) == {'base', *required}), None)
    return {'profiles': rows, 'all_fit': all(r['pass'] for r in rows),
            'required_combo': list(required),
            'required_combo_tested': combo is not None,
            'required_combo_fits': bool(combo and combo['pass'])}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', type=Path, default=DEFAULT)
    p.add_argument('--features', nargs='+', default=['scan', 'aprs'])
    p.add_argument('--size-dir', type=Path, help='read PROFILE/size.txt from this directory instead of building')
    p.add_argument('--output', type=Path, help='write JSON report')
    args = p.parse_args()
    spec = json.loads(args.spec.read_text())
    results = []
    for names, plan in profiles(spec, args.features):
        label = '-'.join(names)
        if args.size_dir:
            size = args.size_dir / label / 'size.txt'
        else:
            # Each invocation rebuilds the currently shared firmware target. These
            # are not distinct profiles until C and Rust services are conditionally linked.
            print(f'{label}: selective linking unavailable; refusing misleading matrix', file=sys.stderr)
            return 2
        if not size.is_file():
            p.error(f'missing linked size for {label}: {size}')
        results.append((names, flash_bytes(size.read_text())))
    result = report(results)
    print(json.dumps(result, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['all_fit'] and result['required_combo_fits'] else 1


if __name__ == '__main__':
    sys.exit(main())
