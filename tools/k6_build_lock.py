"""Inter-process serialization of K6 firmware builds sharing Aura output state."""
from contextlib import contextmanager
import fcntl
from pathlib import Path

LOCK = Path(__file__).resolve().parents[1] / 'firmware/k6-aura/out-fd6818b/.build.lock'


@contextmanager
def exclusive_build():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+b') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
