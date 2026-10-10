"""
Unit tests for netcheck.modules.tcp
"""
import socket
import pytest
from unittest.mock import patch, MagicMock
from netcheck.modules.tcp import check_tcp_connect


class TestTCPConnect:
    @patch("netcheck.modules.tcp.socket.create_connection")
    @patch("netcheck.modules.tcp.dns_lookup")
    def test_tcp_connect_success(self, mock_dns, mock_create_connection):
        mock_dns.return_value = {
            "success": True,
            "metadata": {"ips": ["93.184.216.34"]}
        }
        # mock_create_connection does not raise exception, meaning success
        res = check_tcp_connect("example.com", 80)
        assert res["success"] is True
        assert res["status"] == "SUCCESS"
        mock_create_connection.assert_called_once_with(("93.184.216.34", 80), timeout=5.0)

    @patch("netcheck.modules.tcp.socket.create_connection")
    @patch("netcheck.modules.tcp.dns_lookup")
    def test_tcp_connect_failure(self, mock_dns, mock_create_connection):
        mock_dns.return_value = {
            "success": True,
            "metadata": {"ips": ["93.184.216.34"]}
        }
        mock_create_connection.side_effect = ConnectionRefusedError("refused")

        res = check_tcp_connect("example.com", 80)
        assert res["success"] is False
        assert res["status"] == "FAILED"
        mock_create_connection.assert_called_once_with(("93.184.216.34", 80), timeout=5.0)

