import * as vscode from "vscode";
import { McpClient } from "../mcp/client";
import { getHostOrPrompt, runCheck } from "./shared";

export function registerRunTraceroute(
  context: vscode.ExtensionContext,
  client: McpClient
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.runTraceroute", async () => {
      const host = await getHostOrPrompt(
        "Traceroute — enter hostname or IP",
        "8.8.8.8",
        (v) => (v.trim() ? undefined : "Host is required")
      );
      if (!host) return;

      await runCheck(
        client,
        context.extensionUri,
        "Traceroute",
        host.trim(),
        "traceroute_host",
        { host: host.trim() }
      );
    })
  );
}
