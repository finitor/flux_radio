"""Local radio development workbench: Flask UI backed by the K6 emulator."""
from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path
from typing import Protocol

from sim.k6emu.__main__ import K6Board, overlay_module_bundle
from sim.k6emu.aprs_signal import ui_frame
from sim.k6emu.if_signal import pb1_bits
from sim.k6emu.if_capture import parse_capture
from sim.k6emu.rx_dma import MEASURED_FREE_RUNNING_HZ
from sim.k6emu.if_capture import parse_capture
from sim.k6emu.rx_dma import MEASURED_FREE_RUNNING_HZ

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = ROOT / "firmware/k6-aura/out-fd6818b/aura-fd6818b-blowfang-host.bin"
TEMPLATES = ROOT / "sim/k6ide_templates"
KEYS = ("MENU", "UP", "DOWN", "EXIT", "VM", "AB", "BAND", "SIDE1", "SIDE2",
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "#")


class K6Workbench:
    """Own the virtual flash and board; all Unicorn access is serialized by one lock."""
    def __init__(self, image: Path, spi_path: Path | None = None, cpi: float = 1.5):
        self.lock = threading.RLock()
        self.image = image.expanduser().resolve()
        self.spi_path = spi_path.expanduser().resolve() if spi_path else None
        self.cpi = cpi
        self.spi_data = bytearray(self.spi_path.read_bytes()) if self.spi_path else bytearray(b"\xff" * (2 * 1024 * 1024))
        if len(self.spi_data) != 2 * 1024 * 1024:
            raise ValueError("virtual SPI image must be exactly 2 MiB")
        self.board = None
        self.running = False
        self.started_at = None
        self.error = None
        self._boot()
        self.worker = threading.Thread(target=self._run, name="k6-ide-emulator", daemon=True)
        self.worker.start()

    def _boot(self):
        seed = None
        if self.spi_path:
            self.spi_path.parent.mkdir(parents=True, exist_ok=True)
            self.spi_path.write_bytes(self.spi_data)
            seed = self.spi_path
        self.board = K6Board(self.image, spi_image=seed, cpi=self.cpi, collect_mmio=False)
        if seed is None:
            self.board.flash_data[:] = self.spi_data
        self.running = True
        self.started_at = time.time()
        self.error = None

    def _run(self):
        while True:
            with self.lock:
                if not self.running or not self.board:
                    time.sleep(.04)
                    continue
                try:
                    # Larger Unicorn quanta cut Python/Unicorn call overhead while
                    # keeping virtual-time and peripheral servicing frequent enough
                    # for the live workbench.
                    self.board.run(18_000, 4096)
                    if self.board.fault:
                        self.running = False
                        self.error = f"Firmware fault: {self.board.fault.get('kind')}"
                except Exception as exc:  # keep the UI alive and expose emulator errors
                    self.running = False
                    self.error = str(exc)
            # Yield cooperatively without adding a wall-clock delay. The emulator
            # should use available CPU rather than run at an artificial fraction
            # of host speed; `sleep(0)` lets Flask/UI threads get scheduled.
            time.sleep(0)

    def inject_aprs(self, source="AG7SU", destination="APRS", message=">sim test",
                    ssid=7, noise=0.0, gain=1.0, clip=1.0,
                    emphasis_db=0.0, frequency_offset=0.0, seed=0, dma_mode="direct"):
        """Arm a simulated IF packet; firmware must enable DMA to consume it."""
        if not (0 <= int(ssid) <= 15 and 0 <= float(noise) <= 2
                and 0 < float(gain) <= 20 and 0 < float(clip) <= 1
                and -24 <= float(emphasis_db) <= 24
                and -500 <= float(frequency_offset) <= 500
                and len(message) <= 200):
            raise ValueError("APRS signal parameters outside permitted range")
        if dma_mode not in ("direct", "measured"):
            raise ValueError("invalid DMA mode")
        frame = ui_frame(source, destination, message.encode("ascii"), int(ssid))
        samples = pb1_bits(frame, noise=float(noise), gain=float(gain),
                          clip=float(clip), emphasis_db=float(emphasis_db),
                          frequency_offset=float(frequency_offset), seed=int(seed))
        with self.lock:
            self.board.attach_rx_bits(samples, dma_mode=dma_mode)
            return {"frame_bytes": len(frame), "sample_rate_hz": 85800,
                    "dma_mode": dma_mode,
                    "note": "armed only; reception requires firmware DMA activity"}

    def import_if_capture(self, log: str, sample_rate: int = 85800, dma_mode="direct"):
        if (len(log) > 100_000 or not 1000 <= sample_rate <= 200_000
                or dma_mode not in ("direct", "measured")):
            raise ValueError("capture too large or invalid sample rate")
        samples, metadata = parse_capture(log)
        with self.lock:
            self.board.attach_rx_bits(samples, sample_rate=sample_rate, dma_mode=dma_mode)
        return {**metadata, "sample_rate_hz": sample_rate, "dma_mode": dma_mode,
                "note": "rate supplied by operator, not measured from capture"}

    def aprs_rx_status(self):
        with self.lock:
            dma = self.board.rx_dma if self.board else None
            return {"armed": dma is not None,
                    "dma_mode": getattr(dma, "mode", None),
                    "signal_rate_hz": getattr(dma, "signal_rate_hz", None),
                    "dma_rate_hz": dma.sample_rate if dma else None,
                    "transfers": dma.transfers if dma else 0,
                    "exhausted": dma.exhausted if dma else False,
                    "remaining": dma.remaining if dma else 0}

    def reboot(self):
        with self.lock:
            if self.board:
                self.spi_data[:] = self.board.flash_data
            self._boot()

    def set_running(self, running: bool):
        with self.lock:
            if running and self.board and self.board.fault:
                raise RuntimeError("target faulted; reboot before resuming")
            self.running = bool(running)

    def step(self, instructions: int = 5000):
        with self.lock:
            self.running = False
            if self.board:
                self.board.run(instructions, 256)
                if self.board.fault:
                    self.error = f"Firmware fault: {self.board.fault.get('kind')}"

    def press(self, key: str, down: bool):
        if key not in KEYS:
            raise ValueError("unknown K6 key")
        with self.lock:
            if not self.board:
                raise RuntimeError("board is not booted")
            self.board.press_key(key, down)

    def switch(self, name: str, on: bool):
        with self.lock:
            if name == "power":
                self.board.set_gpio("A", 15, 0 if on else 1)
            elif name == "ptt":
                self.board.set_gpio("A", 10, 0 if on else 1)
            else:
                raise ValueError("unknown switch")

    def modules(self):
        flash = self.board.flash_data if self.board else self.spi_data
        found = []
        # K6 signed library images carry a 16-byte header and 64-bit authenticator.
        for slot in range(32):
            at = 0x110000 + slot * 0x4000
            header = bytes(flash[at:at + 16])
            if len(header) < 16 or header[:3] != b"K6M" or header[13] != 1:
                continue
            code_len = int.from_bytes(header[4:6], "little")
            code = bytes(flash[at + 16:at + 16 + min(code_len, 80)])
            name = "Module"
            if code.startswith(b"K6NM"):
                name = code[4:36].split(b"\0")[0].decode("ascii", "replace") or name
            found.append({"slot": slot, "name": name, "bytes": code_len + 24,
                          "serial": int.from_bytes(header[8:12], "little"),
                          "type": "module" if not header[13] & 6 else "protected data"})
        return found

    def load(self, bundle: Path, key_file: Path | None, slots: set[int] | None):
        with self.lock:
            if not self.board:
                raise RuntimeError("board is not booted")
            import sys
            tool_dir = str(ROOT / "tools")
            if tool_dir not in sys.path:
                sys.path.insert(0, tool_dir)
            import k6_install
            key_path = Path(k6_install.find_key(str(key_file) if key_file else None,
                                                create=False, log=lambda _: None))
            installed = overlay_module_bundle(self.board.flash_data, bundle, key_path, slots)
            self.spi_data[:] = self.board.flash_data
            if self.spi_path:
                self.spi_path.write_bytes(self.spi_data)
            self._boot()  # the firmware scans the module table at startup
            return installed

    def unload(self, slots: list[int]):
        if not slots or any(slot < 0 or slot >= 32 for slot in slots):
            raise ValueError("select one or more slots from 0 through 31")
        with self.lock:
            for slot in slots:
                at = 0x110000 + slot * 0x4000
                header = self.board.flash_data[at:at + 16]
                if header[:3] != b"K6M" or not (header[13] & 1) or (header[13] & 6):
                    raise ValueError(f"slot {slot} is empty or protected; only modules can be unloaded")
            for slot in slots:
                at = 0x110000 + slot * 0x4000
                self.board.flash_data[at:at + 0x4000] = b"\xff" * 0x4000
            self.spi_data[:] = self.board.flash_data
            if self.spi_path:
                self.spi_path.write_bytes(self.spi_data)
            self._boot()

    def state(self):
        with self.lock:
            b = self.board
            return {"model": "Baofeng UV-K6 / FD6818B", "image": str(self.image),
                    "running": self.running, "error": self.error,
                    "instructions": b.instructions if b else 0,
                    "virtual_ms": round(b.cycles / 96_000, 1) if b else 0,
                    "pc": f"0x{b.last_pc:08x}" if b else "—",
                    "uart": bytes(b.uart_tx[-3000:]).decode("utf-8", "replace") if b else "",
                    "modules": self.modules(), "keys": list(KEYS)}

    def screen_svg(self):
        with self.lock:
            ram, reverse = self.board.screen.snapshot()
        pixels = []
        for y in range(64):
            for x in range(128):
                col = 4 + (x if reverse else 127 - x)
                if ram[y // 8][col] & (1 << (y & 7)):
                    pixels.append(f'<rect x="{x}" y="{y}" width="1" height="1"/>')
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 64" '
                'shape-rendering="crispEdges"><rect width="128" height="64" fill="#dddcc8"/>'
                '<g fill="#182319">' + ''.join(pixels) + '</g></svg>')


