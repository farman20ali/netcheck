"""
Tests for check_udp and run_mtr in netcheck.mcp.tools
"""
from unittest.mock import patch

from netcheck.mcp.tools import call_tool


class TestMCPUDPAndMTR:
    @patch("netcheck.modules.udp.check_udp")
    def test_call_tool_check_udp_open_or_filtered(self, mock_check):
        mock_check.return_value = {
            "type": "udp",
            "target": "8.8.8.8:53",
            "status": "OPEN_OR_FILTERED",
            "latency_ms": 15.2,
            "success": True,
            "error": None,
            "metadata": {"host": "8.8.8.8", "port": 53},
        }
        resp = call_tool("check_udp", {"host": "8.8.8.8", "port": 53, "timeout": 2.0})
        assert "isError" not in resp or resp.get("isError") is False
        assert len(resp["content"]) == 1
        assert "OPEN_OR_FILTERED" in resp["content"][0]["text"]

    @patch("netcheck.modules.udp.check_udp")
    def test_call_tool_check_udp_closed(self, mock_check):
        mock_check.return_value = {
            "type": "udp",
            "target": "127.0.0.1:9999",
            "status": "CLOSED",
            "latency_ms": 1.2,
            "success": False,
            "error": "Port unreachable",
            "metadata": {"host": "127.0.0.1", "port": 9999},
        }
        resp = call_tool("check_udp", {"host": "127.0.0.1", "port": 9999})
        assert resp.get("isError") is True
        assert "CLOSED" in resp["content"][0]["text"]

    @patch("netcheck.modules.mtr.mtr")
    def test_call_tool_run_mtr(self, mock_mtr):
        mock_mtr.return_value = {
            "type": "mtr",
            "target": "1.1.1.1",
            "status": "SUCCESS",
            "latency_ms": 25.0,
            "success": True,
            "error": None,
            "metadata": {
                "host": "1.1.1.1",
                "hops": [
                    {"hop": 1, "ip": "192.168.1.1", "loss_pct": 0.0, "avg_rtt_ms": 1.2},
                    {"hop": 2, "ip": "1.1.1.1", "loss_pct": 0.0, "avg_rtt_ms": 12.5},
                ],
            },
        }
        resp = call_tool("run_mtr", {"host": "1.1.1.1", "count": 2, "max_hops": 15})
        assert "isError" not in resp or resp.get("isError") is False
        assert "192.168.1.1" in resp["content"][0]["text"]
