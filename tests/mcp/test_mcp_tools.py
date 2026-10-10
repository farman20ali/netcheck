"""
Unit tests for the NetCheck MCP tools registry and call dispatcher.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from netcheck.mcp.tools import call_tool, TOOLS_LIST


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
