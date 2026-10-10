"""
MCP CLI Commands for NetCheck.

Implements `netcheck mcp install` and `netcheck mcp status`.
"""
import json
import os
import subprocess
import sys


def get_claude_config_path() -> str:
    """Return the platform-specific path to Claude Desktop's configuration file."""
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return os.path.join(appdata, "Claude", "claude_desktop_config.json")
    elif sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    return ""


def cmd_mcp_install() -> None:
    """
    Print Claude Desktop config snippet and instructions.
    Tries to detect and show the path to the user's Claude config file.
    """
    # Attempt to locate executable path or python package command
    python_exe = sys.executable or "python"

    snippet = {
        "mcpServers": {
            "netcheck": {
                "command": python_exe,
                "args": ["-m", "netcheck", "mcp"]
            }
        }
    }

    config_path = get_claude_config_path()

    print("=== NetCheck MCP Server Claude Desktop Installation ===")
    print("\nTo integrate NetCheck with Claude Desktop, add the following configuration")
    print("snippet to your `claude_desktop_config.json` file:\n")
    print(json.dumps(snippet, indent=2))
    print("\n-------------------------------------------------------")

    if config_path:
        print(f"Detected configuration file path:\n  {config_path}\n")
        if os.path.exists(config_path):
            print("Status: File exists. Open it and merge the 'netcheck' server configuration.")
        else:
            print("Status: File does not exist yet. You can create it with the snippet above.")
    else:
        print("Note: Claude Desktop configuration path not detected for this platform.")
        print("Standard paths:")
        print("  - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json")
        print("  - Windows: %APPDATA%\\Claude\\claude_desktop_config.json")

    print("\nEnsure the Python environment where netcheck is installed is accessible.")
    print("=======================================================")


def cmd_mcp_status() -> None:
    """
    Check the health of the MCP server.
    Spawns the local MCP server in a subprocess, runs a JSON-RPC 'initialize' exchange,
    and reports status.
    """
    print("Checking NetCheck MCP Server health...")

    # Spawn the server in a subprocess
    python_exe = sys.executable or "python"
    cmd = [python_exe, "-m", "netcheck", "mcp"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except Exception as exc:
        print(f"❌ Failed to spawn NetCheck MCP subprocess: {exc}")
        sys.exit(1)

    # Prepare initialize request
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "netcheck-status-checker",
                "version": "1.0"
            }
        }
    }

    try:
        # Write request to stdin, read stdout
        stdout_data, stderr_data = proc.communicate(
            input=json.dumps(init_request) + "\n",
            timeout=5.0
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        print("❌ Timeout: MCP Server did not respond within 5 seconds.")
        sys.exit(1)
    except Exception as exc:
        proc.kill()
        print(f"❌ Communication error with MCP Server: {exc}")
        sys.exit(1)

    if proc.returncode is not None and proc.returncode != 0:
        print(f"❌ MCP Server exited with non-zero code {proc.returncode}.")
        if stderr_data:
            print(f"Error output:\n{stderr_data.strip()}")
        sys.exit(1)

    # Parse response
    lines = [line.strip() for line in stdout_data.splitlines() if line.strip()]
    if not lines:
        print("❌ MCP Server did not return any JSON-RPC response.")
        if stderr_data:
            print(f"Error output:\n{stderr_data.strip()}")
        sys.exit(1)

    try:
        response = json.loads(lines[0])
    except json.JSONDecodeError:
        print(f"❌ Failed to parse JSON-RPC response. Received raw output:\n{stdout_data}")
        sys.exit(1)

    # Check for expected properties
    if "error" in response:
        print(f"❌ MCP Server returned an error response:\n{json.dumps(response['error'], indent=2)}")
        sys.exit(1)

    result = response.get("result", {})
    server_info = result.get("serverInfo", {})
    server_name = server_info.get("name")
    server_version = server_info.get("version")

    if server_name == "netcheck":
        print("✅ Success: NetCheck MCP Server is HEALTHY.")
        print(f"   Name:    {server_name}")
        print(f"   Version: {server_version}")
    else:
        print(f"❌ Response matched protocol but server name was '{server_name}' instead of 'netcheck'.")
        sys.exit(1)
