#!/usr/bin/env python3
"""Fail closed on MCU flash budgets for purpose-built FD6818B profiles."""
import argparse
import json
from pathlib import Path

TOTAL = 122_880
BASE_CEILING = 98_304  # 96 KiB; 24 KiB reserved for optional firmware services
OPTIONAL_RESERVE = TOTAL - BASE_CEILING


def flash_bytes(size_text):
    sections = {'.vector_table', '.text', '.rodata', '.gnu.sgstubs', '.k6_id', '.data'}
    return sum(int(fields[1]) for line in size_text.splitlines()
               if len(fields := line.split()) >= 2 and fields[0] in sections)


def assess(used, packs, *, base_ceiling=BASE_CEILING, total=TOTAL):
    if not 0 < base_ceiling < total:
        raise ValueError('invalid base ceiling')
    if used <= 0:
        raise ValueError('missing or invalid linked flash size')
    is_base = set(packs) == {'base'}
    ceiling = base_ceiling if is_base else total
    return {'used': used, 'limit': ceiling, 'remaining': total - used,
            'reserved_for_features': total - base_ceiling,
            'profile': packs, 'pass': used <= ceiling,
            'policy': 'base-ceiling' if is_base else 'total-ceiling',
            'note': 'Multiple optional packs are supported subject to the linked-image cap; '
                    'the reserve is not a guarantee of any particular combination.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size', type=Path, required=True)
    p.add_argument('--packs', required=True, help='comma-separated resolved packs')
    p.add_argument('--base-ceiling', type=int, default=BASE_CEILING)
    args = p.parse_args()
    result = assess(flash_bytes(args.size.read_text()), args.packs.split(','),
                    base_ceiling=args.base_ceiling)
    print(json.dumps(result, indent=2))
    if not result['pass']:
        p.exit(1, 'ERROR: firmware exceeds profile flash budget\n')


if __name__ == '__main__':
    main()
