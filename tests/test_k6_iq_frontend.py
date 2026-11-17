import numpy as np
import pytest
from sim.k6emu.iq_frontend import counts_to_iq, counts_to_frames
from sim.k6emu.iq_stream import decode_frame, stream_gaps


def test_mixed_tone_survives_and_out_of_band_is_rejected():
    fs = 5710000 / 64
    t = np.arange(int(fs * .25)) / fs
    center = 26e6 / 1536
    # Idealized population counts: a tone at +1200 Hz, plus one outside passband.
    counts = 32 + 11 * np.cos(2 * np.pi * (center + 1200) * t) + 8 * np.cos(2 * np.pi * (center + 6500) * t)
    iq, rate = counts_to_iq(counts, gain=14)
    z = np.frombuffer(iq, dtype=np.int8).reshape(-1, 2).astype(float)
    complex_iq = z[:, 0] + 1j * z[:, 1]
    fft = np.fft.fft(complex_iq[400:2000])
    freq = np.fft.fftfreq(len(fft), 1 / rate)
    assert abs(freq[np.argmax(abs(fft))] - 1200) < 15
    assert max(abs(fft[(freq > 1800) & (freq < 3500)])) < max(abs(fft)) / 5


def test_reference_stream_frames_reconstruct():
    fs = 5710000 / 64
    t = np.arange(int(fs * .1)) / fs
    counts = 32 + 12 * np.cos(2 * np.pi * (26e6 / 1536 + 2200) * t)
    frames = [decode_frame(f) for f in counts_to_frames(counts)]
    assert len(frames) > 1
    assert all(x['rate_hz'] == 9600 for x in frames)
    assert list(stream_gaps(frames)) == [0] * len(frames)
    assert len(b''.join(x['samples'] for x in frames)) > 1000


def test_invalid_cutoff_rejected():
    with pytest.raises(ValueError):
        counts_to_iq([32, 33], cutoff_hz=5000)
