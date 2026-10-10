# Network Connectivity Checker (`netcheck`)

[![Version](https://img.shields.io/badge/version-2.4.0-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey.svg)](#)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](#)
[![Tests](https://img.shields.io/badge/tests-305%20passed-brightgreen.svg)](#)

A premium, cross-platform, production-grade **Network Intelligence Engine & CLI** written in pure Python 3. Zero external dependencies. High-concurrency diagnostics, structured output (JSON/CSV/XML), watch/loop mode, shell completions, man page, and an integrated **Model Context Protocol (MCP) Server** for AI assistants.

---

## 🚀 Key Features

- **Zero-Dependency Core** — Built entirely on the Python standard library. No `pip install` needed to run.
- **Cross-Platform** — Native support for Linux, macOS, and Windows with consistent terminal output.
- **11 Subcommands** — Modular `tcp`, `dns`, `http`, `ssl`, `ping`, `interfaces`, `traceroute`, `scan`, `whois`, `udp`, `mtr`.
- **Built-in Presets** — Quick batch checks of cloud endpoints (`aws`, `gcp`, `azure`, `cloudflare`, `github`, etc.).
- **Watch Mode** — Any subcommand loops with `--watch` and configurable `--interval`.
- **Structured Output** — Every check returns `--format text|json|csv|xml`.
- **No-Color Mode** — `--no-color` and `NO_COLOR` env var support for CI/CD pipelines.
- **MCP Server** — Turns `netcheck` into a local tool-server for Claude, ChatGPT, and other AI agents.
- **Lenient Parsing** — Accepts CSVs, URLs, bracketed IPv6, IP ranges (`192.168.1.1-50`), CIDR (`10.0.0.0/24`), port lists (`80,443`), port ranges (`8000-8100`), and `ip:port` notation.
- **Concurrent Batch Checks** — Configurable thread pools (`--jobs`, default 10) with real-time progress.
- **Environment Variables** — `NETCHECK_TIMEOUT`, `NETCHECK_MAX_WORKERS`, `NO_COLOR` for scripting.
- **Shell Completions** — Bash and Zsh tab completion for all subcommands and flags.
- **Man Page** — Full `man netcheck` documentation installed by `install.sh`.

---

## 📦 Installation

### Option 1: pipx — Linux / macOS ✅ Recommended
[`pipx`](https://pipx.pypa.io) installs CLI tools in isolated environments and **automatically handles PATH** — no manual setup needed.

```bash
# Install pipx if you don't have it
python3 -m pip install --user pipx
python3 -m pipx ensurepath          # adds ~/.local/bin to PATH (one-time)

# Then install netcheck
pipx install netcheckx
```

> After `ensurepath`, restart your terminal (or run `source ~/.bashrc`). Then:
> ```bash
> netcheck --help
> ```

---

### Option 1b: pip — Linux / macOS (alternative)
```bash
pip install netcheckx
```
> **Note:** Package name is `netcheckx` (to avoid PyPI conflict). Both `netcheck` and `netcheckx` commands work after install.

**If you see a PATH warning after install**, just run the bundled setup helper — it auto-patches your shell:
```bash
netcheck-setup        # auto-adds ~/.local/bin to ~/.bashrc, ~/.zshrc, ~/.profile
source ~/.bashrc      # reload shell
netcheck --help       # done ✅
```

> Or manually, if preferred:
> ```bash
> echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
> ```


### Option 2: Snap Store (Linux)
```bash
sudo snap install netcheck
sudo snap connect netcheck:network-observe   # enables ping & interfaces
```

### Option 3: Debian package (`.deb`)
```bash
sudo dpkg -i netcheck_2.4.0_amd64.deb
```

### Option 4: Chocolatey (Windows)
```powershell
choco install netcheck
```

### Option 5: macOS `.pkg`
```bash
sudo installer -pkg netcheck-2.4.0.pkg -target /
```

### Option 6: Linux installer (with shell completions + man page)
```bash
git clone https://github.com/farman20ali/netcheck.git
cd netcheck
sudo bash packaging/linux/install.sh
```

### Option 7: Developer / local run (no install)
```bash
git clone https://github.com/farman20ali/netcheck.git
cd netcheck
pip install -e ".[dev]"
python3 -m netcheck --help
```

---

## 🛠️ CLI Reference

### Subcommands

| Subcommand | Description | Example |
|---|---|---|
| `tcp` | TCP port reachability (ranges, CIDR, IP ranges) | `netcheck tcp google.com 80,443` |
| `dns` | DNS A/AAAA resolution + CNAME aliases | `netcheck dns github.com` |
| `http` | HTTP/HTTPS status, size, latency, redirects | `netcheck http https://google.com` |
| `ssl` | SSL certificate + TLS version/cipher/fingerprint | `netcheck ssl google.com -V` |
| `ping` | ICMP ping with min/avg/max RTT stats; IP ranges run concurrently | `netcheck ping 8.8.8.8` |
| `interfaces` | Active network interfaces + optional public IP (`--public`) | `netcheck interfaces --all --public` |
| `ports` | Local listening sockets with process/PID (Docker-aware) | `netcheck ports -f json` |
| `traceroute` | Hop-by-hop network path trace | `netcheck traceroute 8.8.8.8 -m 20` |
| `scan` | Concurrent TCP port scanner with service names | `netcheck scan 192.168.1.1 --ports 1-1024` |
| `whois` | RDAP/WHOIS domain or IP registration lookup | `netcheck whois google.com` |
| `udp` | UDP stateless port checker (interprets ICMP unreachable as CLOSED) | `netcheck udp 8.8.8.8 53` |
| `mtr` | MTR-style combined ping + traceroute latency trace | `netcheck mtr google.com` |
| `preset` | Expand a preconfigured list of hosts to check | `netcheck preset aws` |

### Watch Mode

Any subcommand can be looped with `--watch`:
```bash
netcheck tcp google.com 443 --watch --interval 2    # Refresh every 2s
netcheck http https://api.example.com -w -i 5        # Watch HTTP every 5s
netcheck dns github.com -w                           # Watch DNS (default 2s interval)
```
Press `Ctrl+C` to stop.

### HTTP Subcommand Options

```bash
netcheck http https://api.example.com \
  --method POST \
  -H "Authorization: Bearer token123" \
  -H "Accept: application/json" \
  --auth user:pass
```

| Flag | Description |
|---|---|
| `-X, --method` | HTTP method: `GET` (default), `HEAD`, `POST`, `PUT`, `DELETE`, `PATCH` |
| `-H, --header` | Custom header `Key: Value` (repeatable) |
| `--auth` | Basic auth `user:pass` |

### Interfaces / Public IP Options

```bash
netcheck interfaces                   # Show active interfaces only
netcheck interfaces --all             # Show all interfaces (including inactive)
netcheck interfaces --public          # Also fetch and display public WAN IP
netcheck --my-ip --public            # Legacy flag with public IP
```

### Output Filtering (`--show`)

```bash
netcheck tcp 192.168.1.1-50 22 --show success    # Only successful connections
netcheck tcp 10.0.0.0/24 443 --show fail         # Only failures
netcheck -q 192.168.1.1 80,443 --show success    # Legacy quick-mode filtering
```

### Global Flags

| Flag | Default | Description |
|---|---|---|
| `-t, --timeout` | `5` | Connection timeout in seconds |
| `-j, --jobs` | `10` | Concurrent thread pool size |
| `-f, --format` | `text` | Output format: `text`, `json`, `csv`, `xml` |
| `--json` | — | JSON output shorthand (alias for `-f json`) |
| `--show` | `all` | Filter results: `all`, `success`, or `fail` (for `tcp`/`-q`) |
| `--public` | — | Fetch and display public IP (for `interfaces`/`--my-ip`) |
| `--retry` | `1` | Number of connection attempts |
| `--retry-delay` | `1` | Delay between retries (seconds) |
| `-V, --verbose` | — | Show extended details (headers, SANs, cipher info) |
| `--no-color` | — | Disable ANSI color output |
| `-w, --watch` | — | Enable watch/loop mode |
| `-i, --interval` | `2.0` | Watch refresh interval in seconds |
| `--alert` | — | Comma-separated alert channels: `email`, `slack`, `webhook`, `desktop` |
| `--alert-on` | `any` | Which transitions fire alerts: `any`, `down`, `up` |
| `--alert-cooldown` | `60` | Seconds between repeated alerts per direction |
| `-v, --version` | — | Print version and exit |

### Environment Variables

| Variable | Effect |
|---|---|
| `NETCHECK_TIMEOUT` | Override default connection timeout (float) |
| `NETCHECK_MAX_WORKERS` | Override default thread pool size (integer) |
| `NO_COLOR` | Disable ANSI color output (standard, https://no-color.org/) |
| `NETCHECK_NO_COLOR` | Alternative for disabling color |

```bash
NETCHECK_TIMEOUT=10 NETCHECK_MAX_WORKERS=50 netcheck scan 192.168.1.1
NO_COLOR=1 netcheck ssl google.com -f json
```

### Legacy Flags (kept for backward compatibility)

| Legacy | Equivalent subcommand |
|---|---|
| `-q, --quick <host> <port>` | `netcheck tcp` |
| `-d, --dns <host>` | `netcheck dns` |
| `-p, --ping <host>` | `netcheck ping` (supports IP ranges, runs concurrently) |
| `-s, --status <url>` | `netcheck http` |
| `--cert <host>` | `netcheck ssl` |
| `--my-ip, -ip` | `netcheck interfaces` |
| `--public` | Adds public IP display (works with `-ip` and `interfaces`) |
| `--json` | JSON output shorthand (works with `-q` and `tcp`) |
| `--show all\|success\|fail` | Result filter (works with `-q` and `tcp`) |

---

## 🔍 Traceroute & Port Scan

### Traceroute
```bash
netcheck traceroute google.com             # Full path
netcheck traceroute 8.8.8.8 -m 15        # Limit to 15 hops
netcheck traceroute github.com -f json    # JSON output
```
Uses raw ICMP sockets if run as root; otherwise falls back to system `traceroute`/`tracepath` (Linux/macOS) or `tracert` (Windows).

### Port Scan
```bash
netcheck scan 192.168.1.1                  # Scan ~44 common ports
netcheck scan google.com --ports 80,443,8080
netcheck scan 10.0.0.1 --ports 1-1024 --jobs 100
```

### WHOIS / RDAP Lookup
```bash
netcheck whois google.com      # Domain registrar + creation date
netcheck whois 8.8.8.8         # IP network block + organization
```
Uses modern RDAP (HTTP JSON API) first; falls back to classic WHOIS port 43.

---

## 🤖 MCP Server

`netcheck` ships an integrated [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes all diagnostic functions to AI assistants.

```bash
netcheck --mcp
# or
python3 -m netcheck.mcp.server
```

**Claude Desktop `claude_desktop_config.json`:**
```json
{
  "mcpServers": {
    "netcheck": {
      "command": "python3",
      "args": ["-m", "netcheck.mcp.server"],
      "env": { "PYTHONPATH": "/path/to/netcheck" }
    }
  }
}
```

**Exposed MCP tools (v2.2.0):**

| Tool | Description |
|---|---|
| `check_tcp_connectivity` | TCP port reachability |
| `dns_lookup` | DNS A/AAAA resolution |
| `check_http_status` | HTTP response check |
| `check_ssl_certificate` | SSL certificate validation |
| `ping_host` | ICMP ping |
| `get_network_interfaces` | List local interfaces |
| `get_public_ip` | Get public IP |
| `traceroute` | Trace network path |
| `scan_ports` | TCP port scanner |
| `whois_lookup` | Domain/IP registration |

---

## 🏗️ Building Packages

All packaging is orchestrated by [`build_packages.py`](build_packages.py). Templates live in [`packaging/`](packaging/).

```
packaging/
├── chocolatey/        ← Windows Chocolatey (.nupkg)
│   └── tools/
├── linux/             ← install.sh / uninstall.sh / netcheck.1 / completions
├── macos/             ← macOS .pkg scripts
├── snap/              ← snapcraft.yaml template
└── windows/           ← NSIS installer script (.nsi)
```

### Common build commands

```bash
# Check available tools on this machine
python3 build_packages.py --check

# Sync a new version across all config files
python3 build_packages.py --sync-version 2.3.0

# Build all packages for the current OS
python3 build_packages.py --all

# Individual targets
python3 build_packages.py --pypi      # wheel + sdist
python3 build_packages.py --deb       # Debian .deb
python3 build_packages.py --snap      # Snap .snap
python3 build_packages.py --win       # Windows .exe + NSIS + Chocolatey
python3 build_packages.py --mac       # macOS binary + .pkg
```

---

## 🔧 Shell Completions

### Bash
```bash
# System-wide (requires root)
sudo cp packaging/linux/netcheck.bash-completion /etc/bash_completion.d/netcheck

# Per-user
mkdir -p ~/.local/share/bash-completion/completions
cp packaging/linux/netcheck.bash-completion ~/.local/share/bash-completion/completions/netcheck
```

### Zsh
```bash
mkdir -p ~/.zsh/completions
cp packaging/linux/netcheck.zsh-completion ~/.zsh/completions/_netcheck
# Add to ~/.zshrc:
echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
echo 'autoload -U compinit && compinit' >> ~/.zshrc
```

The installer script (`packaging/linux/install.sh`) does all of this automatically.

## ⚙️ Alerting, Config & Prometheus (`serve`)

NetCheck features a robust, zero-dependency configuration, alerting, and Prometheus metrics engine.

### 1. Configuration Manager

Configure SMTP, Slack, Webhooks, and default check timeouts safely:
```bash
netcheck config init          # Run interactive wizard to generate config
netcheck config show          # Print current configuration + OS keychain status
netcheck config path          # Print path to config.yaml file
netcheck config edit          # Open config.yaml in your local $EDITOR
netcheck config purge         # Delete config.yaml AND wipe all keychain secrets
```

**Credential Safety (System Keychain):**
All sensitive credentials are stored in the OS credential manager (Keychain on macOS, Credential Manager on Windows, GNOME Keyring/KWallet on Linux). `config.yaml` never stores secrets.
```bash
netcheck config set-password email      # SMTP app-password
netcheck config set-password smtp_user  # SMTP sender address
netcheck config set-password smtp_to    # SMTP recipient address(es)
netcheck config set-password slack      # Slack incoming webhook URL
netcheck config set-password webhook    # Generic webhook bearer token
netcheck config clear-password email    # Remove a specific keychain entry
```

**Test your alert channels instantly:**
```bash
netcheck config test-alert email      # Send a real test email now
netcheck config test-alert slack      # Post a test Slack message now
netcheck config test-alert desktop    # Trigger a test desktop notification
netcheck config test-alert webhook    # POST a test webhook payload
```

### 2. Alerting Engine

Trigger alerts on state **changes** (UP ⇄ DOWN transition) during watch or serve loops. This prevents alert storms from repeated failures.

Supported channels:
- **SMTP Email** — STARTTLS with Gmail App Password support; OS keychain credential lookup
- **Slack** — incoming webhook URL stored securely in OS keychain
- **Generic Webhook** — JSON POST with Bearer token stored in keychain and `{target}` template substitution
- **Desktop Notifications** — WinRT Action Center (Windows 10/11), `osascript` (macOS), `notify-send` (Linux)

**Alert flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--alert` | — | Comma-separated channels: `email`, `slack`, `webhook`, `desktop` |
| `--alert-on` | `any` | Which transitions fire alerts: `any`, `down`, `up` |
| `--alert-cooldown` | `60` | Minimum seconds between alerts **per direction** |

**Usage Examples:**
```bash
# Alert via email and Slack on any TCP state change
netcheck tcp api.example.com 443 -w --alert email,slack

# Only alert when a target goes DOWN (suppress UP/recovery alerts)
netcheck tcp api.example.com 443 -w --alert slack --alert-on down

# Alert on recovery only, via desktop notification
netcheck http https://api.example.com -w --alert desktop --alert-on up

# Alert via desktop notifications on DNS changes, 5-minute cooldown
netcheck dns google.com -w --alert desktop --alert-cooldown 300
```

#### 🧪 How to Test Alerts Locally
1. Run the interactive config wizard and configure your alerting channels (e.g., Slack Webhook or Desktop):
   ```bash
   netcheck config init
   ```
2. In Terminal A, start watching a local port with alerts enabled:
   ```bash
   netcheck tcp localhost 9999 -w --alert slack,desktop --interval 2
   ```
   *(NetCheck initially records the baseline state silently.)*
3. In Terminal B, simulate a service going **UP** by starting a quick local listener:
   * **Linux/macOS:** `nc -lk 9999`
   * **Windows (PowerShell):**
     ```powershell
     $listener = [System.Net.Sockets.TcpListener]9999; $listener.Start()
     ```
   NetCheck will register `localhost:9999` as **UP**.
4. Simulate a service going **DOWN** by killing the listener in Terminal B (`Ctrl+C` or `$listener.Stop()`).
   NetCheck will detect the state change and immediately trigger a **DOWN** alert to Slack and Desktop:
   > ❌ **Alert: localhost:9999 is DOWN** (Connection refused)
5. Restart the listener in Terminal B. NetCheck will detect the recovery and emit a **RECOVERED** alert:
   > ✅ **Alert: localhost:9999 is back UP**

---

### 3. Prometheus Metrics Exporter (`serve` mode)

Run `netcheck` as a background daemon monitoring multiple targets and serving `/metrics` in the Prometheus text exposition format.

```bash
# Monitor hosts from a file and serve metrics on port 9090
netcheck serve --metrics --port 9090 hosts.txt
```

Exposed Metrics:
- `netcheck_scrape_count` (Counter)
- `netcheck_check_total{target, check_type}` (Counter)
- `netcheck_check_failures_total{target, check_type}` (Counter)
- `netcheck_latency_seconds{target, check_type}` (Gauge)
- `netcheck_up{target}` (Gauge, 1 = UP, 0 = DOWN)
- `netcheck_uptime_ratio{target, check_type}` (Gauge, 0.0 - 1.0 ratio)

#### 📡 How to Integrate with Prometheus
1. Create a `targets.txt` file containing your endpoints:
   ```text
   google.com:443
   github.com:443
   127.0.0.1:80
   ```
2. Start the NetCheck daemon:
   ```bash
   netcheck serve --metrics --port 9090 targets.txt --interval 10
   ```
3. Verify that the metrics endpoint is outputting valid text format:
   ```bash
   curl http://localhost:9090/metrics
   ```
4. Add the job to your `prometheus.yml` configuration:
   ```yaml
   scrape_configs:
     - job_name: 'netcheck'
       scrape_interval: 10s
       static_configs:
         - targets: ['localhost:9090']
   ```
5. You can now build Grafana dashboards or Alertmanager rules based on the `netcheck_up` metric:
   ```yaml
   # Alertmanager rule example
   groups:
     - name: netcheck_alerts
       rules:
         - alert: EndpointDown
           expr: netcheck_up == 0
           for: 1m
           labels:
             severity: page
           annotations:
             summary: "Endpoint {{ $labels.target }} is offline"
   ```

---

## ⚙️ CI/CD Integration

All subcommands produce **machine-readable structured JSON** output when `-f json` is set. Use this to build health-gate scripts, monitoring alerts, or GitHub Actions checks:

```bash
# Check if a TCP port is open — fail the step if not
netcheck tcp prod.example.com 443 -f json | python3 -c \
  "import sys, json; d=json.load(sys.stdin); sys.exit(0 if d['results'][0]['status']=='success' else 1)"

# Extract DNS IPs with jq
netcheck dns api.example.com -f json | jq '.ips[]'

# List open ports as JSON array
netcheck scan 192.168.1.1 --ports 1-1024 -f json | jq '.open_ports[] | {port, service}'

# Get SSL days-until-expiry, alert if < 30
netcheck ssl prod.example.com -f json | jq -e '.days_until_expiry > 30'

# Traceroute hop count for latency monitoring
netcheck traceroute 8.8.8.8 -f json | jq '.hops | length'

# Listening ports as CSV for spreadsheet import
netcheck ports -f csv > listening_ports.csv

# Use NO_COLOR to suppress ANSI in logs
NO_COLOR=1 netcheck tcp prod.example.com 443

# Override timeout and workers for fast CI checks
NETCHECK_TIMEOUT=3 NETCHECK_MAX_WORKERS=50 netcheck scan 10.0.0.1 --ports 80,443,8080 -f json
```

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | All checks succeeded |
| `1` | One or more checks failed |
| `2` | Argument / usage error |

---

## 🧪 Running Tests

```bash
# Using Make
make test

# Using pytest directly
PYTHONPATH=. python3 -m pytest tests/ -v

# With coverage
PYTHONPATH=. python3 -m pytest tests/ --cov=netcheck --cov-report=term-missing
```

---

## 📁 Repository Structure

```
netcheck/
├── netcheck/                  ← Python package
│   ├── __init__.py            ← version string
│   ├── __main__.py            ← python3 -m netcheck entry point
│   ├── cli.py                 ← CLI argument parsing & dispatch
│   ├── mcp/                   ← MCP server + tool definitions
│   ├── modules/               ← dns, tcp, http, ssl, ping, interfaces,
│   │                             traceroute, port_scanner, whois
│   └── utils/                 ← formatters, retry, concurrency, services
├── packaging/                 ← Platform packaging templates
│   ├── chocolatey/
│   ├── linux/                 ← install.sh, netcheck.1, bash/zsh completions
│   ├── macos/
│   ├── snap/
│   └── windows/
├── tests/                     ← pytest test suite (305 tests)
├── docs/                      ← Guides and release notes
├── .github/workflows/         ← CI (ci.yml) + Release (release.yml)
├── build_packages.py          ← Build orchestration script
├── pyproject.toml             ← Package metadata & build config
├── python-requirements.txt    ← Local dev setup shortcut
└── Makefile                   ← make install / test / clean
```

---

## 🛡️ License

Distributed under the **GNU General Public License v3 (GPL-3.0)**. See [`LICENSE`](LICENSE) for details.
