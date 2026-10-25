"""
Unit tests for netcheck.modules.discover
"""
from unittest.mock import patch

import pytest

from netcheck.modules.discover import (
    _expand_target,
    _probe_host,
    discover_hosts,
)


class TestTargetExpansion:
    def test_expand_cidr(self):
        hosts = _expand_target("192.168.1.0/29")
        # /29 has 6 usable hosts (192.168.1.1 through 192.168.1.6)
        assert len(hosts) == 6
        assert hosts[0] == "192.168.1.1"
        assert hosts[-1] == "192.168.1.6"

    def test_expand_dash_range_short(self):
        hosts = _expand_target("10.0.0.1-5")
        assert hosts == ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4", "10.0.0.5"]

    def test_expand_dash_range_full(self):
        hosts = _expand_target("10.0.0.10-10.0.0.12")
        assert hosts == ["10.0.0.10", "10.0.0.11", "10.0.0.12"]

    def test_expand_single_ip(self):
        hosts = _expand_target("127.0.0.1")
        assert hosts == ["127.0.0.1"]

    def test_expand_invalid_range_order(self):
        with pytest.raises(ValueError, match="Invalid octet range|End address"):
            _expand_target("10.0.0.20-10")

    def test_expand_range_too_large(self):
        with pytest.raises(ValueError, match="Range too large"):
            _expand_target("10.0.0.1-10.0.5.1")


class TestProbeHost:
    @patch("netcheck.modules.discover._ping_probe", return_value=1.5)
    @patch("netcheck.modules.discover._reverse_lookup", return_value="router.local")
    def test_probe_host_ping_success(self, mock_rev, mock_ping):
        rec = _probe_host("192.168.1.1", timeout=1.0)
        assert rec["status"] == "UP"
        assert rec["method"] == "icmp"
        assert rec["latency_ms"] == 1.5
        assert rec["hostname"] == "router.local"

    @patch("netcheck.modules.discover._ping_probe", return_value=None)
    @patch("netcheck.modules.discover._tcp_probe", side_effect=lambda ip, port, to: 2.5 if port == 80 else None)
    @patch("netcheck.modules.discover._reverse_lookup", return_value=None)
    def test_probe_host_tcp_fallback(self, mock_rev, mock_tcp, mock_ping):
        rec = _probe_host("192.168.1.10", timeout=1.0)
        assert rec["status"] == "UP"
        assert rec["method"] == "tcp:80"
        assert rec["latency_ms"] == 2.5
        assert rec["hostname"] is None

    @patch("netcheck.modules.discover._ping_probe", return_value=None)
    @patch("netcheck.modules.discover._tcp_probe", return_value=None)
    def test_probe_host_down(self, mock_tcp, mock_ping):
        rec = _probe_host("192.168.1.99", timeout=1.0)
        assert rec["status"] == "DOWN"
        assert rec["method"] is None
        assert rec["latency_ms"] is None


class TestDiscoverHosts:
    def test_range_limit_exceeded(self):
        res = discover_hosts("10.0.0.0/20")  # 4094 hosts > 1024 limit
        assert res["success"] is False
        assert "Target range too large" in res["error"]

    @patch("netcheck.modules.discover._probe_host")
    def test_discover_hosts_success(self, mock_probe):
        def _mock_probe(ip, timeout):
            if ip == "192.168.1.1":
                return {"ip": ip, "status": "UP", "method": "icmp", "latency_ms": 1.0, "hostname": "gw"}
            return {"ip": ip, "status": "DOWN", "method": None, "latency_ms": None, "hostname": None}

        mock_probe.side_effect = _mock_probe
        res = discover_hosts("192.168.1.1-3", timeout=0.5, max_workers=2)
        assert res["success"] is True
        assert res["type"] == "discover"
        assert res["metadata"]["total_hosts"] == 3
        assert res["metadata"]["live_hosts"] == 1
        assert len(res["metadata"]["hosts"]) == 1
        assert res["metadata"]["hosts"][0]["ip"] == "192.168.1.1"
