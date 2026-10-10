"""
Shared pytest fixtures for all NetCheck tests.

Reusable result dicts, mock factories, and common patchers.
All fixtures are scoped to function by default.
"""
import os
import sys

# Ensure project root is in sys.path when running pytest from any directory layout
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from unittest.mock import MagicMock



# ---------------------------------------------------------------------------
# Result dict fixtures — used by formatter tests and integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def interfaces_result():
    return {
        "type": "interfaces",
        "target": "interfaces",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": None,
        "metadata": {
            "primary_ip": "192.168.1.5",
            "gateway_ip": "192.168.1.1",
            "gateway_dev": "eth0",
            "public_ip": "8.8.8.8",
            "all_interfaces_shown": False,
            "interfaces": {
                "eth0": {
                    "ipv4": ["192.168.1.5"],
                    "ipv6": ["fe80::1"],
                    "status": "UP",
                }
            },
        },
    }


@pytest.fixture
def dns_result():
    return {
        "type": "dns",
        "target": "google.com",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": 12.5,
        "metadata": {
            "resolved_host": "google.com",
            "ips": ["142.250.190.46"],
            "aliases": ["www.google.com"],
            "reverse_dns": "dns.google",
        },
    }


@pytest.fixture
def http_result():
    return {
        "type": "http",
        "target": "http://example.com",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": 45.2,
        "metadata": {
            "status_code": 200,
            "redirect_url": None,
            "size_bytes": 1256,
            "headers": {"content-type": "text/html"},
        },
    }


@pytest.fixture
def ssl_result():
    return {
        "type": "ssl",
        "target": "google.com",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": 110.0,
        "metadata": {
            "subject": {"commonName": "google.com"},
            "issuer": {"organizationName": "Google Trust Services"},
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
            "days_until_expiry": 200,
            "expired": False,
            "sans": ["google.com", "www.google.com"],
        },
    }


@pytest.fixture
def ping_result():
    return {
        "type": "ping",
        "target": "8.8.8.8",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": 15.1,
        "metadata": {
            "host": "8.8.8.8",
            "packets_sent": 4,
            "packets_received": 4,
            "packet_loss_pct": 0.0,
            "min_rtt_ms": 14.0,
            "avg_rtt_ms": 15.0,
            "max_rtt_ms": 16.0,
            "ping_output": "PING 8.8.8.8: 4 packets sent, 4 received",
        },
    }


@pytest.fixture
def tcp_result():
    return {
        "type": "tcp",
        "target": "example.com:80",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": 22.3,
        "metadata": {
            "host": "example.com",
            "port": 80,
            "ip": "93.184.216.34",
            "service": "http",
            "method": "socket",
        },
    }


@pytest.fixture
def ports_result():
    return {
        "type": "ports",
        "target": "ports",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": None,
        "metadata": {
            "listening_ports": [
                {"proto": "TCP", "address": "0.0.0.0", "port": 22, "process": "sshd", "pid": "1234"},
                {"proto": "TCP", "address": "127.0.0.1", "port": 631, "process": "cups", "pid": "567"},
            ]
        },
    }


@pytest.fixture
def scan_result():
    return {
        "type": "scan",
        "target": "example.com",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": None,
        "metadata": {
            "ips": ["93.184.216.34"],
            "open_ports": [{"port": 80, "service": "http", "latency_ms": 5.1}],
            "closed_ports": [{"port": 22, "service": "ssh", "latency_ms": None}],
        },
    }


@pytest.fixture
def traceroute_result():
    return {
        "type": "traceroute",
        "target": "8.8.8.8",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": None,
        "metadata": {
            "hops": [
                {"hop": 1, "ip": "192.168.1.1", "name": "router.local", "latency_ms": 1.2},
                {"hop": 2, "ip": "8.8.8.8", "name": "dns.google", "latency_ms": 11.5},
            ]
        },
    }


@pytest.fixture
def whois_result():
    return {
        "type": "whois",
        "target": "google.com",
        "status": "SUCCESS",
        "success": True,
        "error": None,
        "latency_ms": None,
        "metadata": {
            "type": "domain",
            "rdap_source": "rdap",
            "registrar": "MarkMonitor Inc.",
            "creation_date": "1997-09-15T04:00:00Z",
            "raw_whois": None,
        },
    }


@pytest.fixture
def tcp_batch_results():
    return [
        {
            "type": "tcp", "target": "example.com:80", "status": "SUCCESS", "success": True,
            "error": None, "latency_ms": 22.3,
            "metadata": {"host": "example.com", "port": 80, "method": "socket"},
        },
        {
            "type": "tcp", "target": "example.com:443", "status": "SUCCESS", "success": True,
            "error": None, "latency_ms": 30.1,
            "metadata": {"host": "example.com", "port": 443, "method": "socket"},
        },
    ]


@pytest.fixture
def failed_tcp_result():
    return {
        "type": "tcp", "target": "dead.host:80", "status": "FAILED", "success": False,
        "error": "Connection refused", "latency_ms": 0.0,
        "metadata": {"host": "dead.host", "port": 80},
    }


# ---------------------------------------------------------------------------
# Mock socket factory
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_socket():
    """Return a pre-configured mock socket instance."""
    sock = MagicMock()
    sock.connect_ex.return_value = 0
    sock.__enter__ = MagicMock(return_value=sock)
    sock.__exit__ = MagicMock(return_value=False)
    return sock
