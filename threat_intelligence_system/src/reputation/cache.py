"""TTL + LRU cache shared by all reputation connectors.

Keeps WHOIS/DNS/GeoIP/SSL/feed responses in memory (bounded, LRU-evicted)
with per-entry expiry, so repeated lookups of the same indicator during a
case investigation never trigger duplicate network requests.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional


class TTLCache:
    """Thread-safe TTL cache with LRU eviction."""

    def __init__(self, max_entries: int = 512, ttl_seconds: float = 3600.0) -> None:
        self._max = max_entries
        self._ttl = ttl_seconds
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            expires, value = item
            if time.monotonic() > expires:
                del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + (ttl or self._ttl), value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)  # LRU eviction

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        if value is not None:
            self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
