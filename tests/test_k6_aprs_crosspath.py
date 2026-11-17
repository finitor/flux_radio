"""Cross-check the APRS fixture, independent audio decoder and K6 IF capture.

The IF capture path is NOT wired to the on-radio APRS decoder yet. This
regression deliberately does not claim an end-to-end RF packet decode.
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from modem import aprs
from sim.k6emu.aprs_signal import ui_frame, afsk
from sim.k6emu.if_signal import pb1_bits
from sim.k6emu.if_capture import parse_capture

FRAME = ui_frame('AG7SU', 'APRS', b'>crosspath validation', 7)


def test_generator_frame_matches_independent_ax25_builder():
    assert FRAME == aprs.frame('AG7SU-7', 'APRS', '>crosspath validation')


def test_generated_bell202_audio_decodes_exact_frame():
    samples = np.asarray(afsk(FRAME, sample_rate=aprs.FS), dtype=np.float64)
    decoded = [frame for _, frame in aprs.decode_any(samples, aprs.FS)]
    assert FRAME in decoded, [aprs.describe(f) for f in decoded]


def test_same_frame_enters_real_m0_if_capture_module():
    pytest.importorskip('unicorn')
    from modem import k6mod
    import k6_live_emu as le
    code, entry = k6mod.build(str(ROOT / 'c/k6/mod/ifcapture.c'))
    signal = np.fromiter((2 * b for b in itertools.islice(pb1_bits(FRAME), 20000)),
                         dtype=np.uint8)
    emu = le.Emu(code, entry, signal, 0, 85800, cpi=1.5,
                 max_s=1.0, scratch=4096)
    assert emu.run() is not None
    captured, metadata = parse_capture('\n'.join(emu.said))
    assert metadata['bits'] == 8192
    assert captured == (signal[emu.dma_s0:emu.dma_s0 + 8192] // 2).tolist()
