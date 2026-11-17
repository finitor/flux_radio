import importlib.util
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_install import Cable, InstallError, CMD_CAPS


def test_cable_capabilities_valid_and_invalid():
    cable = object.__new__(Cable)
    cable.call = lambda command: bytes(b'K6CP') + bytes([1, 7, 22, 0]) + bytes(8) if command == CMD_CAPS else None
    result = cable.capabilities()
    assert result['scanner'] and result['fsk_rx']
    assert not result['authenticated'] and not result['build_identity_verified']
    cable.call = lambda command: b'BLWF' + bytes(12)
    with pytest.raises(InstallError, match='malformed'):
        cable.capabilities()
    cable.call = lambda command: b'K6CP' + bytes([1, 0, 22, 0]) + bytes(8)
    with pytest.raises(InstallError, match='invalid'):
        cable.capabilities()


def test_generated_patch_idempotent_and_updates_gates(tmp_path, monkeypatch):
    import subprocess
    repo = Path(__file__).resolve().parents[1]
    script = repo / 'firmware/k6-aura/apply-capability-query.py'
    text = 'const CMD_CABLE_INFO: u8 = 0x56;\n            CMD_CABLE_INFO => {\n'
    # Patch script's fixed generated location in an isolated copy.
    import shutil
    here = tmp_path / 'firmware'
    here.mkdir()
    shutil.copy2(script, here / script.name)
    generated = here / 'build/aura-fd6818b-port/src/cps'
    generated.mkdir(parents=True)
    target = generated / 'mod.rs'
    target.write_text(text)
    (generated.parent.parent / 'build.rs').write_text('    if feat("VOICE_EXPLORE") {\n        File::create(out.join("k6id.x"))')
    for scan in ('0', '1'):
        subprocess.run([sys.executable, str(here / script.name)], env={'K6_SCAN_SERVICE': scan, 'K6_FSK_RX_SERVICE': '0'}, check=True)
        output = target.read_text()
        assert output.count('CMD_CABLE_CAPS if f.addr') == 1
        assert f"2, {1 | (2 if scan == '1' else 0)}, 22, 0" in output
