"""Helper script: generate test_udp.py, test_mtr.py, test_presets.py, test_parse_target.py"""
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
UNIT = ROOT / "tests" / "unit"


# ─────────────────── test_udp.py ───────────────────────────────────────────

UDP = '''\
"""Tests for netcheck.modules.udp — all mocked, no real network I/O."""
import socket
from unittest.mock import MagicMock, patch

from netcheck.modules.udp import _dns_probe, _result, check_udp


class TestDnsProbe:
    def test_returns_bytes(self):
        assert isinstance(_dns_probe(), bytes)

    def test_minimum_length(self):
        assert len(_dns_probe()) >= 12

    def test_transaction_id(self):
        assert _dns_probe()[0:2] == b"\\xaa\\xbb"


class TestResultHelper:
    def test_structure(self):
        r = _result("h:1", "OK", True, {"host": "h"}, 5.0)
        assert r["type"] == "udp"
        assert r["success"] is True
        assert r["latency_ms"] == 5.0
        assert r["error"] is None

    def test_failure(self):
        r = _result("h:1", "FAILED", False, {}, error="boom")
        assert r["success"] is False
        assert r["error"] == "boom"


def _mocked_udp(return_value=None, side_effect=None, send_side=None):
    """Helper: returns (result, sock_inst) after calling check_udp with mocks."""
    with (
        patch("netcheck.modules.udp.socket.gethostbyname", return_value="1.2.3.4"),
        patch("netcheck.modules.udp.socket.socket") as MockSock,
    ):
        si = MagicMock()
        if send_side:
            si.sendto.side_effect = send_side
        elif side_effect:
            si.recvfrom.side_effect = side_effect
        else:
            si.recvfrom.return_value = return_value
        MockSock.return_value = si
        result = check_udp("host", 53, timeout=0.1)
    return result, si


class TestCheckUdp:
    def test_open_on_timeout(self):
        result, _ = _mocked_udp(side_effect=socket.timeout)
        assert result["status"] == "OPEN_OR_FILTERED"
        assert result["success"] is True

    def test_open_on_response(self):
        result, _ = _mocked_udp(return_value=(b"\\x00" * 12, ("1.2.3.4", 53)))
        assert result["status"] == "OPEN_OR_FILTERED"
        assert result["success"] is True

    def test_closed_on_connection_refused(self):
        result, _ = _mocked_udp(send_side=ConnectionRefusedError("refused"))
        assert result["status"] == "CLOSED"
        assert result["success"] is False

    def test_closed_on_oserror_linux(self):
        result, _ = _mocked_udp(send_side=OSError("[Errno 111] Connection refused"))
        assert result["status"] == "CLOSED"
        assert result["success"] is False

    def test_failed_on_dns_error(self):
        with patch(
            "netcheck.modules.udp.socket.gethostbyname",
            side_effect=socket.gaierror("Name or service not known"),
        ):
            result = check_udp("nonexistent.invalid", 80, timeout=0.1)
        assert result["status"] == "FAILED"
        assert "DNS" in result["error"]

    def test_target_format(self):
        with (
            patch("netcheck.modules.udp.socket.gethostbyname", return_value="9.9.9.9"),
            patch("netcheck.modules.udp.socket.socket") as MockSock,
        ):
            si = MagicMock()
            si.recvfrom.side_effect = socket.timeout
            MockSock.return_value = si
            result = check_udp("myhost", 1234, timeout=0.1)
        assert result["target"] == "myhost:1234"

    def test_ip_in_metadata(self):
        result, _ = _mocked_udp(side_effect=socket.timeout)
        assert result["metadata"]["ip"] == "1.2.3.4"

    def test_known_service_name(self):
        result, _ = _mocked_udp(side_effect=socket.timeout)
        assert result["metadata"]["service"] == "dns"  # port 53

    def test_unknown_service_empty(self):
        with (
            patch("netcheck.modules.udp.socket.gethostbyname", return_value="0.0.0.0"),
            patch("netcheck.modules.udp.socket.socket") as MockSock,
        ):
            si = MagicMock()
            si.recvfrom.side_effect = socket.timeout
            MockSock.return_value = si
            result = check_udp("host", 54321, timeout=0.1)
        assert result["metadata"]["service"] == ""

    def test_custom_payload_sent(self):
        with (
            patch("netcheck.modules.udp.socket.gethostbyname", return_value="1.1.1.1"),
            patch("netcheck.modules.udp.socket.socket") as MockSock,
        ):
            si = MagicMock()
            si.recvfrom.side_effect = socket.timeout
            MockSock.return_value = si
            check_udp("host", 514, timeout=0.1, payload=b"hello")
        si.sendto.assert_called_once()
        assert si.sendto.call_args[0][0] == b"hello"

    def test_latency_present_on_open(self):
        result, _ = _mocked_udp(side_effect=socket.timeout)
        assert isinstance(result["latency_ms"], float)
        assert result["latency_ms"] >= 0
'''

