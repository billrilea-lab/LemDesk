"""Single-instance lock for LEMdesk Pro menu bar."""

from __future__ import annotations

import atexit
import os
from pathlib import Path

LOCK = Path.home() / ".config" / "lemdesk" / "lemdesk-pro.pid"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire() -> bool:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            old = int(LOCK.read_text().strip())
        except ValueError:
            old = -1
        if old > 0 and _pid_alive(old):
            return False
    LOCK.write_text(str(os.getpid()))
    atexit.register(release)
    return True


def release() -> None:
    if not LOCK.exists():
        return
    try:
        if int(LOCK.read_text().strip()) == os.getpid():
            LOCK.unlink(missing_ok=True)
    except (ValueError, OSError):
        pass
