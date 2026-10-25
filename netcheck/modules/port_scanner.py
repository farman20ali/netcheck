import socket
import time
from concurrent.futures import as_completed
from typing import Any, Dict, List

from netcheck.modules.dns import dns_lookup
from netcheck.utils.services import get_service_name
from netcheck.utils.threads import DaemonThreadPoolExecutor, cleanup_thread_queues

# Curated list of 50 common ports to scan by default
COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 115, 123, 135, 139, 143, 161, 179, 389, 443, 445, 465, 514, 587,
    636, 993, 995, 1080, 1433, 1434, 1521, 2049, 3000, 3306, 3389, 5060, 5432, 5672, 5900, 6379,
    8000, 8080, 8443, 8888, 9000, 9092, 9200, 27017
]

def scan_port_single(ip: str, port: int, timeout: float = 1.0, grab_banner_flag: bool = False) -> Dict[str, Any]:
    """
    Attempts connection to a single port and IP.
    Classifies port status as:
    - OPEN: 3-way handshake established.
    - CLOSED: Host actively rejected connection (RST / ECONNREFUSED).
    - FILTERED: Connection timed out or dropped by firewall.
    """
    start_time = time.perf_counter()
    try:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((ip, port))
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        res = {
            "port": port,
            "status": "OPEN",
            "service": get_service_name(port),
            "latency_ms": round(duration_ms, 2)
        }
        if grab_banner_flag:
            from netcheck.utils.banners import grab_banner
            b_info = grab_banner(ip, port, timeout=min(timeout, 1.0))
            if b_info.get("detected_service"):
                res["service"] = b_info["detected_service"]
            res["version"] = b_info.get("version")
            res["banner"] = b_info.get("banner")
        return res
    except (socket.timeout, TimeoutError):
        return {
            "port": port,
            "status": "FILTERED",
            "service": get_service_name(port),
            "latency_ms": None
        }
    except ConnectionRefusedError:
        return {
            "port": port,
            "status": "CLOSED",
            "service": get_service_name(port),
            "latency_ms": None
        }
    except OSError as exc:
        err = getattr(exc, "errno", None)
        if err in (10060, 110) or "timed out" in str(exc).lower():
            status = "FILTERED"
        elif err in (10061, 111):
            status = "CLOSED"
        else:
            status = "CLOSED"
        return {
            "port": port,
            "status": status,
            "service": get_service_name(port),
            "latency_ms": None
        }
    except Exception:
        return {
            "port": port,
            "status": "CLOSED",
            "service": get_service_name(port),
            "latency_ms": None
        }

def scan_ports(
    host: str,
    ports: List[int] = None,
    timeout: float = 1.5,
    max_workers: int = 20,
    banner: bool = False,
    delay: float = 0.0,
) -> Dict[str, Any]:
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
            "filtered_ports": [],
            "ips": []
        }
    }

    if len(ports) > 1000:
        result["error"] = f"Port scan exceeds safety limit of 1000 ports (requested {len(ports)})."
        return result

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
    filtered_ports = []

    # Execute checks concurrently
    try:
        with DaemonThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for p in ports:
                if delay > 0.0:
                    time.sleep(delay)
                if banner:
                    fut = executor.submit(scan_port_single, ip_to_scan, p, timeout, banner)
                else:
                    fut = executor.submit(scan_port_single, ip_to_scan, p, timeout)
                futures[fut] = p
            try:
                for future in as_completed(futures):
                    res = future.result()
                    if res["status"] == "OPEN":
                        open_ports.append(res)
                    elif res["status"] == "FILTERED":
                        filtered_ports.append(res)
                    else:
                        closed_ports.append(res)
            except KeyboardInterrupt:
                for f in futures:
                    f.cancel()
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    executor.shutdown(wait=False)
                cleanup_thread_queues()
                raise
    except KeyboardInterrupt:
        raise

    # Sort results by port number
    open_ports.sort(key=lambda x: x["port"])
    closed_ports.sort(key=lambda x: x["port"])
    filtered_ports.sort(key=lambda x: x["port"])

    duration = (time.perf_counter() - start_time) * 1000.0

    result["status"] = "SUCCESS"
    result["success"] = True
    result["latency_ms"] = round(duration, 2)
    result["metadata"]["open_ports"] = open_ports
    result["metadata"]["closed_ports"] = closed_ports
    result["metadata"]["filtered_ports"] = filtered_ports

    return result
