"""
netcheck.modules.discover
~~~~~~~~~~~~~~~~~~~~~~~~~

Host Discovery Sweep — find live hosts on a subnet without root/raw packets.

Strategy (dual-vector):
  1. ICMP ping via system ``ping`` binary (fast, one packet, short timeout).
  2. If ping fails or times out, TCP connect probe to ports 22, 80, 443
     (handles hosts that drop ICMP but accept TCP connections).

A host is considered **UP** if *either* probe succeeds.

Usage::

    from netcheck.modules.discover import discover_hosts

    result = discover_hosts("192.168.1.0/24", timeout=1.0, max_workers=50)
    # {
    #   "type": "discover",
    #   "target": "192.168.1.0/24",
    #   "success": True,
    #   "metadata": {
    #     "total_hosts": 254,
    #     "live_hosts": 3,
    #     "hosts": [
    #       {"ip": "192.168.1.1",  "status": "UP", "method": "icmp", "latency_ms": 1.2, "hostname": "router.local"},
    #       {"ip": "192.168.1.10", "status": "UP", "method": "tcp:80", "latency_ms": 5.4, "hostname": null},
    #     ]
    #   }
    # }
"""

from __future__ import annotations

import ipaddress
import platform
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional

from netcheck.utils.threads import DaemonThreadPoolExecutor, cleanup_thread_queues

# TCP ports to probe as fallback if ICMP is blocked
_TCP_PROBE_PORTS = [22, 80, 443]


def discover_hosts(
    target: str,
    timeout: float = 1.0,
    max_workers: int = 50,
) -> Dict[str, Any]:
    """
    Scan *target* (CIDR or dash-range) for live hosts.

    Returns standard netcheck result envelope with ``metadata.hosts`` list.
    Safety limit: 1024 hosts maximum.
    """
    try:
        host_list = _expand_target(target)
    except ValueError as e:
        return {
            "type": "discover",
            "target": target,
            "status": "FAILED",
            "success": False,
            "latency_ms": None,
            "error": str(e),
            "metadata": {"total_hosts": 0, "live_hosts": 0, "hosts": []},
        }

    if len(host_list) > 1024:
        return {
            "type": "discover",
            "target": target,
            "status": "FAILED",
            "success": False,
            "latency_ms": None,
            "error": f"Target range too large ({len(host_list)} hosts). Maximum is 1024. Use a smaller CIDR (e.g. /22 or smaller).",
            "metadata": {"total_hosts": len(host_list), "live_hosts": 0, "hosts": []},
        }

    t0 = time.perf_counter()
    results: List[Dict[str, Any]] = []

    with DaemonThreadPoolExecutor(max_workers=min(max_workers, len(host_list))) as pool:
        futs = {pool.submit(_probe_host, ip, timeout): ip for ip in host_list}
        try:
            for fut in futs:
                try:
                    results.append(fut.result(timeout=timeout + 2.0))
                except Exception:
                    ip = futs[fut]
                    results.append({"ip": ip, "status": "DOWN", "method": None, "latency_ms": None, "hostname": None})
        except KeyboardInterrupt:
            cleanup_thread_queues()
            raise

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    live = [r for r in results if r["status"] == "UP"]
    # Sort by IP address for deterministic output
    results.sort(key=lambda r: _ip_sort_key(r["ip"]))
    live_sorted = [r for r in results if r["status"] == "UP"]

    return {
        "type": "discover",
        "target": target,
        "status": "SUCCESS",
        "success": True,
        "latency_ms": elapsed_ms,
        "error": None,
        "metadata": {
            "total_hosts": len(host_list),
            "live_hosts": len(live),
            "scan_time_ms": elapsed_ms,
            "hosts": live_sorted,
        },
    }


# ---------------------------------------------------------------------------
# Per-host probe
# ---------------------------------------------------------------------------

