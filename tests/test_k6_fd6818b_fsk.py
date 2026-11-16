"""FD6818B FSK port fixtures.

The register/FIFO tests below validate the test model and expected Aura-driver
transaction. The XL packet vectors come from the real Blowfang pager packer;
the 16-byte chunking is a proposed software framing layer, not yet an on-air
FD6818B capture. Physical RX/TX behavior still needs a bench run.
"""
import pytest

from k6_fd6818b_fsk import (  # noqa: E402
    CHIP_ID,
    FSK_BAUD_1200,
    FSK_CONTROL_BASE,
    FSK_LEN_VALUE,
    FSK_RX_ENABLE,
    FSK_RX_FIFO_CLEAR,
    FSK_RX_MODE,
    FSK_WORDS_VALUE,
    REG_FSK_BAUD,
    REG_FSK_CONTROL,
    REG_FSK_LEN,
    REG_FSK_PREAMBLE,
    REG_FSK_TONE_GAIN,
    REG_FSK_WORDS,
    REG_STATUS,
    REG_WORK_MODE,
    bytes_from_words,
    words_from_bytes,
)
def test_fd6818b_rx_setup_matches_aura_reference_transaction(fd6818b_fsk_model):
    radio = fd6818b_fsk_model
    radio.arm_1200_rx()
    assert CHIP_ID == 0x4829
    assert radio.writes == [
        (REG_FSK_PREAMBLE, 0x00C1),
        (REG_FSK_TONE_GAIN, 0x00E0),
        (REG_FSK_BAUD, FSK_BAUD_1200),
        (REG_FSK_WORDS, FSK_WORDS_VALUE),
        (REG_FSK_LEN, FSK_LEN_VALUE),
        (REG_FSK_CONTROL, FSK_CONTROL_BASE | FSK_RX_FIFO_CLEAR),
        (REG_FSK_CONTROL, FSK_CONTROL_BASE | FSK_RX_ENABLE),
        (REG_WORK_MODE, FSK_RX_MODE),
    ]
    assert radio.rx_armed


def test_fixed_length_fifo_frame_and_irq_ack(fd6818b_fsk_model):
    radio = fd6818b_fsk_model
    radio.arm_1200_rx()
    expected = (0x0123, 0x4567, 0x89AB, 0xCDEF, 0x1357, 0x2468, 0xACE0, 0xFDB9)
    radio.inject_rx_frame(expected)
    assert radio.read(REG_STATUS) & 1
    assert radio.read_frame() == expected
    assert not (radio.read(REG_STATUS) & 1)


def test_fixed_length_fifo_tx_transaction(fd6818b_fsk_model):
    words = tuple(range(0x100, 0x108))
    assert fd6818b_fsk_model.send_frame(words)
    assert fd6818b_fsk_model.tx_frames == [words]
    assert fd6818b_fsk_model.read(REG_WORK_MODE) == 0
    assert fd6818b_fsk_model.read(REG_FSK_CONTROL) == FSK_CONTROL_BASE
    assert fd6818b_fsk_model.writes[:6] == [
        (REG_WORK_MODE, 0x8000),
        (REG_FSK_PREAMBLE, 0x00C1),
        (REG_FSK_TONE_GAIN, 0x00E0),
        (REG_FSK_BAUD, FSK_BAUD_1200),
        (REG_FSK_WORDS, FSK_WORDS_VALUE),
        (REG_FSK_LEN, FSK_LEN_VALUE),
    ]


def test_rx_stop_returns_work_mode_and_fsk_tone_registers_to_idle(fd6818b_fsk_model):
    radio = fd6818b_fsk_model
    radio.arm_1200_rx()
    radio.stop_rx()
    assert radio.writes[-5:] == [
        (REG_FSK_CONTROL, FSK_CONTROL_BASE),
        (REG_WORK_MODE, 0),
        (0x02, 0),
        (REG_FSK_TONE_GAIN, 0),
        (REG_FSK_PREAMBLE, 0),
    ]
    assert radio.read(REG_WORK_MODE) == 0
    assert radio.read(REG_FSK_TONE_GAIN) == 0
    assert radio.read(REG_FSK_PREAMBLE) == 0


@pytest.mark.parametrize("byteorder", ["big", "little"])
def test_blowfang_xl_packet_fixture_splits_into_eight_b_fifo_frames(
        fd6818b_fsk_model, blowfang_xl_packets, byteorder):
    """Keep both wire-order hypotheses as fixtures until the first radio capture settles it."""
    radio = fd6818b_fsk_model
    radio.arm_1200_rx()
    for packet in blowfang_xl_packets:
        assert len(packet) == 128
        chunks = [packet[i:i + 16] for i in range(0, 128, 16)]
        recovered = bytearray()
        for chunk in chunks:
            radio.inject_rx_frame(words_from_bytes(chunk, byteorder))
            recovered.extend(bytes_from_words(radio.read_frame(), byteorder))
        assert bytes(recovered) == packet
        assert len(chunks) == 8
