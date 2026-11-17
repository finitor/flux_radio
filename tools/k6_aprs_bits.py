#!/usr/bin/env python3
"""Summarize the APRS IF RX diagnostic's circular NRZI bit recording."""
import argparse
import json
from pathlib import Path
import re

TOTAL = re.compile(r"\bbits total=(\d+)\b")
ROW = re.compile(r"\bbits (\d+) ([0-9a-fA-F]{32})(?=\s|$)")


def summarize(log):
    total = None
    rows = {}
    for line in log.splitlines():
        match = TOTAL.search(line)
        if match:
            total, rows = int(match[1]), {}
        match = ROW.search(line)
        if match and total is not None:
            rows[int(match[1])] = bytes.fromhex(match[2])
    if total is None or set(rows) != set(range(0, 512, 16)):
        raise ValueError("expected bits total and all 32 bits rows from one APRS IF RX run")
    buf = b"".join(rows[i] for i in range(0, 512, 16))
    first = max(0, total - 4096)
    bits = [(buf[(i >> 3) & 511] >> (i & 7)) & 1 for i in range(first, total)]
    flags = [i + first for i in range(len(bits) - 7)
             if sum(bits[i + j] << j for j in range(8)) == 0x7E]
    runs = []
    for i, at in enumerate(flags):
        if i == 0 or at - flags[i - 1] != 8:
            runs.append([at, 1])
        else:
            runs[-1][1] += 1
    p = sum(bits) / len(bits) if bits else 0
    return dict(total_bits=total, retained_bits=len(bits), ones_fraction=round(p, 4),
                flags=len(flags), chance_flags_at_this_balance=round(
                    max(0, len(bits) - 7) * (1 - p) ** 2 * p ** 6, 1),
                longest_consecutive_flags=max((n for _, n in runs), default=0),
                flag_positions=flags)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.log.read_text(errors="replace")), indent=2))


if __name__ == "__main__":
    main()
