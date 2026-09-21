import math
import threading
import time

from .config import CLEANUP_INTERVAL_SECONDS, CLEANUP_THRESHOLD_SECONDS
from .services.files import cleanup_media_files, ensure_directories, purge_stale_temp_files

_cleanup_thread_started = False
_startup_complete = False
_startup_lock = threading.Lock()
# Sweeps run on a fixed grid (anchor + k * interval) so deletion times can be predicted.
_sweep_anchor = time.time()


def cleanup_worker():
    sweep_index = 1
    while True:
        next_sweep = _sweep_anchor + sweep_index * CLEANUP_INTERVAL_SECONDS
        time.sleep(max(0.0, next_sweep - time.time()))
        cleanup_media_files()
        sweep_index = math.floor((time.time() - _sweep_anchor) / CLEANUP_INTERVAL_SECONDS) + 1


def estimate_deletion_time(modified_timestamp: float) -> float:
    """Return the first scheduled sweep at which a file with this mtime will be past the threshold."""
    expires_at = modified_timestamp + CLEANUP_THRESHOLD_SECONDS
    sweep_index = math.floor((expires_at - _sweep_anchor) / CLEANUP_INTERVAL_SECONDS) + 1
    next_sweep_index = math.floor((time.time() - _sweep_anchor) / CLEANUP_INTERVAL_SECONDS) + 1
    return _sweep_anchor + max(sweep_index, next_sweep_index) * CLEANUP_INTERVAL_SECONDS


def ensure_cleanup_thread():
    global _cleanup_thread_started
    if not _cleanup_thread_started:
        _cleanup_thread_started = True
        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()


def ensure_runtime_ready():
    global _startup_complete, _sweep_anchor
    if _startup_complete:
        return
    with _startup_lock:
        if _startup_complete:
            return
        ensure_directories()
        purge_stale_temp_files()
        _sweep_anchor = time.time()
        cleanup_media_files()
        ensure_cleanup_thread()
        _startup_complete = True
