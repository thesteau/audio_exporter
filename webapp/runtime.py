import threading
import time

from .config import CLEANUP_INTERVAL_SECONDS
from .services.files import cleanup_old_music_files, ensure_directories

_cleanup_thread_started = False
_startup_complete = False
_startup_lock = threading.Lock()


def cleanup_worker():
    while True:
        time.sleep(CLEANUP_INTERVAL_SECONDS)
        cleanup_old_music_files()


def ensure_cleanup_thread():
    global _cleanup_thread_started
    if not _cleanup_thread_started:
        _cleanup_thread_started = True
        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()


def ensure_runtime_ready():
    global _startup_complete
    if _startup_complete:
        return
    with _startup_lock:
        if _startup_complete:
            return
        ensure_directories()
        cleanup_old_music_files()
        ensure_cleanup_thread()
        _startup_complete = True
