# Changelog

All notable changes to netcheck will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0] - 2026-08-26

### Added
- **OS Keychain Credential Storage**: All sensitive alerting credentials (SMTP password, SMTP sender, SMTP recipients, Slack webhook URL, generic webhook bearer token) are now stored in the OS credential manager (Windows Credential Manager, macOS Keychain, GNOME Keyring/KWallet) via the `keyring` library. `config.yaml` no longer stores any secrets.
- **`config purge`**: Wipes `config.yaml` and clears all five keyring secrets in one command — useful for machine decommission or full credential rotation.
- **`config test-alert <channel>`**: Fires a real test alert immediately to `email`, `slack`, `desktop`, or `webhook` without running a watch loop. Reports `SUCCESS` or `FAILED` with full error output.
- **`config show` keyring panel**: Displays both YAML config values and OS keyring status side-by-side with masked credential previews (e.g. `se...@gmail.com`).
- **Directional alert cooldowns**: UP and DOWN cooldown timers are now tracked independently per target so that recovery and re-failure alerts are never incorrectly suppressed by a cross-direction cooldown.
- **`--alert-on` flag**: Filter which state transitions trigger alerts — `any` (default), `down`, or `up`.
- **Native desktop notifications**: `--alert desktop` uses WinRT Action Center toasts on Windows 10/11 (PowerShell fallback to balloon tip), `osascript` on macOS, and `notify-send` on Linux, with optional `plyer` support.
- **Watch mode rolling alert log**: A persistent "Recent Alerts & Logs" panel (up to 8 entries) is rendered at the bottom of the watch window so screen refreshes no longer erase alert history.
- **Watch loop resilience**: `SystemExit` raised by subcommands (e.g. `traceroute`) is now caught inside the watch loop so the loop continues uninterrupted.
- **Legacy single-dash option normalisation**: `-tcp`, `-udp`, `-mtr`, `-dns`, `-http`, `-ssl`, `-ping`, `-scan`, `-whois` are normalised to their subcommand equivalents at the CLI entry point.
- **6 new unit tests** in `test_alerting.py`: directional cooldown correctness, `alert_on` filter all three modes, keyring getter mocking.
- **8 new unit tests** in `test_config.py`: `purge()`, `show()` keyring display formatting, `get_smtp_user()`, `get_smtp_to()`.

### Fixed
- **SMTP `SMTPAuthenticationError` / header accumulation bug**: Rewrote `send_email_alert` to use `smtp.send_message()` (instead of `smtp.sendmail()`) and `del msg["To"]` before each recipient, matching the proven reference implementation. Multi-recipient sends now reuse a single SMTP connection.

### Changed
- `--alert-cooldown` default reduced from 300 s to 60 s to be more responsive in desktop/development usage.
- `config show` output extended with a "Keyring / Secure Store" section showing all five credential statuses.

## [2.3.0] - 2026-07-30

### Added
- **Public IP Resolution** (`--public` flag):
  - `interfaces` subcommand and legacy `--my-ip` flag now accept `--public` to fetch and display the public (WAN) IP address.
  - Concurrent multi-API race strategy: queries `ipify.org`, `checkip.amazonaws.com`, `icanhazip.com`, and `ifconfig.me` in parallel and returns the first valid response.
  - `public_ip_checked` field added to JSON output (`-f json`).
- **Output Filtering** (`--show` flag):
  - `--show all|success|fail` filters result output for batch `tcp` and legacy `-q`/`--quick` checks.
  - Works in all output formats (text, JSON, CSV, XML).
- **`--json` flag alias**:
  - Shorthand for `-f json` in legacy and quick-mode; cleaner for CI pipelines and `jq` piping.
- **Concurrent Ping for IP Ranges**:
  - `-p` / `--ping` now expands IP ranges (`192.168.1.1-20`, CIDR) and dispatches all pings concurrently via a thread pool.
  - Multi-ping JSON output uses a typed envelope (`"type": "ping"`, `"count"`, `"results": [...]`).
  - Results sorted by target IP for deterministic output.
- **Typed Result Envelopes** — all diagnostic modules now include `"type"` in their result dict:
  - `dns`, `http`, `ssl`, `ping`, `tcp`, `interfaces`, `ports`, `traceroute`, `scan`, `whois`.
