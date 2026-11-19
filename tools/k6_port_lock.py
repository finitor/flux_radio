"""Portable, process-scoped advisory serial-port lock.

Do not delete lock files: another process may already have opened the inode.
The OS releases the lock when its handle closes, including on process exit.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re


def port_identity(port, *, windows=None):
    windows = os.name == 'nt' if windows is None else windows
    port = str(port)
    if windows:
        # PySerial accepts COMn and the extended Win32 device spelling.
        if port.startswith('\\\\.\\'):
            port = port[4:]
        if re.fullmatch(r'COM[0-9]+', port, re.IGNORECASE):
            return 'COM' + str(int(port[3:]))
        return port.casefold()
    return os.path.realpath(port)


@contextmanager
def serial_lock(port, folder=None):
    folder = Path(folder) if folder is not None else Path.home() / '.cache' / 'blowfang' / 'pack-ports'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    identity = hashlib.sha256(port_identity(port).encode()).hexdigest()
    with (folder / identity).open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            # Lock byte zero. Windows permits locks beyond EOF.
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BlockingIOError(f'another pack operation is using {port}') from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BlockingIOError(f'another pack operation is using {port}') from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
