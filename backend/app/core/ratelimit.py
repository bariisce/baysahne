"""In-process sliding-window rate limiter.

Scope: per API process. That is adequate for a single-instance deployment; when running several
replicas, put an edge rate limit in front (see docs/DEPLOYMENT.md). Brute-force protection for
admin logins does not depend on this alone — accounts are also locked in the database after
repeated failures (see services/auth.py).
"""

import threading
import time
from collections import defaultdict, deque

from app.core.errors import AppError


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window_seconds:
                q.popleft()
            if len(q) >= limit:
                retry = int(window_seconds - (now - q[0])) + 1
                raise AppError(
                    429,
                    "rate_limited",
                    "Çok fazla deneme yapıldı. Lütfen biraz sonra tekrar deneyin.",
                    {"retry_after_seconds": retry},
                )
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
