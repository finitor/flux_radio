#!/usr/bin/env python3
"""Build the module-only serial bundle for the compact FD6818B VFO host."""
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
    ap.add_argument("--out", default=str(ROOT / "firmware/k6-aura/out-fd6818b/vfo-module-bundle"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    entries, hashes = [], {}
    for slot, name in ((0, "surf"), (30, "vfo")):
        src = ROOT / "c/k6/mod" / f"{name}.c"
        code, entry = k6mod.build(str(src))
        filename = f"mod-{name}.bin"
        (out / filename).write_bytes(code)
        entries.append({"slot": slot, "kind": "module", "file": filename,
                        "name": k6mod.module_name(code) or name,
                        "level": k6mod.source_level(str(src))})
        hashes[filename] = hashlib.sha256(code).hexdigest()
        print(f"slot {slot}: {filename}, {len(code)} bytes, entry={entry}")
    manifest = {"format": 1, "build": "FD6818B Explore VFO module bundle",
                "build_id": "0000000000000000", "library": entries, "sha256": hashes}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