- **Unified `_detect_result_type()` helper** in `formatters.py`:
  - Single authoritative dispatch path for JSON/CSV/XML formatting.
  - Reads `"type"` key first; falls back to metadata heuristics for backward compatibility.
- **Expanded Test Suite** — 8 new tests:
  - `test_my_ip_with_public`, `test_subcommand_interfaces_with_public` — `--public` flag coverage.
  - `test_quick_flag_invalid_args` — validates `-q`/`--quick` requires exactly 2 arguments.
  - `test_ping_flag_ip_range` — concurrent ping range dispatch.
  - `test_ping_range_json_format` — multi-ping JSON envelope structure.

### Changed
- `netcheck/modules/interfaces.py` — `get_public_ip()` extracted as a standalone function; `get_network_interfaces()` accepts `include_public` parameter.
- `netcheck/utils/formatters.py` — type-dispatch rebuilt around `_detect_result_type()`; multi-ping batch JSON envelope added.

## [2.2.0] - 2026-06-28

### Added
- **Tier 3 Diagnostics Modules**:
  - `traceroute` module — support cross-platform native raw ICMP sockets or subprocess-based `traceroute`/`tracepath` fallbacks.
  - `scan` module — fast concurrent port scanner with well-known services dictionary mapping.
  - `whois` module — modern RDAP HTTP-based registration query with legacy WHOIS port 43 TCP socket fallback.
- **Local Listening Ports subcommand** (`ports`):
  - Lists active listening TCP/UDP sockets with address, port, process name, and PID.
  - Docker-aware: resolves process names to running container names automatically.
- **Enhanced Connection Security Metadata**:
  - SSL checks now extract and display the negotiated TLS version, cipher suite, and certificate SHA-256 fingerprint.
- **Advanced HTTP Execution Parameters**:
  - `check_http_status` supports custom HTTP methods (e.g. HEAD, POST), HTTP request headers, and Basic Access Authentication.
- **Watch Loop Mode**:
  - All subcommands support `-w` or `--watch` with polling interval control (`-i` / `--interval`) and screen clear refreshes.
- **Global Runtime Configuration overrides**:
  - Standardized environment variables `NETCHECK_TIMEOUT` and `NETCHECK_MAX_WORKERS` to control connection timeouts and thread pool concurrency.
- **Structured JSON/CSV/XML output for all subcommands** (CI/CD-ready):
  - `ports`, `scan`, `traceroute`, and `whois` now emit type-tagged structured records in all machine-readable formats.
  - JSON keys: `type` (scan/traceroute/ports), `check_type` (whois), `open_ports[]`, `hops[]`, `listening_ports[]`, `registrar`, `creation_date`.
  - CSV headers tailored per result type (e.g. `Hop,IP,Hostname,Latency_MS` for traceroute).
  - XML root element names match result type (`<port_scan>`, `<traceroute>`, `<listening_ports>`, `<whois_lookup>`).
- **Unit and Integration Tests** — expanded to 60 tests:
  - New `TestFormatterTier3` class: 12 tests verifying JSON, CSV, and XML structured output for `ports`, `scan`, `traceroute`, and `whois`.
  - Tests cover both output correctness and field presence for CI/CD script consumption.

## [2.1.0] - 2026-06-21

### Added
- **`packaging/` directory** — all platform-specific templates live in one place:
  - `packaging/snap/snapcraft.yaml` — Snap template with `{version}` placeholder
  - `packaging/linux/install.sh` / `uninstall.sh` — installer scripts
  - `packaging/windows/netcheck.nsi` — NSIS installer template
  - `packaging/chocolatey/` — Chocolatey `.nuspec` + install script
  - `packaging/macos/scripts/` — placeholder for macOS PKG scripts
