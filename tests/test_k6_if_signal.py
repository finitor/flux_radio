from sim.k6emu.aprs_signal import ui_frame, hdlc_bits
from sim.k6emu.if_signal import pb1_bits
from sim.k6emu.rx_dma import GpioRxDma, DMA_BASE, GPIOB_IDR


def test_if_bitstream_is_deterministic_and_responds_to_impairments():
    frame = ui_frame('AG7SU', 'APRS', b'>test')
    clean = list(pb1_bits(frame))
    assert len(clean) == len(hdlc_bits(frame)) * 85800 // 1200
    assert clean == list(pb1_bits(frame))
    assert set(clean) == {0, 1}
    assert clean != list(pb1_bits(frame, noise=0.2, seed=12))


def test_if_bits_reach_circular_dma():
    frame = ui_frame('AG7SU', 'APRS', b'>test')
    ram = {}
    dma = GpioRxDma(lambda addr, value: ram.__setitem__(addr, value),
                    pb1_bits(frame), sample_rate=85800, cpu_hz=85800)
    dma.write(DMA_BASE + 0x10, GPIOB_IDR)
    dma.write(DMA_BASE + 0x14, 0x20001000)
    dma.write(DMA_BASE + 0x0c, 128)
    dma.write(DMA_BASE + 0x08, 1 | (1 << 5) | (1 << 7))
    dma.advance(256)
    assert dma.transfers == 256
    assert len(ram) == 128
    assert set(ram.values()) == {0, 2}