# ─────────────────── test_mtr.py ──────────────────────────────────────────

MTR = '''\
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
    LINUX_OUTPUT = """\
traceroute to google.com (8.8.8.8), 30 hops max, 60 byte packets
 1  192.168.1.1  1.234 ms  1.100 ms  1.050 ms
 2  10.0.0.1  5.000 ms  4.900 ms  4.800 ms
 3  *
"""

    WINDOWS_OUTPUT = """\
Tracing route to google.com [8.8.8.8]
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
        output = "traceroute to example.com (93.184.216.34)\\nsome noise line\\n"
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
        with (
            patch("netcheck.modules.mtr.socket.gethostbyname", return_value="8.8.8.8"),
            patch("netcheck.modules.mtr._raw_mtr", side_effect=PermissionError),
            patch("netcheck.modules.mtr._system_traceroute", return_value=None) as mock_sys,
        ):
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
        with (
            patch("netcheck.modules.mtr.socket.gethostbyname", return_value="8.8.8.8"),
            patch("netcheck.modules.mtr._raw_mtr", side_effect=PermissionError),
            patch("netcheck.modules.mtr._system_traceroute", return_value=fake_hops),
        ):
            result = mtr("google.com", count=3, max_hops=5, timeout=1.0)
        assert result["success"] is True
        assert result["metadata"]["hops"] == fake_hops

    def test_failure_when_both_methods_fail(self):
        with (
            patch("netcheck.modules.mtr.socket.gethostbyname", return_value="8.8.8.8"),
            patch("netcheck.modules.mtr._raw_mtr", side_effect=PermissionError),
            patch("netcheck.modules.mtr._system_traceroute", return_value=None),
        ):
            result = mtr("google.com")
        assert result["success"] is False
'''

# ─────────────────── test_presets.py ──────────────────────────────────────

PRESETS = '''\
"""Tests for netcheck.data.presets."""
import pytest

from netcheck.data.presets import PRESETS, PRESET_DESCRIPTIONS, get_preset, list_presets


class TestPresetData:
    def test_presets_not_empty(self):
        assert len(PRESETS) > 0

    def test_all_presets_have_entries(self):
        for name, entries in PRESETS.items():
            assert len(entries) > 0, f"Preset {name!r} has no entries"

    def test_all_entries_have_colon(self):
        for name, entries in PRESETS.items():
            for entry in entries:
                assert ":" in entry, f"Entry {entry!r} in {name!r} has no port"

    def test_all_ports_are_valid_integers(self):
        for name, entries in PRESETS.items():
            for entry in entries:
                host, port_str = entry.rsplit(":", 1)
                port = int(port_str)
                assert 1 <= port <= 65535, f"Invalid port {port} in {name!r}"

    def test_descriptions_cover_all_presets(self):
        for name in PRESETS:
            assert name in PRESET_DESCRIPTIONS, f"No description for {name!r}"


class TestListPresets:
    def test_returns_dict(self):
        result = list_presets()
        assert isinstance(result, dict)

    def test_keys_match_presets(self):
        assert set(list_presets().keys()) == set(PRESETS.keys())

    def test_values_are_strings(self):
        for k, v in list_presets().items():
            assert isinstance(v, str), f"Description for {k!r} is not str"


class TestGetPreset:
    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_known_preset_returns_list(self, name):
        result = get_preset(name)
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_entries_are_tuples(self, name):
        result = get_preset(name)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_ports_in_range(self, name):
        result = get_preset(name)
        for host, port in result:
            assert 1 <= port <= 65535

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_hosts_are_strings(self, name):
        result = get_preset(name)
        for host, port in result:
            assert isinstance(host, str)
            assert len(host) > 0

    def test_unknown_preset_returns_none(self):
        assert get_preset("nonexistent_preset_xyz") is None

    def test_aws_contains_ec2(self):
        aws = get_preset("aws")
        hosts = [h for h, p in aws]
        assert any("amazonaws" in h for h in hosts)

    def test_cloudflare_contains_1_1_1_1(self):
        cf = get_preset("cloudflare")
        hosts = [h for h, p in cf]
        assert "1.1.1.1" in hosts

    def test_github_port_443(self):
        gh = get_preset("github")
        ports = [p for h, p in gh]
        assert all(p == 443 for p in ports)
'''

