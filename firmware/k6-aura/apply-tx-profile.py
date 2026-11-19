#!/usr/bin/env python3
"""Set the first-boot BandLock selection without restricting later device choices."""
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent / 'build/aura-fd6818b-port/src'
PROFILE_IDS = {'ce': 0, 'fcc': 1, 'gb': 2, '400-430': 3, '400-438': 4,
               'pmr446': 5, 'gmrs-frs': 6, 'ca': 7, 'all-lock': 8, 'unlocked': 9}
name = os.environ.get('K6_TX_PROFILE', 'ce')
if name not in PROFILE_IDS:
    raise SystemExit(f'unknown K6_TX_PROFILE: {name}')
path = ROOT / 'flash_map.rs'
text = path.read_text()
target = f'        band_lock: {PROFILE_IDS[name]}, // catalog initial profile'
pattern = r'(?m)^[ \t]*band_lock: \d+, // (?:CE & CN|catalog initial profile)$'
updated, count = re.subn(pattern, target, text)
if count != 1:
    raise SystemExit('TX profile patch: expected one default band_lock initializer')
path.write_text(updated)
