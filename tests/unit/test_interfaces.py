"""
Unit tests for netcheck.modules.interfaces
"""
import pytest
from netcheck.modules.interfaces import get_network_interfaces


class TestInterfacesListing:
    def test_interfaces_listing(self):
        res = get_network_interfaces()
        assert res["success"] is True
        assert "primary_ip" in res["metadata"]
        assert "interfaces" in res["metadata"]
