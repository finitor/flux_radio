import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_build_identity import NOTE, image_build_id
from k6_pack_install import compatibility_report
from k6_install import Cable, InstallError

def test_raw_image_id():
    note = NOTE + bytes(range(1,9))
    assert image_build_id(b'xxxx' + note) == '0102030405060708'
    for invalid in (b'', b'x'+note, note+note, NOTE+bytes(8)):
        with pytest.raises(ValueError):
            image_build_id(invalid)

def test_radio_identity_comparison():
    c = object.__new__(Cable)
    c.call = lambda _: b'K6CP'+bytes([2,1,22,0])+bytes(range(1,9))
    caps = c.capabilities()
    lock = {'capabilities':['module-loader'], 'modules':[]}
    report = compatibility_report(lock,caps,'0102030405060708')
    assert report['build_id_match'] and report['capabilities_match']
    assert not report['build_identity_verified'] and not report['install_ready']
    assert not compatibility_report(lock,caps,'ff'*8)['build_id_match']
    c.call = lambda _: b'K6CP'+bytes([2,1,22,0])+bytes(8)
    with pytest.raises(InstallError):
        c.capabilities()
