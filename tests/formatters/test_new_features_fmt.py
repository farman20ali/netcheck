"""
Tests for new formatters: discover, DNS propagation, DNS PTR, HTTP waterfall
"""
from netcheck.utils.formatters import format_text


def test_fmt_discover_output():
    res = {
        "type": "discover",
        "target": "192.168.1.0/24",
        "status": "SUCCESS",
        "success": True,
        "latency_ms": 120.5,
        "error": None,
        "metadata": {
            "total_hosts": 254,
            "live_hosts": 2,
            "scan_time_ms": 120.5,
            "hosts": [
                {"ip": "192.168.1.1", "status": "UP", "method": "icmp", "latency_ms": 1.2, "hostname": "gw.home"},
                {"ip": "192.168.1.50", "status": "UP", "method": "tcp:80", "latency_ms": 3.4, "hostname": None},
            ],
        },
    }
    out = format_text([res], use_color=False)
    assert "Host Discovery Sweep for: 192.168.1.0/24" in out
    assert "Found 2 live hosts" in out
    assert "192.168.1.1" in out
    assert "gw.home" in out
    assert "tcp:80" in out


def test_fmt_dns_propagation_output():
    res = {
        "type": "dns",
        "target": "example.com",
        "status": "SUCCESS",
        "success": True,
        "latency_ms": 45.2,
        "error": None,
        "metadata": {
            "query_type": "propagation",
            "domain": "example.com",
            "consistent": True,
            "resolvers": [
                {"resolver": "Google", "resolver_ip": "8.8.8.8", "success": True, "latency_ms": 15.0, "ips": ["93.184.216.34"], "error": None},
                {"resolver": "Cloudflare", "resolver_ip": "1.1.1.1", "success": True, "latency_ms": 10.0, "ips": ["93.184.216.34"], "error": None},
            ],
        },
    }
    out = format_text([res], use_color=False)
    assert "DNS Propagation Check for: example.com" in out
    assert "Google" in out
    assert "Cloudflare" in out
    assert "8.8.8.8" in out
    assert "All resolvers returned matching records" in out


def test_fmt_dns_ptr_output():
    res = {
        "type": "dns",
        "target": "8.8.8.8",
        "status": "SUCCESS",
        "success": True,
        "latency_ms": 14.2,
        "error": None,
        "metadata": {
            "query_type": "PTR",
            "ip": "8.8.8.8",
            "hostname": "dns.google",
        },
    }
    out = format_text([res], use_color=False)
    assert "Reverse DNS (PTR) Lookup for: 8.8.8.8" in out
    assert "dns.google" in out


def test_fmt_http_waterfall_output():
    res = {
        "type": "http",
        "target": "https://example.com",
        "status": "SUCCESS",
        "success": True,
        "latency_ms": 85.0,
        "error": None,
        "metadata": {
            "status_code": 200,
            "redirect_url": None,
            "size_bytes": 1256,
            "headers": {},
            "dns_ms": 12.5,
            "connect_ms": 22.0,
            "tls_ms": 31.2,
            "ttfb_ms": 19.3,
        },
    }
    out = format_text([res], use_color=False)
    assert "Timing Waterfall:" in out
    assert "DNS Lookup:" in out
    assert "12.5ms" in out
    assert "TCP Connect:" in out
    assert "22.0ms" in out
    assert "TLS Handshake:" in out
    assert "31.2ms" in out
    assert "TTFB:" in out
    assert "19.3ms" in out
