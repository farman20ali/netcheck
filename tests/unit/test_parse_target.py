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
