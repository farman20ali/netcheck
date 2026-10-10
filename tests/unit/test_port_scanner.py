"""
Unit tests for netcheck.modules.port_scanner
"""
import pytest
from unittest.mock import patch
from netcheck.modules.port_scanner import scan_ports


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