class RadioAdapter(Protocol):
    """Backend contract for one emulated radio model; UI routes stay model-neutral."""
    def state(self) -> dict: ...
    def screen_svg(self) -> str: ...
    def press(self, key: str, down: bool): ...
    def switch(self, name: str, on: bool): ...
    def inject_aprs(self, **kwargs): ...
    def aprs_rx_status(self) -> dict: ...
    def import_if_capture(self, log: str) -> dict: ...

    def reboot(self): ...
    def set_running(self, running: bool): ...
    def step(self, instructions: int = 5000): ...
    def load(self, bundle: Path, key_file: Path | None, slots: set[int] | None): ...
    def unload(self, slots: list[int]): ...


RADIO_MODELS = {"k6-fd6818b": K6Workbench}


def module_bundle_catalog(include_experimental=False):
    """List checked-in and locally built bundles that the workbench can load."""
    manifests = []
    for parent in (ROOT / "local-modules", ROOT / "firmware/k6-aura/out-fd6818b"):
        if parent.is_dir():
            manifests.extend(parent.glob("*/manifest.json"))
    bundles = []
    preferred = {"surf", "vfo", "cardlink", "explore_scan", "aprsdfsk"}
    for manifest_path in sorted(manifests):
        try:
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("format") != 1:
                continue
            modules = [entry for entry in manifest.get("library", [])
                       if entry.get("kind") == "module"]
            if not modules:
                continue
            # The workbench's default picker is a curated set of current modules.
            # Historical diagnostics and experiments remain accessible explicitly.
            if not include_experimental and manifest_path.parent.name not in preferred:
                continue
            contents = ", ".join(
                f"{entry.get('name', 'Module')} ({'slot ' + str(entry['slot']) if entry.get('slot') is not None else 'automatic slot'})"
                for entry in modules)
            bundles.append({
                "path": str(manifest_path.parent.resolve()),
                "label": f"{contents} · {manifest_path.parent.name}",
                "modules": len(modules),
            })
        except (OSError, ValueError, TypeError):
            continue
    return bundles


