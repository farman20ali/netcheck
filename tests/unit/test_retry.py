"""
Unit tests for netcheck.utils.retry
"""
import pytest
from netcheck.utils.retry import with_retry, retry_call


class TestWithRetryDecorator:
    def test_succeeds_on_first_try(self):
        calls = 0

        @with_retry(retries=3, delay=0.01)
        def fn():
            nonlocal calls
            calls += 1
            return "ok"

        result = fn()
        assert result == "ok"
        assert calls == 1

    def test_retries_and_eventually_succeeds(self):
        calls = 0

        @with_retry(retries=3, delay=0.01)
        def fail_twice():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ValueError("temporary")
            return "success"

        assert fail_twice() == "success"
        assert calls == 3

    def test_raises_after_exhausting_retries(self):
        @with_retry(retries=2, delay=0.01)
        def always_fails():
            raise RuntimeError("permanent")

        with pytest.raises(RuntimeError):
            always_fails()

    def test_zero_retries_raises_immediately(self):
        @with_retry(retries=0, delay=0.01)
        def fail():
            raise ValueError("instant fail")

        with pytest.raises(ValueError):
            fail()


class TestRetryCall:
    def test_successful_call(self):
        result = retry_call(lambda: 42, retries=3, delay=0.01)
        assert result == 42

    def test_retry_on_exception(self):
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 2:
                raise RuntimeError("not ready")
            return "ready"

        result = retry_call(flaky, retries=3, delay=0.01)
        assert result == "ready"
        assert len(attempts) == 2
