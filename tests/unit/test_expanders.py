"""
Unit tests for netcheck.utils.range_expanders
"""
import pytest
from netcheck.utils.range_expanders import expand_ip_range, expand_port_range


class TestExpandIpRange:
    def test_single_ip(self):
        assert expand_ip_range("192.168.1.1") == ["192.168.1.1"]

    def test_last_octet_range(self):
        assert expand_ip_range("192.168.1.1-3") == ["192.168.1.1", "192.168.1.2", "192.168.1.3"]

    def test_cidr_30_has_two_usable_hosts(self):
        result = expand_ip_range("192.168.1.0/30")
        assert result == ["192.168.1.1", "192.168.1.2"]

    def test_hostname_returns_as_is(self):
        result = expand_ip_range("google.com")
        assert result == ["google.com"]

    def test_cidr_32_single_host(self):
        result = expand_ip_range("10.0.0.1/32")
        assert result == ["10.0.0.1"]


class TestExpandPortRange:
    def test_single_port(self):
        assert expand_port_range("80") == [80]

    def test_comma_separated_ports(self):
        assert expand_port_range("80,443") == [80, 443]

    def test_port_range(self):
        assert expand_port_range("8000-8003") == [8000, 8001, 8002, 8003]

    def test_mixed_comma_and_range(self):
        assert expand_port_range("80,8000-8002,443") == [80, 8000, 8001, 8002, 443]

    def test_single_port_integer(self):
        assert expand_port_range("443") == [443]
