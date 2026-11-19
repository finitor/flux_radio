"""Opt-in whole-image keypad and PTT checks for the experimental selector."""
import os
import struct
import subprocess
from pathlib import Path
import pytest

def test_selector_keys():
    image, elf = os.getenv('K6_SIM_VFO_SELECTOR_IMAGE'), os.getenv('K6_SIM_VFO_SELECTOR_ELF')
    if not image or not elf:
        pytest.skip('set matching selector image and ELF')
    u = pytest.importorskip('unicorn')
    from unicorn.arm_const import UC_ARM_REG_R1
    from sim.k6emu.__main__ import K6Board
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from k6_resident_probe import build_probe
    board = K6Board(Path(image), collect_mmio=False)
    board.flash_data[0xB000:0xB004] = b'AURA'
    provider = build_probe()
    board.flash_data[0x110000:0x110000+len(provider)] = provider
    rows = subprocess.check_output(['llvm-nm','-S','-C',elf],text=True).splitlines()
    arena = int(next(r for r in rows if r.endswith('aura::hal::arena::ARENA')).split()[0],16)
    tx = int(next(r for r in rows if r.endswith('<aura::device::radio::Radio>::enter_tx')).split()[0],16)&~1
    callback=arena+16+struct.unpack_from('<H',provider,24)[0]
    events, tx_calls = [], []
    board.uc.hook_add(u.UC_HOOK_CODE,lambda uc,a,s,d: events.append(uc.reg_read(UC_ARM_REG_R1)),begin=callback,end=callback)
    board.uc.hook_add(u.UC_HOOK_CODE,lambda *args: tx_calls.append(1),begin=tx,end=tx)
    def advance(n):
        board.run(n)
        assert not board.fault, board.fault
    def hold(key, ms):
        board.press_key(key)
        end=board.cycles+ms*96000
        while board.cycles<end: advance(2_000_000)
        board.press_key(key,False)
        advance(4_000_000)
    advance(70_000_000)
    assert not events
    for i in range(5):
        hold('SIDE2',1200)
        print('MODE',i+1,'events',len(events),flush=True)
        if i<4: assert not events
    assert events.count(1)==1 and events[-1]==2
    board.set_gpio('A',10,0)
    advance(8_000_000)
    board.set_gpio('A',10,1)
    advance(4_000_000)
    assert not tx_calls, tx_calls
    hold('AB',150)
    assert events[-1]==4,events[-10:]
    hold('AB',150)
    assert events.count(1)>=2 and events[-1]==2
    hold('SIDE2',1200)
    assert events[-1]==4
