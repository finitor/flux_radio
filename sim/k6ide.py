"""Local radio development workbench: Flask UI backed by the K6 emulator."""
from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from sim.k6emu.__main__ import K6Board, overlay_module_bundle

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
        self.board = K6Board(self.image, spi_image=seed, cpi=self.cpi)
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
                started = time.perf_counter()
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
                # Leave a short scheduling gap for the web UI without throttling the
                # emulator to a fraction of the host's available CPU time.
                elapsed = time.perf_counter() - started
            if self.running:
                time.sleep(max(.001, elapsed * .5))

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
    def reboot(self): ...
    def set_running(self, running: bool): ...
    def step(self, instructions: int = 5000): ...
    def load(self, bundle: Path, key_file: Path | None, slots: set[int] | None): ...
    def unload(self, slots: list[int]): ...


RADIO_MODELS = {"k6-fd6818b": K6Workbench}


def module_bundle_catalog():
    """List checked-in and locally built bundles that the workbench can load."""
    manifests = []
    for parent in (ROOT / "local-modules", ROOT / "firmware/k6-aura/out-fd6818b"):
        if parent.is_dir():
            manifests.extend(parent.glob("*/manifest.json"))
    bundles = []
    for manifest_path in sorted(manifests):
        try:
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("format") != 1:
                continue
            modules = [entry for entry in manifest.get("library", [])
                       if entry.get("kind") == "module"]
            if not modules:
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


def create_app(workbench: RadioAdapter, access_token: str | None = None):
    from flask import Flask, jsonify, render_template, request
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.config["workbench"] = workbench
    app.config["access_token"] = access_token or secrets.token_urlsafe(32)

    @app.before_request
    def protect_mutations():
        # Binding to 0.0.0.0 makes the UI reachable off-host. Require a per-run
        # token for every API request, especially module signing/loading.
        if request.path.startswith("/api/"):
            supplied = request.headers.get("Authorization", "")
            if supplied.startswith("Bearer "):
                supplied = supplied[7:]
            if not hmac.compare_digest(supplied, app.config["access_token"]):
                return jsonify(ok=False, error="missing or invalid workbench token"), 401
        return None

    @app.get("/")
    def index():
        return render_template("index.html", state=workbench.state())

    @app.get("/api/state")
    def api_state():
        return jsonify(workbench.state())

    @app.get("/api/module-bundles")
    def api_module_bundles():
        return jsonify(bundles=module_bundle_catalog())

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
    access_token = os.environ.get("K6IDE_TOKEN") or secrets.token_urlsafe(32)
    print(f"K6 IDE simulator at http://{args.host}:{args.port} (virtual RF only)")
    print(f"Local workbench URL: http://127.0.0.1:{args.port}/#token={quote(access_token, safe='')}")
    print(f"Workbench access token: {access_token}")
    print("For another device, replace 127.0.0.1 with this host's LAN address; Ctrl-C stops the workbench.")
    create_app(board, access_token).run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
