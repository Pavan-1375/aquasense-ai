from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    """Small-process limiter for development and single-instance deployments.

    Production deployments should put a shared limiter at the reverse proxy or
    replace this implementation with a Redis-backed limiter.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            if len(self._events) > 5000:
                self._events = defaultdict(deque, {name: values for name, values in self._events.items() if values})
            return True


limiter = InMemoryRateLimiter()
