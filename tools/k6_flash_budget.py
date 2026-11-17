#!/usr/bin/env python3
"""Report linked MCU flash use and approximate ownership from LLVM symbol sizes."""
import argparse
import collections
import re
import subprocess
from pathlib import Path

LIMIT = 122_880
SECTIONS = {'.vector_table', '.text', '.rodata', '.gnu.sgstubs', '.k6_id', '.data'}

def report(elf: Path):
    sections = {}
    for line in subprocess.check_output(['llvm-size', '-A', str(elf)], text=True).splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in SECTIONS:
            sections[parts[0]] = int(parts[1])
    total = sum(sections.values())
    print(f'Image: {elf}\nFlash: {total:,} / {LIMIT:,} bytes ({total/LIMIT:.1%}); free {LIMIT-total:,} bytes')
    print('Flash sections: ' + ', '.join(f'{k}={v:,}' for k,v in sections.items()))
    groups = collections.Counter()
    examples = collections.defaultdict(list)
    for line in subprocess.check_output(['llvm-nm', '-S', '--radix=d', str(elf)], text=True, errors='replace').splitlines():
        m = re.match(r'^\d+\s+(\d+)\s+([TtRrDd])\s+(\S+)', line)
        if not m: continue
        size, kind, name = int(m[1]), m[2], m[3]
        if name.startswith('_R'):
            if '4aura3app5pager7explore' in name: group = 'Rust: Explore'
            elif '4aura3app5pager' in name: group = 'Rust: pager / module host'
            elif '4aura2ui' in name: group = 'Rust: display UI'
            elif '4aura3app' in name: group = 'Rust: radio app'
            elif '4aura6device' in name: group = 'Rust: device'
            elif '4aura3hal' in name: group = 'Rust: HAL'
            elif '4aura3cps' in name: group = 'Rust: CPS / cable'
            elif '4aura' in name: group = 'Rust: other'
            else: group = 'Rust: dependencies / runtime'
        elif name.startswith(('xs_', 'kmx_', 'ex_', 'rt_', 'cw_', 'xd_', 'sted_', 'pxk6_')):
            group = 'C: scanner / decoding / storage'
        else: group = 'C: other / compiler builtins'
        groups[group] += size
        examples[group].append((size, name))
    print('\nApproximate *named-symbol* ownership (not additive to flash sections):')
    for group, size in groups.most_common():
        print(f'  {size:>7,}  {group}')
    print('\nLargest named routines:')
    for size, name in sorted((item for items in examples.values() for item in items), reverse=True)[:18]:
        print(f'  {size:>6,}  {name[:110]}')
    print('\nNote: LTO inlining, anonymous symbols, rodata and linker padding limit attribution accuracy.')

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('elf', type=Path);report(p.parse_args().elf)
