"""Opt-in actual Aura image: discover SPI provider and execute RAM callback."""
import os
import struct
import subprocess
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from k6_resident_probe import build_probe


@pytest.mark.parametrize('finish', ['guard', 'cable'])
def test_whole_firmware_spi_resident_lifecycle(finish):
    image, elf = os.getenv('K6_SIM_VFO_SPI_IMAGE'), os.getenv('K6_SIM_VFO_SPI_ELF')
    if not image or not elf:
        pytest.skip('set K6_SIM_VFO_SPI_IMAGE and K6_SIM_VFO_SPI_ELF (cable-only SPI probe build)')
    u = pytest.importorskip('unicorn')
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1
    from sim.k6emu.__main__ import K6Board
    board = K6Board(Path(image), collect_mmio=False)
    board.flash_data[0xB000:0xB004] = b'AURA'
    provider = build_probe()
    board.flash_data[0x110000:0x110000+len(provider)] = provider
    row = next(row for row in subprocess.check_output(
        ['llvm-nm', '-S', '-C', elf], text=True).splitlines()
        if row.endswith('aura::hal::arena::ARENA'))
    arena, arena_size = (int(v, 16) for v in row.split()[:2])
    callback = arena+16+struct.unpack_from('<H', provider, 24)[0]
    state = arena+((len(provider)+3)&~3)
    events = []
    damage_guard = False
    damage_at = None
    queue_foreground = False
    def hook(uc, address, size, data):
        nonlocal damage_guard, damage_at, queue_foreground
        assert uc.reg_read(UC_ARM_REG_R0) == state
        events.append(uc.reg_read(UC_ARM_REG_R1))
        if damage_guard and events[-1] == 2:
            uc.mem_write(arena+arena_size-4096-4, b'\0'*4)
            damage_guard = False
            damage_at = len(events)
        if queue_foreground and events[-1] == 2:
            uc.mem_write(symbols['aura::app::pager::PENDING_HOST_MENU_AFTER_LIB'], b'\0')
            uc.mem_write(symbols['aura::app::pager::PENDING_LIB_SLOT'], b'\x1f')
            queue_foreground = False
    board.uc.hook_add(u.UC_HOOK_CODE, hook, begin=callback, end=callback)
    from sim.k6emu.resident_audit import ResidentAudit
    audit = ResidentAudit(board, arena=arena, arena_bytes=arena_size,
                          callback=callback, state=state, state_bytes=16) if finish == "guard" else None
    board.run(70_000_000)
    # Exercise ordinary front-panel paths with a live resident provider.
    for key in ('up', 'down', 'menu', 'exit'):
        board.press_key(key, True)
        board.run(4_000_000)
        board.press_key(key, False)
        board.run(4_000_000)
        assert not board.fault, board.fault
    if audit is not None:
        report = audit.report()
        print("Resident UI audit:", report)
        assert not report['lease_violations'], report
        assert report['arena_stack_remaining_bytes'] > 0, report
        # Stop the audit before deliberate corruption and foreground injection.
        for h in audit.hooks:
            board.uc.hook_del(h)
    # UI interactions may stop/restart the provider; record relative counts.
    initial_starts = events.count(1)
    assert events[-1] == 2, events

    assert not board.fault, board.fault
    assert 1 in events and events.count(2) >= 2, events
    assert struct.unpack('<4I', board.uc.mem_read(state,16))[2] == 1
    # Simulated slot removal: native discovery stops the old callback.
    board.flash_data[0x110000:0x114000] = b'\xff'*0x4000
    board.run(8_000_000)
    assert not board.fault, board.fault
    assert events[-1] == 4
    count = len(events)
    board.run(2_000_000)
    assert len(events) == count
    # Reinstall, then corrupt the lease guard: no callback through damaged RAM.
    board.flash_data[0x110000:0x110000+len(provider)] = provider
    board.run(8_000_000)
    assert events.count(1) == initial_starts+1 and events[-1] == 2
    # Queue a real foreground image through Aura's normal deferred launcher.
    # This exercises the stop-before-overwrite boundary, not simulated Python events.
    from modem import k6mod
    foreground = k6mod.image(b'\x00\x20\x70\x47', 0, 2, None, lib=31)
    board.flash_data[0x18C000:0x18C000+len(foreground)] = foreground
    symbols = {r.split()[-1]: int(r.split()[0], 16) for r in subprocess.check_output(
        ['llvm-nm', '-C', elf], text=True).splitlines() if len(r.split()) == 3}
    # Queue at the metadata callback boundary, before next loop's ownership check.
    queue_foreground = True
    starts, stops = events.count(1), events.count(4)
    board.run(12_000_000)
    assert not board.fault, board.fault
    assert events.count(4) == stops+1 and events.count(1) == starts+1
    assert events[-1] == 2
    if finish == 'cable':
        board.inject_uart_rx(b'PROGRAMBF-K6BLWF')
        board.run(8_000_000)
        assert not board.fault, board.fault
        assert events[-1] == 4
        count = len(events)
        board.run(2_000_000)
        assert len(events) == count
        return
    # Inject during a known callback, so an arbitrary instruction cutoff cannot
    # land after the guard check but before the next callback's entry hook.
    damage_guard = True
    board.run(8_000_000)
    assert not board.fault, board.fault
    assert damage_at is not None and not damage_guard
    assert len(events) == damage_at, events[damage_at:]
    board.run(2_000_000)
    assert len(events) == damage_at
