"""Default module-key lifecycle: never replace an existing radio key."""
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import k6_install as installer
from modem import k6mod


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.delenv('BLOWFANG_KEY', raising=False)


def test_key_generation_elsewhere_populates_default_privately(tmp_path):
    custom = tmp_path / 'elsewhere.key'
    k6mod.new_key(str(custom))
    default = tmp_path / '.config/blowfang/k6-mod.key'
    assert default.is_file()
    assert k6mod.read_key(default) == k6mod.read_key(custom)
    assert stat.S_IMODE(default.stat().st_mode) == 0o600


def test_explicit_key_populates_missing_default(tmp_path):
    custom = tmp_path / 'existing.key'
    custom.write_text('12' * 16 + '\n')
    assert installer.find_key(str(custom), log=lambda *x: None) == str(custom)
    default = tmp_path / '.config/blowfang/k6-mod.key'
    assert k6mod.read_key(default) == k6mod.read_key(custom)


def test_conflicting_default_is_preserved_and_warning_emitted(tmp_path):
    default = tmp_path / '.config/blowfang/k6-mod.key'
    default.parent.mkdir(parents=True)
    default.write_text('12' * 16 + '\n')
    other = tmp_path / 'other.key'
    other.write_text('34' * 16 + '\n')
    lines = []
    assert installer.find_key(str(other), log=lines.append) == str(other)
    assert k6mod.read_key(default) != k6mod.read_key(other)
    assert any('different' in line.lower() for line in lines)


def test_legacy_key_is_copied_to_default_without_changing_it(tmp_path):
    legacy = tmp_path / '.config/sotto/k6-mod.key'
    legacy.parent.mkdir(parents=True)
    legacy.write_text('56' * 16 + '\n')
    assert installer.find_key(log=lambda *x: None) == str(legacy)
    assert k6mod.read_key(tmp_path / '.config/blowfang/k6-mod.key') == k6mod.read_key(legacy)


def test_prekeyed_flash_does_not_invent_an_unrelated_key(tmp_path, monkeypatch):
    firmware = tmp_path / 'firmware.bin'
    firmware.write_bytes(b'no placeholder')
    monkeypatch.setattr(installer, 'open_port', lambda _: pytest.fail('radio must not be opened'))
    assert installer.main(['flash', str(firmware)], log=lambda *x, **k: None) == 1
    assert not (tmp_path / '.config/blowfang/k6-mod.key').exists()


def test_flash_does_not_generate_a_misspelled_explicit_key(tmp_path, monkeypatch):
    firmware = tmp_path / 'firmware.bin'
    firmware.write_bytes(b'firmware' + k6mod.PLACEHOLDER)
    missing = tmp_path / 'typo.key'
    monkeypatch.setattr(installer, 'open_port', lambda _: pytest.fail('radio must not be opened'))
    result = installer.main(['--key-file', str(missing), 'flash', str(firmware)], log=lambda *x, **k: None)
    assert result == 1
    assert not missing.exists()
    assert not (tmp_path / '.config/blowfang/k6-mod.key').exists()


def test_flash_creates_default_key_before_opening_radio(tmp_path, monkeypatch):
    firmware = tmp_path / 'firmware.bin'
    firmware.write_bytes(b'firmware' + k6mod.PLACEHOLDER)
    def no_radio(_):
        raise installer.InstallError('test radio unavailable')
    monkeypatch.setattr(installer, 'open_port', no_radio)
    assert installer.main(['flash', str(firmware)], log=lambda *x, **k: None) == 1
    default = tmp_path / '.config/blowfang/k6-mod.key'
    assert default.is_file() and len(k6mod.read_key(default)) == 16