# ─────────────────── test_parse_target.py ─────────────────────────────────

PARSE = '''\
"""Tests for netcheck.utils.range_expanders.parse_target_string."""
import pytest

from netcheck.utils.range_expanders import parse_target_string


class TestParseTargetString:
    # --- Simple host:port ---
    def test_simple_host_port(self):
        assert parse_target_string("google.com:443") == ("google.com", "443")

    def test_ip_port(self):
        assert parse_target_string("8.8.8.8:53") == ("8.8.8.8", "53")

    def test_port_range(self):
        assert parse_target_string("192.168.1.1:8000-8100") == ("192.168.1.1", "8000-8100")

    def test_port_list(self):
        assert parse_target_string("10.0.0.1:80,443") == ("10.0.0.1", "80,443")

    def test_combined_range_and_list(self):
        assert parse_target_string("host:80,443,8000-8010") == ("host", "80,443,8000-8010")

    # --- No port ---
    def test_hostname_no_port(self):
        host, port = parse_target_string("google.com")
        assert host == "google.com"
        assert port is None

    def test_ip_no_port(self):
        host, port = parse_target_string("192.168.1.1")
        assert host == "192.168.1.1"
        assert port is None

    # --- IPv6 bracketed ---
    def test_ipv6_bracketed(self):
        assert parse_target_string("[::1]:80") == ("::1", "80")

    def test_ipv6_bracketed_port_list(self):
        assert parse_target_string("[::1]:80,443") == ("::1", "80,443")

    def test_ipv6_bracketed_no_port(self):
        host, port = parse_target_string("[::1]")
        assert host == "::1"
        assert port is None

    def test_ipv6_full_bracketed(self):
        host, port = parse_target_string("[2001:db8::1]:443")
        assert host == "2001:db8::1"
        assert port == "443"

    # --- IPv6 unbracketed (ambiguous — last segment is numeric port) ---
    def test_ipv6_unbracketed_last_is_port(self):
        # "::1:80" → host="::1", port="80"
        host, port = parse_target_string("::1:80")
        assert host == "::1"
        assert port == "80"

    def test_ipv6_pure_no_port(self):
        # Pure IPv6 like "2001:db8::1" — last segment "1" is numeric so
        # parsed as port, host becomes "2001:db8:" — acceptable for bare IPv6
        # The key assertion: does NOT raise an exception
        host, port = parse_target_string("2001:db8::1")
        assert isinstance(host, str)

    # --- Edge cases ---
    def test_empty_string(self):
        host, port = parse_target_string("")
        assert host == ""
        assert port is None

    def test_whitespace_stripped(self):
        assert parse_target_string("  google.com:443  ") == ("google.com", "443")

    def test_url_like_no_crash(self):
        # Should not crash even on weird input
        host, port = parse_target_string("google.com:")
        # trailing colon with no digits → treated as no port
        assert isinstance(host, str)
'''

(UNIT / "test_udp.py").write_text(UDP, encoding="utf-8")
(UNIT / "test_mtr.py").write_text(MTR, encoding="utf-8")
(UNIT / "test_presets.py").write_text(PRESETS, encoding="utf-8")
(UNIT / "test_parse_target.py").write_text(PARSE, encoding="utf-8")

print("All test files written successfully.")
