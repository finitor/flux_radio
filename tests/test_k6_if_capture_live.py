"""Run actual IF CAPTURE module on Cortex-M0 against generated APRS IF."""
import itertools
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from sim.k6emu.aprs_signal import ui_frame
from sim.k6emu.if_signal import pb1_bits
from sim.k6emu.if_capture import parse_capture


def test_if_capture_module_on_m0_matches_aprs_if_samples():
    pytest.importorskip('unicorn')
    from modem import k6mod
    import k6_live_emu as le

    code, entry = k6mod.build(str(ROOT / 'c/k6/mod/ifcapture.c'))
    assert len(code) < 4096
    frame = ui_frame('AG7SU', 'APRS', b'>sim test', 7)
    stream = np.fromiter((int(bit) * 2 for bit in itertools.islice(pb1_bits(frame), 20000)),
                         dtype=np.uint8)
    emulator = le.Emu(code, entry, stream, 0, 85800, cpi=1.5, max_s=1.0, scratch=4096)
    result = emulator.run()
    assert result is not None
    assert result[0] == 8192, emulator.said
    samples, meta = parse_capture('\n'.join(emulator.said))
    assert meta['bits'] == 8192
    offset = emulator.dma_s0
    assert samples == (stream[offset:offset + len(samples)] // 2).tolist()
    assert emulator.writes[0x34][-1] == 0  # GP0 route restored
