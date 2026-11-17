"""Opt-in cable regression against the compiled firmware in Unicorn."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import k6_pack_install

import k6_install
from k6_build_identity import image_build_id
from k6_install import CABLE_HANDSHAKE, CMD_CAPS, CPS_HEADER, Cable, InstallError, k6mod

TEST_KEY = bytes(range(16))


class SimulatedSerial:
    """Advance the simulated CPU while the real cable client waits for bytes."""

    def __init__(self, board):
        self.board = board
        self.offset = 0
        self.closed = False
        self.requests = []

    def reset_input_buffer(self):
        self.offset = len(self.board.uart_tx)

    def write(self, data):
        self.requests.append(bytes(data))
        self.board.inject_uart_rx(data)
        return len(data)

    def read(self, size):
        if self.offset == len(self.board.uart_tx):
            self.advance(65536)
        data = bytes(self.board.uart_tx[self.offset:self.offset + size])
        self.offset += len(data)
        return data

    def close(self):
        self.closed = True

    def advance(self, instructions):
        self.board.run(instructions)
        assert not self.board.fault, self.board.fault

    def monotonic(self):
        return self.board.cycles / 96_000_000

    def sleep(self, seconds):
        self.advance(round(seconds * 96_000_000 / self.board.cpi))


@pytest.fixture
def simulated_radio(tmp_path, monkeypatch):
    def start(image):
        pytest.importorskip("unicorn")
        from sim.k6emu.__main__ import K6Board

        keyed = tmp_path / "keyed-firmware.bin"
        keyed.write_bytes(k6mod.key_image(image, TEST_KEY))
        board = K6Board(keyed, collect_mmio=False)
        # An erased chip with Aura's first-boot marker is sufficient for boot.
        board.flash_data[0xB000:0xB004] = b"AURA"
        port = SimulatedSerial(board)
        port.advance(70_000_000)

        # Both sides use virtual time even when Unicorn runs slower than the radio.
        monkeypatch.setattr(k6_install, "time", SimpleNamespace(
            monotonic=port.monotonic, sleep=port.sleep,
        ))
        return port
    return start


def test_compiled_base_cable(simulated_radio):
    image_path = os.environ.get("K6_SIM_BASE_IMAGE")
    if not image_path:
        pytest.skip("set K6_SIM_BASE_IMAGE to a Base firmware.bin from tools/k6.py matrix --build")
    image = Path(image_path).read_bytes()
    port = simulated_radio(image)
    before = bytes(port.board.flash_data)
    cable = Cable(port, log=lambda _: None)
    assert cable.handshake(CABLE_HANDSHAKE, wait=3.0)

    reported = cable.capabilities()
    assert reported["format"] == 2
    assert reported["build_id"] == image_build_id(image)
    assert reported["module_loader"]
    assert not reported["scanner"]
    assert not reported["fsk_rx"]
    assert cable.authenticated_capabilities(TEST_KEY) == reported
    with pytest.raises(InstallError, match="expected module key"):
        cable.authenticated_capabilities(bytes(reversed(TEST_KEY)))

    assert sum(req.startswith(bytes([CPS_HEADER, CMD_CAPS])) for req in port.requests) == 3
    assert bytes(port.board.flash_data) == before


def test_compiled_scan_aprs_pack_preflight(simulated_radio, tmp_path, monkeypatch):
    pack_path = os.environ.get("K6_SIM_SCAN_APRS_PACK")
    if not pack_path:
        pytest.skip("set K6_SIM_SCAN_APRS_PACK to the output of tools/k6.py build scan aprs")
    pack = Path(pack_path)
    port = simulated_radio((pack / "firmware.bin").read_bytes())
    before = bytes(port.board.flash_data)
    key_file = tmp_path / "synthetic.key"
    key_file.write_text(TEST_KEY.hex())
    monkeypatch.setattr(k6_install, "open_port", lambda _: port)
    spec = json.loads(k6_pack_install.DEFAULT.read_text())

    report = k6_pack_install.radio_preflight(pack, spec, "simulated", key_file)

    assert set(report["packs"]) == {"base", "scan", "aprs"}
    assert report["build_id_match"]
    assert report["capabilities_match"]
    assert report["capability_report_authenticated"]
    assert report["key_possession_verified"]
    assert port.closed
    assert bytes(port.board.flash_data) == before
