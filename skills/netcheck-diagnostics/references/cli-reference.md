# NetCheck CLI Reference

Verified exit codes, JSON result shapes, and live-captured outputs for NetCheck CLI subcommands.

> **Note on captured outputs:** All outputs were captured live on Windows in a local loopback
> environment. Timestamps are shown as `"<timestamp>"`, the port number used in a given capture
> appears as a real integer (e.g. `12345`), and adapter/process names are shown as
> `"<adapter-name>"` / `"<process>"` / `"<pid>"` where they are machine-specific.
> Error strings reflect the Windows platform; POSIX wording (e.g. `[Errno 111] Connection refused`)
> is expected on Linux/macOS but was not captured here.

---

## 1. Invocation Syntax & Fallback

```bash
netcheck <subcommand> [args] -f json
python -m netcheck <subcommand> [args] -f json
```

---

## 2. Exit Codes

| Exit Code | Constant | Meaning |
|:---:|---|---|
| `0` | `EXIT_OK` | All checks passed. |
| `1` | `EXIT_FAIL` | One or more checks failed, target unreachable, or invalid input rejected before the check ran (see note below). |
| `2` | `EXIT_BAD_ARGS` | Invalid arguments or missing required target (syntax-level). |
| `3` | `EXIT_ERROR` | Unexpected internal exception. |
| `130` | `EXIT_INTERRUPT` | Killed by Ctrl+C / SIGINT. |

> **Note on exit code 1 vs 2:** When a port string like `abc` is passed to `netcheck tcp`, the
> CLI's port expander rejects it silently and exits with code **1** (not 2), printing
> `Error: No valid host or port specified` to stderr with no JSON on stdout.
> If you get exit code 1 with no JSON, read stderr.

---

## 3. Subcommand Reference & Captured Outputs

### `netcheck tcp`

#### A. Successful connection
- **Command:** `netcheck tcp 127.0.0.1 <port> -f json`
- **Exit code:** `0`
- **Output (example values, redacted from a real capture; `<port>` is a real integer):**
```json
{
  "check_date": "<timestamp>",
  "results": [
    {
      "status": "success",
      "host": "127.0.0.1",
      "port": 12345,
      "method": "socket",
      "timestamp": "<timestamp>"
    }
  ]
}
```
Top-level key is `"results"`. Each entry confirms a successful TCP three-way handshake.

#### B. Failed connection (port closed / refused)
- **Command:** `netcheck tcp 127.0.0.1 <port> -f json`
- **Exit code:** `1`
- **Output (example values, redacted from a real capture; `<port>` is a real integer):**
```json
{
  "check_date": "<timestamp>",
  "failures": [
    {
      "status": "failed",
      "host": "127.0.0.1",
      "port": 12345,
      "reason": "All connection attempts failed: 127.0.0.1 ([WinError 10061] No connection could be made because the target machine actively refused it)",
      "timestamp": "<timestamp>"
    }
  ]
}
```
Top-level key is `"failures"`. Inspect `failures[0].reason` for the verbatim OS error.
On Linux the string is expected to be `[Errno 111] Connection refused` (not verified here).

> **Note on failed-TCP timing:** On this Windows host, connecting to a closed loopback port
> with a 3 s timeout took 2027.78 ms in a raw Python socket test before returning errno 10061
> (WSAECONNREFUSED). With a 1 s timeout (`-t 1`), the connection attempt aborted at 1005.76 ms
> as a timeout (reporting "timed out") because the timeout expired before the Windows stack reported
> the refusal. Three CLI runs with the default timeout took ~2.4–2.7 s command elapsed time, each
> returning `[WinError 10061]`. Note that the CLI JSON output for failures does not include
> `latency_ms`. Do not quote command elapsed time as network latency.

#### C. Mixed result (some ports open, some closed)
- **Command:** `netcheck tcp 127.0.0.1 <open>,<closed> -f json`
- **Exit code:** `1`
- **Output (example values, redacted from a real capture):**
```json
{
  "check_date": "<timestamp>",
  "all_results": [
    {
      "status": "success",
      "host": "127.0.0.1",
      "port": 56461,
      "method": "socket",
      "timestamp": "<timestamp>"
    },
    {
      "status": "failed",
      "host": "127.0.0.1",
      "port": 19999,
      "reason": "All connection attempts failed: 127.0.0.1 ([WinError 10061] No connection could be made because the target machine actively refused it)",
      "timestamp": "<timestamp>"
    }
  ]
}
```
Mixed results use the top-level key `"all_results"` (not `"results"` or `"failures"`).
Inspect each entry's `"status"` individually.

