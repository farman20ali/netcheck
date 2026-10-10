import json
import sys

from netcheck.mcp.tools import TOOLS_LIST, call_tool


def start_mcp_server():
    """
    Starts the MCP Server listening for JSON-RPC 2.0 messages on stdin
    and writing responses to stdout. Redirects other standard outputs to stderr.
    """
    # Configure stdin and stdout to use UTF-8 and line-buffering
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8')

    # Save original stdout for JSON-RPC messages
    original_stdout = sys.stdout

    # Redirect all standard prints to sys.stderr to prevent corrupting the JSON-RPC stream
    sys.stdout = sys.stderr

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            method = request.get("method")
            req_id = request.get("id")

            if method == "initialize":
                from netcheck import __version__
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "netcheck",
                            "version": __version__
                        }
                    }
                }

            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": TOOLS_LIST
                    }
                }
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})

                tool_res = call_tool(tool_name, tool_args)

                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": tool_res
                }
            elif method == "ping":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

            original_stdout.write(json.dumps(response) + "\n")
            original_stdout.flush()

        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
            original_stdout.write(json.dumps(response) + "\n")
            original_stdout.flush()
        except Exception as e:
            req_id = locals().get("req_id", None)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            original_stdout.write(json.dumps(response) + "\n")
            original_stdout.flush()

    # Restore stdout upon exit
    sys.stdout = original_stdout
