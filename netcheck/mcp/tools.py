import json
from typing import Any, Dict

from netcheck.cli import run_check_with_retry
from netcheck.modules.dns import dns_lookup
from netcheck.modules.http import check_http_status
from netcheck.modules.interfaces import get_network_interfaces, get_public_ip
from netcheck.modules.ping import ping_host
from netcheck.modules.ssl import check_ssl_certificate
from netcheck.modules.tcp import check_tcp_connect
from netcheck.utils.range_expanders import expand_ip_range, expand_port_range

TOOLS_LIST = [
    {
        "name": "check_tcp_connectivity",
        "description": "Tests TCP connection status for target hosts and ports. Supports IP ranges/CIDRs (e.g. 192.168.1.1-10) and port list/ranges (e.g. 80,443, 8000-8010).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "The target hostname, IP address, CIDR subnet, or IP range."
                },
                "port": {
                    "type": "string",
                    "description": "A single port, comma-separated list of ports, or hyphenated port range."
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds per connection check (default: 5.0).",
                    "default": 5.0
                },
                "retries": {
                    "type": "integer",
                    "description": "Number of check attempts (default: 1).",
                    "default": 1
                }
            },
            "required": ["host", "port"]
        }
    },
    {
        "name": "check_http_status",
        "description": "Checks HTTP/HTTPS connection response status code, content size, latency, and redirect URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full target URL (e.g. https://google.com)."
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 5.0).",
                    "default": 5.0
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "check_ssl_certificate",
        "description": "Validates the SSL/TLS certificate chain of a host and port, extracting expiration, subject, and issuer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "The target hostname (e.g. google.com)."
                },
                "port": {
                    "type": "integer",
                    "description": "SSL port (default: 443).",
                    "default": 443
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 5.0).",
                    "default": 5.0
                }
            },
            "required": ["host"]
        }
    },
    {
        "name": "dns_lookup",
        "description": "Resolves IPv4 and IPv6 (A/AAAA) IP records for a hostname, using local caching.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Hostname or URL to resolve."
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 5.0).",
                    "default": 5.0
                }
            },
            "required": ["host"]
        }
    },
    {
        "name": "ping_host",
        "description": "Pings a host using ICMP packages to measure network round-trip time and packet loss.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target IP address or hostname to ping."
                },
                "count": {
                    "type": "integer",
                    "description": "Number of packets to send (default: 4).",
                    "default": 4
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout per packet in seconds (default: 2.0).",
                    "default": 2.0
                }
            },
            "required": ["host"]
        }
    },
    {
        "name": "get_network_interfaces",
        "description": "Lists all active local network interfaces, their IP addresses, and flags the primary outbound interface.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_listening_ports",
        "description": "Lists local active listening TCP sockets, process names, PIDs, and associated Docker container names.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_public_ip",
        "description": "Queries external lookups to fetch the public internet IP address of this host.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "number",
                    "description": "Request timeout in seconds (default: 3.0).",
                    "default": 3.0
                }
            }
        }
    },
    {
        "name": "traceroute",
        "description": "Traces the network path (hops) from this host to the destination. Uses raw sockets if available, otherwise falls back to the system traceroute/tracepath/tracert binary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target hostname or IP address."
                },
                "max_hops": {
                    "type": "integer",
                    "description": "Maximum number of hops to trace (default: 30).",
                    "default": 30
                },
                "timeout": {
                    "type": "number",
                    "description": "Per-hop timeout in seconds (default: 2.0).",
                    "default": 2.0
                }
            },
            "required": ["host"]
        }
    },
    {
        "name": "scan_ports",
        "description": "Performs a concurrent TCP port scan on a target host. Returns a list of open and closed ports with service names and latency.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target hostname or IP address."
                },
                "ports": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Optional list of port numbers to scan. Defaults to common well-known ports."
                },
                "timeout": {
                    "type": "number",
                    "description": "Per-port timeout in seconds (default: 1.5).",
                    "default": 1.5
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Maximum concurrent scan threads (default: 20).",
                    "default": 20
                }
            },
            "required": ["host"]
        }
    },
    {
        "name": "whois_lookup",
        "description": "Looks up registrar and registration details for a domain or IP address using RDAP (with WHOIS fallback). Returns registrar name, creation date, and registration type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Domain name or IP address to look up (e.g. google.com or 8.8.8.8)."
                }
            },
            "required": ["target"]
        }
    },
    {
        "name": "check_udp",
        "description": "Sends a UDP probe to a host:port and interprets the result. Returns OPEN_OR_FILTERED (no ICMP error within timeout) or CLOSED (ICMP port-unreachable received). Useful for DNS, NTP, SNMP, and other UDP services.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target hostname or IP address."
                },
                "port": {
                    "type": "integer",
                    "description": "UDP port number to probe."
                },
                "timeout": {
                    "type": "number",
                    "description": "Probe timeout in seconds (default: 3.0).",
                    "default": 3.0
                }
            },
            "required": ["host", "port"]
        }
    },
    {
        "name": "run_mtr",
        "description": "Runs an MTR-style combined traceroute + ping to measure per-hop latency and packet loss. Returns each hop with min/avg/max RTT and loss percentage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target hostname or IP address."
                },
                "count": {
                    "type": "integer",
                    "description": "Number of probes per hop (default: 3).",
                    "default": 3
                },
                "max_hops": {
                    "type": "integer",
                    "description": "Maximum number of hops to trace (default: 30).",
                    "default": 30
                },
                "timeout": {
                    "type": "number",
                    "description": "Per-hop timeout in seconds (default: 2.0).",
                    "default": 2.0
                }
            },
            "required": ["host"]
        }
    }
]

