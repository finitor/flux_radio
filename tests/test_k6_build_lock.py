import fcntl
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import k6_build_lock


def test_exclusive_build_acquires_and_releases(tmp_path, monkeypatch):
    path = tmp_path / 'nested' / '.build.lock'
    monkeypatch.setattr(k6_build_lock, 'LOCK', path)
    with k6_build_lock.exclusive_build():
        with path.open('a+b') as contender:
            try:
                fcntl.flock(contender.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError('build lock was not exclusive')
    with path.open('a+b') as contender:
        fcntl.flock(contender.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
