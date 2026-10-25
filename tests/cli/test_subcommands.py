"""
Unit/Integration tests for netcheck.cli.subcommands
"""
from unittest.mock import patch

import pytest

from netcheck.cli.subcommands import handle_subcommands


@patch("netcheck.cli.subcommands.dns_lookup")
def test_handle_subcommands_dns(mock_dns):
    mock_dns.return_value = {"success": True, "status": "SUCCESS", "metadata": {}}
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("dns", ["example.com"])
    assert exc.value.code == 0
    mock_dns.assert_called_once()


def test_handle_subcommands_preset_list(capsys):
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("preset", ["--list"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Available Presets:" in captured.out
    assert "aws" in captured.out
    assert "cloudflare" in captured.out


@patch("netcheck.cli.subcommands.execute_concurrent_checks")
def test_handle_subcommands_preset_run(mock_exec):
    mock_exec.return_value = [{"type": "tcp", "target": "ec2.amazonaws.com:443", "success": True, "status": "SUCCESS"}]
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("preset", ["aws"])
    assert exc.value.code == 0
    mock_exec.assert_called_once()


def test_handle_subcommands_preset_unknown(capsys):
    from netcheck.cli.exitcodes import EXIT_BAD_ARGS
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("preset", ["nonexistent_preset_xyz"])
    assert exc.value.code == EXIT_BAD_ARGS


def test_handle_subcommands_tcp_invalid_port():
    from netcheck.cli.exitcodes import EXIT_BAD_ARGS
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("tcp", ["example.com", "invalid_port"])
    assert exc.value.code == EXIT_BAD_ARGS


def test_handle_subcommands_scan_too_many_ports():
    from netcheck.cli.exitcodes import EXIT_BAD_ARGS
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("scan", ["127.0.0.1", "-p", "1-2000"])
    assert exc.value.code == EXIT_BAD_ARGS


@patch("netcheck.modules.port_scanner.scan_ports")
def test_handle_subcommands_scan_fast(mock_scan):
    mock_scan.return_value = {"type": "scan", "status": "SUCCESS", "success": True, "metadata": {"open_ports": [], "closed_ports": [], "filtered_ports": []}}
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("scan", ["127.0.0.1", "-F"])
    assert exc.value.code == 0
    mock_scan.assert_called_once()
    assert len(mock_scan.call_args[1]["ports"]) == 100


@patch("netcheck.modules.port_scanner.scan_ports")
def test_handle_subcommands_scan_banner(mock_scan):
    mock_scan.return_value = {"type": "scan", "status": "SUCCESS", "success": True, "metadata": {"open_ports": [], "closed_ports": [], "filtered_ports": []}}
    with pytest.raises(SystemExit) as exc:
        handle_subcommands("scan", ["127.0.0.1", "-p", "80,443", "-sV"])
    assert exc.value.code == 0
    mock_scan.assert_called_once()
    assert mock_scan.call_args[1]["banner"] is True
