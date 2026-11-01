"""In-memory sliding-window rate limiter keyed by (hashed IP, mode).

Fine for a single backend instance. If the backend is ever scaled out, move this to Redis.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque

_SALT = os.environ.get("PUNDIT_IP_SALT", "pundit-local-salt")


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{_SALT}:{ip}".encode()).hexdigest()[:32]


class RateLimiter:
    def __init__(self, window_seconds: int = 3600):
        self.window = window_seconds
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, mode: str, limit: int) -> tuple[bool, int]:
        """Return (allowed, seconds until the next slot frees up)."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[(key, mode)]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= limit:
                return False, int(self.window - (now - q[0])) + 1
            q.append(now)
            return True, 0
