#!/usr/bin/env python3
"""Unified Blowfang K6 CLI. Radio writes require explicit subcommands and approval."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from k6_feature_packs import DEFAULT, resolve


def command(argv):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Delegate legacy flags verbatim, including --port before the radio verb.
    if argv and argv[0] in ('radio', 'catalog'):
        tool = 'k6_install.py' if argv[0] == 'radio' else 'k6_store.py'
        rest = argv[1:] or (['serve'] if argv[0] == 'catalog' else [])
        if not rest:
            raise ValueError('radio requires a subcommand (status, backup, flash, load, ...)')
        return subprocess.call([sys.executable, str(ROOT / 'tools' / tool), *rest], cwd=ROOT)
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan', help='resolve capability packs without building')
    plan.add_argument('packs', nargs='+')
    plan.add_argument('--spec', type=Path, default=DEFAULT)
    build = sub.add_parser('build', help='build firmware and modules; no radio writes')
    build.add_argument('packs', nargs='+')
    build.add_argument('--output', type=Path)
    build.add_argument('--spec', type=Path)
    inspect = sub.add_parser('inspect', help='check staged feature-pack integrity (no radio writes)')
    inspect.add_argument('pack', type=Path)
    inspect.add_argument('--spec', type=Path)
    preflight = sub.add_parser('preflight', help='read-only connected-radio compatibility check; restarts radio on session close')
    preflight.add_argument('pack', type=Path)
    preflight.add_argument('--port', required=True)
    preflight.add_argument('--spec', type=Path)
    preflight.add_argument('--key-file', type=Path, help='authenticate capability report using an existing key')
    matrix = sub.add_parser('matrix', help='verify flash budgets of separately linked profiles')
    matrix.add_argument('--size-dir', type=Path)
    matrix.add_argument('--build', action='store_true')
    matrix.add_argument('--build-dir', type=Path)
    matrix.add_argument('--output', type=Path)
    catalog = sub.add_parser('catalog', help='launch local module catalog web UI')
    catalog.add_argument('args', nargs=argparse.REMAINDER)
    radio = sub.add_parser('radio', help='radio cable operations (status, backup, flash, load)')
    radio.add_argument('args', nargs=argparse.REMAINDER)
    args = p.parse_args(argv)
    if args.command == 'plan':
        print(json.dumps(resolve(json.loads(args.spec.read_text()), args.packs), indent=2))
        return 0
    if args.command == 'build':
        cmd = ['k6_pack_build.py', *args.packs]
        if args.output: cmd += ['--output', str(args.output)]
        if args.spec: cmd += ['--spec', str(args.spec)]
    elif args.command == 'inspect':
        cmd = ['k6_pack_install.py', str(args.pack), '--inspect-unverified']
        if args.spec: cmd += ['--spec', str(args.spec)]
    elif args.command == 'preflight':
        cmd = ['k6_pack_install.py', str(args.pack), '--radio-preflight', '--port', args.port]
        if args.key_file: cmd += ['--key-file', str(args.key_file)]
        if args.spec: cmd += ['--spec', str(args.spec)]
    elif args.command == 'matrix':
        cmd = ['k6_pack_matrix.py']
        if args.size_dir: cmd += ['--size-dir', str(args.size_dir)]
        if args.build: cmd += ['--build']
        if args.build_dir: cmd += ['--build-dir', str(args.build_dir)]
        if args.output: cmd += ['--output', str(args.output)]
    elif args.command == 'catalog':
        cmd = ['k6_store.py', *(args.args or ['serve'])]
    else:
        if not args.args:
            p.error('radio requires a subcommand; use radio status, backup, flash, load, etc.')
        cmd = ['k6_install.py', *args.args]
    return subprocess.call([sys.executable, str(ROOT / 'tools' / cmd[0]), *cmd[1:]], cwd=ROOT)


def main(argv=None):
    try:
        return command(argv)
    except (OSError, ValueError, KeyError) as exc:
        print(f'k6: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
