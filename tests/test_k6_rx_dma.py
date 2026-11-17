from sim.k6emu.rx_dma import DMA_BASE, GPIOB_IDR, GpioRxDma


def test_circular_gpio_capture_and_flags():
    ram = {}
    dma = GpioRxDma(lambda addr, value: ram.__setitem__(addr, value),
                    samples=[0, 1, 1, 0, 1, 0], sample_rate=1000, cpu_hz=1000)
    dma.write(DMA_BASE + 0x10, GPIOB_IDR)
    dma.write(DMA_BASE + 0x14, 0x20001000)
    dma.write(DMA_BASE + 0x0c, 4)
    dma.write(DMA_BASE + 0x08, 1 | (1 << 5) | (1 << 7))
    dma.advance(3)
    assert dma.read(DMA_BASE + 0x0c) == 1
    assert dma.read(DMA_BASE) & 4
    dma.advance(3)
    assert dma.read(DMA_BASE + 0x0c) == 2
    assert [ram[0x20001000 + i] for i in range(4)] == [2, 0, 2, 0]
    assert dma.transfers == 6


def test_no_capture_when_disabled_or_wrong_source():
    ram = {}
    dma = GpioRxDma(lambda a, v: ram.__setitem__(a, v), [1, 1], 100, 100)
    dma.write(DMA_BASE + 0x0c, 2)
    dma.write(DMA_BASE + 0x08, 1)
    dma.advance(2)
    assert not ram
