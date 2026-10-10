import socket
import time
from concurrent.futures import TimeoutError
from typing import Any, Dict

from netcheck.utils.cache import dns_cache
from netcheck.utils.normalize import normalize_host
from netcheck.utils.timeout import run_with_timeout


def dns_lookup(raw_target: str, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Resolves DNS for a given hostname or URL.
    Returns structured results with latency and A/AAAA IPs.
    """
    host = normalize_host(raw_target)
    if not host:
        return {
            "type": "dns",
            "target": raw_target,
            "status": "FAILED",
            "latency_ms": 0.0,
            "success": False,
            "error": "Empty host target",
            "metadata": {}
        }

    result = {
        "type": "dns",
        "target": raw_target,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "resolved_host": host,
            "ips": [],
            "aliases": [],
            "reverse_dns": None
        }
    }


    # Check if target is already an IP address
    is_ip = False
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(family, host)
            is_ip = True
            break
        except OSError:
            pass

    if is_ip:
        result["status"] = "SUCCESS"
        result["success"] = True
        result["latency_ms"] = 0.0
        result["metadata"]["ips"] = [host]
        # Attempt a quick reverse lookup
        try:
            def _quick_rev():
                return socket.gethostbyaddr(host)[0]
            rev_name = run_with_timeout(2.0, _quick_rev)
            result["metadata"]["reverse_dns"] = rev_name
        except Exception:
            pass
        return result

    # Check the DNS cache
    cached = dns_cache.get(host)
    if cached:
        result.update(cached)
        result["target"] = raw_target
        return result

    start_time = time.perf_counter()
    try:
        def _resolve():
            try:
                ai = socket.getaddrinfo(host, None, flags=socket.AI_CANONNAME)
            except Exception:
                ai = socket.getaddrinfo(host, None)

            aliases = []
            try:
                _, alias_list, _ = socket.gethostbyname_ex(host)
                aliases = list(alias_list)
            except Exception:
                pass
            return ai, aliases

        addr_info, aliases = run_with_timeout(timeout, _resolve)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        ips = list(set(info[4][0] for info in addr_info))

        for info in addr_info:
            if len(info) > 3 and info[3]:
                canon = info[3]
                if canon != host and canon not in aliases:
                    aliases.append(canon)

        result["status"] = "SUCCESS"
        result["success"] = True
        result["latency_ms"] = round(duration_ms, 2)
        result["metadata"]["ips"] = ips
        result["metadata"]["aliases"] = aliases

        if ips:
            try:
                def _reverse():
                    name, _, _ = socket.gethostbyaddr(ips[0])
                    return name
                rev_name = run_with_timeout(2.0, _reverse)
                result["metadata"]["reverse_dns"] = rev_name
            except Exception as rev_err:
                result["metadata"]["reverse_dns_error"] = str(rev_err)

        # Cache successful resolutions
        dns_cache.set(host, {
            "status": "SUCCESS",
            "success": True,
            "latency_ms": result["latency_ms"],
            "metadata": result["metadata"]
        })

    except TimeoutError as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)
        result["error"] = f"DNS resolution timed out: {e}"
        result["status"] = "FAILED"
        result["success"] = False
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)
        result["error"] = str(e)
        result["status"] = "FAILED"
        result["success"] = False


    return result
