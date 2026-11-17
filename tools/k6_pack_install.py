#!/usr/bin/env python3
"""Verify a feature-pack lockfile; install modules only with explicit approval.

Firmware flashing is intentionally separate: radio module API/firmware capability
attestation is not yet implemented, so an unverified pack cannot be installed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from k6_feature_packs import DEFAULT, resolve


class PackError(ValueError):
    pass


def checked_file(root, name, sha):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise PackError('unsafe artifact path')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise PackError(f'missing or unsafe artifact: {name}')
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != sha:
        raise PackError(f'hash mismatch: {name}')
    return path


def verify_pack(root, spec, *, require_attested=True):
    root = Path(root)
    lock = json.loads((root / 'pack.lock.json').read_text())
    if lock.get('format') != 1 or lock.get('target') != spec['target']:
        raise PackError('unsupported lockfile or radio target')
    plan = resolve(spec, lock['packs'])
    for key in ('packs', 'capabilities', 'modules', 'cargo_features'):
        if key == 'modules':
            actual = [m['name'] for m in lock['modules']]
        else:
            actual = lock[key]
        if actual != plan[key]:
            raise PackError(f'lockfile {key} does not match resolved dependencies')
    firmware = lock['firmware']
    fw = checked_file(root, firmware['path'], firmware['sha256'])
    if fw.stat().st_size != firmware['bytes']:
        raise PackError('firmware byte count mismatch')
    if require_attested and not firmware.get('capabilities_verified'):
        raise PackError('firmware capabilities are not attested; refusing installation')
    for mod in lock['modules']:
        if mod['id'] != f'org.blowfang.k6.{mod["name"]}':
            raise PackError(f'module identity mismatch: {mod["name"]}')
        module_path = checked_file(root, mod['path'], mod['sha256'])
        manifest_path = module_path.parent / 'manifest.json'
        checked_file(root, str(manifest_path.relative_to(root)), mod['manifest_sha256'])
        manifest = json.loads(manifest_path.read_text())
        if len(manifest.get('library', [])) != 1:
            raise PackError(f'invalid module manifest: {mod["name"]}')
        entry = manifest['library'][0]
        if entry['id'] != mod['id'] or entry['level'] != mod['api_level'] or entry['file'] != module_path.name:
            raise PackError(f'module manifest differs from lockfile: {mod["name"]}')
        if not 1 <= mod['api_level'] <= 22:
            raise PackError(f'unsupported module API level: {mod["name"]}')
    return lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path)
    parser.add_argument('--spec', type=Path, default=DEFAULT)
    parser.add_argument('--inspect-unverified', action='store_true', help='inspect only; never install')
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text())
        lock = verify_pack(args.pack, spec, require_attested=not args.inspect_unverified)
        print(json.dumps({'status': 'verified artifacts' if args.inspect_unverified else 'verified lockfile',
                          'install_ready': not args.inspect_unverified,
                          'packs': lock['packs'], 'modules': [m['name'] for m in lock['modules']],
                          'firmware': lock['firmware']['path']}, indent=2))
        print('No radio writes performed. Firmware installation and capability attestation are not implemented here.')
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
