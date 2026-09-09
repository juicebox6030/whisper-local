# Advisory per-user lock; the open descriptor owns the lock until shutdown.
# Never unlink a live lock file, which would allow two different lock inodes.
import fcntl
import os
from pathlib import Path
from .paths import get_app_data_path


def acquire_lock(app_name):
    directory = Path(get_app_data_path())
    directory.mkdir(parents=True, exist_ok=True)
    handle = open(directory / (Path(app_name).name + '.lock'), 'a+')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def release_lock(handle):
    if handle:
        handle.close()
