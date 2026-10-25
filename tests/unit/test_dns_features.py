"""
Unit tests for DNS propagation and Reverse DNS (PTR) in netcheck.modules.dns
"""
import socket
from unittest.mock import patch

from netcheck.modules.dns import (
    _build_dns_query,
    _parse_dns_response,
    dns_propagation,
    reverse_dns,
)


class TestReverseDNS:
    @patch("socket.gethostbyaddr", return_value=("dns.google", [], ["8.8.8.8"]))
    def test_reverse_dns_success(self, mock_ghba):
        res = reverse_dns("8.8.8.8", timeout=2.0)
        assert res["success"] is True
        assert res["status"] == "SUCCESS"
        assert res["metadata"]["hostname"] == "dns.google"
        assert res["metadata"]["query_type"] == "PTR"

    @patch("socket.gethostbyaddr", side_effect=socket.herror(1, "Unknown host"))
    def test_reverse_dns_herror(self, mock_ghba):
        res = reverse_dns("192.0.2.1", timeout=2.0)
        assert res["success"] is False
        assert res["status"] == "FAILED"
        assert "No PTR record found" in res["error"]


class TestDNSPropagation:
    def test_build_dns_query(self):
        query = _build_dns_query("example.com")
        assert len(query) > 12
        assert b"example" in query
        assert b"com" in query

    def test_parse_dns_response_empty(self):
        assert _parse_dns_response(b"") == []

    @patch("netcheck.modules.dns._query_resolver")
    def test_dns_propagation_consistent(self, mock_query):
        mock_query.side_effect = lambda domain, name, rip, port, to: {
            "resolver": name,
            "resolver_ip": rip,
            "success": True,
            "latency_ms": 10.0,
            "ips": ["93.184.216.34"],
            "error": None,
        }
        res = dns_propagation("example.com", timeout=1.0)
        assert res["success"] is True
        assert res["status"] == "SUCCESS"
        assert res["metadata"]["consistent"] is True
        assert len(res["metadata"]["resolvers"]) == 4
        # Verify resolver names
        names = [r["resolver"] for r in res["metadata"]["resolvers"]]
        assert "Google" in names
        assert "Cloudflare" in names
        assert "Quad9" in names
        assert "OpenDNS" in names

    @patch("netcheck.modules.dns._query_resolver")
    def test_dns_propagation_inconsistent(self, mock_query):
        def _resolver_mock(domain, name, rip, port, to):
            ip = "1.2.3.4" if name == "Google" else "5.6.7.8"
            return {
                "resolver": name,
                "resolver_ip": rip,
                "success": True,
                "latency_ms": 12.0,
                "ips": [ip],
                "error": None,
            }

        mock_query.side_effect = _resolver_mock
        res = dns_propagation("example.com", timeout=1.0)
        assert res["success"] is True  # all succeeded
        assert res["metadata"]["consistent"] is False  # but returned different records
