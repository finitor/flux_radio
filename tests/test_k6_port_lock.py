"""Run on real Linux and Windows runners; exercise process-level locking."""
import os
from pathlib import Path
import subprocess
import sys
import pytest
TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from k6_port_lock import port_identity, serial_lock


def test_windows_port_aliases():
    assert port_identity('com12', windows=True) == 'COM12'
    assert port_identity(r'\\.\COM12', windows=True) == 'COM12'
    assert port_identity('COM012', windows=True) == 'COM12'
    assert port_identity('COM1', windows=True) != port_identity('COM12', windows=True)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX symlink test')
def test_posix_symlink_alias(tmp_path):
    target = tmp_path / 'ttyUSB0'
    target.touch()
    alias = tmp_path / 'radio'
    alias.symlink_to(target)
    assert port_identity(alias) == port_identity(target)


def test_other_process_cannot_lock_same_port(tmp_path):
    port = 'COM12' if os.name == 'nt' else str(tmp_path / 'ttyUSB0')
    alias = 'com12' if os.name == 'nt' else port
    code = """
import sys
sys.path.insert(0,sys.argv[1])
from k6_port_lock import serial_lock
try:
    with serial_lock(sys.argv[2],sys.argv[3]):
        print('acquired')
except BlockingIOError:
    sys.exit(23)
"""
    def attempt(name):
        return subprocess.run([sys.executable, '-c', code, str(TOOLS), name, str(tmp_path/'locks')],
                              capture_output=True, text=True, timeout=10)
    with serial_lock(port,tmp_path/'locks'):
        result = attempt(alias)
        assert result.returncode == 23, result.stderr
        assert attempt('COM13' if os.name == 'nt' else port+'1').returncode == 0
    assert attempt(alias).returncode == 0


def test_lock_released_after_exception(tmp_path):
    with pytest.raises(RuntimeError):
        with serial_lock('COM5',tmp_path):
            raise RuntimeError('interrupted')
    with serial_lock('COM5',tmp_path):
        pass
