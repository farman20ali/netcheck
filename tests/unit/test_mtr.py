"""Tests for netcheck.modules.mtr — fully mocked."""
import socket
from unittest.mock import MagicMock, patch

from netcheck.modules.mtr import _parse_traceroute_output, _result, mtr


class TestResultHelper:
    def test_structure_success(self):
        r = _result("host", True, {"hops": []}, latency_ms=10.0)
        assert r["type"] == "mtr"
        assert r["status"] == "SUCCESS"
        assert r["success"] is True
        assert r["latency_ms"] == 10.0

    def test_structure_failure(self):
        r = _result("host", False, {}, error="boom")
        assert r["status"] == "FAILED"
        assert r["success"] is False
        assert r["error"] == "boom"


class TestParseTracerouteOutput:
    LINUX_OUTPUT = """traceroute to google.com (8.8.8.8), 30 hops max, 60 byte packets
 1  192.168.1.1  1.234 ms  1.100 ms  1.050 ms
 2  10.0.0.1  5.000 ms  4.900 ms  4.800 ms
 3  *
"""

    WINDOWS_OUTPUT = """Tracing route to google.com [8.8.8.8]
over a maximum of 30 hops:

  1     1 ms     1 ms     1 ms  192.168.1.1
  2     5 ms     5 ms     5 ms  10.0.0.1
"""

    def test_linux_hop_count(self):
        hops = _parse_traceroute_output(self.LINUX_OUTPUT, is_windows=False)
        assert len(hops) >= 2

    def test_linux_first_hop(self):
        hops = _parse_traceroute_output(self.LINUX_OUTPUT, is_windows=False)
        assert hops[0]["hop"] == 1
        assert hops[0]["ip"] == "192.168.1.1"

    def test_linux_avg_ms(self):
        hops = _parse_traceroute_output(self.LINUX_OUTPUT, is_windows=False)
        hop = next(h for h in hops if h["ip"] == "192.168.1.1")
        expected_avg = round((1.234 + 1.100 + 1.050) / 3, 2)
        assert hop["avg_ms"] == expected_avg

    def test_linux_star_hop(self):
        hops = _parse_traceroute_output(self.LINUX_OUTPUT, is_windows=False)
        star_hop = next((h for h in hops if h["ip"] == "*"), None)
        assert star_hop is not None
        assert star_hop["loss_pct"] == 100.0

    def test_empty_output(self):
        hops = _parse_traceroute_output("", is_windows=False)
        assert hops == []

    def test_irrelevant_lines_ignored(self):
        output = "traceroute to example.com (93.184.216.34)\nsome noise line\n"
        hops = _parse_traceroute_output(output, is_windows=False)
        assert all(isinstance(h["hop"], int) for h in hops)


class TestMtr:
    def test_dns_failure(self):
        with patch(
            "netcheck.modules.mtr.socket.gethostbyname",
            side_effect=socket.gaierror("fail"),
        ):
            result = mtr("nonexistent.invalid", count=1, max_hops=2, timeout=0.1)
        assert result["success"] is False
        assert "DNS" in result["error"]

    def test_result_type(self):
        with patch(
            "netcheck.modules.mtr.socket.gethostbyname",
            side_effect=socket.gaierror("fail"),
        ):
            result = mtr("bad.host", count=1, max_hops=2, timeout=0.1)
        assert result["type"] == "mtr"

    def test_metadata_hops_key(self):
        with patch(
            "netcheck.modules.mtr.socket.gethostbyname",
            side_effect=socket.gaierror("fail"),
        ):
            result = mtr("bad.host")
        assert "hops" in result["metadata"]

    def test_fallback_called_on_permission_error(self):
        """When raw socket raises PermissionError, _system_traceroute is called."""
        with patch("netcheck.modules.mtr.socket.gethostbyname", return_value="8.8.8.8"):
            with patch("netcheck.modules.mtr._raw_mtr", side_effect=PermissionError):
                with patch("netcheck.modules.mtr._system_traceroute", return_value=None) as mock_sys:
                    mtr("google.com", count=1, max_hops=2, timeout=0.1)
        mock_sys.assert_called_once()

    def test_success_from_system_traceroute(self):
        fake_hops = [
            {"hop": 1, "ip": "192.168.1.1", "name": "router",
             "loss_pct": 0.0, "sent": 3, "recv": 3,
             "min_ms": 1.0, "avg_ms": 1.2, "max_ms": 1.5},
            {"hop": 2, "ip": "8.8.8.8", "name": "8.8.8.8",
             "loss_pct": 0.0, "sent": 3, "recv": 3,
             "min_ms": 10.0, "avg_ms": 11.0, "max_ms": 12.0},
        ]
        with patch("netcheck.modules.mtr.socket.gethostbyname", return_value="8.8.8.8"):
            with patch("netcheck.modules.mtr._raw_mtr", side_effect=PermissionError):
                with patch("netcheck.modules.mtr._system_traceroute", return_value=fake_hops):
                    result = mtr("google.com", count=3, max_hops=5, timeout=1.0)
        assert result["success"] is True
        assert result["metadata"]["hops"] == fake_hops

    def test_failure_when_both_methods_fail(self):
        with patch("netcheck.modules.mtr.socket.gethostbyname", return_value="8.8.8.8"):
            with patch("netcheck.modules.mtr._raw_mtr", side_effect=PermissionError):
                with patch("netcheck.modules.mtr._system_traceroute", return_value=None):
                    result = mtr("google.com")
        assert result["success"] is False
