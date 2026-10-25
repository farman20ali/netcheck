"""
Unit tests for the NetCheck MCP tools registry and call dispatcher.
"""
import json
from unittest.mock import patch

from netcheck.mcp.tools import TOOLS_LIST, call_tool


def test_mcp_tools_list():
    tool_names = [t["name"] for t in TOOLS_LIST]
    assert "check_tcp_connectivity" in tool_names
    assert "check_http_status" in tool_names
    assert "get_network_interfaces" in tool_names


@patch("netcheck.mcp.tools.dns_lookup")
def test_mcp_tool_call_dns(mock_dns):
    mock_dns.return_value = {
        "success": True,
        "status": "SUCCESS",
        "metadata": {"ips": ["1.1.1.1"]}
    }

    res = call_tool("dns_lookup", {"host": "one.one.one.one"})
    assert "content" in res
    content_text = res["content"][0]["text"]
    parsed = json.loads(content_text)
    assert parsed["success"] is True
    assert parsed["metadata"]["ips"] == ["1.1.1.1"]
    assert res.get("isError") is None or res.get("isError") is False


@patch("netcheck.mcp.tools.dns_lookup")
def test_mcp_tool_failure_sets_is_error(mock_dns):
    mock_dns.return_value = {
        "success": False,
        "status": "FAILED",
        "error": "Resolution error",
        "metadata": {}
    }
    res = call_tool("dns_lookup", {"host": "bad.domain.invalid"})
    assert res.get("isError") is True
    parsed = json.loads(res["content"][0]["text"])
    assert parsed["success"] is False


def test_mcp_tcp_range_safety_limit():
    # 192.168.1.0/23 = 512 hosts (> 256)
    res = call_tool("check_tcp_connectivity", {"host": "192.168.1.0/23", "port": "80"})
    assert res.get("isError") is True
    assert "exceeds safety limit" in res["content"][0]["text"]


def test_mcp_scan_port_safety_limit():
    ports = list(range(1, 1002))
    res = call_tool("scan_ports", {"host": "127.0.0.1", "ports": ports})
    assert res.get("isError") is True
    assert "safety limit of 1000 ports" in res["content"][0]["text"]
