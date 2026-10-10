/**
 * NetCheck VSCode Extension — Entry Point
 *
 * Registers all commands, starts the MCP server subprocess,
 * and manages the activity bar panel + status bar item.
 */

import * as vscode from "vscode";
import { getClient, resetClient } from "./mcp/client";
import { NetCheckPanel } from "./panels/NetCheckPanel";
import { registerRunTcp } from "./commands/runTcp";
import { registerRunDns } from "./commands/runDns";
import { registerRunHttp } from "./commands/runHttp";
import { registerRunSsl } from "./commands/runSsl";
import { registerRunPing } from "./commands/runPing";
import { registerRunTraceroute } from "./commands/runTraceroute";
import { registerRunScan } from "./commands/runScan";
import { registerRunWhois } from "./commands/runWhois";
import { ensureNetcheckInstalled } from "./installer";

let statusBarItem: vscode.StatusBarItem | undefined;

// ── Activation ─────────────────────────────────────────────────────────────

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const client = getClient(context);

  // Status bar
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBarItem.text = "$(radio-tower) NetCheck";
  statusBarItem.tooltip = "Click to open NetCheck panel";
  statusBarItem.command = "netcheck.openPanel";
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // Register all check commands
  registerRunTcp(context, client);
  registerRunDns(context, client);
  registerRunHttp(context, client);
  registerRunSsl(context, client);
  registerRunPing(context, client);
  registerRunTraceroute(context, client);
  registerRunScan(context, client);
  registerRunWhois(context, client);

  // Open panel command
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.openPanel", () => {
      NetCheckPanel.createOrShow(context.extensionUri);
    })
  );

  // Clear results command
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.clearResults", () => {
      NetCheckPanel.currentPanel?.clearResults();
    })
  );

  // Restart MCP server command
  context.subscriptions.push(
    vscode.commands.registerCommand("netcheck.restartMcp", async () => {
      setStatusBarState("loading");
      try {
        await client.restart();
        setStatusBarState("ready");
        vscode.window.showInformationMessage("NetCheck: MCP server restarted.");
      } catch (err) {
        setStatusBarState("error");
        vscode.window.showErrorMessage(
          `NetCheck: Failed to restart MCP server — ${err instanceof Error ? err.message : err}`
        );
      }
    })
  );

  // Auto-install netcheckx if needed, then start MCP server in background
  activateWithInstall(context, client);
}

// ── Deactivation ───────────────────────────────────────────────────────────

export function deactivate(): void {
  resetClient();
}

// ── Helpers ────────────────────────────────────────────────────────────────

async function activateWithInstall(
  context: vscode.ExtensionContext,
  client: ReturnType<typeof getClient>
): Promise<void> {
  // Step 1: ensure netcheckx is installed at the required version
  const ready = await ensureNetcheckInstalled(context);

  // Step 2: start MCP server regardless (user may fix path manually)
  await startMcpSilently(client);

  if (ready) {
    console.log("[NetCheck] Activated successfully.");
  }
}

async function startMcpSilently(client: ReturnType<typeof getClient>): Promise<void> {
  try {
    setStatusBarState("loading");
    await client.start();
    setStatusBarState("ready");
  } catch (err) {
    setStatusBarState("error");
    console.warn(
      "[NetCheck] MCP server failed to start automatically:",
      err instanceof Error ? err.message : err
    );
    // Don't show an error popup — the user may not have netcheck installed yet.
    // Commands will show a proper error when triggered.
  }
}

type StatusState = "loading" | "ready" | "error";

function setStatusBarState(state: StatusState): void {
  if (!statusBarItem) return;
  switch (state) {
    case "loading":
      statusBarItem.text = "$(sync~spin) NetCheck";
      statusBarItem.tooltip = "NetCheck: Starting MCP server…";
      break;
    case "ready":
      statusBarItem.text = "$(radio-tower) NetCheck";
      statusBarItem.tooltip = "NetCheck: Ready. Click to open panel.";
      break;
    case "error":
      statusBarItem.text = "$(warning) NetCheck";
      statusBarItem.tooltip =
        "NetCheck: MCP server not running. Run 'pip install netcheckx' and restart.";
      break;
  }
}
