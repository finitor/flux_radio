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
from k6_build_identity import image_build_id


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
    root = Path(root).resolve()
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
    if require_attested:
        # A mutable lockfile boolean is not proof of a radio/firmware ABI match.
        # Keep all radio-writing paths disabled until an independent verifier exists.
        raise PackError('firmware capability attestation is not implemented; refusing installation')
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
        hashes = manifest.get('sha256')
        if hashes is not None:
            if not isinstance(hashes, dict) or hashes.get(module_path.name) != mod['sha256']:
                raise PackError(f'module manifest hash differs from lockfile: {mod["name"]}')
        if manifest.get('build_id', '0000000000000000') != '0000000000000000':
            raise PackError(f'module bundle unexpectedly bound to firmware build: {mod["name"]}')
        if not 1 <= mod['api_level'] <= 22:
            raise PackError(f'unsupported module API level: {mod["name"]}')
    return lock



CAPABILITY_FLAGS = {
    'module-loader': 'module_loader',
    'explore-scanner-api': 'scanner',
    'candidate-ranking': 'scanner',
    'cw-tone-observation': 'scanner',
    'fd6818-fsk-rx': 'fsk_rx',
}


def compatibility_report(lock, capabilities, expected_build_id=None):
    """Compare a verified artifact plan with an unauthenticated radio report."""
    missing = [name for name in lock['capabilities']
               if capabilities.get(CAPABILITY_FLAGS.get(name, ''), False) is not True]
    ceiling = capabilities.get('module_api_max', 0)
    if type(ceiling) is not int or not 1 <= ceiling <= 255:
        raise PackError('invalid reported module API ceiling')
    unsupported = [m['name'] for m in lock['modules'] if m['api_level'] > ceiling]
    reported_build_id = capabilities.get('build_id')
    identity_match = bool(expected_build_id and reported_build_id == expected_build_id)
    return {'expected_build_id': expected_build_id, 'reported_build_id': reported_build_id,
            'build_id_match': identity_match, 'capabilities_match': not missing and not unsupported,
            'missing_capabilities': missing, 'unsupported_modules': unsupported,
            'reported_api_max': ceiling, 'authenticated': False,
            'build_identity_verified': False, 'install_ready': False}


def radio_preflight(root, spec, port, key_file=None):
    from k6_install import open_port, open_cable, InstallError
    from types import SimpleNamespace
    lock = verify_pack(root, spec, require_attested=False)
    firmware = Path(root) / lock['firmware']['path']
    try:
        expected_build_id = image_build_id(firmware.read_bytes())
    except ValueError:
        expected_build_id = None  # legacy artifact; cannot match a build ID
    if key_file is not None:
        from modem import k6mod
        key = k6mod.read_key(str(key_file))
        if key == k6mod.PLACEHOLDER:
            raise PackError('placeholder is not a provisioned module key')
    else:
        key = None
    connection = open_port(SimpleNamespace(port=port))
    cable = None
    try:
        cable = open_cable(connection, lambda *_: None, wait=3.0)
        if cable is None:
            raise PackError('no Blowfang cable session')
        caps = cable.authenticated_capabilities(key) if key is not None else cable.capabilities()
        report = compatibility_report(lock, caps, expected_build_id)
        report['key_possession_verified'] = key is not None
        report['capability_report_authenticated'] = key is not None
        # A holder of the shared key can impersonate firmware; no secure boot or
        # hardware measurement is available. Never enable installation here.
        report['packs'] = lock['packs']
        return report
    except InstallError as exc:
        raise PackError(str(exc)) from exc
    finally:
        try:
            if cable is not None:
                cable.end()
        finally:
            connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path)
    parser.add_argument('--spec', type=Path, default=DEFAULT)
    parser.add_argument('--inspect-unverified', action='store_true', help='inspect only; never install')
    parser.add_argument('--radio-preflight', action='store_true', help='query compatibility only; no flash writes (ends cable session with restart)')
    parser.add_argument('--port', help='explicit radio serial port')
    parser.add_argument('--key-file', type=Path, help='explicit existing key for fresh read-only capability challenge')
    args = parser.parse_args()
    if args.radio_preflight and (not args.port or args.inspect_unverified):
        parser.error('--radio-preflight requires --port and cannot be combined with --inspect-unverified')
    if args.key_file and not args.radio_preflight:
        parser.error('--key-file requires --radio-preflight')
    if args.port and not args.radio_preflight:
        parser.error('--port requires --radio-preflight')
    try:
        spec = json.loads(args.spec.read_text())
        if args.radio_preflight:
            report = radio_preflight(args.pack, spec, args.port, args.key_file)
            print(json.dumps(report, indent=2))
            return 0 if report['capabilities_match'] and report['build_id_match'] else 1
        lock = verify_pack(args.pack, spec, require_attested=not args.inspect_unverified)
        print(json.dumps({'status': 'verified artifacts' if args.inspect_unverified else 'verified lockfile',
                          'install_ready': not args.inspect_unverified,
                          'packs': lock['packs'], 'modules': [m['name'] for m in lock['modules']],
                          'firmware': lock['firmware']['path']}, indent=2))
        print('No radio writes performed. Firmware installation and capability attestation are not implemented here.')
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    sys.exit(main())
