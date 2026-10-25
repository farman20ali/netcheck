"""
Pure-Python, zero-dependency banner grabbing and service detection.
Safe, non-destructive protocol probes for common network services.
"""
import re
import socket
import ssl
from typing import Any, Dict, Optional

from netcheck.utils.services import get_service_name


def grab_banner(host: str, port: int, timeout: float = 1.0) -> Dict[str, Any]:
    """
    Attempts non-destructive banner grabbing on an open port.
    Returns:
        {
            "detected_service": str,
            "banner": Optional[str],
            "version": Optional[str]
        }
    """
    default_service = get_service_name(port)
    result = {
        "detected_service": default_service,
        "banner": None,
        "version": None,
    }

    # 1. SSH (Port 22, 2222, etc.)
    if port in (22, 2222) or default_service == "ssh":
        res = _probe_ssh(host, port, timeout)
        if res:
            result.update(res)
            return result

    # 2. HTTP/HTTPS (Port 80, 443, 8080, 8443, etc.)
    if port in (80, 8080, 8000, 3000, 5000) or default_service in ("http", "http-alt", "http-proxy"):
        res = _probe_http(host, port, timeout, use_ssl=False)
        if res:
            result.update(res)
            return result

    if port in (443, 8443) or default_service in ("https", "https-alt"):
        res = _probe_http(host, port, timeout, use_ssl=True)
        if res:
            result.update(res)
            return result

    # 3. FTP (Port 21)
    if port == 21 or default_service == "ftp":
        res = _probe_read_greeting(host, port, timeout, "ftp")
        if res:
            result.update(res)
            return result

    # 4. SMTP (Port 25, 587, 465)
    if port in (25, 587) or default_service in ("smtp", "submission"):
        res = _probe_read_greeting(host, port, timeout, "smtp")
        if res:
            result.update(res)
            return result

    # 5. Redis (Port 6379)
    if port == 6379 or default_service == "redis":
        res = _probe_redis(host, port, timeout)
        if res:
            result.update(res)
            return result

    # 6. MySQL (Port 3306)
    if port == 3306 or default_service == "mysql":
        res = _probe_mysql(host, port, timeout)
        if res:
            result.update(res)
            return result

    # Generic fallback: read any immediate banner sent by server
    res = _probe_generic_read(host, port, timeout)
    if res:
        result.update(res)

    return result


def _probe_ssh(host: str, port: int, timeout: float) -> Optional[Dict[str, Any]]:
    """SSH servers send protocol identification string immediately upon connection."""
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            banner = sock.recv(256).decode("utf-8", errors="replace").strip()
            if banner.startswith("SSH-"):
                version_match = re.search(r"SSH-[0-9.]+-([^\s]+)", banner)
                version = version_match.group(1) if version_match else None
                return {
                    "detected_service": "ssh",
                    "banner": banner,
                    "version": version,
                }
    except Exception:
        pass
    return None


def _probe_http(host: str, port: int, timeout: float, use_ssl: bool = False) -> Optional[Dict[str, Any]]:
    """Send minimal HEAD / HTTP/1.1 probe to extract Server and title headers."""
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        raw_sock = socket.socket(family, socket.SOCK_STREAM)
        raw_sock.settimeout(timeout)
        raw_sock.connect((host, port))

        sock = raw_sock
        if use_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(raw_sock, server_hostname=host)

        with sock:
            req = f"HEAD / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: NetCheck/2.6\r\nConnection: close\r\n\r\n"
            sock.sendall(req.encode("utf-8"))
            resp = sock.recv(1024).decode("utf-8", errors="replace")

            server_header = None
            for line in resp.splitlines():
                if line.lower().startswith("server:"):
                    server_header = line.split(":", 1)[1].strip()
                    break

            service_name = "https" if use_ssl else "http"
            banner_parts = []
            if resp.splitlines():
                banner_parts.append(resp.splitlines()[0])
            if server_header:
                banner_parts.append(f"Server: {server_header}")

            banner_str = " | ".join(banner_parts) if banner_parts else resp.strip()[:100]
            return {
                "detected_service": service_name,
                "banner": banner_str,
                "version": server_header,
            }
    except Exception:
        pass
    return None


def _probe_read_greeting(host: str, port: int, timeout: float, service: str) -> Optional[Dict[str, Any]]:
    """FTP and SMTP servers send a 220 greeting banner upon connection."""
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            banner = sock.recv(512).decode("utf-8", errors="replace").strip()
            if banner.startswith("220"):
                return {
                    "detected_service": service,
                    "banner": banner,
                    "version": banner.splitlines()[0] if banner else None,
                }
    except Exception:
        pass
    return None


def _probe_redis(host: str, port: int, timeout: float) -> Optional[Dict[str, Any]]:
    """Redis responds to PING command with +PONG or -NOAUTH."""
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.sendall(b"PING\r\n")
            resp = sock.recv(128).decode("utf-8", errors="replace").strip()
            if resp in ("+PONG", "-NOAUTH Authentication required.") or resp.startswith(("+PONG", "-NOAUTH")):
                return {
                    "detected_service": "redis",
                    "banner": f"Redis ({resp})",
                    "version": None,
                }
    except Exception:
        pass
    return None


def _probe_mysql(host: str, port: int, timeout: float) -> Optional[Dict[str, Any]]:
    """MySQL sends an initial handshake packet containing the server version string."""
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            packet = sock.recv(256)
            # MySQL initial handshake packet: length(3), seq(1), protocol_version(1), null-terminated version string
            if len(packet) > 5 and packet[4] in (10, 9):  # Protocol version 10 (MySQL 5.x/8.x/MariaDB)
                null_idx = packet.find(b"\x00", 5)
                if null_idx != -1:
                    ver_str = packet[5:null_idx].decode("ascii", errors="replace")
                    return {
                        "detected_service": "mysql",
                        "banner": f"MySQL {ver_str}",
                        "version": ver_str,
                    }
    except Exception:
        pass
    return None


def _probe_generic_read(host: str, port: int, timeout: float) -> Optional[Dict[str, Any]]:
    """Try non-blocking read to see if server sends any banner on connect."""
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(min(timeout, 0.5))
            sock.connect((host, port))
            data = sock.recv(256)
            if data:
                clean_banner = "".join(chr(b) if 32 <= b < 127 else "." for b in data).strip()
                if clean_banner:
                    return {
                        "detected_service": get_service_name(port),
                        "banner": clean_banner[:100],
                        "version": None,
                    }
    except Exception:
        pass
    return None
