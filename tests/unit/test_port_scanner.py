"""
Unit tests for netcheck.modules.port_scanner
"""
import socket
from unittest.mock import patch

from netcheck.modules.port_scanner import scan_port_single, scan_ports


class TestPortScannerModule:
    @patch("netcheck.modules.port_scanner.dns_lookup")
    @patch("netcheck.modules.port_scanner.scan_port_single")
    def test_port_scanner_module(self, mock_scan_single, mock_dns):
        mock_dns.return_value = {
            "success": True,
            "metadata": {"ips": ["1.1.1.1"]}
        }
        mock_scan_single.side_effect = lambda ip, port, timeout: {
            "port": port,
            "status": "OPEN" if port == 80 else "CLOSED",
            "service": "http" if port == 80 else "unknown",
            "latency_ms": 5.0 if port == 80 else None
        }

        res = scan_ports("example.com", ports=[22, 80])
        assert res["success"] is True
        assert len(res["metadata"]["open_ports"]) == 1
        assert res["metadata"]["open_ports"][0]["port"] == 80
        assert len(res["metadata"]["closed_ports"]) == 1
        assert res["metadata"]["closed_ports"][0]["port"] == 22

    def test_port_scanner_safety_limit(self):
        ports = list(range(1, 1005))
        res = scan_ports("example.com", ports=ports)
        assert res["success"] is False
        assert "exceeds safety limit of 1000 ports" in res["error"]

    @patch("socket.socket")
    def test_scan_port_single_tri_state(self, mock_socket_cls):

        # Test OPEN
        mock_sock = mock_socket_cls.return_value.__enter__.return_value
        mock_sock.connect.return_value = None
        r_open = scan_port_single("127.0.0.1", 80)
        assert r_open["status"] == "OPEN"

        # Test CLOSED (ConnectionRefusedError)
        mock_sock.connect.side_effect = ConnectionRefusedError()
        r_closed = scan_port_single("127.0.0.1", 81)
        assert r_closed["status"] == "CLOSED"

        # Test FILTERED (socket.timeout)
        mock_sock.connect.side_effect = socket.timeout()
        r_filtered = scan_port_single("127.0.0.1", 82)
        assert r_filtered["status"] == "FILTERED"
