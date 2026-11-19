#!/usr/bin/env python3
"""Apply the artwork in flux-art-kit/flux-arrays to the firmware branding sources.

Run from any directory with ``python3 apply-flux-art.py``. An alternate art
directory can be supplied as the first argument.
"""
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
PATCHER = ROOT / "firmware/k6-aura/apply-flux-art.py"
DEFAULT_ART = ROOT / "flux-art-kit/flux-arrays"


def main() -> int:
    if len(sys.argv) > 2:
        print(f"usage: {Path(sys.argv[0]).name} [art-directory]", file=sys.stderr)
        return 2
    art_dir = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) == 2 else DEFAULT_ART
    if not PATCHER.is_file():
        print(f"Flux art patcher not found: {PATCHER}", file=sys.stderr)
        return 1
    if not art_dir.is_dir():
        print(f"Flux art directory not found: {art_dir}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["K6_FLUX_ART_DIR"] = str(art_dir)
    return subprocess.run([sys.executable, str(PATCHER)], cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
