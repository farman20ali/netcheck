import * as vscode from "vscode";
import { McpClient } from "../mcp/client";
import { getHostOrPrompt, runCheck } from "./shared";

export function registerRunSsl(
  context: vscode.ExtensionContext,
  client: McpClient
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.runSsl", async () => {
      const hostname = await getHostOrPrompt(
        "SSL certificate check — enter hostname",
        "google.com",
        (v) => (v.trim() ? undefined : "Hostname is required")
      );
      if (!hostname) return;

      await runCheck(
        client,
        context.extensionUri,
        "SSL",
        hostname.trim(),
        "check_ssl_certificate",
        { hostname: hostname.trim() }
      );
    })
  );
}
