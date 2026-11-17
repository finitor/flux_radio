import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_flash_policy import TOTAL, BASE_CEILING, assess, flash_bytes


def test_size_sections():
    assert flash_bytes('.text 500 0\n.rodata 200 0\n.data 30 0\n.bss 1000 0\n') == 730


def test_base_must_leave_room_for_features():
    assert assess(BASE_CEILING, ['base'])['pass']
    assert not assess(BASE_CEILING + 1, ['base'])['pass']
    assert assess(BASE_CEILING + 1, ['base', 'scan'])['pass']
    assert not assess(TOTAL + 1, ['base', 'scan', 'aprs'])['pass']


def test_reserve_is_24_kib():
    assert TOTAL - BASE_CEILING == 24 * 1024
