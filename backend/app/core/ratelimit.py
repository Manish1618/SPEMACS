"""A minimal in-process sliding-window rate limiter.

Used to throttle /auth/login per client IP so a single host cannot spray
credentials across many accounts (the per-account lockout in security.py covers
repeated attempts against one account).

State lives in this process, so behind multiple uvicorn workers each worker
enforces its own window. Moving this to Redis is the change to make when the API
is scaled out; the interface stays the same.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = defaultdict(deque)

# Stop unbounded growth from a spray across many spoofed keys.
_MAX_TRACKED_KEYS = 10_000


def check(key: str, max_attempts: int, window_seconds: int) -> Tuple[bool, int]:
    """Record an attempt for `key`.

    Returns (allowed, retry_after_seconds). When not allowed, the attempt is not
    recorded, so a blocked caller cannot extend their own window indefinitely.
    """
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        if len(_hits) > _MAX_TRACKED_KEYS:
            _prune_locked(cutoff)

        bucket = _hits[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= max_attempts:
            retry_after = int(bucket[0] - cutoff) + 1
            return False, max(retry_after, 1)

        bucket.append(now)
        return True, 0


def reset(key: str) -> None:
    """Clear a key's window - called after a successful login."""
    with _lock:
        _hits.pop(key, None)


def _prune_locked(cutoff: float) -> None:
    for key in [k for k, v in _hits.items() if not v or v[-1] < cutoff]:
        del _hits[key]
