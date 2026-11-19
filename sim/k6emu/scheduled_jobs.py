"""Reference deadline policy; never controls RF or runs a module itself."""
from dataclasses import dataclass

MASK = 0xffffffff
HALF = 0x80000000

@dataclass
class ScheduledJob:
    interval: int
    grace: int
    deadline: int | None = None

    def __post_init__(self):
        if not 0 < self.interval < HALF or not 0 <= self.grace < self.interval:
            raise ValueError("invalid interval or grace")

    def enable(self, now):
        self.deadline = (now + self.interval) & MASK

    def cancel(self):
        self.deadline = None

    def poll(self, now, *, rf_idle, arena_available):
        """Return dispatch/skip once, or None; host must still authorize TX."""
        if self.deadline is None:
            return None
        late = (now - self.deadline) & MASK
        if late >= HALF:
            return None
        if late <= self.grace and not (rf_idle and arena_available):
            return None
        result = "dispatch" if late <= self.grace else "skip"
        # Preserve cadence, never replay missed intervals.
        self.deadline = (self.deadline + (late // self.interval + 1) * self.interval) & MASK
        return result
