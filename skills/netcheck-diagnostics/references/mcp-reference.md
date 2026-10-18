# NetCheck MCP Tool Reference

Details the 11 registered MCP tools, their schemas, and live-captured payloads.

> **Note on captured outputs:** All payloads were captured live on Windows in a local loopback
> environment. Timestamps appear as `"<timestamp>"`, port numbers are real integers,
> and machine-specific names are shown as `"<hostname>"` / `"<adapter-name>"`.
> Error strings reflect the Windows platform; POSIX wording is expected on Linux/macOS
> but was not captured here.

---

## 1. Protocol Architecture & Tool Execution

NetCheck runs a zero-dependency JSON-RPC 2.0 stdio MCP server (`protocolVersion: 2024-11-05`).

### Tool-Name Prefixes
Some clients add a prefix to tool names, for example `mcp__<server>__<tool>` or `<server>_<tool>`.
Always match any tool whose name ends with one of the 11 base names (tool names themselves contain underscores).

### Result Structure
Every successful tool execution returns:
```json
{
  "content": [
    {
      "type": "text",
      "text": "<JSON_STRING>"
    }
  ]
}
```
**CRITICAL:** A JSON-RPC result without `"isError": true` only means the tool ran without
crashing. Parse `content[0].text` as JSON and inspect the result fields.

The fields `success`, `status`, and `error` are **verified present** for the five captured tools
(`check_tcp_connectivity`, `dns_lookup`, `ping_host`, `get_network_interfaces`, and `check_http_status`).
For the other six tools, parse the JSON and use those fields only if present --
do not assume their existence without consulting the captured payloads below.

### Unsupported in MCP
`udp` and `mtr` are CLI-only.

---

## 2. All Registered MCP Tools (11 Tools)

Registered MCP tools:

| Tool Base Name | Description | Required | Optional |
|---|---|---|---|
| `check_tcp_connectivity` | TCP reachability (host + port, accepts ranges/CIDRs) | `host`, `port` | `timeout` (5.0), `retries` (1) |
| `check_http_status` | HTTP status, latency, size, redirects | `url` | `timeout` (5.0) |
| `check_ssl_certificate` | SSL/TLS cert validity and expiry | `host` | `port` (443), `timeout` (5.0) |
| `dns_lookup` | IPv4/IPv6 resolution | `host` | `timeout` (5.0) |
| `ping_host` | ICMP ping for RTT and packet loss | `host` | `count` (4), `timeout` (2.0) |
| `get_network_interfaces` | Local interfaces, IPs, primary interface | -- | -- |
| `get_listening_ports` | Local listening TCP sockets, processes, PIDs | -- | -- |
| `get_public_ip` | Public WAN IP via external lookup | -- | `timeout` (3.0) |
| `traceroute` | Network hop trace | `host` | `max_hops` (30), `timeout` (2.0) |
| `scan_ports` | Concurrent TCP port scan | `host` | `ports` (int[]), `timeout` (1.5), `max_workers` (20) |
| `whois_lookup` | RDAP/WHOIS registrar lookup | `target` | -- |

---

## 3. Live Captured Payloads

### A. `check_tcp_connectivity` -- Successful connection
- **Call:** `check_tcp_connectivity(host="127.0.0.1", port="<port>")`
- **Payload (example values, redacted from a real capture; `<port>` in the call is a real integer):**
```json
[
  {
    "type": "tcp",
    "target": "127.0.0.1:12345",
    "status": "SUCCESS",
    "latency_ms": 1.03,
    "success": true,
    "error": null,
    "metadata": {
      "host": "127.0.0.1",
      "port": 12345,
      "ip": "127.0.0.1",
      "resolved": true,
      "method": "socket",
      "service": ""
    }
  }
]
```
Returns a JSON array. `"success": true`, `"status": "SUCCESS"`.

### B. `check_tcp_connectivity` -- Port closed / refused
- **Call:** `check_tcp_connectivity(host="127.0.0.1", port="<port>")`
- **Payload (example values, redacted from a real capture):**
```json
[
  {
    "type": "tcp",
    "target": "127.0.0.1:12345",
    "status": "FAILED",
    "latency_ms": 2034.28,
    "success": false,
    "error": "All connection attempts failed: 127.0.0.1 ([WinError 10061] No connection could be made because the target machine actively refused it)",
    "metadata": {
      "host": "127.0.0.1",
      "port": 12345,
      "ip": "127.0.0.1",
      "resolved": true,
      "method": "socket",
      "service": ""
    }
  }
]
```
> **Note on failed-TCP timing:** On this Windows host, connecting to a closed loopback port gave
> the following measured results across tool runs:
> - **MCP (`check_tcp_connectivity`):** Under the default 5.0 s timeout, it measured `latency_ms: 2034.28`
>   returning `[WinError 10061]`. With `timeout=3.0`, it measured `latency_ms: 2022.68` returning `[WinError 10061]`.
>   With `timeout=1.0`, it aborted at `latency_ms: 1011.72` reporting `timed out` because the timeout
>   expired before the OS reported the refusal.
> - **CLI (`netcheck tcp`):** Three runs with the default timeout took ~2.4–2.7 s command elapsed time,
>   each returning `[WinError 10061]`. With `-t 1`, it aborted at ~1.5 s command time reporting `timed out`.
>   With `-t 3`, it took ~2.5 s command time returning `[WinError 10061]`. Note that CLI JSON failure output
>   does not include a `latency_ms` field.
> - **Raw Python socket:** With timeout 3.0 s, `s.connect` took 2027.78 ms returning `ConnectionRefusedError: [WinError 10061]`.
>   With timeout 1.0 s, `s.connect` aborted at 1005.76 ms returning `TimeoutError: timed out`.
>
> In all cases, do not report failed-TCP `latency_ms` as network latency.