- **`--sync-version VERSION`** flag in `build_packages.py` — propagates a new version to `__init__.py`, `pyproject.toml`, `netcheck/mcp/server.py`, and `packaging/snap/snapcraft.yaml` in one command.
- **`netcheck/__main__.py`** — standard `python3 -m netcheck` entry point.
- **CI workflow** (`.github/workflows/ci.yml`) — matrix tests across Python 3.8–3.12 on Ubuntu, macOS, Windows.
- **Comprehensive CLI test suite** (`tests/test_cli.py`) — 15 tests covering all subcommands and flags.
- **Snap packaging overhaul** (`packaging/snap/snapcraft.yaml`):
  - Moved Snap icon to `packaging/snap/gui/icon.png` (copied to `snap/gui/` at build time by `build_packages.py`).
  - Re-added multi-architecture builds: `amd64`, `arm64`, `armhf`.
  - Switched plugin from `dump` (bash) to `python` (pure Python 3); only `iputils-ping` needed as a stage-package.
  - Added `PYTHONPATH` environment variable so the snap runtime resolves installed site-packages correctly.
  - Expanded Snap Store description to reflect all v2.x features: subcommand CLI, MCP server, structured output, lenient target parsing, build orchestration, and the `sudo snap connect` instruction.
- **Icon & asset management** (`assets/icons/`):
  - `assets/icons/icon.png` — 512×512 master PNG (source of truth for all icon variants).
  - `assets/icons/icon.ico` — 256×256 Windows ICO (used for `.exe`, NSIS installer, and Add/Remove Programs entry).
  - `packaging/snap/gui/icon.png` — 512×512 PNG for Snap Store listing.
  - `packaging/windows/netcheck.nsi` — wired `Icon`, `UninstallIcon`, and `DisplayIcon` registry key to `assets/icons/icon.ico`.
  - `packaging/chocolatey/netcheck.nuspec` — added `<iconUrl>` pointing to the raw master PNG on GitHub.
  - `build_packages.py` — `--win` target now passes `--icon assets/icons/icon.ico` to PyInstaller; `--snap` copies `packaging/snap/gui/` → `snap/gui/` before `snapcraft` runs.

### Changed
- `build_packages.py` refactored to render templates from `packaging/` instead of embedding inline script strings.
- `build_snap()` now auto-cleans `snap/`, `stage/`, `prime/`, `parts/` artefact directories from the repo root after each build.
- `Makefile` `install`/`uninstall` targets updated to point to `packaging/linux/`.
- `README.md` fully rewritten to reflect Python-native packaging, all install options, and build commands.

### Removed
- `build-deb.sh`, `build-snap.sh` — superseded by `build_packages.py`.
- `check_ip.py`, `check_ip.sh` — legacy wrappers deleted.
- `PYTHON_README.md` — stub file removed; `README.md` is now the single source of truth.
- Root-level `install.sh`, `uninstall.sh`, `snap/` — moved to `packaging/linux/` and `packaging/snap/`.

## [2.0.0] - 2026-06-06


### Added
- **Complete Pure Python 3 Rewrite**:
  - Eliminated legacy Bash scripts and subprocess dependencies in core checking logic.
  - Native cross-platform execution (Linux, macOS, Windows).
  - High-performance, concurrent connectivity checking powered by Python's `concurrent.futures`.
- **Model Context Protocol (MCP) Server**:
  - Built-in MCP integration (run with `netcheck --mcp` or `python3 -m netcheck.mcp.server`).
  - Exposes network diagnostic tools (`dns_lookup`, `ping_host`, `check_tcp_port`, `check_http_status`, `check_ssl_certificate`, and `list_interfaces`) to AI assistants.
- **Lenient Target Parsing & Normalizer**:
  - Input lines are parsed flexibly, extracting hosts and ports from colon-separated lists, comma-separated lists, bracketed IPv6 addresses, and raw URLs (automatically stripping schemes, paths, and slashes).
  - Handles inline comments (`#`), IP ranges, CIDR subnets, and port ranges seamlessly.
- **Advanced Subcommands**:
  - Introduced CLI subcommands (`tcp`, `dns`, `http`, `ssl`, `ping`, `interfaces`) for direct usage, while maintaining full backward-compatible legacy flags (`-q`, `-d`, `-p`, `-s`, `--cert`, `--my-ip`).
- **Robust SSL & Fallback Engine**:
  - Sequential IP attempt loop across all resolved DNS records (IPv4 & IPv6).
  - Custom `cryptography` fallback parsing to fetch certificates details (subject, issuer, dates, SANs) even when validation fails strictly.
- **Color-Coded Output Alignments**:
  - Strips ANSI escape codes dynamically to maintain box alignment and layout padding in terminal outputs.
  - Safe, color-free logging when saving outputs to date-based result files (`result-*.txt`, `fail-*.txt`, `combined-*.txt`).

