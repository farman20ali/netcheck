/**
 * Shared helpers for all NetCheck commands.
 *
 * Provides: host/URL extraction from editor selection, progress wrapper,
 * result formatting, and error surfacing.
 */

import * as vscode from "vscode";
import { McpClient, McpCallResult } from "../mcp/client";
import { NetCheckPanel, CheckResult } from "../panels/NetCheckPanel";

// ── Text extraction ──────────────────────────────────────────────────────

/**
 * Return the current editor selection text (trimmed), or prompt the user.
 */
export async function getHostOrPrompt(
  prompt: string,
  placeholder: string,
  validate?: (v: string) => string | undefined
): Promise<string | undefined> {
  const editor = vscode.window.activeTextEditor;
  const selection = editor?.document.getText(editor.selection).trim();
  if (selection && selection.length > 0 && selection.length < 256) {
    return selection;
  }
  return vscode.window.showInputBox({
    prompt,
    placeHolder: placeholder,
    ignoreFocusOut: true,
    validateInput: validate,
  });
}

// ── Result conversion ─────────────────────────────────────────────────────

export function parseResult(
  checkType: string,
  target: string,
  raw: McpCallResult
): CheckResult {
  const text = raw.content?.[0]?.text ?? "{}";
  let parsed: Record<string, unknown> = {};
  try {
    parsed = JSON.parse(text);
  } catch {
    parsed = { raw: text };
  }

  const success = !raw.isError && parsed["success"] !== false;
  const latencyMs =
    typeof parsed["latency_ms"] === "number"
      ? (parsed["latency_ms"] as number)
      : undefined;
  const errorMsg =
    raw.isError
      ? text
      : typeof parsed["error"] === "string"
      ? (parsed["error"] as string)
      : undefined;

  // Remove noisy top-level fields that are surfaced elsewhere
  const details = { ...parsed };
  delete details["success"];
  delete details["error"];
  delete details["latency_ms"];

  return {
    checkType,
    target,
    success,
    latencyMs,
    details,
    timestamp: new Date().toISOString(),
    error: errorMsg,
  };
}

// ── Command runner ────────────────────────────────────────────────────────

export async function runCheck(
  client: McpClient,
  extensionUri: vscode.Uri,
  checkType: string,
  target: string,
  toolName: string,
  args: Record<string, unknown>
): Promise<void> {
  const panel = NetCheckPanel.createOrShow(extensionUri);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: `NetCheck: ${checkType} → ${target}`,
      cancellable: false,
    },
    async () => {
      try {
        if (!client.isRunning) {
          await client.start();
        }
        const raw = await client.callTool(toolName, args);
        const result = parseResult(checkType, target, raw);
        panel.addResult(result);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        const result: CheckResult = {
          checkType,
          target,
          success: false,
          details: {},
          timestamp: new Date().toISOString(),
          error: errMsg,
        };
        panel.addResult(result);
        vscode.window.showErrorMessage(`NetCheck error: ${errMsg}`);
      }
    }
  );
}