### C. `dns_lookup` -- Successful localhost resolution
- **Call:** `dns_lookup(host="localhost")`
- **Payload (example values, redacted from a real capture):**
```json
{
  "type": "dns",
  "target": "localhost",
  "status": "SUCCESS",
  "latency_ms": 15.79,
  "success": true,
  "error": null,
  "metadata": {
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
}
```
Note: `ips` is inside `metadata` here. The CLI `dns` subcommand places `ips` at the top level.

### D. `ping_host` -- Successful loopback ping
- **Call:** `ping_host(host="127.0.0.1", count=2)`
- **Payload (example values, redacted from a real capture; `ping_output` trimmed):**
```json
{
  "type": "ping",
  "target": "127.0.0.1",
  "status": "SUCCESS",
  "latency_ms": 1037.94,
  "success": true,
  "error": null,
  "metadata": {
    "host": "127.0.0.1",
    "packets_sent": 2,
    "packets_received": 2,
    "packet_loss_pct": 0.0,
    "min_rtt_ms": 0.0,
    "avg_rtt_ms": 0.0,
    "max_rtt_ms": 0.0,
    "ping_output": "<ping command text trimmed>"
  }
}
```
Fields verified: `success`, `status`, `error`. `latency_ms` is total wall-clock time for all ping
iterations, not per-packet RTT; use `min_rtt_ms` / `avg_rtt_ms` / `max_rtt_ms` for RTT.

### E. `get_network_interfaces` -- Local network interfaces
- **Call:** `get_network_interfaces()`
- **Payload (example values, redacted from a real capture; IPs replaced with 192.0.2.x / 198.51.100.x):**
```json
{
  "type": "interfaces",
  "target": "interfaces",
  "status": "SUCCESS",
  "latency_ms": 0.0,
  "success": true,
  "error": null,
  "metadata": {
    "primary_ip": "192.0.2.1",
    "interfaces": {
      "<adapter-name-1>": {
        "ipv4": [
          "192.0.2.1"
        ],
        "ipv6": [],
        "status": "UP",
        "active": true
      },
      "<adapter-name-2>": {
        "ipv4": [
          "198.51.100.1"
        ],
        "ipv6": [],
        "status": "UP",
        "active": false
      },
      "<adapter-name-3>": {
        "ipv4": [
          "198.51.100.2"
        ],
        "ipv6": [],
        "status": "UP",
        "active": false
      }
    },
    "gateway_ip": "192.0.2.254",
    "gateway_dev": null,
    "public_ip": "Unknown",
    "public_ip_checked": false,
    "all_interfaces_shown": false
  }
}
```
Fields verified: `success`, `status`, `error`. Read each interface's `active` and `status` fields
to determine which adapter is currently in use. `gateway_ip` can be `null` if no default gateway
is detected by the OS route tables.

### F. `check_http_status` -- Successful HTTP check
- **Call:** `check_http_status(url="http://127.0.0.1:<port>/")`
- **Payload (example values, redacted from a real capture):**
```json
{
  "type": "http",
  "target": "http://127.0.0.1:12345/",
  "status": "SUCCESS",
  "latency_ms": 95.72,
  "success": true,
  "error": null,
  "metadata": {
    "status_code": 200,
    "redirect_url": null,
    "size_bytes": 1550,
    "headers": {
      "server": "SimpleHTTP/0.6 Python/3.13.3",
      "date": "<date>",
      "content-type": "text/html; charset=utf-8",
      "content-length": "1550"
    }
  }
}
```
Fields verified: `success`, `status`, `error`. Note that `http` can reach internal hosts
and external URLs; disclose this to the user before running.

### G. Invalid tool name
- **Call:** `unknown_tool_name()`
- **Captured response:**
```json
{
  "isError": true,
  "content": [
    {
      "type": "text",
      "text": "Unknown tool: unknown_tool_name"
    }
  ]
}
```
Only an unregistered tool name or unhandled server crash sets `"isError": true`.

### H. Invalid input -- empty or out-of-range port
- **Call:** `check_tcp_connectivity(host="127.0.0.1", port="abc")` (also `port="99999"`, `host=""`)
- **Captured content payload:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "[]"
    }
  ]
}
```
The range expander rejects invalid input silently.
Result is an empty JSON array. `"isError"` is **not** set.

> **Empty-array rule:** An empty array means no check ran. Report as invalid input,
> not a connection result.

### I. Invalid input -- empty host in `dns_lookup`
- **Call:** `dns_lookup(host="")`
- **Captured content payload:**
```json
{
  "type": "dns",
  "target": "",
  "status": "FAILED",
  "latency_ms": 0.0,
  "success": false,
  "error": "Empty host target",
  "metadata": {}
}
```
The server returns this object as a JSON string in content[0].text; shown here parsed.
`"isError"` is **not** set.

> **Result-handling rule:** Failed checks and invalid inputs are reported differently across
> tools. Neither sets `"isError": true`. Never rely on `"isError"` alone to check validity.

---

### Other tools (payloads not captured)
`check_ssl_certificate`, `get_listening_ports`, `get_public_ip`, `traceroute`, `scan_ports`,
`whois_lookup`: not captured in this loopback run; see the tool's inputSchema as reported by your MCP client.

---

## 4. `netcheck mcp` Subcommand

Subcommand behavior:
- `netcheck mcp install`: prints a JSON config snippet to stdout and shows the detected Claude
  Desktop config file path. It does **not** write any file (it prints the snippet to stdout and does not write files).
- `netcheck mcp status`: spawns the MCP server in a subprocess, sends an `initialize` request,
  and prints a health result. It does not modify any files.
