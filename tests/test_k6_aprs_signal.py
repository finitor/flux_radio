from sim.k6emu.aprs_signal import address, afsk, crc16_x25, hdlc_bits, ui_frame


def test_crc_known_vector():
    assert crc16_x25(b'123456789') == 0x906e


def test_ui_frame_addresses_and_fcs():
    frame = ui_frame('AG7SU', 'APRS', b'!4500.00N/12200.00W-Test', 7)
    assert frame[:7] == address('APRS')
    assert frame[7:14] == address('AG7SU', 7, True)
    assert frame[14:16] == b'\x03\xf0'
    assert crc16_x25(frame) == 0x0f47


def test_waveform_deterministic_and_impaired():
    frame = ui_frame('AG7SU', 'APRS', b'>test')
    clean = afsk(frame)
    assert len(clean) == len(hdlc_bits(frame)) * 8
    assert clean == afsk(frame)
    noisy = afsk(frame, noise=0.1, seed=12, gain=4, clip=0.5, emphasis_db=6)
    assert noisy == afsk(frame, noise=0.1, seed=12, gain=4, clip=0.5, emphasis_db=6)
    assert noisy != clean
    assert max(map(abs, noisy)) <= 0.5
