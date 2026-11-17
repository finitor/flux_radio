#!/usr/bin/env python3
"""Extract FD6818B GP0 sample probes from a picocom log.

The result measures whether PB1 changes with an on-air signal. It does not
establish a Bell 202 or AX.25 decode. Each .s8 file contains one signed count
per 64 DMA samples, exactly as emitted by aprsifbcap.c.
"""
import argparse
import base64
import json
import math
from pathlib import Path
import re

CAP = re.compile(r"\bc (\d+) (\d+) (\d+) ks=(\d+) r=(-?\d+) t=(\d+) lost=(\d+)\b")
ROW = re.compile(r"\by (\d+) ([0-9a-fA-F]{4}) ([A-Za-z0-9+/=]+)(?=\s|$)")
NCAP = re.compile(r"\bcap start .*\bncap=(\d+)\b")


def extract(log):
    captures = {}
    ncap = 2160
    for line in log.splitlines():
        match = NCAP.search(line)
        if match:
            ncap = int(match[1])
        match = CAP.search(line)
        if match:
            stage, gain, index, ks, rssi, tick, lost = map(int, match.groups())
            captures[index] = dict(stage=stage, gain=gain, ks=ks, rssi=rssi,
                                   tick=tick, lost=lost, rows={})
        match = ROW.search(line)
        if match:
            index, offset = int(match[1]), int(match[2], 16)
            if index in captures:
                captures[index]["rows"][offset] = base64.b64decode(match[3], validate=True)
    for index, item in captures.items():
        data = bytearray()
        for offset, chunk in sorted(item.pop("rows").items()):
            if offset != len(data):
                raise ValueError(f"capture {index}: missing bytes at {len(data)}")
            data.extend(chunk)
        if len(data) != ncap:
            raise ValueError(f"capture {index}: expected {ncap} samples, got {len(data)}")
        item["samples"] = bytes(data)
    return captures


def summarize(item):
    samples = [v if v < 128 else v - 256 for v in item["samples"]]
    mean = sum(samples) / len(samples)
    rms = math.sqrt(sum((v - mean) ** 2 for v in samples) / len(samples))
    result = {k: v for k, v in item.items() if k != "samples"}
    result.update(samples=len(samples), mean=round(mean, 2), ac_rms=round(rms, 2),
                  min=min(samples), max=max(samples))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="picocom log containing APRS IF CAP output")
    parser.add_argument("--out-dir", type=Path, help="write each raw capture and summary here")
    args = parser.parse_args()
    captures = extract(args.log.read_text(errors="replace"))
    if not captures:
        raise SystemExit("no complete APRS IF CAP captures found")
    summary = {str(index): summarize(item) for index, item in captures.items()}
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for index, item in captures.items():
            (args.out_dir / f"capture-{index:03}.s8").write_bytes(item["samples"])
        (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
