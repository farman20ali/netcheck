"""
Unit tests for netcheck.utils.threads: DaemonThreadPoolExecutor and cleanup_thread_queues
"""
import time
import pytest
from netcheck.utils.threads import DaemonThreadPoolExecutor, cleanup_thread_queues


def test_daemon_threads_created():
    with DaemonThreadPoolExecutor(max_workers=2) as executor:
        fut = executor.submit(lambda: 42)
        assert fut.result() == 42
        for t in executor._threads:
            assert t.daemon is True


def test_immediate_shutdown_on_exception():
    start = time.perf_counter()
    with pytest.raises(RuntimeError):
        with DaemonThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(time.sleep, 2.0)
            raise RuntimeError("simulation")
    duration = time.perf_counter() - start
    # Should not block waiting for the 2-second sleep
    assert duration < 0.5


def test_cleanup_thread_queues():
    # Calling cleanup_thread_queues should be safe and idempotent
    cleanup_thread_queues()
    cleanup_thread_queues()
