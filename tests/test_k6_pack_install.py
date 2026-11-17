import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_feature_packs import resolve
from k6_pack_build import assemble
from k6_pack_install import PackError, verify_pack

SPEC = json.loads((Path(__file__).resolve().parents[1] / 'config/k6-feature-packs.json').read_text())


def pack(tmp_path):
    image = tmp_path / 'fw.bin'
    image.write_bytes(b'firmware fixture')
    def build(name, source, folder):
        (folder / 'module.bin').write_bytes(name.encode())
        (folder / 'manifest.json').write_text(json.dumps({'library': [
            {'id': f'org.blowfang.k6.{name}', 'level': 16, 'file': 'module.bin'}]}))
    root = tmp_path / 'pack'
    assemble(resolve(SPEC, ['scan', 'aprs']), root, image, module_builder=build)
    return root


def test_unattested_firmware_refused(tmp_path):
    root = pack(tmp_path)
    with pytest.raises(PackError, match='not attested'):
        verify_pack(root, SPEC)
    assert len(verify_pack(root, SPEC, require_attested=False)['modules']) == 5


def test_tampered_module_rejected(tmp_path):
    root = pack(tmp_path)
    (root / 'modules/surf/module.bin').write_bytes(b'evil')
    with pytest.raises(PackError, match='hash mismatch'):
        verify_pack(root, SPEC, require_attested=False)


def test_tampered_capabilities_rejected(tmp_path):
    root = pack(tmp_path)
    lock = json.loads((root / 'pack.lock.json').read_text())
    lock['capabilities'].remove('explore-scanner-api')
    (root / 'pack.lock.json').write_text(json.dumps(lock))
    with pytest.raises(PackError, match='capabilities'):
        verify_pack(root, SPEC, require_attested=False)
