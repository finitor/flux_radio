from itertools import islice
from sim.k6emu.if_resample import held_gpio_samples
from sim.k6emu.rx_dma import MEASURED_FREE_RUNNING_HZ


def test_real_clock_rate_is_independent_of_gpio_waveform():
    src = [0, 1, 0, 1, 0, 1]
    actual = list(held_gpio_samples(src, 85800, MEASURED_FREE_RUNNING_HZ))
    assert len(actual) > len(src) * 60
    assert actual[:60] == [0] * 60
    assert actual[70] == 1


def test_emulator_mode_api_available():
    import inspect
    from sim.k6emu.__main__ import K6Board
    assert 'dma_mode' in inspect.signature(K6Board.attach_rx_bits).parameters
