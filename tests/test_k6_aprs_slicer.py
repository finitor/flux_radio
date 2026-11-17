import numpy as np
import pytest
from modem import aprs
from sim.k6emu.aprs_slicer import audio_to_following_fsk, audio_to_plain_fsk


def test_slicer_preserves_tone_crossing_statistics():
    fs = 48000
    t = np.arange(fs) / fs
    mark = audio_to_plain_fsk(np.sin(2 * np.pi * 1200 * t), fs)
    space = audio_to_plain_fsk(np.sin(2 * np.pi * 2200 * t), fs)
    assert len(mark) == len(space) == 4800
    assert 2200 < np.count_nonzero(np.diff(mark)) < 2500
    assert 4200 < np.count_nonzero(np.diff(space)) < 4500


@pytest.mark.xfail(strict=True, reason="uniform 4800 Hz sampling cannot reproduce FD6818 transition-following clock")
def test_audio_to_slicer_to_ax25_frame():
    frame = aprs.frame('AG7SU-7', 'APRS', '>slicer regression')
    bits = aprs.hdlc_bits([frame], pre_flags=40)
    audio = aprs.afsk(bits, fs=48000)
    sliced = audio_to_plain_fsk(audio, 48000)
    line = aprs.dfsk_line(sliced)
    decoded = [x[3] for x in aprs.hdlc_spans(line) if x[2]]
    assert frame in decoded, [aprs.describe(f) for f in decoded]


def test_following_slicer_recovers_position_frame():
    frame = aprs.frame("AG7SU-7", "APRS", "!4538.00N/12222.00W>sim")
    audio = aprs.afsk(aprs.hdlc_bits([frame], pre_flags=40), fs=48000)
    samples = audio_to_following_fsk(audio, 48000)
    line = aprs.dfsk_line(np.r_[samples, np.zeros(40, dtype=np.int8)])
    assert [f for _, _, ok, f in aprs.hdlc_spans(line) if ok] == [frame]
