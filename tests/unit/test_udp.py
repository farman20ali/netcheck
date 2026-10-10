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
        assert _dns_probe()[0:2] == b"\xaa\xbb"


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
    with patch("netcheck.modules.udp.socket.gethostbyname", return_value="1.2.3.4"):
        with patch("netcheck.modules.udp.socket.socket") as MockSock:
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
        result, _ = _mocked_udp(return_value=(b"\x00" * 12, ("1.2.3.4", 53)))
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
        with patch("netcheck.modules.udp.socket.gethostbyname", return_value="9.9.9.9"):
            with patch("netcheck.modules.udp.socket.socket") as MockSock:
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
        with patch("netcheck.modules.udp.socket.gethostbyname", return_value="0.0.0.0"):
            with patch("netcheck.modules.udp.socket.socket") as MockSock:
                si = MagicMock()
                si.recvfrom.side_effect = socket.timeout
                MockSock.return_value = si
                result = check_udp("host", 54321, timeout=0.1)
        assert result["metadata"]["service"] == ""

    def test_custom_payload_sent(self):
        with patch("netcheck.modules.udp.socket.gethostbyname", return_value="1.1.1.1"):
            with patch("netcheck.modules.udp.socket.socket") as MockSock:
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
