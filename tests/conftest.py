"""Shared fixtures for hardware-specific K6 tests."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
for path in (str(ROOT), str(TESTS)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture
def fd6818b_fsk_model():
    from k6_fd6818b_fsk import FD6818BFSKModel

    return FD6818BFSKModel()


@pytest.fixture
def blowfang_xl_packets():
    """Deterministic 128-byte pager packets for framing and reassembly fixtures."""
    from modem.k6_harness import test_packets

    return tuple(bytes(packet) for packet in test_packets("XL"))
