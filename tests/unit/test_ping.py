"""
Unit tests for netcheck.modules.ping
"""
import pytest
from unittest.mock import patch, MagicMock
from netcheck.modules.ping import ping_host


class TestPingHost:
    @patch("netcheck.modules.ping.subprocess.run")
    def test_ping_host_success(self, mock_run):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "2 packets transmitted, 2 received, 0% packet loss"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        res = ping_host("8.8.8.8", count=2)
        assert res["success"] is True
        assert res["metadata"]["packets_sent"] == 2
        assert res["metadata"]["packets_received"] == 2
        assert res["metadata"]["packet_loss_pct"] == 0.0

    @patch("netcheck.modules.ping.subprocess.run")
    def test_ping_host_failure(self, mock_run):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = "0 received, 100% packet loss"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        res = ping_host("8.8.8.8", count=2)
        assert res["success"] is False
        assert res["metadata"]["packet_loss_pct"] == 100.0