def create_app(workbench: RadioAdapter):
    from flask import Flask, jsonify, render_template, request
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.config["workbench"] = workbench
    @app.get("/")
    def index():
        return render_template("index.html", state=workbench.state())

    @app.get("/api/state")
    def api_state():
        return jsonify(workbench.state())

    @app.get("/api/module-bundles")
    def api_module_bundles():
        return jsonify(bundles=module_bundle_catalog(
            include_experimental=request.args.get("all") == "1"))

    @app.get("/api/screen.svg")
    def api_screen():
        from flask import Response
        return Response(workbench.screen_svg(), mimetype="image/svg+xml")

    @app.post("/api/key")
    def api_key():
        body = request.get_json(force=True)
        try:
            workbench.press(str(body["key"]).upper(), bool(body["down"]))
            return jsonify(ok=True)
        except (ValueError, RuntimeError, KeyError) as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.post("/api/switch")
    def api_switch():
        body = request.get_json(force=True)
        try:
            workbench.switch(str(body["name"]), bool(body["on"]))
            return jsonify(ok=True)
        except (ValueError, RuntimeError, KeyError) as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.post("/api/reboot")
    def api_reboot():
        workbench.reboot()
        return jsonify(ok=True)

    @app.post("/api/run")
    def api_run():
        body = request.get_json(force=True)
        try:
            workbench.set_running(bool(body["running"]))
            return jsonify(ok=True)
        except (RuntimeError, KeyError) as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.post("/api/step")
    def api_step():
        workbench.step()
        return jsonify(ok=True)

    @app.post("/api/if-capture/import")
    def api_if_capture_import():
        try:
            body = request.get_json(force=True)
            return jsonify(ok=True, **workbench.import_if_capture(
                str(body["log"]), int(body.get("sample_rate", 85800)),
                str(body.get("dma_mode", "direct"))))
        except (ValueError, TypeError, KeyError) as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.get("/api/aprs/rx")
    def api_aprs_rx_status():
        return jsonify(workbench.aprs_rx_status())

    @app.post("/api/aprs/rx")
    def api_aprs_rx():
        try:
            body = request.get_json(force=True)
            return jsonify(ok=True, **workbench.inject_aprs(**body))
        except (ValueError, TypeError, UnicodeError) as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.post("/api/aprs/import")
    def api_aprs_import():
        try:
            body = request.get_json(force=True)
            if len(body.get("log", "")) > 100000:
                raise ValueError("capture log too large")
            return jsonify(ok=True, **workbench.import_if_capture(body["log"]))
        except (ValueError, TypeError, KeyError) as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.post("/api/modules/load")
    def api_load():
        body = request.get_json(force=True)
        try:
            slots = {int(x) for x in body.get("slots", [])} or None
            installed = workbench.load(Path(body["bundle"]),
                Path(body["key_file"]) if body.get("key_file") else None, slots)
            return jsonify(ok=True, installed=[{"slot": s, "name": n, "bytes": size}
                                               for s, n, size in installed])
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.post("/api/modules/unload")
    def api_unload():
        try:
            body = request.get_json(force=True)
            workbench.unload([int(x) for x in body["slots"]])
            return jsonify(ok=True)
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 400
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=RADIO_MODELS, default="k6-fd6818b",
                        help="radio emulator backend (currently K6 FD6818B)")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--spi-image", type=Path, help="persistent 2 MiB virtual SPI flash dump")
    parser.add_argument("--host", default="0.0.0.0",
                        help="HTTP bind address (default: all interfaces for remote browser access)")
    parser.add_argument("--port", type=int, default=5056)
    parser.add_argument("--cpi", type=float, default=1.5)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"firmware image not found: {args.image}")
    board = RADIO_MODELS[args.model](args.image, args.spi_image, args.cpi)
    print(f"K6 IDE simulator at http://{args.host}:{args.port} (virtual RF only)")
    print(f"On this host: http://127.0.0.1:{args.port}")
    print("On your LAN, use this host's LAN address; Ctrl-C stops the workbench.")
    create_app(board).run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
