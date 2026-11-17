"""Clock-domain bridge for synthetic GPIO IF and faster DMA sampling.

Zero-order hold is physically meaningful for a digital GPIO pin between
source transitions. It is NOT filtering or decimation of real RF captures.
"""
from __future__ import annotations


def held_gpio_samples(source, source_hz: int, dma_hz: int):
    """Yield one DMA observation per tick, holding GPIO until its next edge.

    Source and DMA clocks are independent rational clocks. Both begin at t=0;
    the first source bit is sampled at t=0. Integer arithmetic prevents drift.
    """
    if source_hz <= 0 or dma_hz <= 0:
        raise ValueError('clock rates must be positive')
    source = iter(source)
    try:
        current = int(next(source)) & 1
    except StopIteration:
        return
    phase = 0
    while True:
        yield current
        phase += source_hz
        while phase >= dma_hz:
            phase -= dma_hz
            try:
                current = int(next(source)) & 1
            except StopIteration:
                return