### Changed
- Promoted standard library network calls over external CLI binary dependency wrapping.
- Switched default output formatting to colored CLI panels with clean fallbacks.
- Updated versioning configuration in `pyproject.toml`.

## [1.2.0] - 2025-01-18

### Added
- **Network Interface Display** (`--my-ip`, `-ip`)
  - Show all network interfaces with IPv4/IPv6 addresses
  - Display interface status (UP/DOWN), gateway, and public IP
  - Default shows only active (UP) interfaces
  - `--my-ip --all` flag shows all interfaces including inactive ones
  - Sorted output with filtered loopback and virtual ethernet pairs

- **HTTP Status Checking** (`-s`, `--status`)
  - Check HTTP/HTTPS response codes with curl
  - Display response time in milliseconds
  - Show content size in human-readable format (bytes, KB, MB)
  - Categorize status codes (2xx success, 3xx redirect, 4xx client error, 5xx server error)
  - Verbose mode shows response headers
  - Comprehensive error messages for connection failures

- **SSL Certificate Validation** (`--cert`)
  - Check SSL/TLS certificate validity and expiration
  - Display certificate subject, issuer, and validity dates
  - Calculate days until expiry
  - Warn if certificate expires within 30 days (yellow) or 7 days (red)
  - Verbose mode shows Subject Alternative Names (SANs)
  - Support for URL or hostname:port format

- **Retry Logic** (`--retry`, `--retry-delay`)
  - Retry failed connections with configurable count (default: 1, no retry)
  - Configurable delay between retries in seconds (default: 1)
  - Works with both file mode and quick mode
  - Verbose mode shows retry attempts
  - Helps with intermittent connection issues

### Changed
- Updated help text with all new flags and options
- Improved error messages and user guidance
- Enhanced documentation with v1.2.0 examples

### Dependencies
- Added `curl` for HTTP status checks
- Added `openssl` for SSL certificate validation
- Added `bc` for time calculations
- Added `iproute2` for network interface display

## [1.1.0] - 2024-11-18

### Added
- **ICMP Ping Testing** (`-p`, `--ping`)
  - Ping hosts using ICMP with 4 packets
  - Accept URLs (automatically strips scheme/path)
  - Show detailed statistics
  
- **DNS Lookup** (`-d`, `--dns`)
  - Resolve hostnames to IP addresses
  - Multiple fallback methods (host, getent, dig, nslookup)
  - Accept URLs (automatically extracts hostname)
  - Show IPv4, IPv6, aliases, and reverse DNS

- **Quick Mode Enhancements**
  - Automatic parallel processing for >5 tests
  - Output file support with `-o/--output` flag
  - IP range support (192.168.1.1-50)
  - Streaming results as they complete

- **Input Validation**
  - Comprehensive validation for host and port formats
  - Inline comment removal (supports # comments)
  - Graceful handling of malformed input
  - Helpful warnings for invalid entries
  - Protection against script hanging

- **Dated Result Files**
  - Automatic timestamped output files (result-YYYY-MM-DD.txt)
  - Dated failure reports (fail-YYYY-MM-DD.txt)
  - Easier tracking of test history

### Changed
- Version information with `-v/--version` flag
- Improved snap packaging with proper permissions
- Updated documentation with all new features

### Fixed
- DNS lookup hanging on malformed URLs
- Script hanging on invalid input
- Missing ping statistics in output

## [1.0.0] - 2024-10-15

### Added
- Initial release
- Parallel TCP port connectivity testing
- IP range support (192.168.1.1-50)
- CIDR notation support (10.0.0.0/24)
- Port ranges (8000-8100) and multiple ports (80,443,8080)
- CSV file input support
- Multiple output formats (text, JSON, CSV, XML)
- Quick test mode for one-off checks
- Real-time progress bar
- Response time measurement
- Combined reports
- Man page and bash completion
- Multi-OS support (Ubuntu, Debian, CentOS, Fedora, Arch, openSUSE)
- Three installation methods (manual, DEB, Snap)

[2.3.0]: https://github.com/farman20ali/netcheck/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/farman20ali/netcheck/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/farman20ali/netcheck/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/farman20ali/netcheck/compare/v1.2.0...v2.0.0
[1.2.0]: https://github.com/farman20ali/netcheck/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/farman20ali/netcheck/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/farman20ali/netcheck/releases/tag/v1.0.0
