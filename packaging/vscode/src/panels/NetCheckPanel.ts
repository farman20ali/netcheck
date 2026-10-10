/**
 * NetCheck Webview Panel
 *
 * Renders check results as rich cards in a VSCode webview panel.
 * Accepts postMessage({ type: 'result', data: {...} }) from commands.
 */

import * as vscode from "vscode";

export interface CheckResult {
  checkType: string;
  target: string;
  success: boolean;
  latencyMs?: number;
  details: Record<string, unknown>;
  timestamp: string;
  error?: string;
}

export class NetCheckPanel {
  public static currentPanel: NetCheckPanel | undefined;
  private static readonly viewType = "netcheckResults";

  private readonly _panel: vscode.WebviewPanel;
  private _disposables: vscode.Disposable[] = [];
  private _results: CheckResult[] = [];

  // ── Factory ─────────────────────────────────────────────────────────

  static createOrShow(extensionUri: vscode.Uri): NetCheckPanel {
    const column = vscode.window.activeTextEditor
      ? vscode.ViewColumn.Beside
      : vscode.ViewColumn.One;

    if (NetCheckPanel.currentPanel) {
      NetCheckPanel.currentPanel._panel.reveal(column);
      return NetCheckPanel.currentPanel;
    }

    const panel = vscode.window.createWebviewPanel(
      NetCheckPanel.viewType,
      "NetCheck Results",
      column,
      {
        enableScripts: true,
        localResourceRoots: [vscode.Uri.joinPath(extensionUri, "out")],
        retainContextWhenHidden: true,
      }
    );

    NetCheckPanel.currentPanel = new NetCheckPanel(panel, extensionUri);
    return NetCheckPanel.currentPanel;
  }

  // ── Constructor ──────────────────────────────────────────────────────

  private constructor(
    panel: vscode.WebviewPanel,
    private readonly _extensionUri: vscode.Uri
  ) {
    this._panel = panel;
    this._update();

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    this._panel.webview.onDidReceiveMessage(
      (message: { command: string }) => {
        if (message.command === "clear") {
          this.clearResults();
        }
      },
      null,
      this._disposables
    );
  }

  // ── Public API ───────────────────────────────────────────────────────

  addResult(result: CheckResult): void {
    this._results.unshift(result); // newest first
    if (this._results.length > 100) {
      this._results = this._results.slice(0, 100); // cap at 100
    }
    this._panel.webview.postMessage({ type: "result", data: result });
    this._panel.title = result.success
      ? `✅ ${result.target}`
      : `❌ ${result.target}`;
  }

  clearResults(): void {
    this._results = [];
    this._panel.webview.postMessage({ type: "clear" });
    this._panel.title = "NetCheck Results";
  }

  reveal(): void {
    this._panel.reveal();
  }

  dispose(): void {
    NetCheckPanel.currentPanel = undefined;
    this._panel.dispose();
    while (this._disposables.length) {
      const x = this._disposables.pop();
      if (x) x.dispose();
    }
  }

  // ── HTML ─────────────────────────────────────────────────────────────

  private _update(): void {
    this._panel.webview.html = this._getHtmlForWebview();
  }

