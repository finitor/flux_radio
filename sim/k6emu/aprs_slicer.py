"""Bell 202 audio to modeled FD6818 plain-FSK zero-crossing samples.

This models the slicer input only, not the FD6818's PLL, FIFO or register timing.
"""
import numpy as np


def audio_to_plain_fsk(audio, audio_hz, sample_hz=4800):
    """Return sign bits sampled on a uniform plain-FSK clock.

    Uses nearest earlier audio sample (zero-order hold). A hardware slicer
    follows crossings and does not use a perfectly uniform clock.
    """
    if audio_hz <= 0 or sample_hz <= 0:
        raise ValueError('invalid clock')
    a = np.asarray(audio)
    if a.ndim != 1:
        raise ValueError('expected mono audio')
    at = np.arange((len(a) * sample_hz) // audio_hz, dtype=np.int64)
    return (a[(at * audio_hz) // sample_hz] >= 0).astype(np.int8)
