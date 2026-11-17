import pytest
from sim.k6emu.iq_stream import encode_frame, decode_frame, stream_gaps


def test_roundtrip_and_crc():
    data = bytes([0, 255, 127, 128] * 15)
    frame = encode_frame(data, sequence=42, end_tick=960000, rate_hz=9600)
    parsed = decode_frame(frame)
    assert parsed['samples'] == data
    assert parsed['rate_hz'] == 9600
    assert parsed['end_tick'] == 960000
    with pytest.raises(ValueError, match='CRC'):
        decode_frame(frame[:-5] + bytes([frame[-5] ^ 1]) + frame[-4:])


def test_gaps_and_wrap():
    frames = [{'sequence': n} for n in (0xfffffffe, 0xffffffff, 1, 3)]
    assert list(stream_gaps(frames)) == [0, 0, 1, 1]


def test_reject_bad_inputs():
    with pytest.raises(ValueError):
        encode_frame(b'\0', sequence=0, end_tick=0, rate_hz=9600)
    with pytest.raises(ValueError):
        encode_frame(b'\0\0' * 257, sequence=0, end_tick=0, rate_hz=9600)
    with pytest.raises(ValueError):
        decode_frame(b'bad')


def test_packetize_simulated_iq_preserves_samples_and_clock():
    from sim.k6emu.iq_stream import packetize_iq
    iq = bytes((i % 256 for i in range(1000)))
    packets = [decode_frame(f) for f in packetize_iq(iq, 9600, samples_per_frame=64)]
    assert b''.join(p['samples'] for p in packets) == iq
    assert len(packets) == 8
    assert packets[0]['end_tick'] == 630000
    assert packets[-1]['end_tick'] == 4990000
    assert list(stream_gaps(packets)) == [0] * len(packets)
