"""Parse IF CAPTURE serial logs and replay their original PB1 sample bits."""
from __future__ import annotations
import re

HEADER = re.compile(r'^ifcap v1 bits=(\d+) ticks=(\d+)$')
ROW = re.compile(r'^if ([0-9a-fA-F]+)$')


def parse_capture(log: str) -> tuple[list[int], dict]:
    bits = None
    ticks = None
    data = bytearray()
    ended = False
    for raw in log.splitlines():
        line = raw.strip()
        header = HEADER.fullmatch(line)
        if header:
            if bits is not None:
                raise ValueError('multiple captures in log')
            bits, ticks = map(int, header.groups())
            if not 1 <= bits <= 8192:
                raise ValueError('unsupported sample count')
        elif bits is not None and line == 'ifcap end':
            ended = True
            break
        elif bits is not None:
            row = ROW.fullmatch(line)
            if row:
                data.extend(bytes.fromhex(row.group(1)))
    if bits is None or not ended or len(data) != (bits + 7) // 8:
        raise ValueError('incomplete IF capture')
    samples = [(data[i >> 3] >> (i & 7)) & 1 for i in range(bits)]
    return samples, {'bits': bits, 'ticks_100us': ticks,
                     'sample_rate_hz': None, 'rate_verified': False}
