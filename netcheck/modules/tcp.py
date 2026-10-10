import socket
import time
from typing import Any, Dict

from netcheck.modules.dns import dns_lookup
from netcheck.utils.services import get_service_name


def check_tcp_connect(host: str, port: int, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Performs a TCP connection test to a host and port.
    Resolves DNS beforehand and sequentially attempts connection to all resolved IPs
    (handling dual-stack IPv4/IPv6 fallbacks).
    """
    target_str = f"{host}:{port}"
    result = {
        "type": "tcp",
        "target": target_str,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "host": host,
            "port": port,
            "ip": None,
            "resolved": False,
            "method": "socket",
            "service": get_service_name(port)
        }
    }

    # Resolve DNS first using our cached, timeout-guarded lookup
    dns_res = dns_lookup(host, timeout=min(timeout, 3.0))
    if not dns_res["success"]:
        result["error"] = f"DNS Resolution failed: {dns_res['error']}"
        return result

    ips = dns_res["metadata"]["ips"]
    if not ips:
        result["error"] = "No IP addresses resolved"
        return result

    result["metadata"]["resolved"] = True

    start_time = time.perf_counter()
    errors = []

    # Iterate over all resolved IPs and try connecting. Succeed if at least one works.
    for ip in ips:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                pass

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            result["status"] = "SUCCESS"
            result["success"] = True
            result["latency_ms"] = round(duration_ms, 2)
            result["metadata"]["ip"] = ip
            return result
        except Exception as e:
            errors.append(f"{ip} ({e})")

    # All connection attempts failed
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    result["latency_ms"] = round(duration_ms, 2)
    result["error"] = "All connection attempts failed: " + "; ".join(errors)
    result["status"] = "FAILED"
    result["success"] = False

    # Store the first IP we tried as metadata reference
    result["metadata"]["ip"] = ips[0]
    return result

