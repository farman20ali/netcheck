import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from netcheck.modules.dns import dns_lookup
from netcheck.utils.services import get_service_name

# Curated list of 50 common ports to scan by default
COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 115, 123, 135, 139, 143, 161, 179, 389, 443, 445, 465, 514, 587,
    636, 993, 995, 1080, 1433, 1434, 1521, 2049, 3000, 3306, 3389, 5060, 5432, 5672, 5900, 6379,
    8000, 8080, 8443, 8888, 9000, 9092, 9200, 27017
]

def scan_port_single(ip: str, port: int, timeout: float = 1.0) -> Dict[str, Any]:
    """
    Attempts connection to a single port and IP.
    """
    start_time = time.perf_counter()
    try:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((ip, port))
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "port": port,
            "status": "OPEN",
            "service": get_service_name(port),
            "latency_ms": round(duration_ms, 2)
        }
    except Exception:
        return {
            "port": port,
            "status": "CLOSED",
            "service": get_service_name(port),
            "latency_ms": None
        }

def scan_ports(host: str, ports: List[int] = None, timeout: float = 1.5, max_workers: int = 20) -> Dict[str, Any]:
    """
    Performs concurrent TCP scan on a target host for specified ports.
    """
    if not ports:
        ports = COMMON_PORTS

    result = {
        "type": "scan",
        "target": host,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "open_ports": [],
            "closed_ports": [],
            "ips": []
        }
    }


    start_time = time.perf_counter()

    # Resolve target host IP
    dns_res = dns_lookup(host, timeout=3.0)
    if not dns_res["success"]:
        result["error"] = f"DNS Resolution failed: {dns_res['error']}"
        return result

    ips = dns_res["metadata"]["ips"]
    if not ips:
        result["error"] = "No IP addresses resolved"
        return result

    result["metadata"]["ips"] = ips
    ip_to_scan = ips[0] # Use first resolved IP

    open_ports = []
    closed_ports = []

    # Execute checks concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_port_single, ip_to_scan, p, timeout): p for p in ports}
        for future in as_completed(futures):
            res = future.result()
            if res["status"] == "OPEN":
                open_ports.append(res)
            else:
                closed_ports.append(res)

    # Sort results by port number
    open_ports.sort(key=lambda x: x["port"])
    closed_ports.sort(key=lambda x: x["port"])

    duration = (time.perf_counter() - start_time) * 1000.0

    result["status"] = "SUCCESS"
    result["success"] = True
    result["latency_ms"] = round(duration, 2)
    result["metadata"]["open_ports"] = open_ports
    result["metadata"]["closed_ports"] = closed_ports

    return result