def _probe_host(ip: str, timeout: float) -> Dict[str, Any]:
    """Try ICMP ping then TCP fallback. Return host record."""
    result = _ping_probe(ip, timeout)
    if result is not None:
        hostname = _reverse_lookup(ip)
        return {"ip": ip, "status": "UP", "method": "icmp", "latency_ms": result, "hostname": hostname}

    # Fallback: TCP connect to common ports
    for port in _TCP_PROBE_PORTS:
        latency = _tcp_probe(ip, port, timeout)
        if latency is not None:
            hostname = _reverse_lookup(ip)
            return {"ip": ip, "status": "UP", "method": f"tcp:{port}", "latency_ms": latency, "hostname": hostname}

    return {"ip": ip, "status": "DOWN", "method": None, "latency_ms": None, "hostname": None}


def _ping_probe(ip: str, timeout: float) -> Optional[float]:
    """Single-packet ICMP ping. Returns latency_ms on success, None on failure."""
    plat = platform.system().lower()
    timeout_int = max(1, int(timeout))
    if plat == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_int * 1000), ip]
    elif plat == "darwin":
        cmd = ["ping", "-c", "1", "-t", str(timeout_int), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout_int), ip]

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1.0,
        )
        if proc.returncode == 0:
            return round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        pass
    return None


def _tcp_probe(ip: str, port: int, timeout: float) -> Optional[float]:
    """TCP connect probe. Returns latency_ms on success, None on failure."""
    t0 = time.perf_counter()
    try:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((ip, port))
            return round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        return None


def _reverse_lookup(ip: str) -> Optional[str]:
    """Best-effort reverse DNS. Returns hostname or None."""
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Target expansion helpers
# ---------------------------------------------------------------------------

def _expand_target(target: str) -> List[str]:
    """
    Expand *target* into a flat list of IP strings.

    Supported formats:
      - CIDR:       192.168.1.0/24
      - Dash-range: 192.168.1.1-20  (last-octet range)
      - Single IP:  192.168.1.1
    """
    target = target.strip()

    # CIDR notation
    if "/" in target:
        net = ipaddress.ip_network(target, strict=False)
        # Skip network/broadcast for IPv4 /31 and smaller
        hosts = list(net.hosts())
        if not hosts:
            hosts = [net.network_address]
        return [str(h) for h in hosts]

    # Dash range: 192.168.1.1-20 or 192.168.1.1-192.168.1.20
    if "-" in target:
        parts = target.split("-", 1)
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        # Short form: last octet only (e.g. "192.168.1.1-20")
        if "." not in end_part:
            prefix = ".".join(start_ip.split(".")[:3])
            try:
                start_oct = int(start_ip.split(".")[-1])
                end_oct = int(end_part)
            except ValueError:
                raise ValueError(f"Invalid target range '{target}'")
            if end_oct < start_oct or end_oct > 254:
                raise ValueError(f"Invalid octet range: {start_oct}-{end_oct}")
            return [f"{prefix}.{i}" for i in range(start_oct, end_oct + 1)]
        # Full form: 192.168.1.1-192.168.1.20
        try:
            start_int = int(ipaddress.ip_address(start_ip))
            end_int = int(ipaddress.ip_address(end_part))
            if end_int < start_int:
                raise ValueError(f"End address {end_part} is before start {start_ip}")
            if end_int - start_int > 1023:
                raise ValueError(f"Range too large ({end_int - start_int + 1} hosts > 1024)")
            return [str(ipaddress.ip_address(i)) for i in range(start_int, end_int + 1)]
        except ValueError as e:
            raise ValueError(f"Invalid target range '{target}': {e}") from e

    # Single IP or hostname — treat as /32
    try:
        ipaddress.ip_address(target)
        return [target]
    except ValueError:
        # Try DNS resolve
        try:
            ip = socket.gethostbyname(target)
            return [ip]
        except socket.gaierror:
            raise ValueError(f"Cannot resolve target '{target}' to an IP address")


def _ip_sort_key(ip: str) -> tuple:
    try:
        return tuple(int(x) for x in ip.split("."))
    except Exception:
        return (0, 0, 0, 0)
