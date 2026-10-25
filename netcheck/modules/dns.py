import socket
import struct
import time
from concurrent.futures import TimeoutError
from typing import Any, Dict, List

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


# ---------------------------------------------------------------------------
# Reverse DNS (PTR record)
# ---------------------------------------------------------------------------

def reverse_dns(ip: str, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Perform a reverse DNS (PTR) lookup for the given IP address.

    Returns standard netcheck envelope with ``metadata.hostname``.
    """
    result: Dict[str, Any] = {
        "type": "dns",
        "target": ip,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {"query_type": "PTR", "ip": ip, "hostname": None},
    }

    t0 = time.perf_counter()
    try:
        def _ptr():
            name, _, _ = socket.gethostbyaddr(ip)
            return name

        hostname = run_with_timeout(timeout, _ptr)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        result.update({
            "status": "SUCCESS",
            "success": True,
            "latency_ms": elapsed_ms,
        })
        result["metadata"]["hostname"] = hostname
    except TimeoutError:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        result["latency_ms"] = elapsed_ms
        result["error"] = "PTR lookup timed out"
    except socket.herror as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        result["latency_ms"] = elapsed_ms
        result["error"] = f"No PTR record found: {e}"
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        result["latency_ms"] = elapsed_ms
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# DNS Propagation — multi-resolver check
# ---------------------------------------------------------------------------

# Well-known public resolvers: (name, ip, port)
_PUBLIC_RESOLVERS: List[tuple] = [
    ("Google",      "8.8.8.8",        53),
    ("Cloudflare",  "1.1.1.1",        53),
    ("Quad9",       "9.9.9.9",        53),
    ("OpenDNS",     "208.67.222.222", 53),
]


def dns_propagation(
    domain: str,
    timeout: float = 3.0,
) -> Dict[str, Any]:
    """
    Query *domain* against Google, Cloudflare, Quad9, and OpenDNS in parallel.

    Returns a result envelope with ``metadata.resolvers`` — one entry per
    resolver showing its name, IP, the resolved addresses, latency, and whether
    results are consistent across all resolvers.
    """
    from netcheck.utils.threads import DaemonThreadPoolExecutor, cleanup_thread_queues

    result: Dict[str, Any] = {
        "type": "dns",
        "target": domain,
        "status": "FAILED",
        "success": False,
        "latency_ms": None,
        "error": None,
        "metadata": {
            "query_type": "propagation",
            "domain": domain,
            "resolvers": [],
            "consistent": None,
        },
    }

    t0 = time.perf_counter()

    with DaemonThreadPoolExecutor(max_workers=len(_PUBLIC_RESOLVERS)) as pool:
        futs = {
            pool.submit(_query_resolver, domain, name, ip, port, timeout): (name, ip)
            for name, ip, port in _PUBLIC_RESOLVERS
        }
        try:
            resolver_results = []
            for fut, (name, ip) in futs.items():
                try:
                    res = fut.result(timeout=timeout + 1.0)
                except Exception as e:
                    res = {
                        "resolver": name,
                        "resolver_ip": ip,
                        "success": False,
                        "latency_ms": None,
                        "ips": [],
                        "error": str(e),
                    }
                resolver_results.append(res)
        except KeyboardInterrupt:
            cleanup_thread_queues()
            raise

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    # Sort by resolver order for deterministic output
    order = {name: i for i, (name, _, _) in enumerate(_PUBLIC_RESOLVERS)}
    resolver_results.sort(key=lambda r: order.get(r["resolver"], 99))

    # Check propagation consistency
    successful = [r for r in resolver_results if r["success"]]
    if successful:
        all_ips = [frozenset(r["ips"]) for r in successful]
        consistent = all(s == all_ips[0] for s in all_ips)
    else:
        consistent = None

    all_success = len(successful) == len(_PUBLIC_RESOLVERS)
    any_success = len(successful) > 0

    result.update({
        "status": "SUCCESS" if any_success else "FAILED",
        "success": all_success,
        "latency_ms": elapsed_ms,
    })
    result["metadata"]["resolvers"] = resolver_results
    result["metadata"]["consistent"] = consistent
    if not all_success and any_success:
        result["error"] = f"Partial: {len(successful)}/{len(_PUBLIC_RESOLVERS)} resolvers succeeded"

    return result


def _query_resolver(
    domain: str,
    name: str,
    resolver_ip: str,
    port: int,
    timeout: float,
) -> Dict[str, Any]:
    """Send a raw UDP DNS A-record query to a specific resolver."""
    t0 = time.perf_counter()
    entry: Dict[str, Any] = {
        "resolver": name,
        "resolver_ip": resolver_ip,
        "success": False,
        "latency_ms": None,
        "ips": [],
        "error": None,
    }
    try:
        query = _build_dns_query(domain)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(query, (resolver_ip, port))
            response, _ = sock.recvfrom(512)

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        ips = _parse_dns_response(response)
        entry.update({
            "success": bool(ips),
            "latency_ms": elapsed_ms,
            "ips": ips,
        })
        if not ips:
            entry["error"] = "No A records in response"
    except socket.timeout:
        entry["error"] = "Resolver timed out"
        entry["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        entry["error"] = str(e)
        entry["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return entry


def _build_dns_query(domain: str) -> bytes:
    """Build a minimal DNS A-record query packet."""
    # Header: ID, flags (standard query), QDCOUNT=1, others=0
    header = struct.pack("!HHHHHH", 0xABCD, 0x0100, 1, 0, 0, 0)
    # Question: encode domain name
    qname = b""
    for label in domain.rstrip(".").split("."):
        encoded = label.encode("ascii")
        qname += struct.pack("!B", len(encoded)) + encoded
    qname += b"\x00"  # root label
    question = qname + struct.pack("!HH", 1, 1)  # QTYPE=A, QCLASS=IN
    return header + question


def _parse_dns_response(data: bytes) -> List[str]:
    """Extract IPv4 addresses from a raw DNS response."""
    ips: List[str] = []
    try:
        ancount = struct.unpack("!H", data[6:8])[0]
        if ancount == 0:
            return ips
        # Skip header (12 bytes) and question section
        offset = 12
        # Skip question: find end of QNAME
        while offset < len(data) and data[offset] != 0:
            if data[offset] & 0xC0 == 0xC0:  # pointer
                offset += 2
                break
            offset += data[offset] + 1
        else:
            offset += 1  # null terminator
        offset += 4  # QTYPE + QCLASS

        for _ in range(ancount):
            if offset >= len(data):
                break
            # Skip NAME (may be pointer)
            if data[offset] & 0xC0 == 0xC0:
                offset += 2
            else:
                while offset < len(data) and data[offset] != 0:
                    offset += data[offset] + 1
                offset += 1
            if offset + 10 > len(data):
                break
            rtype, _, _, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
            offset += 10
            if rtype == 1 and rdlength == 4:  # A record
                ip_bytes = data[offset:offset + 4]
                ips.append(socket.inet_ntoa(ip_bytes))
            offset += rdlength
    except Exception:
        pass
    return ips
