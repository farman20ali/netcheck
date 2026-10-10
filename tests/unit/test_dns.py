"""
Unit tests for netcheck.modules.dns
"""
import socket
import pytest
from unittest.mock import patch
from netcheck.modules.dns import dns_lookup


class TestDNSLookup:
    @patch("socket.getaddrinfo")
    def test_dns_lookup_success(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ]
        res = dns_lookup("example.com")
        assert res["success"] is True
        assert res["status"] == "SUCCESS"
        assert "93.184.216.34" in res["metadata"]["ips"]

    @patch("socket.getaddrinfo")
    def test_dns_lookup_failure(self, mock_getaddrinfo):
        mock_getaddrinfo.side_effect = socket.gaierror("dns failure")
        res = dns_lookup("nonexistent.invalid")
        assert res["success"] is False
        assert res["status"] == "FAILED"
