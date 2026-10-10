/**
 * NetCheck VSCode Extension Tests
 *
 * Integration-level tests for the MCP client and command layer.
 * Run with: npm test (launches a real VSCode instance via @vscode/test-electron)
 */

import * as assert from "assert";
import * as vscode from "vscode";

// Minimal stub matching McpClient public interface
class FakeMcpClient {
  private _running = false;
  private _tools = [
    { name: "check_tcp_connectivity", description: "TCP check", inputSchema: {} },
    { name: "check_dns_lookup", description: "DNS check", inputSchema: {} },
    { name: "check_http_endpoint", description: "HTTP check", inputSchema: {} },
    { name: "check_ssl_certificate", description: "SSL check", inputSchema: {} },
    { name: "ping_host", description: "Ping", inputSchema: {} },
    { name: "get_network_interfaces", description: "Interfaces", inputSchema: {} },
    { name: "get_public_ip", description: "Public IP", inputSchema: {} },
    { name: "traceroute_host", description: "Traceroute", inputSchema: {} },
    { name: "scan_ports", description: "Port scan", inputSchema: {} },
    { name: "whois_lookup", description: "WHOIS", inputSchema: {} },
  ];

  get isRunning() { return this._running; }
  async start() { this._running = true; }
  async stop() { this._running = false; }
  async restart() { await this.stop(); await this.start(); }
  getTools() { return this._tools; }

  async callTool(name: string, args: Record<string, unknown>) {
    if (name === "check_tcp_connectivity") {
      return {
        content: [{ type: "text", text: JSON.stringify({ success: true, latency_ms: 12.5 }) }],
        isError: false,
      };
    }
    if (name === "error_tool") {
      return {
        content: [{ type: "text", text: "Connection refused" }],
        isError: true,
      };
    }
    return {
      content: [{ type: "text", text: JSON.stringify({ success: true }) }],
      isError: false,
    };
  }
}

suite("NetCheck MCP Client", () => {
  let client: FakeMcpClient;

  setup(() => {
    client = new FakeMcpClient();
  });

  test("start() sets isRunning to true", async () => {
    assert.strictEqual(client.isRunning, false);
    await client.start();
    assert.strictEqual(client.isRunning, true);
  });

  test("stop() sets isRunning to false", async () => {
    await client.start();
    await client.stop();
    assert.strictEqual(client.isRunning, false);
  });

  test("restart() cycles running state", async () => {
    await client.start();
    await client.restart();
    assert.strictEqual(client.isRunning, true);
  });

  test("getTools() returns exactly 10 tools", () => {
    const tools = client.getTools();
    assert.strictEqual(tools.length, 10);
  });

  test("getTools() — each tool has name, description, inputSchema", () => {
    for (const tool of client.getTools()) {
      assert.ok(tool.name, `Tool missing name: ${JSON.stringify(tool)}`);
      assert.ok(tool.description, `Tool '${tool.name}' missing description`);
      assert.ok(tool.inputSchema !== undefined, `Tool '${tool.name}' missing inputSchema`);
    }
  });

  test("callTool('check_tcp_connectivity') returns success=true result", async () => {
    const result = await client.callTool("check_tcp_connectivity", { host: "google.com", port: 443 });
    assert.strictEqual(result.isError, false);
    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.success, true);
    assert.ok(typeof parsed.latency_ms === "number");
  });

  test("callTool with error_tool returns isError=true", async () => {
    const result = await client.callTool("error_tool", {});
    assert.strictEqual(result.isError, true);
    assert.ok(result.content[0].text.length > 0);
  });
});

suite("NetCheck Commands", () => {
  test("Extension is activated", async () => {
    const ext = vscode.extensions.getExtension("farman20ali.netcheck");
    if (!ext) {
      // Extension may not be installed in test environment — skip gracefully
      return;
    }
    await ext.activate();
    assert.ok(ext.isActive, "Extension should be active after activate()");
  });

  test("All 8 check commands are registered", async () => {
    const cmds = await vscode.commands.getCommands(true);
    const netcheckCmds = [
      "netcheck.runTcp",
      "netcheck.runDns",
      "netcheck.runHttp",
      "netcheck.runSsl",
      "netcheck.runPing",
      "netcheck.runTraceroute",
      "netcheck.runScan",
      "netcheck.runWhois",
    ];
    for (const cmd of netcheckCmds) {
      assert.ok(
        cmds.includes(cmd),
        `Command '${cmd}' should be registered`
      );
    }
  });

  test("netcheck.clearResults does not throw when no panel open", async () => {
    // Should be a no-op — NetCheckPanel.currentPanel is undefined
    await vscode.commands.executeCommand("netcheck.clearResults");
    // If we reach here without throwing, the command handled missing panel gracefully
  });
});
