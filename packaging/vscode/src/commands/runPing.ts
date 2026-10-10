import * as vscode from "vscode";
import { McpClient } from "../mcp/client";
import { getHostOrPrompt, runCheck } from "./shared";

export function registerRunPing(
  context: vscode.ExtensionContext,
  client: McpClient
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.runPing", async () => {
      const host = await getHostOrPrompt(
        "Ping — enter hostname or IP",
        "8.8.8.8",
        (v) => (v.trim() ? undefined : "Host is required")
      );
      if (!host) return;

      await runCheck(
        client,
        context.extensionUri,
        "Ping",
        host.trim(),
        "ping_host",
        { host: host.trim() }
      );
    })
  );
}
