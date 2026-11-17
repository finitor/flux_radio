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
        if name == "explore_scan":
            readme = (
                "# EXPLORE_SCAN\n\n"
                "Receive only. Scans the supported VHF/UHF band sets one segment at a time, ranks "
                "up to 5 likely repeater candidates, lets you try a candidate frequency, and "
                "ignores/unignores candidates. While trying one, the host's shared CW and CTCSS/DCS "
                "decoders can add a confirmed callsign and tone to the candidate. Press B on a "
                "selected candidate to tune Aura VFO B to it. A provisional row appears as soon as "
                "a repeater-band carrier is confirmed; repeated overs and decoder cues update its "
                "grade. Candidate observations are held in RAM for the current run. Saved-repeater "
                "lookup is omitted in this memory-constrained module build.\n\n"
                "Controls: MENU switches between scan status and the candidate list; UP/DOWN "
                "select a candidate; Side 1 parks and listens for CW/CTCSS/DCS, then any key "
                "resumes; B hands the candidate to Aura VFO B; `*` ignores/restores; `#` changes "
                "band set; EXIT leaves the module. "
                "Key 5 reports that saving is unavailable in this compact build.\n\n"
                "This is an experimental port of the original Blowfang Explore workflow for the "
                "FD6818B Flux host. The host links the shared `c/k6/xscan.c` scanner and "
                "`c/k6/explore.c` candidate engine into firmware flash; the module holds only "
                "the UI and working state in the module arena. Manual Try uses the host's shared "
                "decoder APIs. Automatic CW listening, DMR analysis, and table writes are not "
                "ported yet. The host renders the compact original-style Explore list UI. "
                "Requires module API level 21.\n\n"
            )
        elif name == "aprsdfsk":
            readme = (
                "# APRS RX\n\n"
                "Receive-only Bell 202 1200-baud APRS/AX.25 decoder for the FD6818B. It listens "
                "on 144.390 MHz, samples the chip's plain-FSK discriminator output, "
                "and reports valid frames and usable timestamps over the cable. This is a "
                "diagnostic receiver; it does not transmit, digipeat, or expose a KISS TNC.\n\n"
                "The Bell 202 software slicer handles pre-emphasized packets and ignores stale "
                "FIFO words. Emulator captures decode clean packets; weak/noisy RF may still fail.\n\n"
                "The compact Aura module still needs a live-radio check after installing this "
                "FIFO-sentinel fix.\n\n"
                "Source: `c/k6/mod/aprsdfsk.c`; see `docs/k6-aprs-clock.md`. SPDX-License-Identifier: MIT.\n"
            )
        else:
            readme = (
                f"# {name.upper()}\n\n"
                "Experimental original Flux module; not validated on the compact FD6818B host. "
                "Check this module's documented behavior and radio compatibility before use. "
                "Transmit only when the module explicitly supports it and you have verified its settings.\n\n"
            )
        if name != "aprsdfsk":
            readme += (
                f"Source: `c/k6/mod/{name}.c` in the Flux checkout. This local bundle is built "
                "from that checkout and uses an automatically allocated library slot. Rebuild it after "
                "updating the source. See the main project's documentation and MIT license.\n")
        (build / "README.md").write_text(readme)
        subprocess.run(["git", "init", "--quiet", str(build)], check=True)
        build.rename(dest)
    return dest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "local-modules")
    args = parser.parse_args(argv)
    # Keep the local starter catalog aligned with the current FD6818B Flux host.
    # Other upstream modules can be added when they are ported and validated there.
    names = ["surf", "vfo", "cardlink", "explore_scan", "aprsdfsk"]
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
