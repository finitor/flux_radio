import pytest
from sim.k6emu.if_capture import parse_capture
from sim.k6emu.rx_dma import GpioRxDma, DMA_BASE, GPIOB_IDR


def test_serial_capture_replay_to_dma():
    bits, meta = parse_capture('noise\nifcap v1 bits=00010 ticks=000123\nif 4d02\nifcap end\n')
    assert bits == [1, 0, 1, 1, 0, 0, 1, 0, 0, 1]
    assert meta['rate_verified'] is False
    ram = {}
    dma = GpioRxDma(lambda a, v: ram.__setitem__(a, v), bits, 100, 100)
    dma.write(DMA_BASE + 0x10, GPIOB_IDR)
    dma.write(DMA_BASE + 0x14, 0x20001000)
    dma.write(DMA_BASE + 0x0c, 10)
    dma.write(DMA_BASE + 0x08, 1 | (1 << 7))
    dma.advance(10)
    assert [ram[0x20001000 + i] >> 1 for i in range(10)] == bits


def test_incomplete_capture_rejected():
    with pytest.raises(ValueError):
        parse_capture('ifcap v1 bits=00010 ticks=000123\nif 4d02\n')
