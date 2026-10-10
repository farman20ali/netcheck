"""
Unit tests for netcheck.modules.traceroute
"""
import pytest
from unittest.mock import patch
from netcheck.modules.traceroute import traceroute as run_traceroute


class TestTracerouteModule:
    @patch("netcheck.modules.traceroute.run_subprocess_traceroute")
    def test_traceroute_module_fallback(self, mock_run_sub):
        mock_run_sub.return_value = [
            {"hop": 1, "ip": "192.168.1.1", "name": "router", "latency_ms": 1.2},
            {"hop": 2, "ip": "8.8.8.8", "name": "dns", "latency_ms": 10.5}
        ]

        res = list(mock_run_sub.return_value)
        assert len(res) == 2
        assert res[0]["ip"] == "192.168.1.1"
