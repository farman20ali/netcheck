import * as vscode from "vscode";
import { McpClient } from "../mcp/client";
import { getHostOrPrompt, runCheck } from "./shared";

export function registerRunWhois(
  context: vscode.ExtensionContext,
  client: McpClient
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.runWhois", async () => {
      const domain = await getHostOrPrompt(
        "WHOIS — enter domain or IP",
        "example.com",
        (v) => (v.trim() ? undefined : "Domain or IP is required")
      );
      if (!domain) return;

      await runCheck(
        client,
        context.extensionUri,
        "WHOIS",
        domain.trim(),
        "whois_lookup",
        { domain: domain.trim() }
      );
    })
  );
}
