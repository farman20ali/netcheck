# NetCheck — VSCode Extension

Network diagnostics directly inside Visual Studio Code: TCP, DNS, HTTP, SSL, Ping, Traceroute, Port Scan, and WHOIS — powered by the [NetCheck MCP server](https://github.com/farman20ali/netcheck).

---

## Features

| Command | Shortcut | Description |
|---|---|---|
| **NetCheck: Test TCP Connectivity** | Palette / right-click | Connect to any host:port and measure latency |
| **NetCheck: DNS Lookup** | Palette / right-click | Resolve a hostname and show all DNS records |
| **NetCheck: HTTP Check** | Palette / right-click | Check HTTP/HTTPS response code, headers, TLS |
| **NetCheck: SSL Certificate** | Palette / right-click | Inspect cert chain, expiry, subject, issuer |
| **NetCheck: Ping Host** | Palette | ICMP ping with RTT stats |
| **NetCheck: Traceroute** | Palette | Hop-by-hop path to a host |
| **NetCheck: Port Scan** | Palette | Scan a port range on any host |
| **NetCheck: WHOIS Lookup** | Palette / right-click | Domain/IP registration info |

### Activity Bar Panel

Click the **NetCheck** icon (📡) in the left activity bar to open the **Results** panel. Each check renders a real-time card showing:

- ✅/❌ status badge  
- Latency in ms (color-coded: green < 100ms, yellow < 500ms, red > 500ms)  
- Timestamp  
- Full details table  
- Error message (if failed)

### Status Bar

A **NetCheck** status indicator appears in the bottom-left status bar:

- `$(sync~spin) NetCheck` — MCP server starting
- `$(radio-tower) NetCheck` — Ready
- `$(warning) NetCheck` — MCP server not running

### Right-Click in Editor

Highlight a hostname, URL, or IP in any file and right-click to run TCP, DNS, HTTP, SSL, or WHOIS checks instantly.

---

## Requirements

- **Python 3.10+** with `netcheckx` installed:
  ```bash
  pip install netcheckx
  ```
- Verify: `python -m netcheck --version`

---

## Extension Settings

| Setting | Default | Description |
|---|---|---|
| `netcheck.pythonPath` | `"python"` | Path to the Python interpreter with netcheck installed |
| `netcheck.defaultTimeout` | `5` | Network check timeout in seconds |
| `netcheck.showStatusBar` | `true` | Show NetCheck in the status bar |

Example `.vscode/settings.json`:
```json
{
  "netcheck.pythonPath": "/usr/local/bin/python3",
  "netcheck.defaultTimeout": 10
}
```

---

## Installation

### From Marketplace (once published)
1. Open the Extensions panel (`Ctrl+Shift+X`)
2. Search **NetCheck**
3. Click **Install**

### From VSIX (local/dev build)
```bash
cd packaging/vscode
npm install
npm run compile
npx vsce package
code --install-extension netcheck-2.5.0.vsix
```

---

## Development Setup

```bash
# Clone the repo
git clone https://github.com/farman20ali/netcheck.git
cd netcheck/packaging/vscode

# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Open in VSCode and press F5 to launch Extension Development Host
code .
```

### Project Structure

```
packaging/vscode/
├── src/
│   ├── extension.ts           # Entry point — registers all commands
│   ├── mcp/
│   │   └── client.ts          # JSON-RPC MCP client (child process)
│   ├── panels/
│   │   └── NetCheckPanel.ts   # Webview panel with result cards
│   └── commands/
│       ├── shared.ts          # getHostOrPrompt, runCheck helpers
│       ├── runTcp.ts
│       ├── runDns.ts
│       ├── runHttp.ts
│       ├── runSsl.ts
│       ├── runPing.ts
│       ├── runTraceroute.ts
│       ├── runScan.ts
│       └── runWhois.ts
├── test/
│   └── extension.test.ts      # MCP client + command tests
├── package.json
├── tsconfig.json
└── .vscodeignore
```

---

## How It Works

1. On extension activation, NetCheck spawns `python -m netcheck mcp` as a child process  
2. The MCP client sends JSON-RPC 2.0 `initialize`, then `tools/call` for each check  
3. Results stream back via stdout and render as cards in the webview panel  
4. The MCP process is killed on VSCode shutdown

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Status bar shows ⚠ | Run `pip install netcheckx` and restart VSCode |
| Wrong Python used | Set `netcheck.pythonPath` in settings |
| Ping fails on Linux | Ping requires root/CAP_NET_RAW — run VSCode with sudo or use TCP check instead |
| Extension not found | Install via VSIX or wait for Marketplace publish |

---

## Release

Published to the VS Code Marketplace as `farman20ali.netcheck`.  
CI automatically builds `.vsix` on each tag and publishes if `VSCODE_PAT` secret is set.

---

## License

MIT © [farman20ali](https://github.com/farman20ali)
