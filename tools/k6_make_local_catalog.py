#!/usr/bin/env python3
"""Build local Git repositories containing slot-independent K6 module bundles."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modem import k6mod
import k6_install


def make_repo(name, source, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    dest = output / name
    if dest.exists():
        raise FileExistsError(f"{dest} already exists; not overwriting it")
    with tempfile.TemporaryDirectory(prefix=".building-", dir=output) as temp:
        build = Path(temp)
        args = SimpleNamespace(source=str(source), id=f"org.blowfang.k6.{name}", level=None,
                               output=str(build))
        k6_install.cmd_module_bundle(args, log=lambda *args: None)
        (build / "README.md").write_text(
            f"# {name.upper()}\n\n"
            "Experimental original Blowfang module; not validated on the compact FD6818B host. "
            "Some functions may not work and may transmit. Verify radio compatibility, frequencies, "
            "and the built-in callsign before transmitting.\n\n"
            f"Source: `c/k6/mod/{name}.c` in the Blowfang checkout. This local bundle is built "
            "from that checkout and uses an automatically allocated library slot. Rebuild it after "
            "updating the source. See the main project's documentation and MIT license.\n")
        subprocess.run(["git", "init", "--quiet", str(build)], check=True)
        build.rename(dest)
    return dest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "local-modules")
    args = parser.parse_args(argv)
    # Keep the local starter catalog aligned with the current FD6818B Aura host.
    # Other upstream modules can be added when they are ported and validated there.
    names = ["surf", "vfo", "cardlink"]
    failed = []
    for name in names:
        source = ROOT / "c/k6/mod" / (name + ".c")
        try:
            path = make_repo(name, source, args.output)
            print(f"created {path}", flush=True)
        except (OSError, ValueError, k6_install.InstallError, subprocess.CalledProcessError) as exc:
            print(f"FAILED {name}: {exc}", file=sys.stderr, flush=True)
            failed.append(name)
    print(f"created {len(names) - len(failed)}/{len(names)} repositories")
    return bool(failed)


if __name__ == "__main__":
    sys.exit(main())
