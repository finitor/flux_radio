#!/usr/bin/env python3
"""Build a K6 capability pack and lock its module artifacts; never writes to radio."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from k6_feature_packs import DEFAULT, resolve
import k6_install
from k6_flash_policy import assess, flash_bytes


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assemble(plan, output, firmware, *, module_builder=None, verified_firmware=False):
    """Stage a deterministic lockfile and module bundles from a prebuilt firmware image."""
    output = Path(output)
    firmware = Path(firmware)
    if not firmware.is_file():
        raise ValueError(f'firmware image missing: {firmware}')
    output.mkdir(parents=True, exist_ok=True)
    dest = output / 'firmware.bin'
    if firmware.resolve() != dest.resolve():
        shutil.copyfile(firmware, dest)
    modules = []
    for name in plan['modules']:
        source = ROOT / 'c/k6/mod' / f'{name}.c'
        if not source.is_file():
            raise ValueError(f'module source missing: {source}')
        folder = output / 'modules' / name
        folder.mkdir(parents=True, exist_ok=True)
        if module_builder:
            module_builder(name, source, folder)
        else:
            k6_install.cmd_module_bundle(SimpleNamespace(source=str(source),
                id=f'org.blowfang.k6.{name}', level=None, output=str(folder)), log=lambda *_: None)
        manifest = json.loads((folder / 'manifest.json').read_text())
        module_file = folder / manifest['library'][0]['file']
        if manifest['library'][0]['level'] > 22:
            raise ValueError(f'module {name} requires unsupported API level {manifest["library"][0]["level"]}')
        modules.append({'name': name, 'id': manifest['library'][0]['id'],
                        'api_level': manifest['library'][0]['level'],
                        'path': str(module_file.relative_to(output)), 'sha256': digest(module_file),
                        'manifest_sha256': digest(folder / 'manifest.json')})
    lock = {'format': 1, 'target': plan['target'], 'packs': plan['packs'],
            'cargo_features': plan['cargo_features'], 'capabilities': plan['capabilities'],
            'firmware': {'path': 'firmware.bin', 'sha256': digest(dest), 'bytes': dest.stat().st_size,
                         'capabilities_verified': verified_firmware},
            'modules': modules, 'install': {'automatic': False,
                'note': 'Flash firmware and install modules separately with explicit approval; unkeyed firmware rejects modules.'}}
    (output / 'pack.lock.json').write_text(json.dumps(lock, indent=2) + '\n')
    return lock


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('packs', nargs='+')
    p.add_argument('--output', type=Path, default=ROOT / 'firmware/k6-aura/out-fd6818b/packs')
    p.add_argument('--spec', type=Path, default=DEFAULT)
    p.add_argument('--skip-firmware-build', action='store_true', help='use an existing firmware image')
    p.add_argument('--firmware', type=Path, help='required with --skip-firmware-build')
    p.add_argument('--allow-unverified-firmware', action='store_true',
                   help='explicitly allow staging a prebuilt image without verifying capabilities')
    args = p.parse_args()
    try:
        plan = resolve(json.loads(args.spec.read_text()), args.packs)
        if args.skip_firmware_build:
            if args.firmware is None:
                p.error('--firmware is required with --skip-firmware-build')
            if not args.allow_unverified_firmware:
                p.error('prebuilt firmware capability set is unverified; pass --allow-unverified-firmware to stage only')
            image = args.firmware
        else:
            env = os.environ.copy()
            # Existing firmware build still links some optional services unconditionally.
            # Never imply that this plan has already stripped them from flash.
            env['K6_AURA_FEATURES'] = ','.join(['pager-explore'] + plan['cargo_features'])
            env['K6_IMAGE_NAME'] = 'aura-fd6818b-pack'
            env['K6_SCAN_SERVICE'] = '1' if 'scan' in plan['packs'] else '0'
            env['K6_FSK_RX_SERVICE'] = '1' if 'aprs' in plan['packs'] else '0'
            subprocess.run(['sh', str(ROOT / 'firmware/k6-aura/build-fd6818b.sh')],
                           cwd=ROOT, env=env, check=True)
            image = ROOT / 'firmware/k6-aura/out-fd6818b/aura-fd6818b-pack.bin'
            size_file = ROOT / 'firmware/k6-aura/out-fd6818b/size.txt'
            budget = assess(flash_bytes(size_file.read_text()), plan['packs'])
            if not budget['pass']:
                raise ValueError(f'firmware exceeds {budget["policy"]}: {budget["used"]} > {budget["limit"]}')
        lock = assemble(plan, args.output, image, verified_firmware=False)
        print(json.dumps({'lockfile': str(args.output / 'pack.lock.json'),
                          'firmware_bytes': lock['firmware']['bytes'],
                          'modules': [m['name'] for m in lock['modules']],
                          'automatic_install': False}, indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError, k6_install.InstallError) as exc:
        p.error(str(exc))


if __name__ == '__main__':
    main()
