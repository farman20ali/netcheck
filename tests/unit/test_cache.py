"""
Unit tests for netcheck.utils.cache

Timing-sensitive tests use unittest.mock.patch to freeze time.time()
so they are deterministic and never flaky on slow CI runners.
"""
import time
from unittest.mock import patch

import pytest

from netcheck.utils.cache import Cache


class TestCacheTTL:
    def test_get_before_expiry(self):
        """Value is accessible before the TTL elapses."""
        with patch("netcheck.utils.cache.time") as mock_t:
            mock_t.time.return_value = 0.0
            cache = Cache(default_ttl=10)
            cache.set("k", "v")

            mock_t.time.return_value = 5.0   # halfway through TTL
            assert cache.get("k") == "v"

    def test_get_after_expiry(self):
        """Value is evicted and None is returned after TTL elapses."""
        with patch("netcheck.utils.cache.time") as mock_t:
            mock_t.time.return_value = 0.0
            cache = Cache(default_ttl=0.05)
            cache.set("k", "v")             # expiry = 0.05

            mock_t.time.return_value = 0.10  # past expiry
            assert cache.get("k") is None

    def test_overwrite_resets_ttl(self):
        """Overwriting an existing key gives it a fresh TTL from now."""
        with patch("netcheck.utils.cache.time") as mock_t:
            mock_t.time.return_value = 0.0
            cache = Cache(default_ttl=0.05)
            cache.set("k", "first")         # expiry = 0.05

            mock_t.time.return_value = 0.03  # original key not yet expired
            cache.set("k", "second")        # expiry = 0.03 + 0.05 = 0.08

            mock_t.time.return_value = 0.06  # past original expiry, but within new TTL
            assert cache.get("k") == "second"

    def test_overwrite_expired_key_resets_ttl(self):
        """Overwriting a key that is already past its original TTL still works."""
        with patch("netcheck.utils.cache.time") as mock_t:
            mock_t.time.return_value = 0.0
            cache = Cache(default_ttl=0.05)
            cache.set("k", "first")          # expiry = 0.05

            mock_t.time.return_value = 0.10  # original key IS expired
            cache.set("k", "second")         # expiry = 0.10 + 0.05 = 0.15

            mock_t.time.return_value = 0.12  # within new TTL
            assert cache.get("k") == "second"

    def test_miss_returns_none(self):
        cache = Cache(default_ttl=10)
        assert cache.get("nonexistent") is None


class TestCacheEviction:
    def test_max_size_evicts_oldest(self):
        cache = Cache(default_ttl=60, max_size=3)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")
        # k1 is oldest, adding k4 should evict k1
        cache.set("k4", "v4")
        assert cache.get("k1") is None
        assert cache.get("k2") == "v2"
        assert cache.get("k3") == "v3"
        assert cache.get("k4") == "v4"

    def test_max_size_one(self):
        cache = Cache(default_ttl=60, max_size=1)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        assert cache.get("k1") is None
        assert cache.get("k2") == "v2"

    def test_overwrite_does_not_count_as_new_entry(self):
        """Overwriting an existing key should not trigger eviction of other keys."""
        cache = Cache(default_ttl=60, max_size=2)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k1", "updated")  # overwrite — should not evict k2
        assert cache.get("k1") == "updated"
        assert cache.get("k2") == "v2"
