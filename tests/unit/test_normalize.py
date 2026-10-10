"""
Unit tests for netcheck.utils.normalize
"""
import pytest
from netcheck.utils.normalize import normalize_host, parse_line_to_raw_host_port


class TestNormalizeHost:
    def test_strips_https_scheme(self):
        assert normalize_host("https://google.com/path?q=1") == "google.com"

    def test_strips_http_scheme_with_port(self):
        assert normalize_host("http://api.example.com:8443/v1") == "api.example.com"

    def test_host_with_port(self):
        assert normalize_host("192.168.1.1:80") == "192.168.1.1"

    def test_bare_hostname(self):
        assert normalize_host("example.com") == "example.com"

    def test_empty_string(self):
        assert normalize_host("") == ""

    def test_ipv6_with_port(self):
        assert normalize_host("[2001:db8::1]:80") == "2001:db8::1"

    def test_bare_ipv6(self):
        assert normalize_host("2001:db8::1") == "2001:db8::1"


class TestParseLineToRawHostPort:
    def test_ip_with_port_in_url(self):
        assert parse_line_to_raw_host_port("http://192.168.1.1:8080/path") == ("192.168.1.1", "8080")

    def test_https_default_port(self):
        assert parse_line_to_raw_host_port("https://google.com/") == ("google.com", "443")

    def test_ip_range_with_port(self):
        assert parse_line_to_raw_host_port("192.168.1.1-10 80") == ("192.168.1.1-10", "80")

    def test_ipv6_with_port(self):
        assert parse_line_to_raw_host_port("[fe80::1]:80") == ("fe80::1", "80")

    def test_host_comma_ports(self):
        assert parse_line_to_raw_host_port("google.com,80,443") == ("google.com", "80,443")

    def test_host_with_path_defaults_to_80(self):
        assert parse_line_to_raw_host_port("google.com/path") == ("google.com", "80")

    def test_comment_line_returns_empty(self):
        assert parse_line_to_raw_host_port(" # comment line ") == ("", "")