  private _getHtmlForWebview(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>NetCheck Results</title>
  <style>
    :root {
      --success: #4ec9b0;
      --failure: #f48771;
      --neutral: #888;
      --card-bg: var(--vscode-editor-background);
      --card-border: var(--vscode-panel-border);
      --text: var(--vscode-editor-foreground);
      --badge-radius: 4px;
      --font: var(--vscode-font-family, 'Segoe UI', sans-serif);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font);
      color: var(--text);
      padding: 12px;
      background: var(--vscode-sideBar-background);
    }
    #toolbar {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
      align-items: center;
    }
    #toolbar button {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border: none;
      padding: 4px 10px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }
    #toolbar button:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }
    #empty {
      text-align: center;
      color: var(--neutral);
      margin-top: 48px;
      font-size: 13px;
      line-height: 1.8;
    }
    #empty .icon { font-size: 32px; }
    #results { display: flex; flex-direction: column; gap: 10px; }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 10px 12px;
      animation: slideIn 0.2s ease;
      border-left: 3px solid var(--neutral);
    }
    .card.success { border-left-color: var(--success); }
    .card.failure { border-left-color: var(--failure); }

    @keyframes slideIn {
      from { opacity: 0; transform: translateY(-6px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .check-type {
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--neutral);
    }
    .status-badge {
      font-size: 11px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: var(--badge-radius);
    }
    .status-badge.up {
      background: rgba(78, 201, 176, 0.2);
      color: var(--success);
    }
    .status-badge.down {
      background: rgba(244, 135, 113, 0.2);
      color: var(--failure);
    }
    .target {
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 4px;
      word-break: break-all;
    }
    .meta {
      font-size: 11px;
      color: var(--neutral);
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 4px;
    }
    .meta .latency { color: var(--success); font-weight: 600; }
    .meta .latency.slow { color: #ffd700; }
    .meta .latency.very-slow { color: var(--failure); }
    .details-table {
      margin-top: 8px;
      font-size: 11px;
      border-collapse: collapse;
      width: 100%;
    }
    .details-table td {
      padding: 2px 4px;
      vertical-align: top;
    }
    .details-table td:first-child {
      color: var(--neutral);
      white-space: nowrap;
      padding-right: 10px;
      width: 40%;
    }
    .error-text {
      font-size: 11px;
      color: var(--failure);
      margin-top: 6px;
      word-break: break-word;
    }
  </style>
</head>
<body>
  <div id="toolbar">
    <span style="font-size:12px;font-weight:600;">NetCheck Results</span>
    <button onclick="clearResults()">🗑 Clear</button>
  </div>
  <div id="empty">
    <div class="icon">📡</div>
    <p>No results yet.</p>
    <p>Run a check via the Command Palette or right-click menu.</p>
  </div>
  <div id="results"></div>

  <script>
    const vscode = acquireVsCodeApi();

    function clearResults() {
      document.getElementById('results').innerHTML = '';
      document.getElementById('empty').style.display = '';
      vscode.postMessage({ command: 'clear' });
    }

    function latencyClass(ms) {
      if (!ms) return '';
      if (ms < 100) return '';
      if (ms < 500) return 'slow';
      return 'very-slow';
    }

    function renderDetails(details) {
      if (!details || Object.keys(details).length === 0) return '';
      const rows = Object.entries(details).map(([k, v]) => {
        const val = typeof v === 'object' ? JSON.stringify(v) : v;
        return '<tr><td>' + escapeHtml(k) + '</td><td>' + escapeHtml(String(val)) + '</td></tr>';
      }).join('');
      return '<table class="details-table"><tbody>' + rows + '</tbody></table>';
    }

    function escapeHtml(s) {
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function addCard(result) {
      document.getElementById('empty').style.display = 'none';
      const container = document.getElementById('results');
      const card = document.createElement('div');
      card.className = 'card ' + (result.success ? 'success' : 'failure');

      const lat = result.latencyMs;
      const latHtml = lat != null
        ? '<span class="latency ' + latencyClass(lat) + '">' + lat.toFixed(1) + ' ms</span>'
        : '';
      const tsFormatted = new Date(result.timestamp).toLocaleTimeString();

      card.innerHTML =
        '<div class="card-header">' +
          '<span class="check-type">' + escapeHtml(result.checkType) + '</span>' +
          '<span class="status-badge ' + (result.success ? 'up' : 'down') + '">' +
            (result.success ? '✅ UP' : '❌ DOWN') +
          '</span>' +
        '</div>' +
        '<div class="target">' + escapeHtml(result.target) + '</div>' +
        '<div class="meta">' + latHtml + '<span>' + tsFormatted + '</span></div>' +
        (result.error ? '<div class="error-text">⚠ ' + escapeHtml(result.error) + '</div>' : '') +
        renderDetails(result.details);

      container.prepend(card);
    }

    window.addEventListener('message', e => {
      const msg = e.data;
      if (msg.type === 'result') addCard(msg.data);
      else if (msg.type === 'clear') {
        document.getElementById('results').innerHTML = '';
        document.getElementById('empty').style.display = '';
      }
    });
  </script>
</body>
</html>`;
  }
}
