"""
Unit tests for netcheck.utils.timeout
"""
import time
import pytest
from concurrent.futures import TimeoutError
from netcheck.utils.timeout import run_with_timeout


class TestTimeoutMechanism:
    def test_completes_within_timeout(self):
        def quick_func():
            return "done"
        assert run_with_timeout(1.0, quick_func) == "done"

    def test_raises_timeout_error_when_exceeded(self):
        def slow_func():
            time.sleep(0.3)
            return "slow_done"
        with pytest.raises(TimeoutError):
            run_with_timeout(0.1, slow_func)
