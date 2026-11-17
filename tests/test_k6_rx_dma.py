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


def test_measured_dma_clock_separate_from_if_sample_clock():
    from sim.k6emu.rx_dma import MEASURED_FREE_RUNNING_HZ
    assert MEASURED_FREE_RUNNING_HZ == 5_710_000
    ram = {}
    dma = GpioRxDma.measured_free_running(lambda a, v: ram.__setitem__(a, v),
                                          samples=iter([1] * 12000))
    dma.write(DMA_BASE + 0x10, GPIOB_IDR)
    dma.write(DMA_BASE + 0x14, 0x20001000)
    dma.write(DMA_BASE + 0x0c, 1024)
    dma.write(DMA_BASE + 0x08, 1 | (1 << 5) | (1 << 7))
    dma.advance(192000)  # 2 ms at 96 MHz
    assert dma.transfers == 11420
    assert dma.read(DMA_BASE + 0x0c) == 1024 - (11420 % 1024)
    assert dma.elapsed_cycles == 192000

def test_dma_fractional_cycle_accumulation():
    ram = {}
    dma = GpioRxDma(lambda a, v: ram.__setitem__(a, v), [1] * 10, 3, 10)
    dma.write(DMA_BASE + 0x10, GPIOB_IDR)
    dma.write(DMA_BASE + 0x14, 0x20001000)
    dma.write(DMA_BASE + 0x0c, 10)
    dma.write(DMA_BASE + 0x08, 1 | (1 << 7))
    for _ in range(10):
        dma.advance(1)
    assert dma.transfers == 3