#### D. Invalid port argument
- **Command:** `netcheck tcp 127.0.0.1 abc -f json`
- **Exit code:** `1`
- **Output:** `Error: No valid host or port specified` on stderr; no JSON on stdout.
The port expander rejects non-numeric input before any check runs.

---

### `netcheck dns`

- **Command:** `netcheck dns localhost -f json`
- **Exit code:** `0`
- **Output (example values, redacted from a real capture):**
```json
{
  "check_date": "<timestamp>",
  "type": "dns",
  "target": "localhost",
  "success": true,
  "error": null,
  "latency_ms": 26.58,
  "resolved_host": "localhost",
  "ips": [
    "::1",
    "127.0.0.1"
  ],
  "aliases": [
    "<hostname>"
  ],
  "reverse_dns": "<hostname>"
}
```
Note: the CLI `dns` subcommand places `ips` at the **top level** of the object.
The MCP `dns_lookup` tool places them inside a `metadata` object (`metadata.ips`).

---

### `netcheck ping`

- **Command:** `netcheck ping 127.0.0.1 -f json`
- **Exit code:** `0`
- **Output (example values, redacted from a real capture):**
```json
{
  "check_date": "<timestamp>",
  "type": "ping",
  "target": "127.0.0.1",
  "success": true,
  "error": null,
  "latency_ms": 3057.2,
  "host": "127.0.0.1",
  "packets_sent": 4,
  "packets_received": 4,
  "packet_loss_pct": 0.0,
  "min_rtt_ms": 0.0,
  "avg_rtt_ms": 0.0,
  "max_rtt_ms": 0.0,
  "ping_output": "<ping command output>"
}
```
Top-level `latency_ms` is **total wall-clock command time** (all iterations), not RTT.
True RTT is in `min_rtt_ms` / `avg_rtt_ms` / `max_rtt_ms`.

---

### `netcheck interfaces`

- **Command:** `netcheck interfaces -f json`
- **Exit code:** `0`
- **Output (example values, redacted from a real capture):**
```json
{
  "check_date": "<timestamp>",
  "type": "interfaces",
  "primary_ip": "192.0.2.10",
  "interfaces": {
    "<adapter-name>": {
      "ipv4": ["192.0.2.10"],
      "ipv6": [],
      "status": "UP",
      "active": true
    }
  },
  "gateway_ip": "192.0.2.1",
  "gateway_dev": null,
  "public_ip": "Unknown",
  "public_ip_checked": false,
  "all_interfaces_shown": false
}
```
Read each interface's `active` and `status` fields to determine which adapter is currently in use.
`gateway_ip` comes from OS route tables and can be `null` if no default gateway is detected.

---

### `netcheck ports`

- **Command:** `netcheck ports -f json`
- **Exit code:** `0`
- **Output (example values, redacted from a real capture):**
```json
{
  "check_date": "<timestamp>",
  "type": "ports",
  "success": true,
  "error": null,
  "listening_ports": [
    {
      "proto": "TCP",
      "address": "0.0.0.0",
      "port": 12345,
      "process": "<process>",
      "pid": "<pid>"
    }
  ]
}
```
IPv6 listeners appear with the address in brackets (e.g. `"[::1]"`, verified) and IPv4 listeners with the plain address (e.g. `"127.0.0.1"` or `"0.0.0.0"`).

---

### `netcheck http`

- **Command:** `netcheck http http://127.0.0.1:<port> -f json`
- **Exit code:** `0`
- **Output (example values, redacted from a real capture):**
```json
{
  "check_date": "<timestamp>",
  "type": "http",
  "target": "http://127.0.0.1:12345",
  "success": true,
  "error": null,
  "latency_ms": 109.43,
  "status_code": 200,
  "redirect_url": null,
  "size_bytes": 1511,
  "headers": {
    "server": "SimpleHTTP/0.6 Python/3.13.3",
    "content-type": "text/html; charset=utf-8",
    "content-length": "1511"
  }
}
```
> **Outbound reach:** `netcheck http` follows the URL as given and can reach internal hosts,
> localhost services, and external URLs. Disclose this to the user before running.

---

### `netcheck ssl`

- **Syntax:** `netcheck ssl <host> [port] -f json` (`port` optional, default 443).
- Output schema not captured in this loopback run; see `--help`.

---

### Other subcommands (not captured)
- `netcheck traceroute`, `netcheck scan`, `netcheck whois`, `netcheck mtr`: see `--help`.
- `netcheck udp <host> <port>`: CLI-only (not in MCP). Schema not captured.
  UDP silence is ambiguous -- no response can mean the port is open, filtered, or the host is down.
