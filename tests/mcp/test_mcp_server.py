"""
Unit tests for the NetCheck MCP server protocol and messaging.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from netcheck.mcp.server import start_mcp_server


@patch("sys.stdin")
@patch("sys.stdout")
def test_mcp_server_initialize(mock_stdout, mock_stdin):
    # Mock inputs
    mock_stdin.__iter__.return_value = [
        json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {"protocolVersion": "2024-11-05"}
        }) + "\n"
    ]

    original_writes = []
    def mock_write(data):
        original_writes.append(data)
    mock_stdout.write.side_effect = mock_write

    start_mcp_server()

    assert len(original_writes) > 0
    resp = json.loads(original_writes[0].strip())
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "netcheck"


@patch("sys.stdin")
@patch("sys.stdout")
def test_mcp_server_tools_list(mock_stdout, mock_stdin):
    mock_stdin.__iter__.return_value = [
        json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2
        }) + "\n"
    ]

    original_writes = []
    mock_stdout.write.side_effect = lambda data: original_writes.append(data)

    start_mcp_server()

    assert len(original_writes) > 0
    resp = json.loads(original_writes[0].strip())
    assert resp["id"] == 2
    assert "tools" in resp["result"]
    assert any(t["name"] == "check_tcp_connectivity" for t in resp["result"]["tools"])


@patch("sys.stdin")
@patch("sys.stdout")
def test_mcp_server_ping(mock_stdout, mock_stdin):
    mock_stdin.__iter__.return_value = [
        json.dumps({
            "jsonrpc": "2.0",
            "method": "ping",
            "id": 3
        }) + "\n"
    ]

    original_writes = []
    mock_stdout.write.side_effect = lambda data: original_writes.append(data)

    start_mcp_server()

    assert len(original_writes) > 0
    resp = json.loads(original_writes[0].strip())
    assert resp["id"] == 3
    assert resp["result"] == {}
