import * as vscode from "vscode";
import { McpClient } from "../mcp/client";
import { getHostOrPrompt, runCheck } from "./shared";

export function registerRunHttp(
  context: vscode.ExtensionContext,
  client: McpClient
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.runHttp", async () => {
      const url = await getHostOrPrompt(
        "HTTP check — enter URL",
        "https://example.com",
        (v) =>
          v.trim().startsWith("http")
            ? undefined
            : "URL must start with http:// or https://"
      );
      if (!url) return;

      await runCheck(
        client,
        context.extensionUri,
        "HTTP",
        url.trim(),
        "check_http_endpoint",
        { url: url.trim() }
      );
    })
  );
}
