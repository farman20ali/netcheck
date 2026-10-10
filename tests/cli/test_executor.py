"""
Unit/Integration tests for netcheck.cli.executor
"""
import pytest
from unittest.mock import patch, MagicMock
from netcheck.cli.executor import run_check_with_retry, execute_concurrent_checks


class TestExecutor:
    def test_run_check_with_retry_success(self):
        check_fn = MagicMock(return_value={"success": True, "data": "yes"})
        res = run_check_with_retry(check_fn, retries=3, delay=0.001)
        assert res["success"] is True
        assert check_fn.call_count == 1

    def test_run_check_with_retry_flaky_success(self):
        calls = []
        def flaky_fn():
            calls.append(1)
            if len(calls) < 2:
                return {"success": False, "error": "temp"}
            return {"success": True, "data": "ok"}

        res = run_check_with_retry(flaky_fn, retries=3, delay=0.001)
        assert res["success"] is True
        assert len(calls) == 2

    @patch("netcheck.cli.executor.check_tcp_connect")
    def test_execute_concurrent_checks(self, mock_tcp):
        mock_tcp.return_value = {"success": True, "latency_ms": 10.0}
        targets = [("1.1.1.1", 80), ("8.8.8.8", 53)]
        results = execute_concurrent_checks(targets, timeout=1.0, max_jobs=2, retries=1, retry_delay=0.001)
        assert len(results) == 2
        assert all(r["success"] for r in results)
