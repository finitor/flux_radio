"""Experimental wideband IF-to-IQ reference pipeline, for simulator validation.

Input is the signed 64-bit-sample population count produced by GP0 DMA;
this is NOT the eventual MCU implementation. Explicitly filter before
reducing sample rate, and preserve the clock-domain distinction.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

from .iq_stream import packetize_iq


def counts_to_iq(counts, *, dma_hz=5_710_000, count_size=64,
                 center_hz=26e6 / 1536, output_hz=9600,
                 cutoff_hz=3600, gain=100.0):
    """Mix, anti-alias filter and resample GP0 population counts to complex IQ.

    Returns (interleaved signed 8-bit IQ, actual_output_rate). The count stream
    represents the mean of count_size GPIO observations, not raw GPIO bytes.
    """
    if dma_hz <= 0 or count_size <= 0 or output_hz <= 0:
        raise ValueError('invalid sampling clock')
    fs = dma_hz / count_size
    if not 0 < cutoff_hz < min(fs, output_hz) / 2:
        raise ValueError('cutoff must be below both Nyquist limits')
    x = np.asarray(counts, dtype=np.float64)
    if x.ndim != 1 or not np.all(np.isfinite(x)):
        raise ValueError('counts must be a finite one-dimensional array')
    if len(x) == 0:
        return b'', output_hz
    # Averages of binary samples: remove the 0.5 DC population baseline.
    centered = (x / count_size - 0.5)
    t = np.arange(len(x)) / fs
    mixed = centered * np.exp(-2j * np.pi * center_hz * t)
    # Zero-phase filtering is an offline reference, not a real-time MCU filter.
    sos = signal.butter(6, cutoff_hz, fs=fs, output='sos')
    filtered = signal.sosfilt(sos, mixed)
    from fractions import Fraction
    ratio = Fraction(output_hz / fs).limit_denominator(100000)
    iq = signal.resample_poly(filtered, ratio.numerator, ratio.denominator)
    values = np.stack((iq.real, iq.imag), axis=-1) * gain
    quantized = np.clip(np.rint(values), -128, 127).astype(np.int8)
    return quantized.tobytes(), fs * ratio.numerator / ratio.denominator


def counts_to_frames(counts, *, frame_samples=128, **kwargs):
    """Return protocol frames from the offline reference front end."""
    iq, rate = counts_to_iq(counts, **kwargs)
    return list(packetize_iq(iq, round(rate), samples_per_frame=frame_samples))
