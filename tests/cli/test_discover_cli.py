"""
Tests for CLI discover, dns --reverse, and dns --propagate commands
"""
from unittest.mock import patch

import pytest

from netcheck.cli.subcommands import handle_subcommands


class TestNewSubcommands:
    @patch("netcheck.modules.discover.discover_hosts")
    def test_cli_discover(self, mock_discover):
        mock_discover.return_value = {
            "type": "discover",
            "target": "192.168.1.0/29",
            "status": "SUCCESS",
            "success": True,
            "latency_ms": 10.0,
            "error": None,
            "metadata": {"total_hosts": 6, "live_hosts": 0, "hosts": []},
        }
        with pytest.raises(SystemExit) as exc:
            handle_subcommands("discover", ["192.168.1.0/29", "-j", "10", "--no-color"])
        assert exc.value.code == 0
        mock_discover.assert_called_once_with("192.168.1.0/29", timeout=5.0, max_workers=10)

    @patch("netcheck.modules.dns.reverse_dns")
    def test_cli_dns_reverse(self, mock_rev):
        mock_rev.return_value = {
            "type": "dns",
            "target": "8.8.8.8",
            "status": "SUCCESS",
            "success": True,
            "latency_ms": 12.0,
            "error": None,
            "metadata": {"query_type": "PTR", "ip": "8.8.8.8", "hostname": "dns.google"},
        }
        with pytest.raises(SystemExit) as exc:
            handle_subcommands("dns", ["8.8.8.8", "--reverse", "--no-color"])
        assert exc.value.code == 0
        mock_rev.assert_called_once_with("8.8.8.8", 5.0)

    @patch("netcheck.modules.dns.dns_propagation")
    def test_cli_dns_propagate(self, mock_prop):
        mock_prop.return_value = {
            "type": "dns",
            "target": "example.com",
            "status": "SUCCESS",
            "success": True,
            "latency_ms": 20.0,
            "error": None,
            "metadata": {"query_type": "propagation", "domain": "example.com", "resolvers": [], "consistent": True},
        }
        with pytest.raises(SystemExit) as exc:
            handle_subcommands("dns", ["example.com", "--propagate", "--no-color"])
        assert exc.value.code == 0
        mock_prop.assert_called_once_with("example.com", timeout=5.0)

    @patch("netcheck.modules.dns.dns_propagation")
    def test_cli_dns_propagation_subcommand(self, mock_prop):
        mock_prop.return_value = {
            "type": "dns",
            "target": "example.com",
            "status": "SUCCESS",
            "success": True,
            "latency_ms": 20.0,
            "error": None,
            "metadata": {"query_type": "propagation", "domain": "example.com", "resolvers": [], "consistent": True},
        }
        with pytest.raises(SystemExit) as exc:
            handle_subcommands("dns-propagation", ["example.com", "--no-color"])
        assert exc.value.code == 0
        mock_prop.assert_called_once_with("example.com", timeout=5.0)