def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatches tool calls from the MCP server to the appropriate Python modules.
    Returns standard MCP content structures.
    """
    try:
        if name == "check_tcp_connectivity":
            host = arguments.get("host")
            port_str = str(arguments.get("port"))
            timeout = float(arguments.get("timeout", 5.0))
            retries = int(arguments.get("retries", 1))

            # Expand hosts/ports
            hosts = expand_ip_range(host)
            ports = expand_port_range(port_str)

            if len(hosts) * len(ports) > 256:
                return _mcp_error_response(
                    f"Target count exceeds safety limit of 256 checks ({len(hosts) * len(ports)} requested). Limit IP/port range."
                )

            results = []
            for h in hosts:
                for p in ports:
                    res = run_check_with_retry(check_tcp_connect, args=(h, p, timeout), retries=retries)
                    results.append(res)

            return _mcp_success_response(results)

        elif name == "check_http_status":
            url = arguments.get("url")
            timeout = float(arguments.get("timeout", 5.0))
            res = check_http_status(url, timeout)
            return _mcp_success_response(res)

        elif name == "check_ssl_certificate":
            host = arguments.get("host")
            port = int(arguments.get("port", 443))
            timeout = float(arguments.get("timeout", 5.0))
            res = check_ssl_certificate(host, port, timeout)
            return _mcp_success_response(res)

        elif name == "dns_lookup":
            host = arguments.get("host")
            timeout = float(arguments.get("timeout", 5.0))
            res = dns_lookup(host, timeout)
            return _mcp_success_response(res)

        elif name == "ping_host":
            host = arguments.get("host")
            count = int(arguments.get("count", 4))
            timeout = float(arguments.get("timeout", 2.0))
            res = ping_host(host, count, timeout)
            return _mcp_success_response(res)

        elif name == "get_network_interfaces":
            res = get_network_interfaces()
            return _mcp_success_response(res)

        elif name == "get_listening_ports":
            from netcheck.modules.interfaces import check_listening_ports
            res = check_listening_ports()
            return _mcp_success_response(res)

        elif name == "get_public_ip":
            timeout = float(arguments.get("timeout", 3.0))
            ip = get_public_ip(timeout)
            return _mcp_success_response({"public_ip": ip, "success": ip != "Unknown"})

        elif name == "traceroute":
            from netcheck.modules.traceroute import traceroute as run_traceroute
            host = arguments.get("host")
            max_hops = int(arguments.get("max_hops", 30))
            timeout = float(arguments.get("timeout", 2.0))
            res = run_traceroute(host, max_hops=max_hops, timeout=timeout)
            return _mcp_success_response(res)

        elif name == "scan_ports":
            from netcheck.modules.port_scanner import scan_ports
            host = arguments.get("host")
            ports = arguments.get("ports", None)
            if ports and len(ports) > 1000:
                return _mcp_error_response(
                    f"Port scan exceeds safety limit of 1000 ports ({len(ports)} requested)."
                )
            timeout = float(arguments.get("timeout", 1.5))
            max_workers = int(arguments.get("max_workers", 20))
            res = scan_ports(host, ports=ports, timeout=timeout, max_workers=max_workers)
            return _mcp_success_response(res)

        elif name == "whois_lookup":
            from netcheck.modules.whois import lookup_registration
            target = arguments.get("target")
            res = lookup_registration(target)
            return _mcp_success_response(res)

        elif name == "check_udp":
            from netcheck.modules.udp import check_udp
            host = arguments.get("host")
            port = int(arguments.get("port"))
            timeout = float(arguments.get("timeout", 3.0))
            res = check_udp(host, port, timeout)
            return _mcp_success_response(res)

        elif name == "run_mtr":
            from netcheck.modules.mtr import mtr
            host = arguments.get("host")
            count = int(arguments.get("count", 3))
            max_hops = int(arguments.get("max_hops", 30))
            timeout = float(arguments.get("timeout", 2.0))
            res = mtr(host, count=count, max_hops=max_hops, timeout=timeout)
            return _mcp_success_response(res)

        else:
            return _mcp_error_response(f"Unknown tool: {name}")

    except Exception as e:
        return _mcp_error_response(f"Internal error executing tool {name}: {str(e)}")

def _mcp_success_response(data: Any) -> Dict[str, Any]:
    resp: Dict[str, Any] = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, indent=2)
            }
        ]
    }
    # MCP standard: if check result indicates failure, set isError: True
    if isinstance(data, dict):
        if data.get("success") is False or data.get("status") == "FAILED":
            resp["isError"] = True
    elif isinstance(data, list):
        if any(isinstance(x, dict) and (x.get("success") is False or x.get("status") == "FAILED") for x in data):
            resp["isError"] = True
    return resp

def _mcp_error_response(message: str) -> Dict[str, Any]:
    return {
        "isError": True,
        "content": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
