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


def audio_to_following_fsk(audio, audio_hz):
    """Model FD6818 plain-FSK samples by following Bell 202 zero crossings.

    A mark half-cycle contributes two equal samples and a space half-cycle
    contributes one. This is a clean-signal model; it omits analog filtering
    and the chip's clock acquisition and noise behavior.
    """
    if audio_hz < 8800:
        raise ValueError("audio clock must be at least 8800 Hz")
    a = np.asarray(audio)
    if a.ndim != 1:
        raise ValueError("expected mono audio")
    levels = a >= 0
    edges = np.flatnonzero(levels[1:] != levels[:-1]) + 1
    mark_threshold = audio_hz * (1 / 2400 + 1 / 4400) / 2
    return np.repeat(levels[edges[:-1]], 1 + (np.diff(edges) >= mark_threshold)).astype(np.int8)
