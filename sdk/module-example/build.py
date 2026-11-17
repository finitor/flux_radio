#!/usr/bin/env python3
"""Build a catalog-ready bundle using an explicit Flux checkout."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
MODULE_ID = "org.flux.example.hello"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flux", required=True, type=Path, help="Flux source checkout")
    args = parser.parse_args()
    flux = args.flux.expanduser().resolve()
    subprocess.run([sys.executable, str(flux / "tools/k6_install.py"),
                    "module-bundle", str(ROOT / "src/hello.c"),
                    "--id", MODULE_ID, "-o", str(ROOT / "dist")],
                   cwd=flux, check=True)
