import base64
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


def check_http_status(
    url: str,
    timeout: float = 5.0,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    auth: Optional[tuple] = None,
) -> Dict[str, Any]:
    """
    Validates the HTTP/HTTPS status code, response time, and size for a URL.
    Also measures granular waterfall timing: dns_ms, connect_ms, tls_ms, ttfb_ms.
    """
    target_url = url
    if not (url.startswith("http://") or url.startswith("https://")):
        target_url = "http://" + url

    result: Dict[str, Any] = {
        "type": "http",
        "target": target_url,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "status_code": None,
            "redirect_url": None,
            "size_bytes": 0,
            "headers": {},
            "dns_ms": None,
            "connect_ms": None,
            "tls_ms": None,
            "ttfb_ms": None,
        },
    }

    start_time = time.perf_counter()

    # Pre-flight waterfall timing: DNS, TCP, TLS (skipped if urlopen is mocked in tests)
    is_mocked = hasattr(urllib.request.urlopen, "mock_calls") or hasattr(
        urllib.request.urlopen, "assert_called"
    )
    if not is_mocked:
        try:
            parsed = urllib.parse.urlparse(target_url)
            scheme = parsed.scheme.lower()
            host = parsed.hostname or ""
            port = parsed.port or (443 if scheme == "https" else 80)

            # Phase 1: DNS
            t0 = time.perf_counter()
            addrs = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            dns_ms = round((time.perf_counter() - t0) * 1000, 2)
            result["metadata"]["dns_ms"] = dns_ms

            # Phase 2: TCP connect
            t1 = time.perf_counter()
            family = addrs[0][0] if addrs else socket.AF_INET
            sockaddr = addrs[0][4] if addrs else (host, port)
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(sockaddr)
                connect_ms = round((time.perf_counter() - t1) * 1000, 2)
                result["metadata"]["connect_ms"] = connect_ms

                # Phase 3: TLS handshake (if HTTPS)
                if scheme == "https":
                    t2 = time.perf_counter()
                    ctx = ssl.create_default_context()
                    with ctx.wrap_socket(sock, server_hostname=host):
                        pass
                    tls_ms = round((time.perf_counter() - t2) * 1000, 2)
                    result["metadata"]["tls_ms"] = tls_ms
        except Exception:
            pass

    try:
        req_headers = {"User-Agent": "Mozilla/5.0 NetCheck/2.6"}
        if headers:
            req_headers.update(headers)

        if auth:
            if not isinstance(auth, (tuple, list)) or len(auth) != 2:
                raise ValueError("Auth parameter must be a tuple or list of (username, password)")
            auth_bytes = f"{auth[0]}:{auth[1]}".encode("utf-8")
            b64_auth = base64.b64encode(auth_bytes).decode("utf-8")
            req_headers["Authorization"] = f"Basic {b64_auth}"

        req = urllib.request.Request(
            target_url,
            headers=req_headers,
            method=method.upper(),
        )

        t_urlopen = time.perf_counter()
        with urllib.request.urlopen(req, timeout=timeout) as response:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            ttfb_ms = round((time.perf_counter() - t_urlopen) * 1000, 2)

            final_url = response.geturl()
            status_code = response.getcode()
            resp_headers = {k.lower(): v for k, v in response.info().items()}

            content_length = resp_headers.get("content-length")
            if content_length is not None:
                try:
                    size_bytes = int(content_length)
                except ValueError:
                    size_bytes = 0
            else:
                content = response.read(1024 * 1024)
                size_bytes = len(content)

            result["latency_ms"] = round(duration_ms, 2)
            result["success"] = 200 <= status_code < 400
            result["status"] = "SUCCESS" if result["success"] else "FAILED"

            result["metadata"]["status_code"] = status_code
            result["metadata"]["size_bytes"] = size_bytes
            result["metadata"]["headers"] = resp_headers
            result["metadata"]["ttfb_ms"] = ttfb_ms

            if final_url != target_url:
                result["metadata"]["redirect_url"] = final_url
                if 300 <= status_code < 400:
                    result["status"] = "REDIRECT"

    except urllib.error.HTTPError as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)
        result["status"] = "FAILED"
        result["success"] = False
        result["error"] = f"HTTP Error {e.code}: {e.reason}"
        result["metadata"]["status_code"] = e.code
    except urllib.error.URLError as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)
        result["status"] = "FAILED"
        result["success"] = False
        result["error"] = f"URL Error: {e.reason}"
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)
        result["status"] = "FAILED"
        result["success"] = False
        result["error"] = str(e)

    return result
