"""
Unit/Integration tests for netcheck.cli.subcommands
"""
import pytest
from unittest.mock import patch, MagicMock
from netcheck.cli.subcommands import handle_subcommands


@patch("netcheck.cli.subcommands.dns_lookup")
def test_handle_subcommands_dns(mock_dns):
    mock_dns.return_value = {"success": True, "status": "SUCCESS", "metadata": {}}
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("dns", ["example.com"])
    assert exc.value.code == 0
    mock_dns.assert_called_once()
