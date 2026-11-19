#!/usr/bin/env python3
"""Fail closed on MCU flash budgets for purpose-built FD6818B profiles."""
import argparse
import json
from pathlib import Path

TOTAL = 122_880
BASE_DESIGN_GOAL = 98_304  # 96 KiB is a design goal, never a build limit


def flash_bytes(size_text):
    sections = {'.vector_table', '.text', '.rodata', '.gnu.sgstubs', '.k6_id', '.data'}
    return sum(int(fields[1]) for line in size_text.splitlines()
               if len(fields := line.split()) >= 2 and fields[0] in sections)


def assess(used, packs, *, base_design_goal=BASE_DESIGN_GOAL, total=TOTAL):
    if base_design_goal <= 0:
        raise ValueError('invalid Base design goal')
    if used <= 0:
        raise ValueError('missing or invalid linked flash size')
    is_base = set(packs) == {'base'}
    target_over = is_base and used > base_design_goal
    return {'used': used, 'limit': total, 'remaining': total - used,
            'profile': packs, 'pass': used <= total,
            'policy': 'application-limit',
            'base_design_goal_bytes': base_design_goal,
            'base_target_over': target_over,
            'base_target_over_by': max(0, used - base_design_goal) if is_base else 0,
            'note': 'Multiple optional packs are supported subject to the linked-image cap; '
                    'the reserve is not a guarantee of any particular combination.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size', type=Path, required=True)
    p.add_argument('--packs', required=True, help='comma-separated resolved packs')
    p.add_argument('--base-design-goal', type=int, default=BASE_DESIGN_GOAL)
    args = p.parse_args()
    result = assess(flash_bytes(args.size.read_text()), args.packs.split(','),
                    base_design_goal=args.base_design_goal)
    print(json.dumps(result, indent=2))
    if not result['pass']:
        p.exit(1, 'ERROR: firmware exceeds profile flash budget\n')


if __name__ == '__main__':
    main()
