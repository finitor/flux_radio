"""Experimental AFSK -> one-bit GP0/PB1 IF fixture.

This is a deliberately simplified FM discriminator model, not a calibrated
FD6818B transfer function. Its output is suitable for exercising the DMA
plumbing, but must not be treated as evidence of RF decoder performance.
"""
from __future__ import annotations
import math
from .aprs_signal import afsk


def pb1_bits(frame: bytes, *, sample_rate: int = 85800, deviation_hz: float = 3000,
             if_hz: float = 12000, noise: float = 0.0, gain: float = 1.0,
             clip: float = 1.0, emphasis_db: float = 0.0, seed: int = 0,
             frequency_offset: float = 0.0):
    """Quantize a frequency-modulated IF carrier to PB1 logic levels."""
    audio = afsk(frame, sample_rate=sample_rate, noise=noise, gain=gain,
                 clip=clip, emphasis_db=emphasis_db, seed=seed,
                 frequency_offset=frequency_offset)
    phase = 0.0
    for value in audio:
        phase = (phase + 2 * math.pi * (if_hz + deviation_hz * value) / sample_rate) % (2 * math.pi)
        yield int(math.sin(phase) >= 0)
