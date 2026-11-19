import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_flash_policy import TOTAL, BASE_DESIGN_GOAL, assess, flash_bytes


def test_size_sections():
    assert flash_bytes('.text 500 0\n.rodata 200 0\n.data 30 0\n.bss 1000 0\n') == 730


def test_base_target_is_separate_from_hard_image_limit():
    assert assess(BASE_DESIGN_GOAL, ['base'])['pass']
    over_target = assess(BASE_DESIGN_GOAL + 1, ['base'])
    assert over_target['pass']
    assert over_target['base_target_over'] is True
    assert over_target['limit'] == TOTAL
    assert assess(BASE_DESIGN_GOAL + 1, ['base', 'scan'])['pass']
    assert not assess(TOTAL + 1, ['base', 'scan', 'data'])['pass']


def test_design_goal_does_not_change_hard_limit():
    assert TOTAL == 120 * 1024
    assert assess(BASE_DESIGN_GOAL + 1, ['base'], base_design_goal=1)['pass']
