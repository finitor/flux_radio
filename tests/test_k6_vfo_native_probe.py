"""Opt-in whole-image test for the experimental native VFO lifecycle probe."""
import os
import subprocess
from pathlib import Path
import pytest

def test_native_probe_ticks(tmp_path):
    image = os.environ.get("K6_SIM_VFO_IMAGE")
    elf = os.environ.get("K6_SIM_VFO_ELF")
    if not image or not elf:
        pytest.skip("set K6_SIM_VFO_IMAGE and K6_SIM_VFO_ELF")
    u = pytest.importorskip("unicorn")
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1
    from sim.k6emu.__main__ import K6Board
    board = K6Board(Path(image), collect_mmio=False)
    board.flash_data[0xB000:0xB004] = b"AURA"
    syms = {line.split()[-1]: int(line.split()[0], 16) & ~1
            for line in subprocess.check_output(["llvm-nm", "--defined-only", elf], text=True).splitlines()
            if line.split()[-1] == "vm_probe"}
    arena_row = next(row for row in subprocess.check_output(
        ["llvm-nm", "-S", "-C", elf], text=True).splitlines()
        if row.endswith("aura::hal::arena::ARENA"))
    arena, size = (int(v, 16) for v in arena_row.split()[:2])
    events = []
    pointers = []
    def callback(uc, address, size, data):
        events.append(uc.reg_read(UC_ARM_REG_R1))
        pointers.append(uc.reg_read(UC_ARM_REG_R0))
    board.uc.hook_add(u.UC_HOOK_CODE, callback, begin=syms["vm_probe"], end=syms["vm_probe"])
    board.run(70_000_000)
    assert not board.fault, board.fault
    assert 1 in events and events.count(2) >= 2, events
    assert set(pointers) == {arena}
    # Corrupt the stack boundary guard while resident; the probe must latch off.
    guard = arena + size - 4096 - 4
    assert bytes(board.uc.mem_read(guard, 4)) == bytes.fromhex("474f4656")
    board.uc.mem_write(guard, b"\0" * 4)
    count = len(events)
    board.run(8_000_000)
    assert not board.fault, board.fault
    assert len(events) == count
