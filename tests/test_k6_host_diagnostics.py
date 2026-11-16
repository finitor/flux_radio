"""Small CPU fixtures for the host-contract diagnostic machinery."""
import struct

import pytest

pytest.importorskip('unicorn')
from sim.k6emu.__main__ import K6Board, APP_BASE, RAM_BASE, RAM_BYTES


def board_for(tmp_path, code):
    image = tmp_path / 'fixture.bin'
    image.write_bytes(struct.pack('<II', RAM_BASE + RAM_BYTES, APP_BASE + 9) + code)
    return K6Board(image)


def test_invalid_read_records_fault_and_does_not_resume(tmp_path):
    board = board_for(tmp_path, bytes.fromhex('0868fee7'))  # ldr r0,[r1]; b .
    board.uc.reg_write(board.arm.UC_ARM_REG_R1, 0x30000000)
    board.run(4, 1)
    assert board.fault['kind'] == 'invalid_memory'
    assert board.fault['address'] == '0x30000000'
    assert board.fault['registers']['pc'] == f'0x{APP_BASE + 8:08x}'
    registers = board.cpu_registers()
    board.run(10)
    assert board.cpu_registers() == registers


def test_write_watch_records_actual_cpu_store(tmp_path):
    board = board_for(tmp_path, bytes.fromhex('0860fee7'))  # str r0,[r1]; b .
    address = RAM_BASE + 0x1800
    board.uc.reg_write(board.arm.UC_ARM_REG_R0, 0x12345678)
    board.uc.reg_write(board.arm.UC_ARM_REG_R1, address)
    board.watch_write(address, 4)
    board.run(2, 1)
    assert len(board.memory_writes) == 1
    event = board.memory_writes[0]
    assert event['value'] == '0x12345678'
    assert event['pc'] == f'0x{APP_BASE + 8:08x}'
    assert event['sp'] == f'0x{RAM_BASE + RAM_BYTES:08x}'
    assert board.fault is None
    for start, size in ((address, 0), (RAM_BASE - 1, 4), (RAM_BASE + RAM_BYTES - 1, 4)):
        with pytest.raises(ValueError):
            board.watch_write(start, size)
