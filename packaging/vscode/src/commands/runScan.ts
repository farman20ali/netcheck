import * as vscode from "vscode";
import { McpClient } from "../mcp/client";
import { getHostOrPrompt, runCheck } from "./shared";

export function registerRunScan(
  context: vscode.ExtensionContext,
  client: McpClient
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.runScan", async () => {
      const host = await getHostOrPrompt(
        "Port scan — enter hostname or IP",
        "192.168.1.1",
        (v) => (v.trim() ? undefined : "Host is required")
      );
      if (!host) return;

      const portRange = await vscode.window.showInputBox({
        prompt: "Port range to scan",
        placeHolder: "1-1024",
        value: "1-1024",
        ignoreFocusOut: true,
        validateInput: (v) =>
          /^\d+(-\d+)?$/.test(v.trim()) ? undefined : "Enter a port range like 1-1024 or a single port",
      });
      if (portRange === undefined) return;

      const [startStr, endStr] = portRange.split("-");
      const startPort = parseInt(startStr, 10);
      const endPort = endStr ? parseInt(endStr, 10) : startPort;

      await runCheck(
        client,
        context.extensionUri,
        "Port Scan",
        `${host.trim()} (${portRange})`,
        "scan_ports",
        { host: host.trim(), start_port: startPort, end_port: endPort }
      );
    })
  );
}
