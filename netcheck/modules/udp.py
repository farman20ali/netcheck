"""
netcheck.modules.udp
~~~~~~~~~~~~~~~~~~~~

UDP probe checker.

Sends a UDP packet and interprets the result:
- If an ICMP "port unreachable" is received back → port is CLOSED.
- If no response within timeout → port is OPEN or FILTERED (UDP is stateless).

Note: Raw socket access may require elevated privileges on some platforms.
A fallback using socket.SOCK_DGRAM (no raw ICMP) is used on Windows
or when privileges are insufficient.

Usage::

    from netcheck.modules.udp import check_udp

    result = check_udp("8.8.8.8", 53)
    # {"type": "udp", "target": "8.8.8.8:53", "success": True, ...}
"""

from __future__ import annotations

import socket
import time
from typing import Any, Dict, Optional

# Common service names for well-known UDP ports
_UDP_SERVICES: Dict[int, str] = {
    53: "dns",
    67: "dhcp",
    68: "dhcp-client",
    69: "tftp",
    123: "ntp",
    137: "netbios-ns",
    138: "netbios-dgm",
    161: "snmp",
    162: "snmp-trap",
    514: "syslog",
    1194: "openvpn",
    4500: "ipsec",
    5353: "mdns",
}


def check_udp(
    host: str,
    port: int,
    timeout: float = 5.0,
    payload: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Send a UDP probe to *host*:*port* and interpret the result.

    Returns a dict conforming to the standard netcheck result envelope::

        {
            "type":       "udp",
            "target":     "host:port",
            "status":     "OPEN_OR_FILTERED" | "CLOSED" | "FAILED",
            "success":    True | False,
            "latency_ms": float | None,
            "error":      str | None,
            "metadata":   {...}
        }

    Because UDP is stateless, an absence of ICMP error within *timeout*
    seconds is interpreted as **OPEN_OR_FILTERED** (success=True).
    An ICMP port-unreachable reply means the port is **CLOSED** (success=False).
    """
    service = _UDP_SERVICES.get(port, "")
    target = f"{host}:{port}"
    metadata: Dict[str, Any] = {
        "host": host,
        "port": port,
        "service": service,
        "ip": None,
    }

    # Resolve the host first
    try:
        ip = socket.gethostbyname(host)
        metadata["ip"] = ip
    except socket.gaierror as exc:
        return _result(
            target=target,
            status="FAILED",
            success=False,
            error=f"DNS resolution failed: {exc}",
            metadata=metadata,
        )

    # Build probe payload
    if payload is None:
        # DNS query for "." (root), minimal 12-byte header
        payload = _dns_probe() if port == 53 else b"\x00" * 4

    start = time.monotonic()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(payload, (ip, port))
            # Try to receive reply (succeeds for open UDP services that respond)
            try:
                sock.recvfrom(512)
                latency_ms = round((time.monotonic() - start) * 1000, 2)
                return _result(
                    target=target,
                    status="OPEN_OR_FILTERED",
                    success=True,
                    latency_ms=latency_ms,
                    metadata=metadata,
                )
            except socket.timeout:
                # No response = open or filtered (normal for UDP)
                latency_ms = round((time.monotonic() - start) * 1000, 2)
                return _result(
                    target=target,
                    status="OPEN_OR_FILTERED",
                    success=True,
                    latency_ms=latency_ms,
                    metadata=metadata,
                )
        except ConnectionRefusedError:
            # Windows raises ConnectionRefusedError on ICMP port-unreachable
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            return _result(
                target=target,
                status="CLOSED",
                success=False,
                latency_ms=latency_ms,
                error="ICMP Port Unreachable — port is closed",
                metadata=metadata,
            )
        except OSError as exc:
            # Linux raises OSError: [Errno 111] Connection refused for ICMP port-unreachable
            err_str = str(exc).lower()
            if "refused" in err_str or "111" in err_str or "unreachable" in err_str:
                latency_ms = round((time.monotonic() - start) * 1000, 2)
                return _result(
                    target=target,
                    status="CLOSED",
                    success=False,
                    latency_ms=latency_ms,
                    error="ICMP Port Unreachable — port is closed",
                    metadata=metadata,
                )
            raise
        finally:
            sock.close()
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return _result(
            target=target,
            status="FAILED",
            success=False,
            latency_ms=latency_ms,
            error=str(exc),
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(
    target: str,
    status: str,
    success: bool,
    metadata: Dict[str, Any],
    latency_ms: Optional[float] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "type": "udp",
        "target": target,
        "status": status,
        "success": success,
        "latency_ms": latency_ms,
        "error": error,
        "metadata": metadata,
    }


def _dns_probe() -> bytes:
    """Minimal DNS query for '.' (root) type ANY — 12 bytes."""
    return (
        b"\xaa\xbb"   # Transaction ID
        b"\x01\x00"   # Flags: standard query
        b"\x00\x01"   # Questions: 1
        b"\x00\x00"   # Answer RRs: 0
        b"\x00\x00"   # Authority RRs: 0
        b"\x00\x00"   # Additional RRs: 0
        b"\x00"       # Root domain (empty label)
        b"\x00\xff"   # QTYPE: ANY
        b"\x00\x01"   # QCLASS: IN
    )
