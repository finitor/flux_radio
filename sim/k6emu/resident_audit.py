"""Observed RAM-write and stack bounds while a native resident callback owns RAM.

This records executed emulator paths, not static worst-case or hardware timing.
It does not alter emulated memory or synthesize callback events.
"""
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_PC


class ResidentAudit:
    def __init__(self, board, *, arena, arena_bytes, callback, state, state_bytes,
                 stack_reserve=4096, ram_end=0x20006000):
        self.arena = arena
        self.end = arena + arena_bytes
        self.guard = self.end - stack_reserve - 4
        self.state = state
        self.state_end = state + state_bytes
        self.ram_end = ram_end
        self.active = False
        self.events = {}
        self.min_main_sp = ram_end
        self.min_arena_sp = self.end
        self.min_arena_write = self.end
        self.violations = {}
        self.writes = 0
        self.hooks = [
            board.uc.hook_add(UC_HOOK_CODE, self._callback, begin=callback, end=callback),
            board.uc.hook_add(UC_HOOK_MEM_WRITE, self._write, begin=0x20000000, end=ram_end-1),
        ]

    def _callback(self, uc, address, size, data):
        event = uc.reg_read(UC_ARM_REG_R1)
        self.events[event] = self.events.get(event, 0) + 1
        if event == 1:
            self.active = True
        elif event == 4:
            self.active = False

    def _write(self, uc, access, address, size, value, data):
        if not self.active:
            return
        self.writes += 1
        sp = uc.reg_read(UC_ARM_REG_SP)
        if self.arena <= sp <= self.end:
            self.min_arena_sp = min(self.min_arena_sp, sp)
            if self.arena <= address < self.end:
                self.min_arena_write = min(self.min_arena_write, address)
        elif self.end < sp <= self.ram_end:
            self.min_main_sp = min(self.min_main_sp, sp)
        # Any native writer entering the proposed image/state lease is relevant,
        # including writes to unused space that a larger resident could occupy.
        if address < self.guard+4 and address+size > self.arena:
            if not (self.state <= address and address+size <= self.state_end):
                key = (address, size, uc.reg_read(UC_ARM_REG_PC))
                self.violations[key] = self.violations.get(key, 0) + 1

    def report(self):
        low = min(self.min_arena_sp, self.min_arena_write)
        return {
            'callback_events': self.events,
            'observed_writes_while_active': self.writes,
            'arena_stack_depth_bytes': self.end-low,
            'arena_stack_remaining_bytes': low-(self.guard+4),
            'main_stack_depth_from_ram_end_bytes': self.ram_end-self.min_main_sp,
            'main_stack_gap_above_arena_bytes': self.min_main_sp-self.end,
            'lease_violations': [dict(address=hex(a), size=n, pc=hex(pc), count=count)
                                 for (a, n, pc), count in sorted(self.violations.items())],
            'scope': 'Executed writes/SP while resident active; excludes boot, inactive handoffs and unexecuted paths.',
        }
