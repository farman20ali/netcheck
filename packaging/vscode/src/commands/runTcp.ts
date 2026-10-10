import * as vscode from "vscode";
import { McpClient } from "../mcp/client";
import { getHostOrPrompt, runCheck } from "./shared";

export function registerRunTcp(
  context: vscode.ExtensionContext,
  client: McpClient
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.runTcp", async () => {
      const input = await getHostOrPrompt(
        "TCP check — enter host (and optionally :port)",
        "google.com:443",
        (v) => (v.trim() ? undefined : "Host is required")
      );
      if (!input) return;

      let host = input.trim();
      let port = 80;

      const match = host.match(/^(.+):(\d+)$/);
      if (match) {
        host = match[1];
        port = parseInt(match[2], 10);
      } else {
        const portStr = await vscode.window.showInputBox({
          prompt: "Port number",
          placeHolder: "443",
          value: "443",
          validateInput: (v) =>
            /^\d+$/.test(v) && +v > 0 && +v < 65536
              ? undefined
              : "Enter a valid port (1–65535)",
        });
        if (portStr === undefined) return;
        port = parseInt(portStr, 10);
      }

      await runCheck(
        client,
        context.extensionUri,
        "TCP",
        `${host}:${port}`,
        "check_tcp_connectivity",
        { host, port }
      );
    })
  );
}
