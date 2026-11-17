import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_feature_packs import resolve
from k6_pack_build import assemble, digest


def test_pack_lock_and_module_hashes(tmp_path):
    spec = json.loads((Path(__file__).resolve().parents[1] / 'config/k6-feature-packs.json').read_text())
    plan = resolve(spec, ['scan', 'aprs'])
    image = tmp_path / 'input.bin'
    image.write_bytes(b'firmware-test-fixture')
    def fake_build(name, source, folder):
        payload = name.encode()
        (folder / 'module.bin').write_bytes(payload)
        (folder / 'manifest.json').write_text(json.dumps({'library': [{'id': f'org.blowfang.k6.{name}',
            'file': 'module.bin', 'level': 22}]}))
    output = tmp_path / 'pack'
    lock = assemble(plan, output, image, module_builder=fake_build)
    assert [m['name'] for m in lock['modules']] == plan['modules']
    assert digest(output / lock['firmware']['path']) == lock['firmware']['sha256']
    for mod in lock['modules']:
        assert digest(output / mod['path']) == mod['sha256']
    assert lock['install']['automatic'] is False
    assert json.loads((output / 'pack.lock.json').read_text()) == lock
