#!/usr/bin/env python3
"""Build the sideloadable EXPLORE scan module bundle."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from modem import k6mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--sim-fixture", action="store_true",
                    help="build a simulator-only fixture with one synthetic ranked candidate")
    args = ap.parse_args()
    out = Path(args.out) if args.out else ROOT / (
        "firmware/k6-aura/out-fd6818b/explore-module-sim-bundle" if args.sim_fixture else
        "firmware/k6-aura/out-fd6818b/explore-module-bundle")
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / "c/k6/mod/explore_scan.c"
    flags = k6mod.CFLAGS + (["-DK6_EXPLORE_SIM_FIXTURE=1"] if args.sim_fixture else [])
    code, entry = k6mod.build(str(source), cflags=flags)
    name = "mod-explore.bin"
    (out / name).write_bytes(code)
    manifest = {
        "format": 1,
        "build": ("SIMULATION ONLY: EXPLORE UI fixture" if args.sim_fixture else
                  "Aura sideloadable EXPLORE scan module"),
        "build_id": "0000000000000000",
        "library": [{"slot": 29, "kind": "module", "file": name,
                      "name": k6mod.module_name(code) or "EXPLORE",
                      "level": k6mod.source_level(str(source))}],
        "sha256": {name: hashlib.sha256(code).hexdigest()},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"slot 29: {name}, {len(code)} bytes, entry={entry}, module={manifest['library'][0]['name']}")


if __name__ == "__main__":
    main()
