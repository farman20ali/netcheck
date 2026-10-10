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
            timeout = float(arguments.get("timeout", 1.5))
            max_workers = int(arguments.get("max_workers", 20))
            res = scan_ports(host, ports=ports, timeout=timeout, max_workers=max_workers)
            return _mcp_success_response(res)

        elif name == "whois_lookup":
            from netcheck.modules.whois import lookup_registration
            target = arguments.get("target")
            res = lookup_registration(target)
            return _mcp_success_response(res)

        else:
            return _mcp_error_response(f"Unknown tool: {name}")

    except Exception as e:
        return _mcp_error_response(f"Internal error executing tool {name}: {str(e)}")

def _mcp_success_response(data: Any) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, indent=2)
            }
        ]
    }

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
