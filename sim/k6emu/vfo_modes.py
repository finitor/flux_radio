"""Executable reference contract for cooperative VFO modes, not firmware execution."""
from dataclasses import dataclass
from collections import Counter

@dataclass(frozen=True)
class Mode:
    id: int
    label: str
    image_bytes: int
    state_bytes: int
    api: int = 1

class Runtime:
    """One resident RX-only provider; host owns RF, PTT and arena arbitration."""
    def __init__(self, budget=11776, reserve=1024):
        self.budget = budget - reserve
        self.providers = {}
        self.selected = [None, None]
        self.watching = 0
        self.resident = None
        self.blocked = False
        self.events = []
        self.frequency = [146520000, 440850000]

    def discover(self, entries):
        counts = Counter(m.id for m in entries)
        self.providers = {m.id:m for m in entries if
            counts[m.id] == 1 and 32 <= m.id <= 254 and m.api == 1
            and 1 <= len(m.label) <= 8 and m.label.isascii()
            and m.image_bytes > 0 and m.state_bytes >= 0
            and m.image_bytes + m.state_bytes <= self.budget}
        for side, id in enumerate(self.selected):
            if id is not None and id not in self.providers:
                self.selected[side] = None
                self.events.append(('missing', side, id))
        self.reconcile()

    def select(self, side, id):
        if id is not None and id not in self.providers:
            raise ValueError('unavailable mode')
        self.selected[side] = id
        self.reconcile()

    def reconcile(self):
        id = self.selected[self.watching]
        target = None if self.blocked or id is None else (self.watching,self.providers[id])
        if target == self.resident:
            return
        if self.resident:
            self.events.append(('deactivate', self.resident[0],self.resident[1].id))
        self.resident = target
        if target:
            self.events.append(('activate',target[0],target[1].id))

    def watch(self, side):
        self.watching = side
        self.reconcile()

    def arena_busy(self, busy):
        self.blocked = busy
        self.reconcile()

    def retune(self, side, hz):
        self.frequency[side] = hz
        if self.resident and self.resident[0] == side:
            self.events.append(('reset_rx',side,self.resident[1].id))

    def tick(self, samples=()):
        if self.resident:
            self.events.append(('rx', self.resident[0], tuple(samples)))

    def ptt_allowed(self, side):
        # Only native modes can proceed to ordinary host TX authorization.
        return self.selected[side] is None and not self.blocked
