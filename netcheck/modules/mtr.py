"""
netcheck.modules.mtr
~~~~~~~~~~~~~~~~~~~~

MTR-style combined Ping + Traceroute per-hop latency measurement.

Sends multiple ICMP-TTL probes to each hop along the route to *host*
and records min/avg/max round-trip time and packet-loss percentage
per hop — exactly like the classic `mtr` tool.

Falls back to the system `traceroute`/`tracert` if raw sockets are
unavailable (no root / no CAP_NET_RAW).

Usage::

    from netcheck.modules.mtr import mtr

    result = mtr("google.com", count=3, max_hops=30, timeout=2.0)
    # {
    #   "type": "mtr",
    #   "target": "google.com",
    #   "success": True,
    #   "latency_ms": 58.4,   # avg latency to destination
    #   "metadata": {
    #     "hops": [
    #       {"hop": 1, "ip": "192.168.1.1", "name": "router", "loss_pct": 0.0,
    #        "sent": 3, "recv": 3, "min_ms": 1.0, "avg_ms": 1.2, "max_ms": 1.5},
    #       ...
    #     ]
    #   }
    # }
"""

from __future__ import annotations

import platform
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional


def mtr(
    host: str,
    count: int = 3,
    max_hops: int = 30,
    timeout: float = 2.0,
) -> Dict[str, Any]:
    """
    Run MTR-style combined traceroute + ping to *host*.

    Tries raw-socket ICMP TTL probing first; falls back to the system
    ``traceroute``/``tracert`` command if privileges are unavailable.

    Returns a standard netcheck result dict with ``type="mtr"``.
    """
    target_display = host
    metadata: Dict[str, Any] = {"host": host, "hops": []}

    # Resolve host
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror as exc:
        return _result(
            target=target_display,
            success=False,
            error=f"DNS resolution failed: {exc}",
            metadata=metadata,
        )

    # Attempt raw-socket MTR
    try:
        hops = _raw_mtr(ip, count=count, max_hops=max_hops, timeout=timeout)
        if hops:
            metadata["hops"] = hops
            dest_hop = next((h for h in reversed(hops) if h["ip"] == ip), hops[-1] if hops else None)
            final_latency = dest_hop["avg_ms"] if dest_hop else None
            return _result(
                target=target_display,
                success=True,
                latency_ms=final_latency,
                metadata=metadata,
            )
    except PermissionError:
        pass  # fallback to system command
    except Exception:
        pass

    # Fallback: system traceroute/tracert
    hops = _system_traceroute(host, max_hops=max_hops, timeout=timeout)
    if hops is not None:
        metadata["hops"] = hops
        dest_hop = next((h for h in reversed(hops) if h.get("ip") == ip), hops[-1] if hops else None)
        final_latency = dest_hop.get("avg_ms") if dest_hop else None
        return _result(
            target=target_display,
            success=True,
            latency_ms=final_latency,
            metadata=metadata,
        )

    return _result(
        target=target_display,
        success=False,
        error="MTR failed: raw sockets unavailable and system traceroute not found",
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Raw ICMP MTR
# ---------------------------------------------------------------------------

def _raw_mtr(
    dest_ip: str,
    count: int = 3,
    max_hops: int = 30,
    timeout: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    Send ICMP TTL probes using raw sockets.

    Raises PermissionError if raw sockets are unavailable.
    Returns list of hop dicts.
    """
    import struct

    ICMP_ECHO_REQUEST = 8

    def _checksum(data: bytes) -> int:
        s = 0
        for i in range(0, len(data), 2):
            w = (data[i] << 8) + (data[i + 1] if i + 1 < len(data) else 0)
            s += w
        s = (s >> 16) + (s & 0xFFFF)
        s += s >> 16
        return ~s & 0xFFFF

    def _icmp_packet(seq: int) -> bytes:
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, 0, 1, seq)
        payload = b"netcheck-mtr" * 3
        checksum = _checksum(header + payload)
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, checksum, 1, seq)
        return header + payload

    # Test raw socket availability
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        test_sock.close()
    except PermissionError:
        raise

    hops: List[Dict[str, Any]] = []


    for ttl in range(1, max_hops + 1):
        latencies: List[float] = []
        hop_ip: Optional[str] = None
        hop_name: Optional[str] = None

        for seq in range(count):
            recv_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            recv_sock.settimeout(timeout)
            send_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)

            try:
                packet = _icmp_packet(seq)
                t0 = time.monotonic()
                send_sock.sendto(packet, (dest_ip, 0))

                try:
                    _, addr = recv_sock.recvfrom(1024)
                    rtt = (time.monotonic() - t0) * 1000
                    if hop_ip is None:
                        hop_ip = addr[0]
                        try:
                            hop_name = socket.gethostbyaddr(hop_ip)[0]
                        except socket.herror:
                            hop_name = hop_ip
                    latencies.append(round(rtt, 2))
                except socket.timeout:
                    pass
            finally:
                send_sock.close()
                recv_sock.close()

        sent = count
        recv = len(latencies)
        loss_pct = round((sent - recv) / sent * 100, 1) if sent > 0 else 100.0
        min_ms = round(min(latencies), 2) if latencies else None
        max_ms = round(max(latencies), 2) if latencies else None
        avg_ms = round(sum(latencies) / len(latencies), 2) if latencies else None

        hop: Dict[str, Any] = {
            "hop": ttl,
            "ip": hop_ip or "*",
            "name": hop_name or "*",
            "loss_pct": loss_pct,
            "sent": sent,
            "recv": recv,
            "min_ms": min_ms,
            "avg_ms": avg_ms,
            "max_ms": max_ms,
        }
        hops.append(hop)

        if hop_ip == dest_ip:
            break

    return hops


# ---------------------------------------------------------------------------
# System traceroute fallback
# ---------------------------------------------------------------------------

def _system_traceroute(
    host: str,
    max_hops: int = 30,
    timeout: float = 2.0,
) -> Optional[List[Dict[str, Any]]]:
    """
    Fall back to system ``traceroute`` / ``tracert`` and parse the output.

    Returns a list of hop dicts (min_ms/avg_ms/max_ms may be None if
    not parseable), or None if the command is not available.
    """
    is_windows = platform.system().lower() == "windows"
    if is_windows:
        cmd = ["tracert", "-d", "-h", str(max_hops), "-w", str(int(timeout * 1000)), host]
    else:
        cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", str(int(timeout)), host]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_hops * (timeout + 1),
        )
        output = proc.stdout or proc.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    return _parse_traceroute_output(output, is_windows)


def _parse_traceroute_output(
    output: str,
    is_windows: bool,
) -> List[Dict[str, Any]]:
    """Parse system traceroute/tracert output into hop dicts."""
    import re

    hops: List[Dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        if is_windows:
            # tracert: "  1    <1 ms    <1 ms    <1 ms  192.168.1.1"
            m = re.match(
                r"^\s*(\d+)\s+(.+?)\s+([\d.<]+)\s+ms\s+[\d.<]+\s+ms\s+[\d.<]+\s+ms\s+([\d.]+)\s*$",
                line,
            )
            if not m:
                m = re.match(r"^\s*(\d+).*?([\d.]+)\s*$", line)
            if m:
                hop_num = int(m.group(1))
                ip = m.group(2) if len(m.groups()) > 2 else "*"
                hops.append({
                    "hop": hop_num, "ip": ip, "name": ip,
                    "loss_pct": 0.0, "sent": 3, "recv": 3,
                    "min_ms": None, "avg_ms": None, "max_ms": None,
                })
        else:
            # traceroute: " 1  192.168.1.1  0.941 ms  0.905 ms  0.987 ms"
            m = re.match(
                r"^\s*(\d+)\s+([\d.]+|\*)\s+([\d.]+)\s+ms.*?([\d.]+)\s+ms.*?([\d.]+)\s+ms",
                line,
            )
            if m:
                hop_num = int(m.group(1))
                ip = m.group(2)
                rtt1, rtt2, rtt3 = float(m.group(3)), float(m.group(4)), float(m.group(5))
                avg = round((rtt1 + rtt2 + rtt3) / 3, 2)
                hops.append({
                    "hop": hop_num, "ip": ip, "name": ip,
                    "loss_pct": 0.0, "sent": 3, "recv": 3,
                    "min_ms": round(min(rtt1, rtt2, rtt3), 2),
                    "avg_ms": avg,
                    "max_ms": round(max(rtt1, rtt2, rtt3), 2),
                })
            elif re.match(r"^\s*(\d+)\s+\*", line):
                hop_num = int(re.match(r"^\s*(\d+)", line).group(1))
                hops.append({
                    "hop": hop_num, "ip": "*", "name": "*",
                    "loss_pct": 100.0, "sent": 3, "recv": 0,
                    "min_ms": None, "avg_ms": None, "max_ms": None,
                })

    return hops


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _result(
    target: str,
    success: bool,
    metadata: Dict[str, Any],
    latency_ms: Optional[float] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "type": "mtr",
        "target": target,
        "status": "SUCCESS" if success else "FAILED",
        "success": success,
        "latency_ms": latency_ms,
        "error": error,
        "metadata": metadata,
    }
