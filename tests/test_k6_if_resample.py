from itertools import islice

import pytest

from sim.k6emu.if_resample import held_gpio_samples
from sim.k6emu.rx_dma import DMA_BASE, GPIOB_IDR, GpioRxDma, MEASURED_FREE_RUNNING_HZ


def test_exact_integer_ratio_holds_each_gpio_value():
    assert list(held_gpio_samples([0, 1, 0], 2, 8)) == [0] * 4 + [1] * 4 + [0] * 4


def test_noninteger_clocks_no_phase_drift():
    samples = list(held_gpio_samples([i & 1 for i in range(100)], 3, 10))
    assert len(samples) == 334  # t=0 through t=33.3 inclusive
    assert samples[0] == 0
    assert samples[4] == 1


def test_measured_dma_reads_held_gpio_without_accelerating_waveform():
    ram = {}
    source = [0, 1, 0, 1, 1, 0]
    dma = GpioRxDma.measured_free_running(
        lambda a, v: ram.__setitem__(a, v),
        held_gpio_samples(source, 85800, MEASURED_FREE_RUNNING_HZ))
    dma.write(DMA_BASE + 0x10, GPIOB_IDR)
    dma.write(DMA_BASE + 0x14, 0x20001000)
    dma.write(DMA_BASE + 0x0c, 512)
    dma.write(DMA_BASE + 0x08, 1 | (1 << 7))
    dma.advance(96000)  # 1 ms, exhaust source before this
    assert dma.exhausted
    values = [ram[0x20001000 + i] >> 1 for i in range(dma.transfers)]
    assert values[:66] == [0] * 66
    assert values[67:133] == [1] * 66
    assert len(values) > 300


def test_invalid_rates():
    with pytest.raises(ValueError):
        list(held_gpio_samples([1], 0, 100))
