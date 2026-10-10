import * as vscode from "vscode";
import { McpClient } from "../mcp/client";
import { getHostOrPrompt, runCheck } from "./shared";

export function registerRunDns(
  context: vscode.ExtensionContext,
  client: McpClient
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.runDns", async () => {
      const hostname = await getHostOrPrompt(
        "DNS lookup — enter hostname",
        "google.com",
        (v) => (v.trim() ? undefined : "Hostname is required")
      );
      if (!hostname) return;

      await runCheck(
        client,
        context.extensionUri,
        "DNS",
        hostname.trim(),
        "check_dns_lookup",
        { hostname: hostname.trim() }
      );
    })
  );
}
