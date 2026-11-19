"""Opt-in full firmware scheduled probe test, using actual Thumb callbacks."""
import os
import subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize("contention", [False, True])
def test_scheduled_probe(contention):
    image,elf=os.getenv('K6_SIM_SCHEDULED_IMAGE'),os.getenv('K6_SIM_SCHEDULED_ELF')
    if not image or not elf: pytest.skip('requires matching scheduled probe image/ELF')
    u=pytest.importorskip('unicorn')
    from unicorn.arm_const import UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3
    from sim.k6emu.__main__ import K6Board
    board=K6Board(Path(image),collect_mmio=False)
    board.flash_data[0xB000:0xB004]=b'AURA'
    def symbol(name):
        return int(next(r for r in subprocess.check_output(['llvm-nm','-C',elf],text=True).splitlines()
                        if r.endswith(' '+name)).split()[0],16)&~1
    events, polls, tx = [], [], []
    def probe(uc,a,s,d): events.append(uc.reg_read(UC_ARM_REG_R1))
    def poll(uc,a,s,d):
        now=uc.reg_read(UC_ARM_REG_R1)
        if not polls or now>=polls[-1][0]+100:
            polls.append((now,uc.reg_read(UC_ARM_REG_R2),uc.reg_read(UC_ARM_REG_R3)))
    for name,hook in [('vm_probe',probe),('sd_poll',poll),('<aura::device::radio::Radio>::enter_tx',lambda *a:tx.append(1))]:
        addr=symbol(name)
        board.uc.hook_add(u.UC_HOOK_CODE,hook,begin=addr,end=addr)
    def advance(ms):
        end=board.cycles+ms*96000
        while board.cycles<end:
            board.run(8_000_000)
            assert not board.fault,board.fault
    if contention:
        import sys, struct
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from k6_resident_probe import build_probe
        provider=build_probe()
        board.flash_data[0x110000:0x110000+len(provider)]=provider
        arena=symbol('aura::hal::arena::ARENA')
        callback=arena+16+struct.unpack_from('<H',provider,24)[0]
        resident=[]
        board.uc.hook_add(u.UC_HOOK_CODE,lambda uc,a,s,d:resident.append(uc.reg_read(UC_ARM_REG_R1)),begin=callback,end=callback)
        advance(2000)
        def mode():
            board.press_key('SIDE2')
            advance(1200)
            board.press_key('SIDE2',False)
            advance(100)
        for _ in range(5): mode()
        assert resident and resident[-1]==2
        advance(6000)
        assert not events, (events, polls[-60:], resident[-30:])
        assert any(now>=10000 and not available for now,idle,available in polls)
        # First deadline expires under contention, then the next cadence runs.
        mode()
        assert resident[-1]==4
        advance(11000)
        assert b'K6 SCHEDULED skipped' in board.uart_tx
    else:
        advance(25000)
    print('events',events,'polls tail',polls[-20:],flush=True)
    assert events and len(events)%3==0
    assert events==[1,2,4]*(len(events)//3)
    assert not tx
    assert any(p[1] and p[2] for p in polls)
