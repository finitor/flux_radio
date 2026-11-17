import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_capability_receipt import create, verify, write


def test_receipt_binds_image_and_plan(tmp_path):
    image = tmp_path / 'firmware.bin'
    image.write_bytes(b'firmware')
    plan = {'target': 'fd6818b', 'packs': ['base'], 'capabilities': ['module-loader'], 'cargo_features': ['spilib']}
    gates = {'K6_SCAN_SERVICE': '0'}
    path = tmp_path / 'firmware.receipt.json'
    receipt = write(path, image, plan, gates)
    assert json.loads(path.read_text()) == receipt
    assert verify(receipt, image, plan, gates)
    assert receipt['radio_attested'] is False
    image.write_bytes(b'changed')
    with pytest.raises(ValueError, match='does not match'):
        verify(receipt, image, plan, gates)
    image.write_bytes(b'firmware')
    with pytest.raises(ValueError, match='does not match'):
        verify(receipt, image, {**plan, 'capabilities': []}, gates)


def test_receipt_binds_nondefault_theme(tmp_path):
    image = tmp_path / 'firmware.bin'
    image.write_bytes(b'firmware')
    plan = {'target': 'fd6818b', 'packs': ['base'], 'capabilities': [], 'cargo_features': [], 'theme': 'classic'}
    receipt = create(image, plan, {})
    assert receipt['theme'] == 'classic'
    assert verify(receipt, image, plan, {})
    with pytest.raises(ValueError, match='does not match'):
        verify(receipt, image, {**plan, 'theme': 'minimal'}, {})
