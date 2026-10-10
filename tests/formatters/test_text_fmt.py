"""
Unit tests for text_fmt
"""
from netcheck.utils.formatters import format_text


def test_text_interfaces_format(interfaces_result):
    out = format_text([interfaces_result], use_color=False)
    assert "Network Interface Information" in out
    assert "Interface: eth0" in out
    assert "IPv4: 192.168.1.5" in out


def test_text_dns_format(dns_result):
    out = format_text([dns_result], use_color=False)
    assert "DNS Lookup for: google.com" in out
    assert "Hostname: google.com" in out
    assert "142.250.190.46" in out


def test_text_http_format(http_result):
    out = format_text([http_result], use_color=False)
    assert "HTTP Status Check for: http://example.com" in out
    assert "Code: 200 OK" in out


def test_text_ssl_format(ssl_result):
    out = format_text([ssl_result], use_color=False)
    assert "SSL/TLS Certificate Check for: google.com" in out
    assert "Subject: CN = google.com" in out
    assert "Issuer: O = Google Trust Services" in out


def test_text_ping_format(ping_result):
    out = format_text([ping_result], use_color=False)
    assert "ICMP Ping Test for: 8.8.8.8" in out
    assert "Ping successful" in out


def test_text_ports_format(ports_result):
    out = format_text([ports_result], use_color=False)
    assert "Local Listening Ports & Services" in out
    assert "sshd" in out
    assert "cups" in out


def test_text_scan_format(scan_result):
    out = format_text([scan_result], use_color=False)
    assert "Port Scan for: example.com" in out
    assert "Port 80    - OPEN (http)" in out


def test_text_traceroute_format(traceroute_result):
    out = format_text([traceroute_result], use_color=False)
    assert "Traceroute to: 8.8.8.8" in out
    assert "router.local" in out
    assert "dns.google" in out


def test_text_whois_format(whois_result):
    out = format_text([whois_result], use_color=False)
    assert "Registration/WHOIS Lookup for: google.com" in out
    assert "Registrar/Owner: MarkMonitor Inc." in out
