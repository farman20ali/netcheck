import threading
import time
from typing import Any, Dict, Optional, Tuple


class Cache:
    """Thread-safe cache with time-to-live (TTL) support and size limit."""
    def __init__(self, default_ttl: float = 300.0, max_size: int = 1000):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            value, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        duration = ttl if ttl is not None else self._default_ttl
        with self._lock:
            now = time.time()
            expiry = now + duration

            # Clean expired items, but never evict the key we're about to write
            expired_keys = [k for k, (_, exp) in self._cache.items() if now > exp and k != key]
            for k in expired_keys:
                del self._cache[k]

            # Evict oldest if still full (only when key is new)
            if len(self._cache) >= self._max_size and key not in self._cache:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = (value, expiry)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

# Global instances for DNS and other resources
dns_cache = Cache(default_ttl=3600.0, max_size=2000)  # 1 hour for DNS, max 2000 items
general_cache = Cache(default_ttl=60.0, max_size=1000)  # 1 minute for general lookups, max 1000 items

